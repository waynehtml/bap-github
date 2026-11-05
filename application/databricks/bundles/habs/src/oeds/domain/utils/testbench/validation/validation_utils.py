"""Dispatch configured Testbench verifications to registered validators.

This module owns Spark-session acquisition for validation. Orchestration code
can therefore construct :class:`ValidationRunner` without carrying Spark as a
lifecycle dependency.
"""

from __future__ import annotations

import logging
from typing import Any

from pyspark.sql import SparkSession

from oeds.domain.utils.testbench.validation.table_equals_file import (
    TableEqualsFileValidator,
)
from oeds.domain.utils.testbench.validation.validator import Validator

logger = logging.getLogger(__name__)


class ValidationRunner:
    """Resolve validation types and run each enabled verification in order."""

    def __init__(self, spark: SparkSession | None = None):
        """Initialize validation with an injected or active Spark session.

        Args:
            spark: Optional session for compatibility and isolated tests. When
                omitted, use the active session or create one through Spark's
                standard builder.
        """
        # Spark ownership stays at the validation boundary; callers may inject
        # a session for tests, while production callers use the active runtime.
        self.spark = spark
        if self.spark is None:
            self.spark = (
                SparkSession.getActiveSession()
                or SparkSession.builder.getOrCreate()
            )
        self.validators: dict[str, Validator] = {
            "table_equals_file": TableEqualsFileValidator(),
        }

    def run(
        self, test_config: dict[str, Any], context: dict[str, Any] | None = None
    ) -> None:
        """Run enabled verifications and let validator failures bubble up.

        Args:
            test_config: Fully resolved Testbench case dictionary.
            context: Optional execution metadata passed unchanged to validators.

        Raises:
            ValueError: A validation definition is malformed or names an
                unsupported validator type.
        """
        if not isinstance(test_config, dict):
            raise ValueError("test_config must be a JSON object.")

        validate_cfg = test_config.get("validate", {})
        if validate_cfg is None:
            validate_cfg = {}
        if not isinstance(validate_cfg, dict):
            raise ValueError("validate must be a JSON object.")

        if validate_cfg.get("enabled") is False:
            logger.info("Validation skipped because validate.enabled is false.")
            return

        verifications = validate_cfg.get("verifications", [])
        if verifications is None:
            verifications = []
        if not isinstance(verifications, list):
            raise ValueError("validate.verifications must be a list.")

        for index, verification in enumerate(verifications):
            if not isinstance(verification, dict):
                raise ValueError(
                    f"validate.verifications[{index}] must be a JSON object."
                )

            verification_name = str(
                verification.get("name") or f"verification_{index + 1}"
            )
            if verification.get("enabled") is False:
                logger.info("Skipping disabled verification '%s'.", verification_name)
                continue

            validator_type = verification.get("type")
            if not isinstance(validator_type, str) or not validator_type.strip():
                raise ValueError(
                    f"Verification '{verification_name}' must define a non-empty type."
                )

            validator_type = validator_type.strip()
            # The registry keeps orchestration independent from each concrete
            # validator and provides one clear extension point for new types.
            validator = self.validators.get(validator_type)
            if validator is None:
                raise ValueError(
                    f"Unknown validation type '{validator_type}' for verification "
                    f"'{verification_name}'."
                )

            logger.info(
                "Running verification '%s' with validator type '%s'.",
                verification_name,
                validator_type,
            )
            validator.validate(self.spark, verification, context=context)
