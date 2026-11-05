"""Apply direct Unity Catalog grants from the shared permission registry.

The registry in ``oeds.config.permission`` defines grant intent:
- ``groups[env]`` maps permission aliases to account group names.
- ``permissions`` selects schema references and their read/write groups.

Every selected permission entry is processed regardless of its catalog.

ConfigManager loads environment-specific resources before shared resources.
SchemaManager resolves logical catalog names and object references. Read grants
apply only to configured tables or views; writes are table-only. This module
does not grant catalog/schema usage privileges, revoke grants, or scan view
dependencies.
"""

# Malformed permission configuration retains ValueError for API compatibility.
# ruff: noqa: TRY004

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any, ClassVar

from oeds.domain.utils.config import config_utils
from oeds.domain.utils.schema import schema_utils
from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)

_READ_PRIVILEGE = "SELECT"
_WRITE_PRIVILEGE = "MODIFY"


class PermissionManager:
    """Load permission configuration and grant access to configured objects.

    This manager owns its configuration validation and grant execution. It uses
    ConfigManager and SchemaManager directly. Read grants target configured
    objects without resolving view dependencies.
    """

    _CONFIG_FILE = "default.json"
    _CONFIG_PACKAGE = "oeds.config.permission"
    _environment: ClassVar[str | None] = None

    def __init__(self, env: str) -> None:
        """Bind an instance to initialized configuration, schema, and Spark services.

        Args:
            env: Environment name, normalized to lowercase after trimming.

        ConfigManager and SchemaManager must already be initialized. The config
        environment must match ``env`` so grants use the intended group aliases
        and resource overrides. Reuse the active Spark session or create one.
        Construction does not load the permission registry or execute grants.

        Raises:
            ValueError: If ``env`` is not a non-empty string.
            RuntimeError: If a required manager is uninitialized or the config
                environment does not match.
        """
        self.env = self._normalize_env(env)
        self._config_manager = config_utils.ConfigManager.get_instance(
            self._CONFIG_PACKAGE
        )
        if self._config_manager.environment != self.env:
            raise RuntimeError(
                "PermissionManager environment "
                f"'{self.env}' does not match ConfigManager environment "
                f"'{self._config_manager.environment}'"
            )
        self.schema_manager = schema_utils.SchemaManager.get_instance()
        self.spark = (
            SparkSession.getActiveSession() or SparkSession.builder.getOrCreate()
        )

        logger.info(
            "Initialized PermissionManager for env '%s' using config package '%s'",
            self.env,
            self._CONFIG_PACKAGE,
        )

    @classmethod
    def initialize(cls, env: str) -> type[PermissionManager]:
        """Record the environment for subsequent ``get_instance()`` calls.

        Returns the class to support ``initialize(env).get_instance()``. This
        does not initialize ConfigManager or SchemaManager, create a Spark
        session, or alter existing instances.
        """
        normalized_env = cls._normalize_env(env)
        cls._environment = normalized_env
        logger.info(
            "Configured PermissionManager for env '%s'",
            normalized_env,
        )
        return cls

    @classmethod
    def get_instance(cls) -> PermissionManager:
        """Create a fresh manager using the environment set by ``initialize``.

        Instances are not cached or shared. Raises RuntimeError when this class
        has not been initialized; constructor failures also propagate.
        """
        environment = cls._environment
        if environment is None:
            raise RuntimeError(
                "PermissionManager is not initialized. "
                "Call PermissionManager.initialize(env) first."
            )

        return cls(environment)

    @staticmethod
    def _normalize_env(env: str) -> str:
        """Validate and normalize an environment name."""
        if not isinstance(env, str) or not env.strip():
            raise ValueError("env is required")

        return env.strip().lower()

    def get_registry(self, config_file: str | None = None) -> dict[str, Any]:
        """Read raw permission JSON without normalizing its grant entries.

        Args:
            config_file: Packaged filename; None selects ``default.json``.
                ConfigManager prefers ``<env>/<filename>`` and falls back to
                the shared filename under ``oeds.config.permission``.

        Returns:
            The decoded registry. Each call reloads the resource; selecting an
            alternate file does not change the default for subsequent calls.

        Raises:
            ValueError: If the filename is blank or the JSON root is not an
                object. JSON decoding and configuration-loading errors propagate.
        """
        if config_file is not None and not str(config_file).strip():
            raise ValueError("config_file cannot be empty when provided")

        selected_config_file = (
            self._CONFIG_FILE if config_file is None else str(config_file).strip()
        )
        logger.info(
            "Loading permission config '%s' from package '%s'",
            selected_config_file,
            self._CONFIG_PACKAGE,
        )

        registry_text = self._config_manager.load_config_resource(selected_config_file)
        registry = json.loads(registry_text)
        if not isinstance(registry, dict):
            raise ValueError("Permission registry must be a JSON object.")

        logger.debug("Loaded permission registry keys: %s", sorted(registry.keys()))
        return registry

    def _resolve_groups(
        self, aliases: Any, available_groups: Mapping[str, str]
    ) -> list[str]:
        """Map a read/write alias list through the active environment's groups.

        None or an empty list means no grants of that kind. Preserve configured
        order and reject unknown aliases before any grant statements execute.
        """
        if aliases in (None, []):
            return []
        if not isinstance(aliases, list):
            raise ValueError("Permission groups must be defined as a list.")

        resolved_groups: list[str] = []
        for alias in aliases:
            alias_name = str(alias).strip()
            if not alias_name:
                raise ValueError(
                    "Permission groups cannot contain an empty group alias."
                )
            if alias_name not in available_groups:
                raise ValueError(f"Unknown permission group '{alias_name}'.")
            resolved_groups.append(available_groups[alias_name])

        logger.debug(
            "Resolved permission groups: aliases=%s, groups=%s",
            aliases,
            resolved_groups,
        )
        return resolved_groups

    def _load_config(self, config_file: str | None = None) -> dict[str, Any]:
        """Validate and normalize the packaged config into one predictable structure.

        Returns a mapping with:
        - ``permissions``: a ``ref -> {read: [groups], write: [groups]}`` mapping
          containing full account group names for the current environment.

        Both an object and a list of permission objects are accepted for config
        compatibility. Missing read/write lists become empty lists. Validate
        all entries before selecting a target or executing grants; invalid
        entries elsewhere in the registry can therefore block a targeted run.
        Configured permission entries determine the objects to process.
        """
        registry = self.get_registry(config_file=config_file)

        groups = registry.get("groups")
        if not isinstance(groups, Mapping):
            raise ValueError("Permission registry must define groups as an object.")

        env_groups = groups.get(self.env)
        if not isinstance(env_groups, Mapping) or not env_groups:
            raise ValueError(
                f"Permission registry must define groups for env '{self.env}'."
            )

        normalized_groups: dict[str, str] = {}
        for alias, full_name in env_groups.items():
            if not alias or not str(alias).strip():
                raise ValueError("Permission group aliases must be non-empty strings.")
            if not full_name or not str(full_name).strip():
                raise ValueError(
                    f"Permission group '{alias}' must map to a non-empty full name."
                )
            normalized_groups[str(alias).strip()] = str(full_name).strip()

        raw_permissions = registry.get("permissions")
        permission_entries: dict[str, Any] = {}
        if isinstance(raw_permissions, Mapping):
            permission_entries = dict(raw_permissions)
        elif isinstance(raw_permissions, list) and raw_permissions:
            for index, entry in enumerate(raw_permissions):
                if not isinstance(entry, Mapping):
                    raise ValueError(
                        f"Permission registry entry at index {index} "
                        "must be an object mapping refs to grants."
                    )
                for schema_ref, permission in entry.items():
                    schema_ref_name = str(schema_ref).strip()
                    if schema_ref_name in permission_entries:
                        raise ValueError(
                            f"Permission ref '{schema_ref_name}' "
                            "is defined more than once."
                        )
                    permission_entries[schema_ref_name] = permission
        else:
            raise ValueError(
                "Permission registry must define permissions "
                "as a non-empty object or list of objects."
            )

        normalized_permissions: dict[str, dict[str, list[str]]] = {}
        for schema_ref, permission in permission_entries.items():
            if not schema_ref or not str(schema_ref).strip():
                raise ValueError("Permission refs must be non-empty strings.")
            if not isinstance(permission, Mapping):
                raise ValueError(
                    f"Permission config for ref '{schema_ref}' must be an object."
                )

            normalized_permissions[str(schema_ref).strip()] = {
                "read": self._resolve_groups(
                    permission.get("read", []), normalized_groups
                ),
                "write": self._resolve_groups(
                    permission.get("write", []), normalized_groups
                ),
            }

        logger.debug(
            "Loaded permission config summary for env '%s': "
            "%s group(s), %s permission ref(s)",
            self.env,
            len(normalized_groups),
            len(normalized_permissions),
        )
        logger.debug("Resolved groups for env '%s': %s", self.env, normalized_groups)
        logger.debug(
            "Resolved permissions for env '%s': %s", self.env, normalized_permissions
        )

        return {"permissions": normalized_permissions}

    def _resolve_full_table_name(self, schema_ref: str) -> str:
        """Resolve a registry reference to ``catalog.schema.object``.

        The reference names a configured table or view, not a SQL schema.
        SchemaManager owns physical naming; this lookup does not check that
        the object exists in Unity Catalog.
        """
        schema_ref_value = str(schema_ref).strip()
        if not schema_ref_value:
            raise ValueError("schema_ref cannot be empty.")

        full_table_name = self.schema_manager.find(schema_ref_value).full_name
        logger.debug(
            "Resolved schema ref '%s' via schema manager to '%s'",
            schema_ref_value,
            full_table_name,
        )
        return full_table_name

    def _grant_permissions(
        self,
        *,
        privilege: str,
        object_names: list[str],
        group_names: list[str],
        statements: list[str],
        execute: bool,
    ) -> None:
        """Log and collect each object/group grant, optionally executing it.

        ``statements`` is the caller-owned list used for execution summaries.
        Empty group lists produce no SQL. Spark errors propagate immediately;
        earlier successful grants are not rolled back.
        """
        for object_name in object_names:
            for group_name in group_names:
                sql = f"GRANT {privilege} ON {object_name} TO `{group_name}`"
                logger.info("Prepared permission SQL for '%s': %s", object_name, sql)
                statements.append(sql)
                if execute:
                    logger.debug("Executing SQL: %s", sql)
                    self.spark.sql(sql)

    def apply_permissions(
        self,
        schema: str | None = None,
        execute: bool = True,
        *,
        config_file: str | None = None,
    ) -> None:
        """Apply every selected permission entry regardless of its catalog.

        Args:
            schema: One configured object reference, or None for all entries.
                Despite its name, this is not a SQL schema name.
            execute: True executes grants; False logs the same SQL for preview.
                Preview still loads configuration and checks live object type
                for write grants, but does not verify read-target existence.
            config_file: Alternate packaged registry for this call only; None
                selects ``default.json`` with environment-first resolution.

        The ``permissions`` entries define grant scope; ``schema`` can narrow
        that scope to one configured reference. Object names still
        resolve through SchemaManager's catalog bindings. Read groups receive
        SELECT on the object itself; write groups receive MODIFY only when the
        target is not reported as a view.

        Returns:
            None. Prepared SQL and applied references are logged.

        Raises:
            ValueError: For invalid config, an empty/unknown selected reference,
                or write groups configured for a view. Resource, schema lookup,
                metadata, and Spark execution errors propagate unchanged.

        Grants are additive and not transactional. A later failure, including
        view-write validation, can leave earlier grants applied. Previously
        granted permissions are never revoked by this method.
        """
        config = self._load_config(config_file=config_file)
        statements: list[str] = []
        applied_refs: list[str] = []

        selected_permissions = config["permissions"]
        if schema is not None:
            selected_schema = str(schema).strip()
            if not selected_schema:
                raise ValueError("schema cannot be empty.")
            if selected_schema not in config["permissions"]:
                raise ValueError(
                    f"Permission ref '{selected_schema}' is not defined in the config."
                )
            selected_permissions = {
                selected_schema: config["permissions"][selected_schema]
            }

        logger.info(
            "Applying permissions for env '%s' across %s configured ref(s)",
            self.env,
            len(selected_permissions),
        )

        for schema_ref, permission in selected_permissions.items():
            full_table_name = self._resolve_full_table_name(schema_ref)

            logger.debug(
                "Resolved schema ref '%s' to full object name '%s'",
                schema_ref,
                full_table_name,
            )

            logger.info(
                "Applying permissions for ref '%s' to object '%s'",
                schema_ref,
                full_table_name,
            )
            logger.debug(
                "Resolved permission entry for ref '%s': "
                "read_groups=%s, write_groups=%s",
                schema_ref,
                permission["read"],
                permission["write"],
            )

            self._grant_permissions(
                privilege=_READ_PRIVILEGE,
                object_names=[full_table_name],
                group_names=permission["read"],
                statements=statements,
                execute=execute,
            )

            if permission["write"]:
                table_info = self.spark.catalog.getTable(full_table_name)
                if table_info.tableType == "VIEW":
                    raise ValueError(
                        f"Permission ref '{schema_ref}' "
                        f"resolves to view '{full_table_name}', "
                        "but write permissions are only supported for tables."
                    )

                logger.debug(
                    "Applying write permissions for ref '%s' to table '%s'",
                    schema_ref,
                    full_table_name,
                )
                self._grant_permissions(
                    privilege=_WRITE_PRIVILEGE,
                    object_names=[full_table_name],
                    group_names=permission["write"],
                    statements=statements,
                    execute=execute,
                )

            applied_refs.append(schema_ref)

        logger.info(
            "Finished applying permissions for env '%s': %s applied, %s statement(s)",
            self.env,
            len(applied_refs),
            len(statements),
        )
        logger.debug("Applied refs for env '%s': %s", self.env, applied_refs)
        logger.debug(
            "Generated GRANT statements for env '%s': %s", self.env, statements
        )
