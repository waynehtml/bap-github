"""Execute Databricks DDL rendered from DataForge schema definitions.

``SchemaDeploymentManager`` consumes the shared ``SchemaManager`` registry and
submits fully resolved table or view statements through Spark. Definition
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
    """Deploy configured schema objects through the active Spark session.

    The shared ``SchemaManager`` must be initialized first. Views are always
    created or replaced. Tables support plain creation, replacement, or
    idempotent ``IF NOT EXISTS`` creation.
    """

    _environment: ClassVar[str | None] = None

    def __init__(self, env: str) -> None:
        """Bind a caller-owned schema manager and an available Spark session."""
        self.env = self._normalize_env(env)
        self.schema_manager = schema_utils.SchemaManager.get_instance()
        if self.schema_manager.env != self.env:
            raise RuntimeError(
                "SchemaDeploymentManager environment "
                f"'{self.env}' does not match SchemaManager environment "
                f"'{self.schema_manager.env}'"
            )
        # Reuse the caller's session when possible to preserve its runtime context.
        self.spark = (
            SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        )

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
        self.spark.sql(resolved_sql)
