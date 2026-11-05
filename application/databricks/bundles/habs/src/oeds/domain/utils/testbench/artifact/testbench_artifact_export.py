"""Export Spark SQL results as reusable Testbench Parquet artifacts.

Artifacts are restricted to the case root's ``fixtures`` and ``expected``
directories. They can capture only a result schema or the complete result data.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from pyspark.sql import SparkSession

from oeds.domain.utils.testbench.environment import ResourceUtils

logger = logging.getLogger(__name__)

_SUPPORTED_EXPORT_MODES = frozenset({"schema", "data"})
_SUPPORTED_ARTIFACT_ROOTS = frozenset({"fixtures", "expected"})


@dataclass(frozen=True)
class TableArtifactExport:
    """Describe one completed Testbench table-artifact export.

    Attributes:
        output_path: Case-relative artifact directory written by the exporter.
        export_mode: Normalized ``schema`` or ``data`` export mode.
        columns: Ordered Spark result column names.
    """

    output_path: str
    export_mode: str
    columns: tuple[str, ...]


class TableArtifactExporter:
    """Build setup fixtures and expected datasets from configured Spark SQL.

    The exporter validates output paths before executing SQL so generated data
    cannot escape the Testbench-managed artifact directories.
    """

    def __init__(
        self,
        *,
        case_root: str,
        spark: SparkSession | None = None,
    ) -> None:
        """Initialize an exporter for one Testbench case root.

        Args:
            case_root: Absolute Unity Catalog Volume path containing Testbench
                cases and artifacts.
            spark: Optional Spark session. The active or default session is used
                when omitted.
        """
        # Reuse ResourceUtils path validation so lifecycle and authoring tools
        # interpret the Testbench case root consistently.
        self._resource_utils = ResourceUtils(case_root=case_root)
        self.spark = spark or (
            SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        )

    def export_configured_artifact(
        self,
        *,
        test_config: Mapping[str, Any],
        artifact_name: str,
        overwrite: bool = False,
    ) -> TableArtifactExport:
        """Export one named artifact from a resolved Testbench case.

        Args:
            test_config: Resolved Testbench case containing ``artifacts``.
            artifact_name: Unique configured artifact name to export.
            overwrite: Whether existing output may be replaced.

        Returns:
            Metadata describing the completed export.

        Raises:
            TypeError: If the case or an artifact has an invalid type.
            ValueError: If the artifact list or selected artifact is invalid.
        """
        artifacts = self._artifact_configs(test_config)
        normalized_artifact_name = self._required_text(
            artifact_name,
            "artifact_name",
        )
        # Artifact names are unique after normalization, so a single match is
        # sufficient and avoids exposing list selection to callers.
        matching_artifacts = [
            artifact
            for artifact in artifacts
            if artifact["name"] == normalized_artifact_name
        ]
        if not matching_artifacts:
            raise ValueError(
                f"Testbench artifact '{normalized_artifact_name}' is not configured"
            )

        artifact = matching_artifacts[0]
        logger.info("Exporting configured Testbench artifact '%s'", artifact["name"])
        return self.export_sql(
            sql=artifact["sql"],
            output_path=artifact["output_path"],
            export_mode=artifact["export_mode"],
            overwrite=overwrite,
        )

    def export_sql(
        self,
        *,
        sql: str,
        output_path: str,
        export_mode: str = "data",
        overwrite: bool = False,
    ) -> TableArtifactExport:
        """Export a Spark SQL result to a Testbench Parquet directory.

        ``schema`` mode writes a zero-row DataFrame so the artifact retains the
        result's Spark schema without copying records. ``data`` mode writes the
        complete SQL result and its schema. SQL is passed directly to
        :meth:`SparkSession.sql` and may therefore have side effects.

        Args:
            sql: Spark SQL statement whose result will be exported.
            output_path: Relative artifact directory beneath ``case_root``.
            export_mode: ``schema`` or ``data``.
            overwrite: Whether existing output may be replaced.

        Returns:
            Metadata describing the completed export.

        Raises:
            TypeError: If an argument has an invalid type.
            ValueError: If an argument is blank, unsupported, or outside the
                managed Testbench artifact directories.

        Spark SQL and write failures propagate unchanged.
        """
        normalized_sql = self._required_text(sql, "sql")
        normalized_output_path = self._artifact_path(output_path)
        normalized_export_mode = self._export_mode(export_mode)
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a bool")

        resolved_output_path = self._resource_utils.resolve_test_path(
            normalized_output_path
        )
        spark_output_path = self._resource_utils.spark_source_path(
            resolved_output_path
        )
        dataframe = self.spark.sql(normalized_sql)
        # Limiting to zero rows preserves Spark's resolved schema without
        # materializing fixture or expected records.
        if normalized_export_mode == "schema":
            dataframe = dataframe.limit(0)

        write_mode = "overwrite" if overwrite else "errorifexists"
        logger.info(
            "Writing Testbench artifact to '%s' with mode=%s",
            resolved_output_path,
            normalized_export_mode,
        )
        dataframe.write.mode(write_mode).format("parquet").save(spark_output_path)

        result = TableArtifactExport(
            output_path=normalized_output_path,
            export_mode=normalized_export_mode,
            columns=tuple(dataframe.columns),
        )
        logger.info(
            "Completed Testbench table artifact export with %s column(s)",
            len(result.columns),
        )
        return result

    @classmethod
    def _artifact_configs(
        cls,
        test_config: Mapping[str, Any],
    ) -> list[dict[str, str]]:
        """Validate and normalize all artifact definitions in a case.

        Args:
            test_config: Resolved case containing an ``artifacts`` list.

        Returns:
            Normalized artifact dictionaries with unique names.
        """
        if not isinstance(test_config, Mapping):
            raise TypeError("test_config must be a mapping")
        raw_artifacts = test_config.get("artifacts")
        if not isinstance(raw_artifacts, list) or not raw_artifacts:
            raise ValueError(
                "Testbench case field 'artifacts' must be a non-empty list"
            )

        artifacts: list[dict[str, str]] = []
        artifact_names: set[str] = set()
        for index, raw_artifact in enumerate(raw_artifacts):
            if not isinstance(raw_artifact, Mapping):
                raise TypeError(f"artifacts[{index}] must be an object")
            name = cls._required_text(
                raw_artifact.get("name"),
                f"artifacts[{index}].name",
            )
            if name in artifact_names:
                raise ValueError(f"Duplicate Testbench artifact name '{name}'")
            artifact_names.add(name)
            artifacts.append(
                {
                    "name": name,
                    "sql": cls._required_text(
                        raw_artifact.get("sql"),
                        f"artifacts[{index}].sql",
                    ),
                    "output_path": cls._artifact_path(
                        raw_artifact.get("output_path")
                    ),
                    "export_mode": cls._export_mode(
                        raw_artifact.get("export_mode", "data"),
                        label=f"artifacts[{index}].export_mode",
                    ),
                }
            )
        return artifacts

    @staticmethod
    def _required_text(value: Any, name: str) -> str:
        """Return a trimmed required string or raise a field-specific error."""
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError(f"{name} is required")
        return normalized_value

    @classmethod
    def _artifact_path(cls, output_path: Any) -> str:
        """Require a safe path beneath a managed artifact directory.

        Absolute paths, URI components, traversal, and platform-specific
        separators are rejected before the path reaches Spark.
        """
        normalized_output_path = cls._required_text(output_path, "output_path")
        relative_path = PurePosixPath(normalized_output_path)
        parsed_path = urlsplit(normalized_output_path)
        if (
            parsed_path.scheme
            or parsed_path.netloc
            or parsed_path.query
            or parsed_path.fragment
            or relative_path.is_absolute()
            or ".." in relative_path.parts
            or "\\" in normalized_output_path
            or "\x00" in normalized_output_path
        ):
            raise ValueError(
                "output_path must be a relative POSIX path beneath case_root"
            )
        if (
            not relative_path.parts
            or relative_path.parts[0] not in _SUPPORTED_ARTIFACT_ROOTS
        ):
            supported_roots = ", ".join(
                f"{root}/" for root in sorted(_SUPPORTED_ARTIFACT_ROOTS)
            )
            raise ValueError(f"output_path must be beneath: {supported_roots}")
        if len(relative_path.parts) < 2:
            raise ValueError("output_path must include an artifact directory name")
        return relative_path.as_posix()

    @classmethod
    def _export_mode(cls, export_mode: Any, label: str = "export_mode") -> str:
        """Normalize and validate an artifact export mode."""
        normalized_export_mode = cls._required_text(export_mode, label).lower()
        if normalized_export_mode not in _SUPPORTED_EXPORT_MODES:
            supported_modes = ", ".join(sorted(_SUPPORTED_EXPORT_MODES))
            raise ValueError(f"{label} must be one of: {supported_modes}")
        return normalized_export_mode
