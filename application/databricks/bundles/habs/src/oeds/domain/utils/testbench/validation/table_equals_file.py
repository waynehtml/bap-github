"""Compare a Unity Catalog table with an expected Spark-readable dataset.

The comparison checks column names, Spark data types, row counts, and row
multiset equality. Duplicate records therefore remain significant.
"""

from __future__ import annotations

import logging
from typing import Any

from pyspark.sql import DataFrame, SparkSession

from oeds.domain.utils.testbench.validation.validator import Validator

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS = {"parquet", "csv", "delta"}


class TableEqualsFileValidator(Validator):
    """Compare a table and expected dataset with Spark multiset operations."""

    type = "table_equals_file"

    def validate(
        self,
        spark: SparkSession,
        config: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Raise when the actual table does not exactly match the expected file.

        Args:
            spark: Session used to read the table and expected dataset.
            config: Resolved verification configuration.
            context: Reserved execution metadata for validator extensions.

        Raises:
            ValueError: Required configuration is missing or malformed.
            AssertionError: Columns, types, counts, or records do not match.
        """
        verification_name = str(config.get("name") or self.type)
        actual_cfg = _require_mapping(config.get("actual"), "actual", verification_name)
        expected_cfg = _require_mapping(
            config.get("expected"), "expected", verification_name
        )

        actual_table = _require_string(
            actual_cfg.get("table"), "actual.table", verification_name
        )
        expected_path = _require_string(
            expected_cfg.get("path"), "expected.path", verification_name
        )
        expected_format = _normalize_expected_format(
            expected_cfg.get("format"), verification_name
        )

        logger.info("Starting table_equals_file validation")
        logger.info("Verification name: %s", verification_name)
        logger.info("Actual table name: %s", actual_table)
        logger.info("Expected file path: %s", expected_path)

        actual_df = spark.table(actual_table)
        if "filter" in actual_cfg:
            actual_filter = _require_string(
                actual_cfg.get("filter"), "actual.filter", verification_name
            )
            logger.debug(
                "Applying actual table filter for verification '%s': %s",
                verification_name,
                actual_filter,
            )
            actual_df = actual_df.filter(actual_filter)

        expected_options = expected_cfg.get("options", {})
        if expected_options is None:
            expected_options = {}
        if not isinstance(expected_options, dict):
            raise ValueError(
                f"Verification '{verification_name}' expected.options must be a "
                "JSON object."
            )

        expected_df = (
            spark.read.format(expected_format)
            .options(**expected_options)
            .load(expected_path)
        )

        compare_cfg = config.get("compare", {})
        if compare_cfg is None:
            compare_cfg = {}
        if not isinstance(compare_cfg, dict):
            raise ValueError(
                f"Verification '{verification_name}' compare must be a JSON object."
            )

        ignore_columns = compare_cfg.get("ignore_columns", [])
        ignore_columns = _normalize_ignore_columns(ignore_columns, verification_name)

        actual_df = _drop_existing_columns(actual_df, ignore_columns)
        expected_df = _drop_existing_columns(expected_df, ignore_columns)

        ordered_columns = _assert_matching_columns(
            actual_df, expected_df, verification_name
        )
        # Select one deterministic order before comparing corresponding Spark
        # data types and rows.
        actual_df = actual_df.select(*ordered_columns)
        expected_df = expected_df.select(*ordered_columns)
        _assert_matching_types(actual_df, expected_df, verification_name)

        actual_count = actual_df.count()
        expected_count = expected_df.count()
        logger.info("Actual count: %s", actual_count)
        logger.info("Expected count: %s", expected_count)

        # exceptAll preserves duplicates. Running it in both directions detects
        # missing and unexpected records without assuming a unique key.
        missing_rows = expected_df.exceptAll(actual_df)
        unexpected_rows = actual_df.exceptAll(expected_df)
        missing_count = missing_rows.count()
        unexpected_count = unexpected_rows.count()
        logger.info("Missing count: %s", missing_count)
        logger.info("Unexpected count: %s", unexpected_count)

        if missing_count != 0 or unexpected_count != 0:
            message = (
                "table_equals_file validation failed for verification "
                f"'{verification_name}': actual table '{actual_table}' does not "
                f"match expected file '{expected_path}'. "
                f"actual_count={actual_count}, expected_count={expected_count}, "
                f"missing_count={missing_count}, unexpected_count={unexpected_count}."
            )
            logger.error("Validation failed: %s", message)
            raise AssertionError(message)

        logger.info("Validation passed for verification '%s'", verification_name)


def _require_mapping(
    value: Any, field_name: str, verification_name: str
) -> dict[str, Any]:
    """Return a required verification object with a contextual error."""
    if not isinstance(value, dict):
        raise ValueError(
            f"Verification '{verification_name}' {field_name} must be a JSON object."
        )
    return value


def _require_string(value: Any, field_name: str, verification_name: str) -> str:
    """Return a required trimmed verification string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Verification '{verification_name}' {field_name} must be a "
            "non-empty string."
        )
    return value.strip()


