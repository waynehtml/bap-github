"""Discover and render Databricks table and view definitions.

Schema definitions live in modules under ``oeds.config.schema``. Each module
exports a ``DEFINITION`` dictionary and its module name becomes the logical
reference used by callers. :class:`SchemaManager` discovers references during
initialization, then imports and validates only the definition requested by a
caller. It qualifies catalog names and renders SQL without executing it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Any, ClassVar

from pyspark.sql.types import LongType, StructField, StructType

import oeds.domain.utils.config.config_utils as config_utils

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PACKAGE = "oeds.config.schema"

# Match logical schema references embedded in SQL, such as ``{tbl_customer}``.
_PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class SchemaRegistry:
    """Resolved definition for one runtime-qualified table or view.

    ``catalog``, ``database``, and ``name`` identify the Unity Catalog object.
    ``kind`` distinguishes tables, views, and materialized views (``mv``).
    ``sql`` contains the configured
    DDL body, while ``schema`` optionally supplies Spark column metadata used
    when rendering a table's ``{schema}`` placeholder.
    """

    catalog: str
    database: str
    name: str
    kind: str
    sql: str | None = None
    schema: StructType | None = None

    @property
    def full_name(self) -> str:
        """Return the three-part Unity Catalog object name."""
        return f"{self.catalog}.{self.database}.{self.name}"

    @property
    def short_name(self) -> str:
        """Return the two-part schema and object name."""
        return f"{self.database}.{self.name}"

    @property
    def is_table(self) -> bool:
        """Return whether this registry describes a table."""
        return self.kind == "table"

    @property
    def is_view(self) -> bool:
        """Return whether this registry describes a view."""
        return self.kind == "view"

    @property
    def is_materialized_view(self) -> bool:
        """Return whether this registry describes a materialized view."""
        return self.kind == "mv"


class SchemaManager:
    """Resolve caller-requested schema definitions for one environment."""

    _configuration: ClassVar[
        tuple[str, config_utils.ModuleMap, str, Mapping[str, str]] | None
    ] = None

    def __init__(
        self,
        env: str,
        module_map: config_utils.ModuleMap,
        *,
        catalog_mapping: Mapping[str, str] | None = None,
        default_catalog: str,
    ) -> None:
        """Create a caller-owned manager from one configuration snapshot.

        ``default_catalog`` must be a non-empty physical catalog name and is
        used only when a definition omits its ``catalog`` key.
        """
        self.env = self._normalize_env(env)
        self._default_catalog = self._normalize_default_catalog(default_catalog)
        if not isinstance(module_map, config_utils.ModuleMap):
            raise TypeError("module_map must be a ModuleMap")
        self._module_map = module_map
        self._catalog_mapping = self._normalize_catalog_mapping(catalog_mapping)

    @classmethod
    def initialize(
        cls,
        env: str,
        *,
        catalog_mapping: Mapping[str, str] | None = None,
        default_catalog: str,
    ) -> type[SchemaManager]:
        """Build the module map used by future caller-owned managers.

        Every successful call atomically replaces the configuration snapshot.
        Definitions without a catalog use the required physical default catalog
        unchanged, without mapping or adding an environment prefix.
        Catalog mappings bind logical definition catalogs to complete physical
        names without an environment prefix. Unmapped catalogs retain the
        ``{env}_{catalog}`` convention. The mapping is copied; existing managers
        retain their snapshot after reinitialization.

        Args:
            env: Environment used for configuration discovery and fallback names.
            catalog_mapping: Optional logical-to-physical catalog mapping. Keys
                and values must be strings. Surrounding whitespace is stripped;
                catalog names are not validated.
            default_catalog: Required physical catalog for definitions that omit
                ``catalog``. Surrounding whitespace is stripped.

        Returns:
            The manager class so callers may chain :meth:`get_instance`.

        Raises:
            ValueError: If ``env`` is empty or is not a string, or the default
                catalog is blank.
            TypeError: If the default catalog is not a string, or the mapping
                or its keys or values have invalid types.
        """
        normalized_env = cls._normalize_env(env)
        normalized_default_catalog = cls._normalize_default_catalog(default_catalog)
        normalized_catalog_mapping = cls._normalize_catalog_mapping(catalog_mapping)
        config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )
        if config_manager.environment != normalized_env:
            raise RuntimeError(
                "SchemaManager environment "
                f"'{normalized_env}' does not match ConfigManager environment "
                f"'{config_manager.environment}'"
            )
        module_map = config_manager.discover_module_map()
        cls._configuration = (
            normalized_env,
            module_map,
            normalized_default_catalog,
            normalized_catalog_mapping,
        )
        logger.info(
            "Configured SchemaManager for env '%s' with %s schema reference(s)",
            normalized_env,
            len(module_map),
        )
        return cls

    @classmethod
    def get_instance(cls) -> SchemaManager:
        """Create a caller-owned manager from the configured snapshot.

        Raises:
            RuntimeError: If the manager has not been initialized or the
                ConfigManager environment has changed.
        """
        configuration = cls._configuration
        if configuration is None:
            raise RuntimeError(
                "SchemaManager is not initialized. "
                "Call SchemaManager.initialize(env, default_catalog=...) first."
            )

        environment, module_map, default_catalog, catalog_mapping = configuration
        config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )
        if config_manager.environment != environment:
            raise RuntimeError(
                "SchemaManager environment "
                f"'{environment}' does not match ConfigManager environment "
                f"'{config_manager.environment}'"
            )

        return cls(
            environment,
            module_map,
            catalog_mapping=catalog_mapping,
            default_catalog=default_catalog,
        )

    @staticmethod
    def _normalize_env(env: str) -> str:
        """Validate and normalize an environment name for catalog qualification."""
        if not isinstance(env, str) or not env.strip():
            raise ValueError("env is required")

        return env.strip().lower()

    @staticmethod
    def _normalize_default_catalog(default_catalog: str) -> str:
        """Validate the physical catalog used by definitions without a catalog."""
        if not isinstance(default_catalog, str):
            raise TypeError("default_catalog must be a string")
        if not default_catalog.strip():
            raise ValueError("default_catalog must be a non-empty string")
        return default_catalog.strip()

    @staticmethod
    def _normalize_catalog_mapping(
        catalog_mapping: Mapping[str, str] | None,
    ) -> Mapping[str, str]:
        """Trim and copy string catalog bindings into an immutable snapshot."""
        if catalog_mapping is None:
            return MappingProxyType({})
        if not isinstance(catalog_mapping, Mapping):
            raise TypeError("catalog_mapping must be a mapping")

        normalized_mapping: dict[str, str] = {}
        for logical_catalog, physical_catalog in catalog_mapping.items():
            if not isinstance(logical_catalog, str) or not isinstance(
                physical_catalog, str
            ):
                raise TypeError("catalog_mapping keys and values must be strings")
            normalized_mapping[logical_catalog.strip()] = physical_catalog.strip()

        return MappingProxyType(normalized_mapping)

    def resolve_catalog(self, catalog: str) -> str:
        """Resolve a logical catalog using this manager's runtime bindings.

        Mapped values are complete catalog names and are never prefixed.
        Unmapped catalogs use ``{env}_{catalog}``. Schema references use these
        bindings to resolve their physical catalog names.

        Raises:
            ValueError: If ``catalog`` is not a non-empty string.
        """
        if not isinstance(catalog, str) or not catalog.strip():
            raise ValueError("catalog must be a non-empty string")
        catalog = catalog.strip()
        return self._catalog_mapping.get(catalog, f"{self.env}_{catalog}")

    def get_module_map(self) -> dict[str, str]:
        """Return a printable copy of discovered refs and full module names."""
        return dict(self._module_map.items())

    def find(self, name: str) -> SchemaRegistry:
        """Import and resolve one registry by logical module reference.

        An omitted ``catalog`` uses the configured physical default. Explicit
        catalog values use normal resolution and must be non-empty strings.

        Raises:
            ValueError: If ``name`` is empty or no matching definition exists.
        """
        logger.debug("Looking up schema registry '%s'", name)
        if not name or not str(name).strip():
            raise ValueError("name is required")

        module_name = str(name).strip()
        if module_name not in self._module_map:
            raise ValueError(f"'{module_name}' is not defined")

        module = self._module_map.import_module(module_name)
        full_module_name = module.__name__
        definition = self._load_definition(module)

        object_name = self._get_required_field(
            definition, "name", full_module_name
        )
        object_kind = self._get_required_field(
            definition, "kind", full_module_name
        )
        catalog = (
            self.resolve_catalog(definition["catalog"])
            if "catalog" in definition
            else self._default_catalog
        )
        database = self._get_required_field(
            definition, "database", full_module_name
        )

        schema_registry = SchemaRegistry(
            kind=object_kind,
            catalog=catalog,
            database=database,
            name=object_name,
            sql=definition.get("sql"),
            schema=definition.get("schema"),
        )
        logger.debug(
            "Resolved %s module '%s' for schema '%s'",
            object_kind,
            full_module_name,
            object_name,
        )
        return schema_registry

    def render_view_sql(self, schema_ref: str) -> str:
        """Render view SQL by resolving logical schema placeholders.

        Each ``{reference}`` must identify another discovered schema object and
        is replaced with that object's runtime-qualified full name. Hardcoded
        catalog names in SQL are not rewritten.

        Raises:
            ValueError: If a referenced schema definition does not exist.
            TypeError: If the view does not provide non-empty SQL text.
        """
        schema_registry = self.find(schema_ref)
        if not isinstance(schema_registry.sql, str) or not schema_registry.sql.strip():
            raise TypeError(
                f"View '{schema_registry.name}' must define non-empty SQL text in 'sql'"
            )

        sql_body = schema_registry.sql
        # De-duplicate placeholders while retaining their first-seen SQL order.
        placeholders = list(dict.fromkeys(_PLACEHOLDER_PATTERN.findall(sql_body)))
        for placeholder in placeholders:
            full_name = self.find(placeholder).full_name
            logger.debug(
                "Resolved placeholder '%s' to '%s' while rendering view '%s'",
                placeholder,
                full_name,
                schema_registry.name,
            )
            sql_body = sql_body.replace(f"{{{placeholder}}}", full_name)

        return sql_body

    def render_table_sql(self, schema_ref: str) -> str:
        """Render table SQL, expanding the optional ``{schema}`` placeholder.

        Table SQL accepts no logical object placeholders. When ``{schema}`` is
        present, its Spark ``StructType`` is converted to Databricks column DDL,
        including supported identity, default, nullability, and comment metadata.

        Raises:
            ValueError: If SQL contains an unsupported placeholder.
            TypeError: If SQL or required Spark schema metadata is missing.
        """
        schema_registry = self.find(schema_ref)
        if not isinstance(schema_registry.sql, str) or not schema_registry.sql.strip():
            raise TypeError(
                f"Table '{schema_registry.name}' must define non-empty SQL text in 'sql'"
            )

        sql_body = schema_registry.sql
        # De-duplicate placeholders while retaining their first-seen SQL order.
        placeholders = list(dict.fromkeys(_PLACEHOLDER_PATTERN.findall(sql_body)))
        for placeholder in placeholders:
            if placeholder != "schema":
                raise ValueError(
                    f"Table '{schema_registry.name}' uses unsupported placeholder '{placeholder}' in 'sql'"
                )

            if schema_registry.schema is None:
                raise TypeError(
                    f"Table '{schema_registry.name}' uses '{{schema}}' in 'sql' but does not define 'schema'"
                )

            schema_sql = self._render_table_columns(schema_registry)
            logger.debug(
                "Resolved placeholder '%s' while rendering table '%s'",
                placeholder,
                schema_registry.name,
            )
            sql_body = sql_body.replace(f"{{{placeholder}}}", schema_sql)

        return sql_body

    def _load_definition(self, module: ModuleType) -> dict[str, Any]:
        """Load the ``DEFINITION`` dictionary exported by one module."""
        definition = getattr(module, "DEFINITION", None)
        if isinstance(definition, dict):
            return definition

        raise ValueError(
            f"Unable to resolve schema definition from '{module.__name__}'. "
            "Expected a dict variable named 'DEFINITION'."
        )

    def _get_required_field(
        self, definition: dict[str, Any], key: str, module_name: str
    ) -> Any:
        """Return a required definition value or identify the invalid module."""
        if key in definition:
            return definition[key]

        raise ValueError(f"Definition '{module_name}' must provide '{key}'")

    def _render_table_columns(self, schema_registry: SchemaRegistry) -> str:
        """Render column DDL from a registry's Spark ``StructType``.

        Identity fields use a dedicated renderer because Databricks identity
        syntax replaces the normal type/nullability/default construction path.
        """
        if schema_registry.schema is None:
            raise TypeError(
                f"Table '{schema_registry.name}' must define 'schema' to render column SQL"
            )

        identity_field = self._find_identity_field(schema_registry)
        col_defs: list[str] = []
        for field in schema_registry.schema.fields:
            # Identity columns cannot share the normal default-expression path.
            if identity_field and field.name == identity_field.name:
                col_defs.append(self._render_identity_column(field, schema_registry))
                continue

            nullability = "" if field.nullable else " NOT NULL"
            base_sql = (
                f"    `{field.name}` {field.dataType.simpleString()}{nullability}"
            )
            base_sql = self._append_default_clause(base_sql, field)
            col_defs.append(self._append_comment_clause(base_sql, field))

        return ",\n".join(col_defs)

    def _find_identity_field(
        self, schema_registry: SchemaRegistry
    ) -> StructField | None:
        """Validate and return the sole identity field, when configured.

        Raises:
            ValueError: If more than one field declares identity metadata.
            TypeError: If the identity metadata is not a dictionary.
        """
        if schema_registry.schema is None:
            return None

        identity_fields = [
            field
            for field in schema_registry.schema.fields
            if "identity" in (field.metadata or {})
        ]
        if not identity_fields:
            return None

        if len(identity_fields) > 1:
            field_names = ", ".join(field.name for field in identity_fields)
            raise ValueError(
                f"Table '{schema_registry.name}' defines multiple identity columns: {field_names}"
            )

        field = identity_fields[0]
        identity_config = field.metadata.get("identity")
        if not isinstance(identity_config, dict):
            raise TypeError(
                f"Table '{schema_registry.name}' identity metadata for column '{field.name}' must be a dict"
            )

        return field

    def _render_identity_column(
        self, field: StructField, schema_registry: SchemaRegistry
    ) -> str:
        """Validate identity metadata and render one Databricks column clause."""
        identity_config = field.metadata.get("identity")
        if "default" in (field.metadata or {}):
            raise ValueError(
                f"Table '{schema_registry.name}' identity column '{field.name}' "
                "must not define default metadata"
            )
        if not isinstance(field.dataType, LongType):
            raise TypeError(
                f"Table '{schema_registry.name}' identity column '{field.name}' must use LongType/BIGINT"
            )

        if field.nullable:
            raise ValueError(
                f"Table '{schema_registry.name}' identity column '{field.name}' must be non-nullable"
            )

        start = identity_config.get("start", 1)
        always = identity_config.get("always", True)

        if not isinstance(start, int):
            raise TypeError(
                f"Table '{schema_registry.name}' identity column '{field.name}' metadata 'start' must be an int"
            )

        if not isinstance(always, bool):
            raise TypeError(
                f"Table '{schema_registry.name}' identity column '{field.name}' metadata 'always' must be a bool"
            )

        mode = "ALWAYS" if always else "BY DEFAULT"
        base_sql = (
            f"    `{field.name}` BIGINT NOT NULL "
            f"GENERATED {mode} AS IDENTITY (START WITH {start} INCREMENT BY 1)"
        )
        return self._append_comment_clause(base_sql, field)

    def _append_default_clause(self, base_sql: str, field: StructField) -> str:
        """Append a validated SQL expression from ``default`` metadata."""
        default_expression = (field.metadata or {}).get("default")
        if default_expression is None:
            return base_sql

        if not isinstance(default_expression, str):
            raise TypeError(
                f"Column '{field.name}' metadata 'default' must be a string"
            )

        normalized_expression = default_expression.strip()
        if not normalized_expression:
            raise ValueError(
                f"Column '{field.name}' metadata 'default' must not be empty"
            )

        return f"{base_sql} DEFAULT {normalized_expression}"

    def _append_comment_clause(self, base_sql: str, field: StructField) -> str:
        """Append an escaped SQL comment from ``comment`` metadata."""
        comment = (field.metadata or {}).get("comment")
        if comment is None:
            return base_sql

        if not isinstance(comment, str):
            raise TypeError(
                f"Column '{field.name}' metadata 'comment' must be a string"
            )

        escaped_comment = comment.replace("'", "''")
        return f"{base_sql} COMMENT '{escaped_comment}'"
