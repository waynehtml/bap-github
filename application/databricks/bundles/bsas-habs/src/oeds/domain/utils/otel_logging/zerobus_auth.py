"""Entra -> Databricks Zerobus token exchange and process-local token caches.

Reference request format: databricks/zerobus-sdk (see README.md).
No Databricks OAuth secret, personal access token, or ambient app identity is used.
"""
from __future__ import annotations

import base64
import json
import math
import os
import re
import ssl
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, Request, build_opener,
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9._~+/\-]+=*\Z", re.ASCII)
_PART_RE = re.compile(r"[A-Za-z0-9_-]+\Z", re.ASCII)
_SAFE_OAUTH_ERRORS = frozenset({
    "invalid_request", "invalid_client", "invalid_grant", "unauthorized_client",
    "unsupported_grant_type", "invalid_scope", "invalid_target",
    "access_denied", "temporarily_unavailable", "server_error",
})


class TokenError(RuntimeError):
    """Sanitized authentication failure. Never carries a response body or token."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def https_origin(value: str, label: str) -> str:
    """Require a trusted HTTPS origin, without credentials, path, or query."""
    if not isinstance(value, str) or value != value.strip():
        raise ValueError(f"{label} must be an HTTPS origin")
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        raise ValueError(f"{label} has an invalid port") from None
    if (
        parts.scheme != "https" or not parts.hostname
        or parts.username is not None or parts.password is not None
        or parts.path not in ("", "/") or parts.query or parts.fragment
        or any(c.isspace() for c in value)
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError(f"{label} must be an HTTPS origin without a path or query")
    return f"https://{parts.netloc}"


def _validate_token(value: Any) -> str:
    if (
        not isinstance(value, str) or len(value) > 131072
        or not _TOKEN_RE.fullmatch(value)
    ):
        raise TokenError("Token is empty or is not a valid bearer-header value")
    return value


def _jwt_exp(value: str) -> float | None:
    """Read UNVERIFIED exp only to shorten cache lifetime, never to authorize."""
    try:
        segments = value.split(".")
        if len(segments) != 3:
            return None
        segment = segments[1]
        payload = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        claims = json.loads(payload)
        exp = claims.get("exp")
        if isinstance(exp, bool) or not isinstance(exp, (int, float)):
            return None
        number = float(exp)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, AttributeError, UnicodeError, OverflowError):
        return None


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a subject token or client secret to a redirect target.
        return None


class OAuthHttpClient:
    """Standard-library HTTPS form POST; certificate verification stays enabled.

    The timeout is a socket-operation timeout, not a hard end-to-end deadline.
    Requests are deliberately not logged. There is no .netrc/ambient auth lookup.
    Proxy configuration, when present, follows urllib's standard environment rules.
    """

    def __init__(self, timeout_seconds: float = 5.0, ca_file: str | None = None):
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive and finite")
        self.timeout_seconds = float(timeout_seconds)
        self._ssl = ssl.create_default_context(cafile=ca_file)

    def post_form(self, url: str, fields: Mapping[str, str]) -> dict[str, Any]:
        parts = urlsplit(url)
        if (
            parts.scheme != "https" or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.query or parts.fragment
        ):
            raise ValueError("Token endpoint must be a trusted HTTPS URL")
        request = Request(
            url,
            data=urlencode(dict(fields)).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )
        # Construct per request: callers need not share mutable HTTP session state.
        opener = build_opener(HTTPSHandler(context=self._ssl), _NoRedirect())
        try:
            with opener.open(request, timeout=self.timeout_seconds) as response:
                payload = response.read(1048577)
            if len(payload) > 1048576:
                raise TokenError("OAuth response exceeded the size limit")
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise TokenError("OAuth response was not a JSON object")
            return data
        except HTTPError as error:
            status = error.code
            safe_code = ""
            try:
                data = json.loads(error.read(8192))
                candidate = data.get("error") if isinstance(data, dict) else None
                if isinstance(candidate, str) and candidate in _SAFE_OAUTH_ERRORS:
                    safe_code = f"; {candidate}"
            except (ValueError, OSError):
                pass
            finally:
                error.close()
            raise TokenError(
                f"OAuth request failed (HTTP {status}{safe_code})",
                retryable=status in (408, 429) or status >= 500,
            ) from None
        except (URLError, TimeoutError, OSError):
            raise TokenError(
                "OAuth HTTPS request failed; check connectivity and TLS trust",
                retryable=True,
            ) from None
        except (ValueError, UnicodeError):
            raise TokenError("OAuth response was not valid JSON") from None


@dataclass(frozen=True)
class _Token:
    value: str = field(repr=False)
    expires_at: float
    refresh_at: float


@dataclass(frozen=True)
class TokenCacheStats:
    cache_hits: int
    successful_mints: int
    failed_mints: int
    fallback_uses: int
    seconds_remaining: float


class _CachedTokenProvider:
    """One locked cache per identity/scope/provider instance."""

    def __init__(
        self,
        *,
        refresh_ahead_seconds: float = 300,
        failure_backoff_seconds: float = 5,
        minimum_validity_seconds: float = 5,
        lock_timeout_seconds: float = 15,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ):
        for name, value in (
            ("refresh_ahead_seconds", refresh_ahead_seconds),
            ("failure_backoff_seconds", failure_backoff_seconds),
            ("minimum_validity_seconds", minimum_validity_seconds),
            ("lock_timeout_seconds", lock_timeout_seconds),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        self._refresh_ahead = float(refresh_ahead_seconds)
        self._backoff = float(failure_backoff_seconds)
        self._minimum_validity = float(minimum_validity_seconds)
        self._lock_timeout = float(lock_timeout_seconds)
        self._clock = clock
        self._wall_clock = wall_clock
        self._pid = os.getpid()
        self._lock = threading.Lock()
        self._cached: _Token | None = None
        self._retry_at = 0.0
        self._last_error: TokenError | None = None
        self._hits = self._mints = self._failures = self._fallbacks = 0

    def _check_process(self) -> None:
        if os.getpid() != self._pid:
            raise TokenError("Create a new token provider in the child process")

    def _mint(self) -> _Token:
        raise NotImplementedError

    def _parse_response(
        self,
        response: Mapping[str, Any],
        started: float,
        wall_started: float,
        subject_token: str | None = None,
    ) -> _Token:
        value = _validate_token(response.get("access_token"))
        token_type = response.get("token_type", "Bearer")
        if not isinstance(token_type, str) or token_type.lower() != "bearer":
            raise TokenError("OAuth returned an unsupported token_type")
        raw_ttl = response.get("expires_in")
        # Do not invent a lifetime or keep an unbounded cache entry.
        if isinstance(raw_ttl, bool):
            raise TokenError("OAuth response needs a positive integer expires_in")
        if isinstance(raw_ttl, str) and raw_ttl.strip().isdigit():
            raw_ttl = int(raw_ttl.strip())
        if not isinstance(raw_ttl, int) or not 0 < raw_ttl <= 2**31:
            raise TokenError("OAuth response needs a positive integer expires_in")
        ttl = float(raw_ttl)
        for token in (subject_token, value):
            exp = _jwt_exp(token) if token else None
            if exp is not None:
                ttl = min(ttl, exp - wall_started)
        expires_at = started + ttl
        if expires_at - self._clock() <= self._minimum_validity:
            raise TokenError(
                "Obtained token is expired or too close to expiry; "
                "the subject-token supplier must renew its source token",
                retryable=True,
            )
        # A fixed five-minute buffer on a one-minute source token would mint
        # on every export. Clamp the lead time for short-lived credentials.
        lead = min(self._refresh_ahead, ttl * 0.10)
        return _Token(value, expires_at, expires_at - lead)

    def get_token(self) -> str:
        """Return cached token or lazily renew; concurrent callers mint once."""
        self._check_process()
        if not self._lock.acquire(timeout=self._lock_timeout):
            raise TokenError("Timed out waiting for token renewal", retryable=True)
        try:
            now = self._clock()
            cached = self._cached
            usable = cached is not None and now < (
                cached.expires_at - self._minimum_validity
            )
            if usable and now < cached.refresh_at:
                self._hits += 1
                return cached.value
            if now < self._retry_at:
                if usable and self._last_error and self._last_error.retryable:
                    self._fallbacks += 1
                    return cached.value
                error = self._last_error
                raise TokenError(
                    str(error) if error else "Token renewal is in backoff",
                    retryable=error.retryable if error else True,
                )
            try:
                fresh = self._mint()
            except TokenError as error:
                self._failures += 1
                self._last_error = error
                self._retry_at = self._clock() + self._backoff
                # Only transient failures may reuse an older still-valid token.
                if (
                    error.retryable and cached is not None
                    and self._clock() < cached.expires_at - self._minimum_validity
                ):
                    self._fallbacks += 1
                    return cached.value
                self._cached = None
                raise
            self._cached = fresh
            self._mints += 1
            self._retry_at = 0.0
            self._last_error = None
            return fresh.value
        finally:
            self._lock.release()

    def invalidate(self, rejected_token: str | None = None) -> None:
        """Force a later re-mint. A stale rejection cannot remove a newer token."""
        self._check_process()
        if not self._lock.acquire(timeout=self._lock_timeout):
            raise TokenError("Timed out invalidating token cache", retryable=True)
        try:
            if rejected_token is None or (
                self._cached is not None and self._cached.value == rejected_token
            ):
                self._cached = None
                self._retry_at = 0.0
                self._last_error = None
        finally:
            self._lock.release()

    def stats(self) -> TokenCacheStats:
        self._check_process()
        if not self._lock.acquire(timeout=self._lock_timeout):
            raise TokenError("Timed out reading token-cache statistics", retryable=True)
        try:
            remaining = max(
                0.0, self._cached.expires_at - self._clock()
            ) if self._cached else 0.0
            return TokenCacheStats(
                self._hits, self._mints, self._failures, self._fallbacks, remaining
            )
        finally:
            self._lock.release()


class ZerobusTokenProvider(_CachedTokenProvider):
    """Exchange a renewable Entra/IdP JWT for a table-scoped Zerobus token.

    `get_subject_token` is called only when the Zerobus token needs renewal.
    It must return a current token and use bounded network timeouts.
    `databricks_client_id` is the approved principal's application UUID, not its
    numeric SCIM ID. Pass None only for an explicitly configured account-wide
    federation policy. A working Entra token for Jobs/SQL alone is insufficient.
    """

    def __init__(
        self,
        *,
        workspace_url: str,
        workspace_id: str,
        table_name: str,
        get_subject_token: Callable[[], str],
        databricks_client_id: str | None,
        http_client: OAuthHttpClient | None = None,
        **cache_options: Any,
    ):
        super().__init__(**cache_options)
        self._workspace_url = https_origin(workspace_url, "workspace_url")
        if not isinstance(workspace_id, str) or not re.fullmatch(r"[0-9]+", workspace_id):
            raise ValueError("workspace_id must be a nonempty string of digits")
        parts = table_name.split(".")
        if len(parts) != 3 or any(not _PART_RE.fullmatch(p) for p in parts):
            raise ValueError(
                "table_name must be catalog.schema.table with unquoted "
                "letters, digits, underscores, or hyphens"
            )
        if not callable(get_subject_token):
            raise TypeError("get_subject_token must be callable")
        if databricks_client_id is not None and (
            not isinstance(databricks_client_id, str)
            or not databricks_client_id.strip()
        ):
            raise ValueError("databricks_client_id must be nonempty or explicitly None")
        self._workspace_id = workspace_id
        self._table_name = table_name
        self._databricks_client_id = databricks_client_id
        self._subject_supplier = get_subject_token
        self._http = http_client or OAuthHttpClient()

    @property
    def workspace_url(self) -> str:
        return self._workspace_url

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    @property
    def table_name(self) -> str:
        return self._table_name

    @property
    def databricks_client_id(self) -> str | None:
        return self._databricks_client_id

    def authorization_details(self) -> list[dict[str, Any]]:
        catalog, schema, _ = self.table_name.split(".")
        return [
            {
                "type": "unity_catalog_privileges",
                "privileges": ["USE CATALOG"],
                "object_type": "CATALOG",
                "object_full_path": catalog,
            },
            {
                "type": "unity_catalog_privileges",
                "privileges": ["USE SCHEMA"],
                "object_type": "SCHEMA",
                "object_full_path": f"{catalog}.{schema}",
            },
            {
                "type": "unity_catalog_privileges",
                "privileges": ["SELECT", "MODIFY"],
                "object_type": "TABLE",
                "object_full_path": self.table_name,
                "operations": ["zerobuswrite"],
            },
        ]

    def _mint(self) -> _Token:
        started, wall_started = self._clock(), self._wall_clock()
        try:
            subject = _validate_token(self._subject_supplier())
        except TokenError:
            raise
        except Exception:
            # Do not preserve an exception message/chain that may contain a token.
            raise TokenError(
                "Subject-token supplier failed; inspect that helper separately",
                retryable=True,
            ) from None
        exp = _jwt_exp(subject)
        if exp is not None and exp - self._wall_clock() <= self._minimum_validity:
            raise TokenError(
                "Subject token is expired or near expiry; renew the Entra token",
                retryable=True,
            )
        fields = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "subject_token": subject,
            "scope": "all-apis",
            "resource": (
                f"api://databricks/workspaces/{self.workspace_id}/"
                "zerobusDirectWriteApi"
            ),
            "authorization_details": json.dumps(
                self.authorization_details(), separators=(",", ":")
            ),
        }
        if self.databricks_client_id is not None:
            fields["client_id"] = self.databricks_client_id
        response = self._http.post_form(
            f"{self.workspace_url}/oidc/v1/token", fields
        )
        return self._parse_response(response, started, wall_started, subject)


class EntraClientSecretTokenProvider(_CachedTokenProvider):
    """Optional complete Entra client-credentials supplier using only stdlib.

    The high-level initializer wires this to ZerobusTokenProvider automatically. The scope must match the federation policy's expected audience.
    Only Microsoft public-cloud Entra endpoints are constructed by this helper.
    """

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str | Callable[[], str],
        scope: str,
        http_client: OAuthHttpClient | None = None,
        **cache_options: Any,
    ):
        super().__init__(**cache_options)
        if not re.fullmatch(r"[A-Za-z0-9.-]+", tenant_id):
            raise ValueError("tenant_id must be a tenant UUID or tenant domain")
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id is required")
        if not isinstance(scope, str) or not scope.endswith("/.default") or any(c.isspace() for c in scope):
            raise ValueError("scope must be one resource ending in /.default")
        if isinstance(client_secret, str) and not client_secret:
            raise ValueError("client_secret is required")
        if not callable(client_secret) and not isinstance(client_secret, str):
            raise TypeError("client_secret must be a string or callable")
        self._url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._http = http_client or OAuthHttpClient()

    def _mint(self) -> _Token:
        started, wall_started = self._clock(), self._wall_clock()
        try:
            secret = (
                self._client_secret() if callable(self._client_secret)
                else self._client_secret
            )
            if not isinstance(secret, str) or not secret:
                raise ValueError
        except Exception:
            raise TokenError("Entra client-secret supplier failed") from None
        response = self._http.post_form(self._url, {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": secret,
            "scope": self._scope,
        })
        return self._parse_response(response, started, wall_started)