def _normalize_expected_format(value: Any, verification_name: str) -> str:
    """Normalize and validate the expected dataset format."""
    expected_format = _require_string(
        value, "expected.format", verification_name
    ).lower()
    if expected_format not in _SUPPORTED_FORMATS:
        supported_formats = ", ".join(sorted(_SUPPORTED_FORMATS))
        raise ValueError(
            f"Verification '{verification_name}' expected.format "
            f"'{expected_format}' is not supported. "
            f"Supported formats: {supported_formats}."
        )
    return expected_format


def _normalize_ignore_columns(value: Any, verification_name: str) -> list[str]:
    """Normalize the optional list of columns excluded from comparison."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"Verification '{verification_name}' compare.ignore_columns must "
            "be a list of strings."
        )

    ignore_columns: list[str] = []
    for index, column_name in enumerate(value):
        if not isinstance(column_name, str) or not column_name.strip():
            raise ValueError(
                f"Verification '{verification_name}' "
                f"compare.ignore_columns[{index}] must be a non-empty string."
            )
        ignore_columns.append(column_name.strip())
    return ignore_columns


def _drop_existing_columns(df: DataFrame, ignore_columns: list[str]) -> DataFrame:
    """Drop configured columns that exist and ignore absent optional names."""
    columns_to_drop = [
        column_name for column_name in ignore_columns if column_name in df.columns
    ]
    if not columns_to_drop:
        return df
    logger.debug("Dropping ignored columns: %s", columns_to_drop)
    return df.drop(*columns_to_drop)


def _assert_matching_columns(
    actual_df: DataFrame, expected_df: DataFrame, verification_name: str
) -> list[str]:
    """Require identical column names and return their deterministic order."""
    actual_columns = set(actual_df.columns)
    expected_columns = set(expected_df.columns)
    if actual_columns != expected_columns:
        missing_from_actual = sorted(expected_columns - actual_columns)
        unexpected_in_actual = sorted(actual_columns - expected_columns)
        raise AssertionError(
            "table_equals_file validation failed for verification "
            f"'{verification_name}': "
            f"actual and expected columns do not match. "
            f"missing_from_actual={missing_from_actual}, "
            f"unexpected_in_actual={unexpected_in_actual}."
        )
    return sorted(actual_columns)


def _assert_matching_types(
    actual_df: DataFrame, expected_df: DataFrame, verification_name: str
) -> None:
    """Require matching Spark data types for every aligned column."""
    actual_types = _schema_types_by_column(actual_df)
    expected_types = _schema_types_by_column(expected_df)
    mismatches = [
        {
            "column": column_name,
            "actual_type": actual_types[column_name],
            "expected_type": expected_types[column_name],
        }
        for column_name in sorted(actual_types)
        if actual_types[column_name] != expected_types[column_name]
    ]
    if mismatches:
        raise AssertionError(
            "table_equals_file validation failed for verification "
            f"'{verification_name}': actual and expected column data types do "
            f"not match. mismatches={mismatches}."
        )


def _schema_types_by_column(df: DataFrame) -> dict[str, str]:
    """Map each DataFrame column to Spark's stable simple type string."""
    return {field.name: field.dataType.simpleString() for field in df.schema.fields}
