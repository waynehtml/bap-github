"""Define the contract implemented by Testbench verification types."""

from __future__ import annotations

from typing import Any

from pyspark.sql import SparkSession


class Validator:
    """Base interface for one named verification implementation.

    Subclasses declare a stable ``type`` value and raise when verification
    fails. Successful validation returns without producing a result model.
    """

    # ValidationRunner uses this identifier when registering concrete types.
    type: str

    def validate(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Validate one resolved verification definition.

        Args:
            spark: Session owned by the validation layer.
            config: Resolved verification dictionary from the case.
            context: Optional lifecycle metadata for diagnostic use.

        Raises:
            NotImplementedError: The concrete validator did not implement the
                contract.
        """
        raise NotImplementedError
