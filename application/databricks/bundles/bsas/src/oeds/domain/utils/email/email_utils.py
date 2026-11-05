"""Compose and send configured or direct emails through supported providers.

The manager owns configuration, template rendering, recipient resolution, and
attachment conversion for registry-based and direct HTML messages. Common email
clients are treated strictly as transport clients and are only invoked through
their ``send_email`` methods.
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from collections.abc import Mapping, Sequence
from string import Template
from typing import ClassVar, Literal, TypeAlias, cast

import pandas as pd
from oeds.core.email_client import EmailClient
from oeds.core.email_graph_client import GraphEmailClient
import oeds.domain.utils.config.config_utils as config_utils

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PACKAGE = "oeds.config.email"
_DEFAULT_CONFIG_FILE = "default.json"
_MAX_GRAPH_DIRECT_ATTACHMENT_BYTES = 3 * 1024 * 1024

EmailProvider: TypeAlias = Literal["logicapp", "graph", "databridge"]


class EmailManager:
    """Send registry-based or direct HTML messages through one provider.

    :meth:`initialize` configures one provider, and :meth:`get_instance`
    creates a caller-owned manager from that configuration.
    """

    _configuration: ClassVar[dict[str, object] | None] = None

    def __init__(
        self,
        *,
        provider: EmailProvider,
        connection: Mapping[str, object],
        recipient_mappings: Mapping[str, str],
        config_file: str = _DEFAULT_CONFIG_FILE,
    ) -> None:
        """Create a manager from one email configuration snapshot.

        Args:
            provider: Transport provider name.
            connection: Provider-specific transport configuration.
            recipient_mappings: Mapping of configured recipient keys to email
                addresses.
            config_file: Packaged email registry JSON filename.
        """
        self._provider = self._normalize_provider(provider)
        self._connection = self._normalize_connection(
            provider=self._provider,
            connection=connection,
        )
        self.recipient_mappings = self._normalize_recipient_mappings(
            recipient_mappings
        )
        self.config_file = self._normalize_config_file(config_file)
        self._config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )

    @classmethod
    def initialize(
        cls,
        *,
        provider: EmailProvider,
        connection: Mapping[str, object],
        config_file: str = _DEFAULT_CONFIG_FILE,
        recipient_mappings: Mapping[str, str],
    ) -> type[EmailManager]:
        """Configure the provider used by future caller-owned managers.

        Args:
            provider: ``"logicapp"``, ``"graph"``, or ``"databridge"``.
            connection: Provider-specific transport configuration.
            config_file: Packaged email registry JSON filename.
            recipient_mappings: Mapping of configured recipient keys to email
                addresses.

        Returns:
            The manager class so callers may chain :meth:`get_instance`.
        """
        normalized_provider = cls._normalize_provider(provider)
        normalized_connection = cls._normalize_connection(
            provider=normalized_provider,
            connection=connection,
        )
        normalized_mappings = cls._normalize_recipient_mappings(recipient_mappings)
        normalized_config_file = cls._normalize_config_file(config_file)
        cls._configuration = {
            "provider": normalized_provider,
            "connection": normalized_connection,
            "config_file": normalized_config_file,
            "recipient_mappings": normalized_mappings,
        }
        logger.info(
            "Configured EmailManager for provider '%s'",
            normalized_provider,
        )
        return cls

    @classmethod
    def get_instance(cls) -> EmailManager:
        """Create a caller-owned manager from the active configuration."""
        configuration = cls._configuration
        if configuration is None:
            raise RuntimeError(
                "EmailManager is not initialized. "
                "Call EmailManager.initialize(...) first."
            )

        return cls(
            provider=cast(EmailProvider, configuration["provider"]),
            connection=cast(Mapping[str, object], configuration["connection"]),
            config_file=cast(str, configuration["config_file"]),
            recipient_mappings=cast(
                Mapping[str, str],
                configuration["recipient_mappings"],
            ),
        )

    @staticmethod
    def _normalize_provider(provider: str) -> EmailProvider:
        if not isinstance(provider, str):
            raise TypeError("provider must be a string.")

        normalized_provider = provider.strip().lower()
        if normalized_provider not in {"logicapp", "graph", "databridge"}:
            raise ValueError("provider must be logicapp, graph, or databridge.")
        return cast(EmailProvider, normalized_provider)

    @classmethod
    def _normalize_connection(
        cls,
        *,
        provider: EmailProvider,
        connection: Mapping[str, object],
    ) -> dict[str, object]:
        if not isinstance(connection, Mapping):
            raise TypeError("connection must be a mapping.")
        if any(not isinstance(key, str) for key in connection):
            raise ValueError("connection keys must be strings.")

        if provider == "databridge":
            from .databridge_email_client import DataBridgeEmailClient

            return DataBridgeEmailClient.normalize_connection(connection)

        required_fields = (
            {"logicapp_url"}
            if provider == "logicapp"
            else {"tenant_id", "client_id", "client_secret", "sender_email"}
        )
        allowed_fields = (
            required_fields
            if provider == "logicapp"
            else required_fields | {"request_timeout_sec"}
        )
        unknown_fields = sorted(set(connection) - allowed_fields)
        if unknown_fields:
            raise ValueError(
                f"Unsupported {provider} connection field(s): "
                f"{', '.join(unknown_fields)}."
            )
        missing_fields = sorted(required_fields - set(connection))
        if missing_fields:
            raise ValueError(
                f"Missing required {provider} connection field(s): "
                f"{', '.join(missing_fields)}."
            )

        if provider == "logicapp":
            return {
                "logicapp_url": cls._normalize_connection_string(
                    connection["logicapp_url"],
                    "logicapp_url",
                )
            }

        normalized_connection: dict[str, object] = {
            field_name: cls._normalize_connection_string(
                connection[field_name],
                field_name,
            )
            for field_name in sorted(required_fields)
        }
        request_timeout_sec = connection.get("request_timeout_sec", 30)
        if (
            isinstance(request_timeout_sec, bool)
            or not isinstance(request_timeout_sec, (int, float))
            or request_timeout_sec <= 0
        ):
            raise ValueError("request_timeout_sec must be greater than zero.")
        normalized_connection["request_timeout_sec"] = float(request_timeout_sec)
        return normalized_connection

    @staticmethod
    def _normalize_connection_string(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"connection['{field_name}'] must be a non-empty string."
            )
        return value.strip()

    def _create_email_client(self) -> EmailClient | GraphEmailClient:
        """Create the configured transport client for one send operation."""
        if self._provider == "logicapp":
            return EmailClient(cast(str, self._connection["logicapp_url"]))

        return GraphEmailClient(
            tenant_id=cast(str, self._connection["tenant_id"]),
            client_id=cast(str, self._connection["client_id"]),
            client_secret=cast(str, self._connection["client_secret"]),
            sender=cast(str, self._connection["sender_email"]),
            request_timeout_sec=cast(
                float,
                self._connection["request_timeout_sec"],
            ),
        )

    @staticmethod
    def _normalize_recipient_mappings(
        recipient_mappings: Mapping[str, str],
    ) -> dict[str, str]:
        if not isinstance(recipient_mappings, Mapping):
            raise TypeError("recipient_mappings must be a mapping.")

        normalized_mappings: dict[str, str] = {}
        for recipient_key, email_address in recipient_mappings.items():
            if not isinstance(recipient_key, str) or not recipient_key.strip():
                raise ValueError("recipient_mappings keys must be non-empty strings.")
            if not isinstance(email_address, str) or not email_address.strip():
                raise ValueError(
                    f"recipient_mappings['{recipient_key}'] must be a non-empty string."
                )
            normalized_mappings[recipient_key.strip()] = email_address.strip()

        return normalized_mappings

    @staticmethod
    def _normalize_direct_recipients(
        recipients: str | Sequence[str],
    ) -> list[str]:
        """Normalize direct recipient addresses without validating syntax."""
        if isinstance(recipients, str):
            normalized_recipients = [
                recipient.strip()
                for recipient in recipients.replace(";", ",").split(",")
                if recipient.strip()
            ]
        elif isinstance(recipients, Sequence) and not isinstance(
            recipients, (bytes, bytearray)
        ):
            normalized_recipients = []
            for index, recipient in enumerate(recipients):
                if not isinstance(recipient, str) or not recipient.strip():
                    raise ValueError(
                        f"recipients[{index}] must be a non-empty string."
                    )
                normalized_recipients.append(recipient.strip())
        else:
            raise TypeError("recipients must be a string or a sequence of strings.")

        if not normalized_recipients:
            raise ValueError("At least one recipient is required.")
        return normalized_recipients

    @staticmethod
    def _normalize_config_file(config_file: str) -> str:
        if not isinstance(config_file, str) or not config_file.strip():
            raise ValueError("config_file must be a non-empty string.")

        return config_file.strip()

    def _load_registry_map(self) -> dict[str, object]:
        """Load the packaged email registry from JSON."""
        logger.info(
            "Loading email config from package '%s' and file '%s'",
            _DEFAULT_CONFIG_PACKAGE,
            self.config_file,
        )
        registry_text = self._config_manager.load_config_resource(self.config_file)
        registry = json.loads(registry_text)
        if not isinstance(registry, dict):
            raise ValueError("Email registry must be a JSON object.")
        return registry

    def _load_email_template(self, template_ref: str) -> str:
        """Load a body-only HTML template from the email config package."""
        if not isinstance(template_ref, str) or not template_ref.strip():
            raise ValueError("template must be a non-empty string.")

        template_html = self._config_manager.load_config_resource(
            template_ref.strip()
        )
        if not template_html.strip():
            raise ValueError(f"Email template '{template_ref}' is empty.")
        return template_html

    def get_email_registry(self, template_ref: str) -> dict[str, object]:
        """Load and resolve one email definition and its recipient addresses.

        Args:
            template_ref: Email key in the packaged registry, such as
                ``"failure"``.

        Returns:
            Dictionary containing the template path, configured subject, and
            resolved recipient addresses.
        """
        if not isinstance(template_ref, str) or not template_ref.strip():
            raise ValueError("template_ref must be a non-empty string.")

        registry_key = template_ref.strip()
        definition = self._load_registry_map().get(registry_key)
        if not isinstance(definition, Mapping):
            raise ValueError(f"Email registry '{registry_key}' not found.")

        template_path = definition.get("template")
        configured_subject = definition.get("subject")
        recipient_keys = definition.get("recipients")

        if not isinstance(template_path, str) or not template_path.strip():
            raise ValueError(
                f"Email registry '{registry_key}' must define a non-empty template path."
            )
        if not isinstance(configured_subject, str) or not configured_subject.strip():
            raise ValueError(
                f"Email registry '{registry_key}' must define a non-empty subject."
            )
        if not isinstance(recipient_keys, list) or not recipient_keys:
            raise ValueError(
                f"Email registry '{registry_key}' must define a non-empty recipients list."
            )

        invalid_keys = [
            key for key in recipient_keys if not isinstance(key, str) or not key.strip()
        ]
        if invalid_keys:
            raise ValueError(
                f"Email registry '{registry_key}' contains invalid recipient keys."
            )

        normalized_keys = [key.strip() for key in recipient_keys]
        missing_keys = [
            key for key in normalized_keys if key not in self.recipient_mappings
        ]
        if missing_keys:
            logger.debug(
                "Email registry '%s' skipped unmapped recipient key(s): %s",
                registry_key,
                ", ".join(missing_keys),
            )

        recipients = [
            self.recipient_mappings[key]
            for key in normalized_keys
            if key in self.recipient_mappings
        ]
        if not recipients:
            raise ValueError(
                f"Email registry '{registry_key}' has no mapped recipients."
            )
        logger.debug(
            "Resolved email registry '%s' recipient_count=%d",
            registry_key,
            len(recipients),
        )
        return {
            "template": template_path.strip(),
            "subject": configured_subject.strip(),
            "recipients": recipients,
        }

    @staticmethod
    def _is_spark_dataframe(value: object) -> bool:
        """Return whether a value is a PySpark DataFrame when PySpark is available."""
        try:
            from pyspark.sql import DataFrame as SparkDataFrame
        except ImportError:
            return False
        return isinstance(value, SparkDataFrame)

    def df_to_email_table(self, dataframe: object) -> str:
        """Convert a pandas or PySpark DataFrame into a styled HTML table."""
        if isinstance(dataframe, pd.DataFrame):
            pandas_dataframe = dataframe
        elif self._is_spark_dataframe(dataframe):
            # Spark data must be materialized locally before pandas can render it.
            pandas_dataframe = dataframe.toPandas()
        else:
            raise TypeError("dataframe must be a pandas or PySpark DataFrame.")

        html = pandas_dataframe.to_html(index=False, border=1)
        return (
            html.replace(
                '<table border="1"',
                '<table border="1" style="border-collapse:collapse;'
                'border:1px solid black;"',
            )
            .replace(
                "<td>",
                '<td style="border:1px solid black;padding:8px 12px;">',
            )
            .replace(
                "<th>",
                '<th style="border:1px solid black;padding:8px 12px;">',
            )
        )

    def _normalize_variables(
        self,
        variables: Mapping[str, object] | None,
    ) -> dict[str, object]:
        """Prepare template variables, including DataFrame-to-HTML conversion."""
        if variables is None:
            return {}
        if not isinstance(variables, Mapping):
            raise TypeError("variables must be a mapping.")

        normalized: dict[str, object] = {}
        for key, value in variables.items():
            if not isinstance(key, str) or not key:
                raise ValueError("variables keys must be non-empty strings.")
            if isinstance(value, pd.DataFrame) or self._is_spark_dataframe(value):
                normalized[key] = self.df_to_email_table(value)
            elif value is None:
                normalized[key] = ""
            else:
                normalized[key] = value
        return normalized

    @staticmethod
    def _render_template_value(
        value: str,
        variables: Mapping[str, object],
        field_name: str,
    ) -> str:
        """Substitute dynamic variables in a subject or body template."""
        try:
            rendered_value = Template(value).safe_substitute(variables)
        except ValueError as exc:
            raise ValueError(f"Invalid placeholder in email {field_name}.") from exc
        if not rendered_value.strip():
            raise ValueError(f"Rendered email {field_name} cannot be empty.")
        return rendered_value

    def _attachment_content_to_bytes(self, content: object) -> bytes:
        """Convert a supported attachment value into bytes."""
        if isinstance(content, bytes):
            content_bytes = content
        elif isinstance(content, bytearray):
            content_bytes = bytes(content)
        elif isinstance(content, str):
            content_bytes = content.encode("utf-8")
        elif isinstance(content, pd.DataFrame):
            content_bytes = content.to_csv(index=False, header=True).encode("utf-8")
        elif self._is_spark_dataframe(content):
            content_bytes = (
                content.toPandas().to_csv(index=False, header=True).encode("utf-8")
            )
        else:
            raise TypeError(
                f"Unsupported attachment content type '{type(content).__name__}'. "
                "Expected str, bytes, bytearray, pandas DataFrame, or PySpark DataFrame."
            )

        if not content_bytes:
            raise ValueError("Attachment content cannot be empty.")
        return content_bytes

    def _build_attachments(
        self,
        attachments: list[Mapping[str, object]] | None,
    ) -> list[dict[str, str]]:
        """Build provider-specific attachments from transport-neutral definitions."""
        if attachments is None:
            return []
        if not isinstance(attachments, list):
            raise TypeError("attachments must be a list.")

        provider_attachments: list[dict[str, str]] = []
        for index, attachment in enumerate(attachments):
            if not isinstance(attachment, Mapping):
                raise TypeError(f"attachments[{index}] must be a mapping.")

            name = attachment.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    f"attachments[{index}].name must be a non-empty string."
                )
            if "content" not in attachment:
                raise ValueError(f"attachments[{index}] must define content.")

            normalized_name = name.strip()
            content_bytes = self._attachment_content_to_bytes(attachment["content"])
            encoded_content = base64.b64encode(content_bytes).decode("ascii")

            if self._provider == "logicapp":
                provider_attachments.append(
                    {"Name": normalized_name, "ContentBytes": encoded_content}
                )
                continue

            content_type = attachment.get("content_type")
            if content_type is None:
                content_type = (
                    mimetypes.guess_type(normalized_name)[0]
                    or "application/octet-stream"
                )
            if not isinstance(content_type, str) or not content_type.strip():
                raise ValueError(
                    f"attachments[{index}].content_type must be a non-empty string."
                )
            if len(content_bytes) >= _MAX_GRAPH_DIRECT_ATTACHMENT_BYTES:
                raise ValueError(
                    f"attachments[{index}] must be smaller than 3 MiB for Graph."
                )

            provider_attachments.append(
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": normalized_name,
                    "contentType": content_type.strip(),
                    "contentBytes": encoded_content,
                }
            )

        return provider_attachments

    def _send_composed_email(
        self,
        *,
        recipients: list[str],
        subject: str,
        body: str,
        attachments: list[dict[str, str]],
    ) -> None:
        """Send one composed email through the configured provider."""
        if self._provider == "databridge":
            from .databridge_email_client import DataBridgeEmailClient

            DataBridgeEmailClient(self._connection).send_email(
                recipients=recipients,
                subject=subject,
                body=body,
                attachments=attachments,
            )
            return

        email_client = self._create_email_client()

        if self._provider == "logicapp":
            logicapp_client = cast(EmailClient, email_client)
            logicapp_client.send_email(
                recipients=recipients,
                subject=subject,
                body=body,
                attachments=attachments,
            )
        else:
            graph_client = cast(GraphEmailClient, email_client)
            graph_client.send_email(
                recipients=recipients,
                subject=subject,
                body=body,
                body_format="html",
                attachments=attachments,
            )

    def send_email(
        self,
        *,
        template_ref: str,
        variables: Mapping[str, object] | None = None,
        subject: str | None = None,
        attachments: list[Mapping[str, object]] | None = None,
    ) -> None:
        """Render and send one configured email.

        Args:
            template_ref: Email key in the packaged registry.
            variables: Dynamic values used by the configured subject and HTML
                body template.
            subject: Optional dynamic subject that overrides the configured
                subject.
            attachments: Optional list of mappings containing ``name``,
                ``content``, and an optional ``content_type``.

        Raises:
            TypeError: If variables or attachments use unsupported types.
            ValueError: If configuration, recipients, subject, body, or
                attachments are invalid.
        """
        email_definition = self.get_email_registry(template_ref)
        normalized_variables = self._normalize_variables(variables)

        if subject is not None and not isinstance(subject, str):
            raise TypeError("subject must be a string or None.")
        subject_template = (
            subject if subject is not None else str(email_definition["subject"])
        )
        rendered_subject = self._render_template_value(
            subject_template,
            normalized_variables,
            "subject",
        ).strip()

        template_html = self._load_email_template(str(email_definition["template"]))
        rendered_body = self._render_template_value(
            template_html,
            normalized_variables,
            "body",
        )
        provider_attachments = self._build_attachments(attachments)
        recipients = cast(list[str], email_definition["recipients"])

        logger.info(
            "Sending configured email '%s' provider=%s recipient_count=%d "
            "attachment_count=%d",
            template_ref,
            self._provider,
            len(recipients),
            len(provider_attachments),
        )

        self._send_composed_email(
            recipients=recipients,
            subject=rendered_subject,
            body=rendered_body,
            attachments=provider_attachments,
        )

    def send_direct_email(
        self,
        *,
        recipients: str | Sequence[str],
        subject: str,
        body: str,
        attachments: list[Mapping[str, object]] | None = None,
    ) -> None:
        """Send an HTML email without loading a registry entry or template.

        Args:
            recipients: One comma- or semicolon-delimited string, or a sequence
                of recipient addresses.
            subject: Non-empty email subject.
            body: Non-empty raw HTML body. The value is sent unchanged.
            attachments: Optional list of mappings containing ``name``,
                ``content``, and an optional ``content_type``.

        Raises:
            TypeError: If recipients, subject, body, or attachments use
                unsupported types.
            ValueError: If recipients, subject, body, or attachments are invalid.
        """
        normalized_recipients = self._normalize_direct_recipients(recipients)

        if not isinstance(subject, str):
            raise TypeError("subject must be a string.")
        normalized_subject = subject.strip()
        if not normalized_subject:
            raise ValueError("subject must be a non-empty string.")

        if not isinstance(body, str):
            raise TypeError("body must be a string.")
        if not body.strip():
            raise ValueError("body must be a non-empty string.")

        provider_attachments = self._build_attachments(attachments)
        logger.info(
            "Sending direct email provider=%s recipient_count=%d "
            "attachment_count=%d",
            self._provider,
            len(normalized_recipients),
            len(provider_attachments),
        )

        self._send_composed_email(
            recipients=normalized_recipients,
            subject=normalized_subject,
            body=body,
            attachments=provider_attachments,
        )
