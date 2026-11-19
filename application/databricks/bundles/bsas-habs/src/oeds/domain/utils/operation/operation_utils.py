"""Record and query successful dataset operations in the configured Delta table."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType

import oeds.core.uc_utils as uc_utils
import oeds.domain.utils.schema.schema_utils as schema_utils

logger = logging.getLogger(__name__)

_SCHEMA_REF = "tbl_operation_status"
_SUPPORTED_LAYERS = frozenset({"STANDARDIZATION", "CURATION", "INTEGRATION"})
_DEPENDENCY_FILTER_NAMES = frozenset(
    {
        "dataset",
        "layer",
        "batch_id",
        "job_run_id",
        "job_name",
        "job_id",
        "job_trigger_type",
        "completed_at",
    }
)
_BIGINT_MIN = -(2**63)
_BIGINT_MAX = 2**63 - 1


@dataclass(frozen=True)
class RegexFilter:
    """Mark a text filter as a case-insensitive Spark regular expression."""

    pattern: str

    def __post_init__(self) -> None:
        if not isinstance(self.pattern, str):
            raise TypeError("pattern must be a string")
        if not self.pattern.strip():
            raise ValueError("pattern cannot be blank")


@dataclass(frozen=True)
class TimeFilter:
    """Select a calendar day, an open time bound, or a closed time range."""

    on: date | None = None
    start: date | datetime | None = None
    end: date | datetime | None = None

    def __post_init__(self) -> None:
        if self.on is not None:
            if isinstance(self.on, datetime) or not isinstance(self.on, date):
                raise TypeError("on must be a date")
            if self.start is not None or self.end is not None:
                raise ValueError("on cannot be combined with start or end")
            _end_boundary(self.on)
            return

        if self.start is None and self.end is None:
            raise ValueError("provide on, start, or end")

        for name, value in (("start", self.start), ("end", self.end)):
            if value is not None and not isinstance(value, (date, datetime)):
                raise TypeError(f"{name} must be a date or datetime")

        if self.end is not None and not isinstance(self.end, datetime):
            _end_boundary(self.end)

        if self.start is None or self.end is None:
            return

        start_is_aware = _is_aware_datetime(self.start)
        end_is_aware = _is_aware_datetime(self.end)
        if start_is_aware != end_is_aware:
            raise ValueError("start and end must use compatible timezone awareness")

        normalized_start = _start_boundary(self.start)
        normalized_end, end_is_exclusive = _end_boundary(self.end)
        if end_is_exclusive:
            is_reversed = normalized_start >= normalized_end
        else:
            is_reversed = normalized_start > normalized_end
        if is_reversed:
            raise ValueError("start must be before or equal to end")


@dataclass(frozen=True)
class OperationStatusRecord:
    """Represent one successful operation-status table record."""

    dataset: str
    layer: str
    batch_id: str
    job_name: str | None
    job_id: int | None
    job_run_id: int | None
    job_trigger_type: str | None
    job_context: str | None
    completed_at: datetime


def _dependency_criteria(criteria: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and copy criteria for one operation-status dependency.

    Dependency criteria reuse ``find_latest_status`` filters. Every dependency
    requires non-null ``dataset`` and ``layer`` values so it has a stable
    identity for lookup and logging.
    """
    if not isinstance(criteria, Mapping):
        raise TypeError("criteria must be a mapping")

    # Isolate the dependency from later changes to the caller's mapping.
    normalized_criteria = dict(criteria)
    if not normalized_criteria:
        raise ValueError("criteria cannot be empty")
    if not all(isinstance(name, str) for name in normalized_criteria):
        raise TypeError("criteria keys must be strings")

    # Keep dependency lookups aligned with the supported latest-record filters.
    unknown_names = set(normalized_criteria) - _DEPENDENCY_FILTER_NAMES
    if unknown_names:
        unknown_text = ", ".join(sorted(unknown_names))
        raise ValueError(f"unsupported dependency criteria: {unknown_text}")

    # These fields identify the upstream dataset in task logs and are therefore
    # required even when another criterion could independently locate a record.
    missing_identity_names = [
        name
        for name in ("dataset", "layer")
        if normalized_criteria.get(name) is None
    ]
    if missing_identity_names:
        missing_text = ", ".join(missing_identity_names)
        raise ValueError(
            f"dependency criteria must include non-null values for: {missing_text}"
        )

    return normalized_criteria


