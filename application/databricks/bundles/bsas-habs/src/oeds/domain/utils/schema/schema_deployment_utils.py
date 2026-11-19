"""Execute Databricks DDL rendered from DataForge schema definitions.

``SchemaDeploymentManager`` consumes the shared ``SchemaManager`` registry and
submits resolved DDL through Spark or a SQL warehouse for materialized views. Definition
discovery and SQL-body rendering remain in ``schema_utils``; this module owns
only deployment-time statement assembly and execution.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from pyspark.sql import SparkSession

import oeds.domain.utils.schema.schema_utils as schema_utils

logger = logging.getLogger(__name__)


class SchemaDeploymentManager:
    """Deploy schema objects through Spark or an explicit SQL warehouse.

    The shared ``SchemaManager`` must be initialized first. Views are always
    created or replaced. Tables support plain creation, replacement, or
    idempotent ``IF NOT EXISTS`` creation.
    """

    _environment: ClassVar[str | None] = None

    def __init__(self, env: str) -> None:
        """Bind a caller-owned schema manager without acquiring Spark."""
        self.env = self._normalize_env(env)
        self.schema_manager = schema_utils.SchemaManager.get_instance()
        if self.schema_manager.env != self.env:
            raise RuntimeError(
                "SchemaDeploymentManager environment "
                f"'{self.env}' does not match SchemaManager environment "
                f"'{self.schema_manager.env}'"
            )
        self.spark: SparkSession | None = None

        logger.info(
            "Initialized SchemaDeploymentManager for env '%s'",
            self.schema_manager.env,
        )

    @classmethod
    def initialize(cls, env: str) -> type[SchemaDeploymentManager]:
        """Configure the environment and return the class for chained creation."""
        normalized_env = cls._normalize_env(env)
        cls._environment = normalized_env
        logger.info(
            "Configured SchemaDeploymentManager for env '%s'",
            normalized_env,
        )
        return cls

    @classmethod
    def get_instance(cls) -> SchemaDeploymentManager:
        """Create a caller-owned deployment manager for the configured environment."""
        environment = cls._environment
        if environment is None:
            raise RuntimeError(
                "SchemaDeploymentManager is not initialized. "
                "Call SchemaDeploymentManager.initialize(env) first."
            )

        return cls(environment)

    @staticmethod
    def _normalize_env(env: str) -> str:
        """Validate and normalize an environment name."""
        if not isinstance(env, str) or not env.strip():
            raise ValueError("env is required")

        return env.strip().lower()

    def create_view(self, schema_ref: str) -> None:
        """Create or replace the view identified by ``schema_ref``.

        Placeholder resolution and SQL validation are delegated to the shared
        schema manager before the final statement is submitted to Spark.

        Raises:
            RuntimeError: If ``schema_ref`` identifies a non-view object.
            ValueError: If the reference or one of its dependencies is unknown.
            TypeError: If the view does not define usable SQL text.
        """
        schema_registry = self.schema_manager.find(schema_ref)
        if not schema_registry.is_view:
            raise RuntimeError(f"Schema object '{schema_registry.name}' is not a view")

        sql_body = self.schema_manager.render_view_sql(schema_ref)
        resolved_sql = (
            f"CREATE OR REPLACE VIEW {schema_registry.full_name} AS\n{sql_body.strip()}"
        )
        logger.info(
            "Creating view '%s' for ref '%s'", schema_registry.full_name, schema_ref
        )
        logger.debug(
            "Resolved view SQL for '%s': %s", schema_registry.name, resolved_sql
        )
        if self.spark is None:
            self.spark = (
                SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
            )
        self.spark.sql(resolved_sql)

    def create_table(
        self,
        schema_ref: str,
        *,
        if_not_exists: bool = False,
        replace: bool = False,
    ) -> None:
        """Create the Unity Catalog table identified by ``schema_ref``.

        ``replace`` selects ``CREATE OR REPLACE TABLE`` and ``if_not_exists``
        selects ``CREATE TABLE IF NOT EXISTS``. With neither option, a standard
        ``CREATE TABLE`` statement is used.

        Raises:
            RuntimeError: If ``schema_ref`` identifies a non-table object.
            ValueError: If both creation modes are requested or SQL is invalid.
            TypeError: If the table lacks required SQL or schema metadata.
        """
        schema_registry = self.schema_manager.find(schema_ref)
        if not schema_registry.is_table:
            raise RuntimeError(f"Schema object '{schema_registry.name}' is not a table")

        if replace and if_not_exists:
            raise ValueError("replace and if_not_exists cannot both be True")

        # Choose the mutually exclusive DDL mode before appending the SQL body.
        create_prefix = f"CREATE TABLE {schema_registry.full_name}"
        if replace:
            create_prefix = f"CREATE OR REPLACE TABLE {schema_registry.full_name}"
        elif if_not_exists:
            create_prefix = f"CREATE TABLE IF NOT EXISTS {schema_registry.full_name}"

        sql_body = self.schema_manager.render_table_sql(schema_ref)
        resolved_sql = f"{create_prefix}\n{sql_body.strip()}"
        logger.info(
            "Creating table '%s' for ref '%s'", schema_registry.full_name, schema_ref
        )
        logger.debug(
            "Resolved table SQL for '%s': %s", schema_registry.name, resolved_sql
        )
        if self.spark is None:
            self.spark = (
                SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
            )
        self.spark.sql(resolved_sql)

    def create_materialized_view(
        self,
        schema_ref: str,
        warehouse_id: str | None = None,
        *,
        if_not_exists: bool = False,
        replace: bool = False,
        timeout_seconds: int = 1800,
    ) -> None:
        """Create a configured materialized view with resolved SQL references.

        Requires kind ``mv``. With neither creation flag, use plain CREATE;
        ``replace`` and ``if_not_exists`` are mutually exclusive. Supply a
        warehouse ID to use execute_ddl, or omit it to require an active Spark
        session on supported serverless compute. The timeout applies only to
        warehouse execution. Execution failures propagate; no fallback occurs.
        """
        registry = self.schema_manager.find(schema_ref)
        if not registry.is_materialized_view:
            raise RuntimeError(
                f"Schema object '{registry.name}' is not a materialized view"
            )
        if not isinstance(if_not_exists, bool) or not isinstance(replace, bool):
            raise TypeError("if_not_exists and replace must be booleans")
        if replace and if_not_exists:
            raise ValueError("replace and if_not_exists cannot both be True")
        prefix = "CREATE MATERIALIZED VIEW"
        if replace:
            prefix = "CREATE OR REPLACE MATERIALIZED VIEW"
        elif if_not_exists:
            prefix = "CREATE MATERIALIZED VIEW IF NOT EXISTS"
        sql_body = self.schema_manager.render_view_sql(schema_ref)
        sql = f"{prefix} {registry.full_name} AS\n{sql_body.strip()}"
        logger.info("Creating materialized view '%s'", registry.full_name)
        self._execute_materialized_view_ddl(sql, warehouse_id, timeout_seconds)

    def refresh_materialized_view(
        self,
        schema_ref: str,
        warehouse_id: str | None = None,
        *,
        full: bool = False,
        timeout_seconds: int = 1800,
    ) -> None:
        """Synchronously refresh an existing configured materialized view.

        Requires kind ``mv``. ``full=True`` forces full recomputation; otherwise
        Databricks selects the refresh strategy. Use the same compute type as
        creation: an explicit warehouse, or active supported serverless Spark.
        The timeout applies only to warehouse execution. Errors propagate.
        """
        registry = self.schema_manager.find(schema_ref)
        if not registry.is_materialized_view:
            raise RuntimeError(
                f"Schema object '{registry.name}' is not a materialized view"
            )
        if not isinstance(full, bool):
            raise TypeError("full must be a boolean")
        sql = f"REFRESH MATERIALIZED VIEW {registry.full_name}"
        if full:
            sql += " FULL"
        sql += " SYNC"
        logger.info("Refreshing materialized view '%s'", registry.full_name)
        self._execute_materialized_view_ddl(sql, warehouse_id, timeout_seconds)

    def _execute_materialized_view_ddl(
        self, sql: str, warehouse_id: str | None, timeout_seconds: int
    ) -> None:
        """Route materialized-view DDL without implicitly selecting compute."""
        if warehouse_id is not None:
            if not isinstance(warehouse_id, str):
                raise TypeError("warehouse_id must be a string")
            if not warehouse_id.strip():
                raise ValueError("warehouse_id must not be blank")
            from oeds.domain.utils.databricks.databricks_utils import execute_ddl

            execute_ddl(sql, warehouse_id, timeout_seconds=timeout_seconds)
            return
        spark = SparkSession.getActiveSession()
        if spark is None:
            raise RuntimeError(
                "Materialized-view execution requires an active Spark session "
                "on supported serverless compute, or an explicit warehouse_id"
            )
        spark.sql(sql)
