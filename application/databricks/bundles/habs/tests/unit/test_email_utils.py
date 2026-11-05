"""Unit tests for DataForge email composition and dispatch."""

from __future__ import annotations

import base64
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

DATAFORGE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DATAFORGE_ROOT / "src"))

# EmailManager is tested at the DataForge boundary, so its DataKit transports
# are replaced before importing the module. Provider behavior is asserted on
# the mocked send_email calls below.
oeds_core_module = types.ModuleType("oeds.core")
email_client_module = types.ModuleType("oeds.core.email_client")
email_graph_client_module = types.ModuleType("oeds.core.email_graph_client")
email_client_module.EmailClient = type("EmailClient", (), {})
email_graph_client_module.GraphEmailClient = type("GraphEmailClient", (), {})
sys.modules["oeds.core"] = oeds_core_module
sys.modules["oeds.core.email_client"] = email_client_module
sys.modules["oeds.core.email_graph_client"] = email_graph_client_module

EmailManager = importlib.import_module(
    "oeds.domain.utils.email.email_utils"
).EmailManager


class EmailManagerTestCase(unittest.TestCase):
    """Exercise registry-free and configured EmailManager sends."""

    @staticmethod
    def _create_manager(provider: str) -> EmailManager:
        manager = object.__new__(EmailManager)
        manager._provider = provider
        manager._connection = {}
        return manager

    def test_send_direct_email_through_logic_app(self) -> None:
        manager = self._create_manager("logicapp")
        email_client = MagicMock()
        manager._create_email_client = MagicMock(return_value=email_client)
        manager.get_email_registry = MagicMock(
            side_effect=AssertionError("registry must not be loaded")
        )
        manager._load_registry_map = MagicMock(
            side_effect=AssertionError("registry must not be loaded")
        )
        manager._load_email_template = MagicMock(
            side_effect=AssertionError("template must not be loaded")
        )
        body = "\n<html><body>Cost: $5</body></html>\n"

        manager.send_direct_email(
            recipients=(
                " first@example.org;second@example.org, first@example.org "
            ),
            subject="  Direct report  ",
            body=body,
            attachments=[
                {
                    "name": "report.txt",
                    "content": "hello",
                    "content_type": "text/plain",
                }
            ],
        )

        email_client.send_email.assert_called_once_with(
            recipients=[
                "first@example.org",
                "second@example.org",
                "first@example.org",
            ],
            subject="Direct report",
            body=body,
            attachments=[
                {
                    "Name": "report.txt",
                    "ContentBytes": base64.b64encode(b"hello").decode("ascii"),
                }
            ],
        )
        manager.get_email_registry.assert_not_called()
        manager._load_registry_map.assert_not_called()
        manager._load_email_template.assert_not_called()

    def test_send_direct_email_through_graph(self) -> None:
        manager = self._create_manager("graph")
        email_client = MagicMock()
        manager._create_email_client = MagicMock(return_value=email_client)
        body = "<html><body><strong>Ready</strong></body></html>"

        manager.send_direct_email(
            recipients=("first@example.org", "second@example.org"),
            subject="Status",
            body=body,
            attachments=[{"name": "status.csv", "content": b"state\nready\n"}],
        )

        email_client.send_email.assert_called_once_with(
            recipients=["first@example.org", "second@example.org"],
            subject="Status",
            body=body,
            body_format="html",
            attachments=[
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": "status.csv",
                    "contentType": "text/csv",
                    "contentBytes": base64.b64encode(b"state\nready\n").decode(
                        "ascii"
                    ),
                }
            ],
        )

    def test_send_direct_email_rejects_invalid_recipients(self) -> None:
        manager = self._create_manager("logicapp")

        invalid_recipients = (
            ("", ValueError),
            (" , ; ", ValueError),
            ([], ValueError),
            ([""], ValueError),
            (["valid@example.org", None], ValueError),
            (b"recipient@example.org", TypeError),
            (123, TypeError),
        )
        for recipients, expected_exception in invalid_recipients:
            with (
                self.subTest(recipients=recipients),
                self.assertRaises(expected_exception),
            ):
                manager.send_direct_email(
                    recipients=recipients,
                    subject="Subject",
                    body="<p>Body</p>",
                )

    def test_send_direct_email_rejects_invalid_subject_and_body(self) -> None:
        manager = self._create_manager("logicapp")

        for subject, expected_exception in (
            ("", ValueError),
            ("   ", ValueError),
            (None, TypeError),
        ):
            with (
                self.subTest(subject=subject),
                self.assertRaises(expected_exception),
            ):
                manager.send_direct_email(
                    recipients="recipient@example.org",
                    subject=subject,
                    body="<p>Body</p>",
                )

        for body, expected_exception in (
            ("", ValueError),
            ("   ", ValueError),
            (None, TypeError),
        ):
            with (
                self.subTest(body=body),
                self.assertRaises(expected_exception),
            ):
                manager.send_direct_email(
                    recipients="recipient@example.org",
                    subject="Subject",
                    body=body,
                )

    def test_send_direct_email_reuses_attachment_validation(self) -> None:
        manager = self._create_manager("graph")

        with self.assertRaisesRegex(ValueError, "Attachment content cannot be empty"):
            manager.send_direct_email(
                recipients="recipient@example.org",
                subject="Subject",
                body="<p>Body</p>",
                attachments=[{"name": "empty.txt", "content": ""}],
            )

        with self.assertRaisesRegex(ValueError, "must be smaller than 3 MiB"):
            manager.send_direct_email(
                recipients="recipient@example.org",
                subject="Subject",
                body="<p>Body</p>",
                attachments=[
                    {
                        "name": "large.bin",
                        "content": b"x" * (3 * 1024 * 1024),
                    }
                ],
            )

    def test_send_email_preserves_registry_workflow(self) -> None:
        manager = self._create_manager("logicapp")
        email_client = MagicMock()
        manager._create_email_client = MagicMock(return_value=email_client)
        manager.get_email_registry = MagicMock(
            return_value={
                "template": "template/status.html",
                "subject": "$environment status",
                "recipients": ["configured@example.org"],
            }
        )
        manager._load_email_template = MagicMock(
            return_value="<p>Hello $recipient</p>"
        )

        manager.send_email(
            template_ref="status",
            variables={"environment": "DEV", "recipient": "team"},
        )

        manager.get_email_registry.assert_called_once_with("status")
        manager._load_email_template.assert_called_once_with("template/status.html")
        email_client.send_email.assert_called_once_with(
            recipients=["configured@example.org"],
            subject="DEV status",
            body="<p>Hello team</p>",
            attachments=[],
        )


if __name__ == "__main__":
    unittest.main()