def _is_aware_datetime(value: date | datetime) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


def _start_boundary(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _end_boundary(value: date | datetime) -> tuple[datetime, bool]:
    if isinstance(value, datetime):
        return value, False
    try:
        following_day = value + timedelta(days=1)
    except OverflowError as exc:
        raise ValueError("date boundary must be earlier than date.max") from exc
    return datetime.combine(following_day, time.min), True


def _required_text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")

    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"{name} is required")

    return normalized_value


def _optional_text(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string or None")

    return value.strip() or None


def _enum_value(
    value: str,
    *,
    name: str,
    supported_values: frozenset[str],
) -> str:
    normalized_value = _required_text(value, name).upper()
    if normalized_value not in supported_values:
        supported_text = ", ".join(sorted(supported_values))
        raise ValueError(f"{name} must be one of: {supported_text}")

    return normalized_value


def _optional_job_identifier(
    value: int | str | None,
    *,
    name: str,
) -> int | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError(f"{name} must be an int or numeric string")

    normalized_value = value.strip() if isinstance(value, str) else value
    if normalized_value == "":
        return None

    try:
        identifier = int(normalized_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if not _BIGINT_MIN <= identifier <= _BIGINT_MAX:
        raise ValueError(f"{name} must fit in a signed BIGINT")

    return identifier


class OperationStatusManager:
    """Record and query successful operations for one Delta table."""

    def __init__(self, table_ref: str = _SCHEMA_REF) -> None:
        """Resolve a schema table reference and initialize the manager."""
        self.table_ref = _required_text(table_ref, "table_ref")
        schema_registry = schema_utils.SchemaManager.get_instance().find(
            self.table_ref
        )
        if not schema_registry.is_table:
            raise ValueError(
                f"Schema reference '{self.table_ref}' must identify a table"
            )

        self.status_table_name = schema_registry.full_name
        self.spark = (
            SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        )
        logger.info(
            "Initialized OperationStatusManager using table '%s'",
            self.status_table_name,
        )

    def record_status(
        self,
        *,
        dataset: str,
        layer: str,
        batch_id: str,
        job_run_id: int | str | None = None,
        job_name: str | None = None,
        job_id: int | str | None = None,
        job_trigger_type: str | None = None,
        job_context: Any = None,
    ) -> None:
        """Append one successful dataset-operation record to the Delta table.

        The method assigns ``completed_at`` with Spark's current timestamp
        before appending the row; it does not rely on a table-column default.

        Args:
            dataset: Unique logical dataset name.
            layer: Standardization, curation, or integration layer.
            batch_id: Dataset-specific logical batch identifier.
            job_run_id: Optional Databricks job run identifier.
            job_name: Optional Databricks job name.
            job_id: Optional Databricks job identifier.
            job_trigger_type: Optional Databricks ``job.trigger.type`` value.
            job_context: Optional JSON-compatible diagnostic context.

        Raises:
            TypeError: If an argument has an invalid type or ``job_context``
                cannot be serialized to JSON.
            ValueError: If a required value is blank, an enum or identifier is
                invalid, JSON contains a non-finite number, or the configured
                schema is missing ``completed_at``.

        Spark and Delta write failures propagate to the caller unchanged.
        """
        normalized_dataset = _required_text(dataset, "dataset")
        normalized_layer = _enum_value(
            layer,
            name="layer",
            supported_values=_SUPPORTED_LAYERS,
        )
        normalized_batch_id = _required_text(batch_id, "batch_id")
        normalized_job_name = _optional_text(job_name, "job_name")
        normalized_job_id = _optional_job_identifier(
            job_id,
            name="job_id",
        )
        normalized_job_run_id = _optional_job_identifier(
            job_run_id,
            name="job_run_id",
        )
        normalized_job_trigger_type = _optional_text(
            job_trigger_type,
            "job_trigger_type",
        )
        serialized_job_context = (
            None
            if job_context is None
            else json.dumps(
                job_context,
                separators=(",", ":"),
                sort_keys=True,
                allow_nan=False,
            )
        )

        table_schema = uc_utils.extract_table_schema(self.status_table_name)
        if "completed_at" not in table_schema.fieldNames():
            raise ValueError(
                f"Table '{self.status_table_name}' must define completed_at"
            )

        input_schema = StructType(
            [field for field in table_schema.fields if field.name != "completed_at"]
        )
        record = {
            "dataset": normalized_dataset,
            "layer": normalized_layer,
            "batch_id": normalized_batch_id,
            "job_name": normalized_job_name,
            "job_id": normalized_job_id,
            "job_run_id": normalized_job_run_id,
            "job_trigger_type": normalized_job_trigger_type,
            "job_context": serialized_job_context,
        }

        status_dataframe = self.spark.createDataFrame([record], schema=input_schema)
        status_dataframe = status_dataframe.withColumn(
            "completed_at",
            F.current_timestamp(),
        ).select(*table_schema.fieldNames())

        logger.info(
            "Appending successful operation to '%s': dataset=%s layer=%s "
            "batch_id=%s job_run_id=%s",
            self.status_table_name,
            normalized_dataset,
            normalized_layer,
            normalized_batch_id,
            normalized_job_run_id,
        )
        status_dataframe.write.format("delta").mode("append").saveAsTable(
            self.status_table_name
        )

    def find_statuses(
        self,
        *,
        latest_only: bool = True,
        dataset: str | RegexFilter | None = None,
        layer: str | RegexFilter | None = None,
        batch_id: str | RegexFilter | None = None,
        job_run_id: int | str | None = None,
        job_name: str | RegexFilter | None = None,
        job_id: int | str | None = None,
        job_trigger_type: str | RegexFilter | None = None,
        completed_at: TimeFilter | None = None,
    ) -> DataFrame:
        """Return successful operation records matching the supplied filters.

        Plain text values use exact equality. :class:`RegexFilter` values use
        case-insensitive Spark ``rlike`` matching. Numeric job identifiers use
        equality, and :class:`TimeFilter` selects a day or timestamp bounds.

        All field filters are optional and are combined with logical AND. By
        default, the lazy result contains only the newest match. Set
        ``latest_only=False`` to return every match ordered by ``completed_at``
        newest first. Every table column is preserved. Spark and table-read
        failures propagate unchanged.
        """
        if not isinstance(latest_only, bool):
            raise TypeError("latest_only must be a bool")

        text_filters: tuple[
            tuple[str, str | RegexFilter | None, frozenset[str] | None], ...
        ] = (
            ("dataset", dataset, None),
            ("layer", layer, _SUPPORTED_LAYERS),
            ("batch_id", batch_id, None),
            ("job_name", job_name, None),
            ("job_trigger_type", job_trigger_type, None),
        )

        normalized_text_filters: list[tuple[str, str | RegexFilter]] = []
        for column_name, value, supported_values in text_filters:
            if value is None:
                continue
            if isinstance(value, RegexFilter):
                normalized_text_filters.append((column_name, value))
                continue
            if not isinstance(value, str):
                raise TypeError(
                    f"{column_name} must be a string, RegexFilter, or None"
                )
            normalized_value = (
                _required_text(value, column_name)
                if supported_values is None
                else _enum_value(
                    value,
                    name=column_name,
                    supported_values=supported_values,
                )
            )
            normalized_text_filters.append((column_name, normalized_value))

        normalized_job_id = _optional_job_identifier(job_id, name="job_id")
        normalized_job_run_id = _optional_job_identifier(
            job_run_id,
            name="job_run_id",
        )
        if completed_at is not None and not isinstance(completed_at, TimeFilter):
            raise TypeError("completed_at must be a TimeFilter or None")

        filter_count = (
            len(normalized_text_filters)
            + int(normalized_job_id is not None)
            + int(normalized_job_run_id is not None)
            + int(completed_at is not None)
        )
        logger.info(
            "Querying successful operations from '%s' with %s filters "
            "(latest_only=%s)",
            self.status_table_name,
            filter_count,
            latest_only,
        )
        status_dataframe = self.spark.table(self.status_table_name)

        for column_name, value in normalized_text_filters:
            column = F.col(column_name)
            condition = (
                column.rlike(f"(?i:{value.pattern})")
                if isinstance(value, RegexFilter)
                else column == value
            )
            status_dataframe = status_dataframe.where(condition)

        for column_name, value in (
            ("job_id", normalized_job_id),
            ("job_run_id", normalized_job_run_id),
        ):
            if value is not None:
                status_dataframe = status_dataframe.where(
                    F.col(column_name) == value
                )

        if completed_at is not None:
            completed_column = F.col("completed_at")
            if completed_at.on is not None:
                day_start = _start_boundary(completed_at.on)
                day_end, _ = _end_boundary(completed_at.on)
                status_dataframe = status_dataframe.where(
                    (completed_column >= F.lit(day_start))
                    & (completed_column < F.lit(day_end))
                )
            else:
                if completed_at.start is not None:
                    status_dataframe = status_dataframe.where(
                        completed_column
                        >= F.lit(_start_boundary(completed_at.start))
                    )
                if completed_at.end is not None:
                    end_boundary, end_is_exclusive = _end_boundary(
                        completed_at.end
                    )
                    end_condition = (
                        completed_column < F.lit(end_boundary)
                        if end_is_exclusive
                        else completed_column <= F.lit(end_boundary)
                    )
                    status_dataframe = status_dataframe.where(end_condition)

        if latest_only:
            return status_dataframe.orderBy(
                F.col("completed_at").desc(),
                F.col("job_run_id").desc_nulls_last(),
            ).limit(1)

        return status_dataframe.orderBy(F.col("completed_at").desc())

    def find_latest_status(
        self,
        *,
        dataset: str | RegexFilter | None = None,
        layer: str | RegexFilter | None = None,
        batch_id: str | RegexFilter | None = None,
        job_run_id: int | str | None = None,
        job_name: str | RegexFilter | None = None,
        job_id: int | str | None = None,
        job_trigger_type: str | RegexFilter | None = None,
        completed_at: TimeFilter | None = None,
    ) -> OperationStatusRecord | None:
        """Return the newest matching successful operation, or ``None``.

        Unlike :meth:`find_statuses`, this convenience method is eager. It
        delegates all filtering and ordering to that method, then executes a
        Spark action to retrieve the first row. Validation, table-read, regex,
        and Spark failures propagate unchanged.
        """
        latest_status = self.find_statuses(
            latest_only=True,
            dataset=dataset,
            layer=layer,
            batch_id=batch_id,
            job_run_id=job_run_id,
            job_name=job_name,
            job_id=job_id,
            job_trigger_type=job_trigger_type,
            completed_at=completed_at,
        ).first()
        if latest_status is None:
            return None

        return OperationStatusRecord(
            dataset=latest_status["dataset"],
            layer=latest_status["layer"],
            batch_id=latest_status["batch_id"],
            job_name=latest_status["job_name"],
            job_id=latest_status["job_id"],
            job_run_id=latest_status["job_run_id"],
            job_trigger_type=latest_status["job_trigger_type"],
            job_context=latest_status["job_context"],
            completed_at=latest_status["completed_at"],
        )

    def resolve_dependency(
        self,
        criteria: Mapping[str, Any],
    ) -> OperationStatusRecord | None:
        """Return the newest successful record matching dependency criteria."""
        normalized_criteria = _dependency_criteria(criteria)
        return self.find_latest_status(**normalized_criteria)


__all__ = [
    "OperationStatusManager",
    "OperationStatusRecord",
    "RegexFilter",
    "TimeFilter",
]
