"""Reference data helpers."""

from __future__ import annotations

import logging
from datetime import date
from typing import ClassVar

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger(__name__)


class ReferenceManager:
    """Load reference data from one reference catalog."""

    _reference_catalog: ClassVar[str | None] = None

    def __init__(self, reference_catalog: str) -> None:
        self.reference_catalog = self._normalize_reference_catalog(reference_catalog)

    @classmethod
    def initialize(cls, reference_catalog: str) -> type[ReferenceManager]:
        """Configure the catalog and return the class for chained creation."""
        normalized_catalog = cls._normalize_reference_catalog(reference_catalog)
        cls._reference_catalog = normalized_catalog
        logger.info(
            "Configured ReferenceManager for catalog '%s'",
            normalized_catalog,
        )
        return cls

    @classmethod
    def get_instance(cls) -> ReferenceManager:
        """Create a caller-owned manager from the configured catalog."""
        reference_catalog = cls._reference_catalog
        if reference_catalog is None:
            raise RuntimeError(
                "ReferenceManager is not initialized. "
                "Call ReferenceManager.initialize(reference_catalog) first."
            )

        return cls(reference_catalog)

    @staticmethod
    def _normalize_reference_catalog(reference_catalog: str) -> str:
        if not isinstance(reference_catalog, str) or not reference_catalog.strip():
            raise ValueError("reference_catalog is required")

        return reference_catalog.strip()

    def get_holidays(
        self,
        holiday_group: str,
        exact: bool = False,
    ) -> list[date]:
        """Return holiday dates for one reference holiday group.

        By default, matches when inGroup contains holiday_group case-insensitively.
        Set exact=True to require case-insensitive equality.
        """
        if not holiday_group or not str(holiday_group).strip():
            raise ValueError("holiday_group is required")

        holiday_group = str(holiday_group).strip()
        holiday_group_sql = holiday_group.replace("'", "''")
        group_filter = (
            f"LOWER(TRIM(holiday_view.inGroup)) = LOWER('{holiday_group_sql}')"
            if exact
            else f"INSTR(LOWER(holiday_view.inGroup), LOWER('{holiday_group_sql}')) > 0"
        )
        spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()

        logger.info(
            "Loading holiday dates from reference catalog '%s' for group '%s' using %s match",
            self.reference_catalog,
            holiday_group,
            "exact" if exact else "contains",
        )

        itm_holiday_view = f"{self.reference_catalog}.standardized_db.vw_itm_holiday_calendar"

        holidays_df = spark.sql(
            f"""
            SELECT
                holiday_view.date
            FROM {itm_holiday_view} holiday_view
            WHERE {group_filter}
            """
        )

        holiday_dates = [
            date.fromisoformat(str(row["date"]))
            for row in holidays_df.collect()
            if row["date"] is not None
        ]

        logger.info(
            "Loaded %s holiday date(s) from reference catalog '%s'",
            len(holiday_dates),
            self.reference_catalog,
        )
        return holiday_dates

    def get_leis(self) -> DataFrame:
        """Return all LEI organizations as a lazy Spark DataFrame.

        Loads every column and row from the configured reference catalog's
        ``curated_db.tbl_itm_lei_organizations`` table.
        """
        spark = SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()

        # The schema and table are stable contracts; only the catalog varies.
        lei_organizations_table = (
            f"{self.reference_catalog}.curated_db.tbl_itm_lei_organizations"
        )
        return spark.table(lei_organizations_table)
