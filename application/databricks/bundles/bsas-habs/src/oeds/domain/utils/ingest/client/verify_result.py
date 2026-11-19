from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class VerifyResult:
    """Structured ingestion verification result."""

    status: Literal["SUCCESS", "TIMEOUT"]
    expected: list[dict[str, Any]]
    matched: list[dict[str, Any]]
    unmatched: list[dict[str, Any]]

    @property
    def is_success(self) -> bool:
        return self.status == "SUCCESS"
