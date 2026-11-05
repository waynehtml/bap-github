"""Stage composed email attachments and send through a DataBridge job."""

from __future__ import annotations

import base64
import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import cast
from uuid import uuid4

from oeds.domain.utils.ingest.ingest_utils import DisConnectionOptions, run_ingest

logger = logging.getLogger(__name__)
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.@-]+")
_TEMPLATE_STARTS = ("{{", "{%", "{#", "<<", "<%", "<#")


def _literal_message(value: str) -> str:
    """Keep already-composed text literal through DataBridge template rendering.

    Text containing server template markers is encoded as a task-stage string
    expression. Unicode escapes hide its braces and angle brackets from the
    earlier config stage; the task stage then restores the original text.
    Ordinary text passes through unchanged. The ingestion template's ``tojson``
    filter handles JSON escaping separately.
    """
    if not any(marker in value for marker in _TEMPLATE_STARTS):
        return value
    quoted = json.dumps(value, ensure_ascii=False)
    for character in "<>{}":
        quoted = quoted.replace(character, f"\\u{ord(character):04x}")
    return "<< " + quoted + " >>"


class DataBridgeEmailClient:
    """Submit one synchronous email pipeline with isolated Volume staging.

    Attachments use the normalized base64 file dictionaries produced by
    EmailManager. Only secret references are included in the job configuration.
    Staged files remain available for externally managed lifecycle cleanup.
    """

    def __init__(self, connection: Mapping[str, object]) -> None:
        """Store validated settings; defer file access and job submission to send."""
        self.connection = self.normalize_connection(connection)

    @staticmethod
    def normalize_connection(connection: Mapping[str, object]) -> dict[str, object]:
        """Validate each provider setting in order without external I/O.

        Args:
            connection: Job credentials in ``dis_connection``, a shared Volume
                ``tmp_root``, the caller's ``job_run_id``, a sender mailbox, and
                Graph secret scope/key references. Optional settings select the
                ingestion config, polling intervals, and total attachment cap.

        Returns:
            A new mapping with defaults applied and string values normalized.
            Graph scope/key entries remain references, not resolved secrets.

        Raises:
            TypeError: If the job connection is not ``DisConnectionOptions``.
            ValueError: If required fields are missing or supported values are invalid.
        """
        normalized: dict[str, object] = {}

        # dis_connection
        if "dis_connection" not in connection:
            raise ValueError("connection['dis_connection'] is required.")
        dis_connection = connection["dis_connection"]
        if not isinstance(dis_connection, DisConnectionOptions):
            raise TypeError("dis_connection must be DisConnectionOptions.")

        # workspace host
        if not isinstance(dis_connection.host, str) or not dis_connection.host.strip():
            raise ValueError("dis_connection.host must be a non-empty string.")

        # azure_tenant_id
        if (
            not isinstance(dis_connection.azure_tenant_id, str)
            or not dis_connection.azure_tenant_id.strip()
        ):
            raise ValueError(
                "dis_connection.azure_tenant_id must be a non-empty string."
            )

        # azure_client_id
        if (
            not isinstance(dis_connection.azure_client_id, str)
            or not dis_connection.azure_client_id.strip()
        ):
            raise ValueError(
                "dis_connection.azure_client_id must be a non-empty string."
            )

        # azure_client_secret
        if (
            not isinstance(dis_connection.azure_client_secret, str)
            or not dis_connection.azure_client_secret.strip()
        ):
            raise ValueError(
                "dis_connection.azure_client_secret must be a non-empty string."
            )

        # azure_workspace_resource_id
        if (
            not isinstance(dis_connection.azure_workspace_resource_id, str)
            or not dis_connection.azure_workspace_resource_id.strip()
        ):
            raise ValueError(
                "dis_connection.azure_workspace_resource_id must be a non-empty string."
            )

        # dis_job_id
        if type(dis_connection.dis_job_id) is not int or dis_connection.dis_job_id <= 0:
            raise ValueError("dis_connection.dis_job_id must be a positive integer.")
        normalized["dis_connection"] = dis_connection

        # tmp_root
        if "tmp_root" not in connection:
            raise ValueError("connection['tmp_root'] is required.")
        tmp_root = connection["tmp_root"]
        if not isinstance(tmp_root, str) or not tmp_root.strip():
            raise ValueError("connection['tmp_root'] must be a non-empty string.")
        tmp_root = tmp_root.strip()
        normalized["tmp_root"] = str(PurePosixPath(tmp_root))

        # job_run_id
        if "job_run_id" not in connection:
            raise ValueError("connection['job_run_id'] is required.")
        job_run_id = connection["job_run_id"]
        if type(job_run_id) is int and job_run_id >= 0:
            job_run_id = str(job_run_id)
        if not isinstance(job_run_id, str) or not job_run_id.strip():
            raise ValueError("connection['job_run_id'] must be a non-empty string.")
        job_run_id = job_run_id.strip()
        normalized["job_run_id"] = job_run_id

        # sender_email
        if "sender_email" not in connection:
            raise ValueError("connection['sender_email'] is required.")
        sender_email = connection["sender_email"]
        if not isinstance(sender_email, str) or not sender_email.strip():
            raise ValueError("connection['sender_email'] must be a non-empty string.")
        normalized["sender_email"] = sender_email.strip()

        # graph_secret_scope
        if "graph_secret_scope" not in connection:
            raise ValueError("connection['graph_secret_scope'] is required.")
        graph_secret_scope = connection["graph_secret_scope"]
        if not isinstance(graph_secret_scope, str) or not graph_secret_scope.strip():
            raise ValueError(
                "connection['graph_secret_scope'] must be a non-empty string."
            )
        graph_secret_scope = graph_secret_scope.strip()
        normalized["graph_secret_scope"] = graph_secret_scope

        # graph_tenant_id_key
        if "graph_tenant_id_key" not in connection:
            raise ValueError("connection['graph_tenant_id_key'] is required.")
        graph_tenant_id_key = connection["graph_tenant_id_key"]
        if not isinstance(graph_tenant_id_key, str) or not graph_tenant_id_key.strip():
            raise ValueError(
                "connection['graph_tenant_id_key'] must be a non-empty string."
            )
        graph_tenant_id_key = graph_tenant_id_key.strip()
        normalized["graph_tenant_id_key"] = graph_tenant_id_key

        # graph_client_id_key
        if "graph_client_id_key" not in connection:
            raise ValueError("connection['graph_client_id_key'] is required.")
        graph_client_id_key = connection["graph_client_id_key"]
        if not isinstance(graph_client_id_key, str) or not graph_client_id_key.strip():
            raise ValueError(
                "connection['graph_client_id_key'] must be a non-empty string."
            )
        graph_client_id_key = graph_client_id_key.strip()
        normalized["graph_client_id_key"] = graph_client_id_key

        # graph_client_secret_key
        if "graph_client_secret_key" not in connection:
            raise ValueError("connection['graph_client_secret_key'] is required.")
        graph_client_secret_key = connection["graph_client_secret_key"]
        if (
            not isinstance(graph_client_secret_key, str)
            or not graph_client_secret_key.strip()
        ):
            raise ValueError(
                "connection['graph_client_secret_key'] must be a non-empty string."
            )
        graph_client_secret_key = graph_client_secret_key.strip()
        normalized["graph_client_secret_key"] = graph_client_secret_key

        # ingest_config_file
        ingest_config_file = connection.get("ingest_config_file", "email.json")
        if not isinstance(ingest_config_file, str) or not ingest_config_file.strip():
            raise ValueError(
                "connection['ingest_config_file'] must be a non-empty string."
            )
        ingest_config_file = ingest_config_file.strip()
        normalized["ingest_config_file"] = ingest_config_file

        # wait_timeout_sec
        wait_timeout_sec = connection.get("wait_timeout_sec", 1800)
        if type(wait_timeout_sec) is not int or wait_timeout_sec < 1:
            raise ValueError("connection['wait_timeout_sec'] must be an integer >= 1.")
        normalized["wait_timeout_sec"] = wait_timeout_sec

        # wait_poll_sec
        wait_poll_sec = connection.get("wait_poll_sec", 10)
        if type(wait_poll_sec) is not int or wait_poll_sec < 1:
            raise ValueError("connection['wait_poll_sec'] must be an integer >= 1.")
        normalized["wait_poll_sec"] = wait_poll_sec

        # max_total_attachment_bytes
        max_total_attachment_bytes = connection.get(
            "max_total_attachment_bytes", 10485760
        )
        if (
            type(max_total_attachment_bytes) is not int
            or max_total_attachment_bytes < 0
        ):
            raise ValueError(
                "connection['max_total_attachment_bytes'] must be an integer >= 0."
            )
        normalized["max_total_attachment_bytes"] = max_total_attachment_bytes

        return normalized

    def send_email(
        self,
        *,
        recipients: list[str],
        subject: str,
        body: str,
        attachments: list[dict[str, str]],
    ) -> None:
        """Stage composed attachments and wait for the DataBridge job to succeed.

        Args:
            recipients: Addresses already resolved by EmailManager.
            subject: Composed subject, protected from server-side templating.
            body: Composed HTML sent inline in the ingestion config.
            attachments: EmailManager file dictionaries containing ``name`` and
                base64 ``contentBytes``. This transport checks filenames and
                total decoded size; it has no separate per-file size check.

        Returns:
            None after run_ingest confirms job success. The provider does not
            inspect individual task results or confirm recipient delivery.

        Raises:
            ValueError: If filenames, base64 content, or total size are invalid.
            OSError: If staging directories or files cannot be written.
            IngestTaskError: If run_ingest cannot prepare the config or confirm
                successful job completion, including waiting timeouts.

        Files remain under ``<tmp_root>/<job_run_id>/<guid>`` for lifecycle
        cleanup, including partial staging and failed or uncertain submissions.
        Errors propagate without retrying; an uncertain send may still complete.
        """

        # Validate attachment names and decode their content
        files: dict[str, bytes] = {}
        total_bytes = 0
        for attachment in attachments:
            name = attachment["name"]
            if name in {".", ".."} or any(char in name for char in "/\\:\x00"):
                raise ValueError("DataBridge attachment names must be plain filenames.")
            if name in files:
                raise ValueError("DataBridge attachment filenames must be unique.")

            # Decode the content to get the original bytes
            content = base64.b64decode(attachment["contentBytes"], validate=True)
            files[name] = content
            total_bytes += len(content)

        # Check the total size of all attachments against the maximum allowed size
        if total_bytes > cast(int, self.connection["max_total_attachment_bytes"]):
            raise ValueError("Combined attachments exceed max_total_attachment_bytes.")

        # Stage attachments in a unique directory under the shared tmp_root
        staging_root = Path(cast(str, self.connection["tmp_root"])).resolve()
        staging_dir = None
        if files:
            # Isolate each send, including multiple sends from the same job run.
            staging_dir = (
                staging_root / cast(str, self.connection["job_run_id"]) / uuid4().hex
            ).resolve()
            if not staging_dir.is_relative_to(staging_root):
                raise ValueError("Email staging directory must remain under tmp_root.")
            staging_dir.mkdir(parents=True, exist_ok=False)
            for name, content in files.items():
                with (staging_dir / name).open("xb") as attachment_file:
                    attachment_file.write(content)
            logger.info(
                "Email attachments staged count=%d path=%s", len(files), staging_dir
            )

        # None omits the download task; message bodies always remain inline.
        template_params = {
            "src_dir": staging_dir.as_posix() if staging_dir else None,
            "secret_scope": self.connection["graph_secret_scope"],
            "tenant_id_key": self.connection["graph_tenant_id_key"],
            "client_id_key": self.connection["graph_client_id_key"],
            "client_secret_key": self.connection["graph_client_secret_key"],
            "sender_literal": _literal_message(
                cast(str, self.connection["sender_email"])
            ),
            "recipient_literals": [_literal_message(value) for value in recipients],
            "subject_literal": _literal_message(subject),
            "body_literal": _literal_message(body),
            "max_total_attachment_bytes": self.connection["max_total_attachment_bytes"],
        }

        # run_ingest raises for every job status other than SUCCESS.
        dis_connection = cast(DisConnectionOptions, self.connection["dis_connection"])
        run_ingest(
            connection=dis_connection,
            config_file=cast(str, self.connection["ingest_config_file"]),
            template_params=template_params,
            debug=True,
            verification=None,
            wait_timeout_sec=cast(int, self.connection["wait_timeout_sec"]),
            wait_poll_sec=cast(int, self.connection["wait_poll_sec"]),
        )
