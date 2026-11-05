"""Compose and deliver a report for one completed Testbench execution."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import fields
from datetime import datetime, timezone
from html import escape
from typing import Any
from urllib.parse import urlsplit

from oeds.domain.utils.testbench.runner_context import RunnerContext

logger = logging.getLogger(__name__)

_SECRET_FIELD_MARKERS = (
    "accesskey",
    "apikey",
    "authorization",
    "bearer",
    "clientsecret",
    "connectionstring",
    "credential",
    "password",
    "passphrase",
    "privatekey",
    "secret",
    "secrete",
    "token",
)


class ReportUtils:
    """Render, log, and optionally email a Testbench runner context."""

    @staticmethod
    def compose_subject(context: RunnerContext) -> str:
        """Compose the final Testbench email subject."""
        outcome = "succeeded" if context.case_status == "SUCCEEDED" else "failed"
        return f"Testbench {outcome} on {context.dataset}:{context.case_name}"

    @classmethod
    def compose_body(cls, context: RunnerContext) -> str:
        """Render every runner-context field as a safe HTML key/value row."""
        rows = []
        for context_field in fields(context):
            field_name = context_field.name
            value = getattr(context, field_name)
            rendered_value = cls._render_value(
                cls._redact_value(value, field_name=field_name)
            )
            escaped_field_name = escape(field_name, quote=True)

            if cls._is_http_url(value):
                escaped_url = escape(str(value).strip(), quote=True)
                rendered_cell = f'<a href="{escaped_url}">{escaped_url}</a>'
            elif isinstance(value, (Mapping, list, tuple, set, frozenset)):
                rendered_cell = f"<pre>{escape(rendered_value, quote=True)}</pre>"
            else:
                rendered_cell = escape(rendered_value, quote=True)

            rows.append(
                "<tr>"
                f'<th style="text-align:left;vertical-align:top;padding:6px;">'
                f"{escaped_field_name}</th>"
                f'<td style="padding:6px;">{rendered_cell}</td>'
                "</tr>"
            )

        return (
            "<html><body>"
            f"<h2>{escape(cls.compose_subject(context), quote=True)}</h2>"
            '<table style="border-collapse:collapse;" border="1">'
            + "".join(rows)
            + "</table></body></html>"
        )

    @classmethod
    def report(cls, context: RunnerContext) -> None:
        """Log the final report and email it when a creator is available."""
        subject = cls.compose_subject(context)
        body = cls.compose_body(context)
        logger.info(
            "Testbench report composed: dataset=%s case_name=%s "
            "case_status=%s target_job_run_status=%s",
            context.dataset,
            context.case_name,
            context.case_status,
            context.target_job_run_status or "None",
        )

        if context.service_job_run_create_user is None:
            logger.info(
                "Testbench report email skipped because the service run creator "
                "is unavailable."
            )
            return

        try:
            cls._send_email(
                recipient=context.service_job_run_create_user,
                subject=subject,
                body=body,
            )
        except Exception:
            logger.warning("Testbench report email delivery failed.")
            return
        logger.info("Testbench report email submitted.")

    @staticmethod
    def _send_email(*, recipient: str, subject: str, body: str) -> None:
        """Send one report through the configured direct-email interface."""
        from oeds.domain.utils.email import EmailManager

        EmailManager.get_instance().send_direct_email(
            recipients=recipient,
            subject=subject,
            body=body,
        )

    @classmethod
    def _redact_value(cls, value: Any, *, field_name: str | None = None) -> Any:
        """Recursively redact values associated with secret-like field names."""
        if field_name is not None and cls._is_secret_field(field_name):
            return "<redacted>"
        if isinstance(value, Mapping):
            return {
                str(key): cls._redact_value(item, field_name=str(key))
                for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
            }
        if isinstance(value, (list, tuple)):
            return [cls._redact_value(item) for item in value]
        if isinstance(value, (set, frozenset)):
            return sorted((cls._redact_value(item) for item in value), key=str)
        return value

    @staticmethod
    def _is_secret_field(field_name: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]", "", field_name.strip().lower())
        return any(marker in normalized for marker in _SECRET_FIELD_MARKERS)

    @classmethod
    def _render_value(cls, value: Any) -> str:
        """Render one context value deterministically for the HTML report."""
        if value is None:
            return "None"
        if isinstance(value, datetime):
            resolved = (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            )
            return resolved.isoformat().replace("+00:00", "Z")
        if isinstance(value, Exception):
            return f"{type(value).__name__}: {value}"
        if isinstance(value, Mapping):
            return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        if isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        ):
            return json.dumps(value, separators=(",", ":"), default=str)
        if isinstance(value, (set, frozenset)):
            return json.dumps(
                sorted(value, key=str),
                separators=(",", ":"),
                default=str,
            )
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    @staticmethod
    def _is_http_url(value: Any) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False
        parsed = urlsplit(value.strip())
        return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


__all__ = ["ReportUtils"]
