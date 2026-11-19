"""Create workspace SDK clients with explicitly selected authentication."""

from typing import Literal
from urllib.parse import urlsplit

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config


def create_workspace_client(
    *,
    host: str,
    auth_mode: Literal["aad", "obo"],
    resource_id: str | None = None,
    tenant_id: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    user_token: str | None = None,
) -> WorkspaceClient:
    """Return a new SDK client using caller-supplied credentials.

    Args:
        host: Workspace hostname or HTTPS URL, with an optional trailing slash.
        auth_mode: Case-insensitive aad or obo; unrelated credentials are ignored.
        resource_id: Azure workspace resource ID, required for aad.
        tenant_id: Entra tenant ID, required for aad.
        client_id: Entra service-principal application ID, required for aad.
        client_secret: Entra application secret, required for aad.
        user_token: Current Databricks user token without a Bearer prefix,
            required for obo. No token exchange or refresh is performed.

    OBO clients belong to the current request and must not be globally cached.
    The caller owns header extraction, secrets, and refreshed user tokens.
    Authentication is selected explicitly and never falls back to another mode.
    SDK configuration and authentication errors propagate to the caller.

    Raises:
        ValueError: The host, mode, or credentials required by that mode are invalid.
    """
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a nonempty string.")
    normalized_host = host.strip()
    if "://" not in normalized_host:
        normalized_host = f"https://{normalized_host}"
    try:
        parsed = urlsplit(normalized_host)
        port = parsed.port
    except ValueError:
        raise ValueError("host must be a workspace hostname or HTTPS URL.") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or "?" in normalized_host
        or "#" in normalized_host
        or any(char.isspace() for char in normalized_host)
        or "\\" in normalized_host
        or (port is not None and port != 443)
    ):
        raise ValueError("host must be a workspace hostname or HTTPS URL.")
    normalized_host = f"https://{parsed.hostname}"

    if not isinstance(auth_mode, str) or auth_mode.lower() not in ("aad", "obo"):
        raise ValueError("auth_mode must be aad or obo.")
    if auth_mode.lower() == "obo":
        if not isinstance(user_token, str) or not user_token.strip():
            raise ValueError("obo mode requires a nonempty user_token string.")
        if user_token.strip().lower().startswith("bearer "):
            raise ValueError("user_token must not include a Bearer prefix.")
        config = Config(
            host=normalized_host,
            auth_type="pat",
            token=user_token.strip(),
        )
    else:
        for name, value in (
            ("resource_id", resource_id),
            ("tenant_id", tenant_id),
            ("client_id", client_id),
            ("client_secret", client_secret),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"aad mode requires a nonempty {name} string.")
        config = Config(
            host=normalized_host,
            auth_type="azure-client-secret",
            azure_workspace_resource_id=resource_id,
            azure_tenant_id=tenant_id,
            azure_client_id=client_id,
            azure_client_secret=client_secret,
        )
    return WorkspaceClient(config=config)
