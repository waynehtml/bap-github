"""Utilities for loading files into tables from packaged mappings."""

from __future__ import annotations

import logging
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any, ClassVar

from oeds.core.df_utils import normalize_column_names, normalize_nulls
from oeds.core.df_validator import Rule, validate_df
from oeds.core.file_reader import load_file_failfast
from oeds.core.uc_utils import delta_batch_update
from pyspark.sql import DataFrame

import oeds.domain.utils.config.config_utils as config_utils
import oeds.domain.utils.datafile.datafile_utils as datafile_utils
import oeds.domain.utils.schema.schema_utils as schema_utils

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PACKAGE = "oeds.config.fileloader"
_DEFAULT_MODE = "overwrite"
_SUPPORTED_MODES = {"append", "overwrite", "replace"}
_RUNTIME_CONTEXT_KEY = "_runtime"
_NORMALIZE_KEYS = {"column_names", "null_values"}
_WRITE_KEYS = {"mode", "batch_column"}


@dataclass(frozen=True)
class FileLoadNormalization:
    """Optional DataFrame normalization applied before transformation."""

    column_names: bool = False
    null_values: tuple[str, ...] | None = None


@dataclass(frozen=True)
class FileLoadWrite:
    """Write behavior for one file load mapping."""

    mode: str = _DEFAULT_MODE
    batch_column: str | None = None


@dataclass(frozen=True)
class FileLoadMapping:
    """Resolved mapping for loading one source file into one table."""

    ref: str
    file_ref: str
    tbl_ref: str
    normalize: FileLoadNormalization = field(default_factory=FileLoadNormalization)
    transform: Callable[[DataFrame, dict[str, Any] | None], DataFrame] | None = None
    rules: tuple[Rule, ...] = ()
    write: FileLoadWrite = field(default_factory=FileLoadWrite)

    @property
    def mode(self) -> str:
        """Return the configured write mode for backward-compatible callers."""
        return self.write.mode


class FileLoader:
    """Load one requested file mapping from a configuration snapshot."""

    _configuration: ClassVar[tuple[str, config_utils.ModuleMap] | None] = None

    def __init__(
        self,
        env: str,
        module_map: config_utils.ModuleMap,
    ) -> None:
        """Create a caller-owned loader from one configuration snapshot."""
        self.env = self._normalize_env(env)
        if not isinstance(module_map, config_utils.ModuleMap):
            raise TypeError("module_map must be a ModuleMap")
        self._module_map = module_map
        self.schema_manager = schema_utils.SchemaManager.get_instance()
        self.datafile_manager = datafile_utils.DatafileManager.get_instance()
        dependency_environments = {
            "SchemaManager": self.schema_manager.env,
            "DatafileManager": self.datafile_manager.env,
        }
        for manager_name, dependency_environment in dependency_environments.items():
            if dependency_environment != self.env:
                raise RuntimeError(
                    f"FileLoader environment '{self.env}' does not match "
                    f"{manager_name} environment '{dependency_environment}'"
                )

    @classmethod
    def initialize(cls, env: str) -> type[FileLoader]:
        """Build the module map and return the class for chained creation."""
        normalized_env = cls._normalize_env(env)
        config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )
        if config_manager.environment != normalized_env:
            raise RuntimeError(
                "FileLoader environment "
                f"'{normalized_env}' does not match ConfigManager environment "
                f"'{config_manager.environment}'"
            )
        module_map = config_manager.discover_module_map()
        cls._configuration = (normalized_env, module_map)
        logger.info(
            "Configured FileLoader for env '%s' with %s mapping reference(s)",
            normalized_env,
            len(module_map),
        )
        return cls

    @classmethod
    def get_instance(cls) -> FileLoader:
        """Create a caller-owned loader from the configured snapshot."""
        configuration = cls._configuration
        if configuration is None:
            raise RuntimeError(
                "FileLoader is not initialized. "
                "Call FileLoader.initialize(env) first."
            )

        environment, module_map = configuration
        config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )
        if config_manager.environment != environment:
            raise RuntimeError(
                "FileLoader environment "
                f"'{environment}' does not match ConfigManager environment "
                f"'{config_manager.environment}'"
            )

        return cls(environment, module_map)

    @staticmethod
    def _normalize_env(env: str) -> str:
        """Validate and normalize an environment name."""
        if not isinstance(env, str) or not env.strip():
            raise ValueError("env is required")

        return env.strip().lower()

    def get_module_map(self) -> dict[str, str]:
        """Return a printable copy of discovered refs and full module names."""
        return dict(self._module_map.items())

    def find(self, ref: str) -> FileLoadMapping:
        """Import and resolve one file load mapping by reference."""
        logger.debug("Looking up file load mapping '%s'", ref)
        if not ref or not str(ref).strip():
            raise ValueError("ref is required")

        load_ref = str(ref).strip()
        if load_ref not in self._module_map:
            raise ValueError(f"File load mapping for '{load_ref}' not found")

        module = self._module_map.import_module(load_ref)
        module_name = module.__name__
        definition = getattr(module, "DEFINITION", None)
        if not isinstance(definition, dict):
            raise ValueError(
                f"Unable to resolve file load mapping from '{module_name}'. "
                "Expected 'DEFINITION' to be a dict."
            )

        transform = definition.get("transform")
        if transform is not None and not callable(transform):
            raise TypeError(
                f"File load mapping '{load_ref}' transform must be callable "
                "when provided"
            )

        mapping = FileLoadMapping(
            ref=load_ref,
            file_ref=str(
                self._get_required_field(definition, "file_ref", module_name)
            ).strip(),
            tbl_ref=str(
                self._get_required_field(definition, "tbl_ref", module_name)
            ).strip(),
            normalize=self._resolve_normalization(
                definition.get("normalize"), module_name
            ),
            transform=transform,
            rules=self._resolve_rules(definition.get("rules", ()), module_name),
            write=self._resolve_write(definition, module_name),
        )
        logger.debug(
            "Resolved file load mapping '%s' for file ref '%s', table ref '%s', "
            "and write mode '%s'",
            load_ref,
            mapping.file_ref,
            mapping.tbl_ref,
            mapping.write.mode,
        )
        return mapping

    def load_file(
        self,
        ref: str,
        *,
        file_base_uri: str | None = None,
        mode: str | None = None,
        batch_id: str | int | date | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Normalize, transform, validate, and write one file load mapping.

        Args:
            ref: Required mapping reference to load.
            file_base_uri: Optional base URI joined to the configured file path.
            mode: Optional runtime override for the configured write mode.
            batch_id: Logical batch value required by ``replace`` mode and
                prohibited for the other modes.
            context: Runtime values copied and enriched under the reserved
                ``_runtime`` key before a transform is called.

        Raises:
            TypeError: If context or a transform return value has an invalid type.
            ValueError: If the mapping, write arguments, or paths are invalid.
            RuntimeError: If a configured DataFrame validation rule fails.
        """
        if not ref or not str(ref).strip():
            raise ValueError("ref is required")
        if context is not None and not isinstance(context, dict):
            raise TypeError("context must be a dict or None")
        if context is not None and _RUNTIME_CONTEXT_KEY in context:
            raise ValueError(
                f"context key '{_RUNTIME_CONTEXT_KEY}' is reserved for runtime metadata"
            )

        normalized_file_base_uri = (
            str(file_base_uri).strip()
            if file_base_uri is not None and str(file_base_uri).strip()
            else None
        )

        load_ref = str(ref).strip()
        logger.info(
            "Loading file load mapping '%s' using file base URI '%s'",
            load_ref,
            normalized_file_base_uri or "<none>",
        )

        file_load_mapping = self.find(load_ref)
        datafile_registry = self.datafile_manager.find(file_load_mapping.file_ref)
        schema_registry = self.schema_manager.find(file_load_mapping.tbl_ref)
        full_table_name = schema_registry.full_name

        # Resolve and validate write behavior before reading the external file.
        resolved_mode = (
            str(mode).strip()
            if mode is not None and str(mode).strip()
            else file_load_mapping.write.mode
        ).lower()
        if resolved_mode not in _SUPPORTED_MODES:
            supported_modes = ", ".join(sorted(_SUPPORTED_MODES))
            raise ValueError(f"mode must be one of: {supported_modes}")

        batch_column = file_load_mapping.write.batch_column
        if resolved_mode == "replace":
            if batch_column is None:
                raise ValueError(
                    f"File load mapping '{file_load_mapping.ref}' must configure "
                    "write.batch_column for mode='replace'"
                )
            if batch_id is None:
                raise ValueError("batch_id is required for mode='replace'")
        elif batch_id is not None:
            raise ValueError("batch_id must be omitted unless mode='replace'")

        if not datafile_registry.path or not str(datafile_registry.path).strip():
            raise ValueError(
                f"Datafile registry '{datafile_registry.ref}' must provide 'path' "
                f"for file load '{file_load_mapping.ref}'"
            )
        resolved_file_path = str(datafile_registry.path).strip()
        if normalized_file_base_uri:
            resolved_file_path = (
                f"{normalized_file_base_uri.rstrip('/')}/"
                f"{resolved_file_path.lstrip('/')}"
            )

        if datafile_registry.schema is None:
            raise ValueError(
                f"Datafile registry '{datafile_registry.ref}' must provide "
                f"'schema' for file load '{file_load_mapping.ref}'"
            )

        file_format = datafile_registry.format or "csv"

        logger.info(
            "Loading file mapping '%s': file ref '%s' from '%s' into table "
            "ref '%s' using mode '%s'",
            file_load_mapping.ref,
            file_load_mapping.file_ref,
            resolved_file_path,
            file_load_mapping.tbl_ref,
            resolved_mode,
        )
        logger.info(
            "Resolved target table '%s' for file load '%s'",
            full_table_name,
            file_load_mapping.ref,
        )

        df = load_file_failfast(
            resolved_file_path,
            file_format,
            schema=datafile_registry.schema,
            options=datafile_registry.options,
        )

        # Normalization establishes the stable input contract seen by transforms.
        if file_load_mapping.normalize.column_names:
            logger.info(
                "Normalizing column names for file load '%s'",
                file_load_mapping.ref,
            )
            df = normalize_column_names(df)

        if file_load_mapping.normalize.null_values is not None:
            logger.info(
                "Normalizing null values for file load '%s'",
                file_load_mapping.ref,
            )
            df = normalize_nulls(
                df,
                null_values=file_load_mapping.normalize.null_values,
            )

        if file_load_mapping.transform:
            logger.info(
                "Applying transform for file load '%s'", file_load_mapping.ref
            )
            runtime_metadata: dict[str, Any] = {
                "ref": file_load_mapping.ref,
                "file_ref": file_load_mapping.file_ref,
                "tbl_ref": file_load_mapping.tbl_ref,
                "mode": resolved_mode,
            }
            if batch_column is not None:
                runtime_metadata["batch_column"] = batch_column
            if batch_id is not None:
                runtime_metadata["batch_id"] = batch_id

            transform_context = dict(context or {})
            transform_context[_RUNTIME_CONTEXT_KEY] = runtime_metadata
            df = file_load_mapping.transform(df, transform_context)
            if not isinstance(df, DataFrame):
                raise TypeError(
                    f"File load mapping '{file_load_mapping.ref}' transform "
                    "must return a DataFrame"
                )

        if file_load_mapping.rules:
            logger.info(
                "Validating file load '%s' using %s rule(s)",
                file_load_mapping.ref,
                len(file_load_mapping.rules),
            )
            validation_result = validate_df(df, file_load_mapping.rules)
            if not validation_result.success:
                failed_rules = [
                    result.expectation
                    for result in validation_result.results
                    if not result.success
                ]
                logger.error(
                    "Validation failed for file load '%s' on rule(s): %s",
                    file_load_mapping.ref,
                    ", ".join(failed_rules),
                )
                raise RuntimeError(
                    f"Validation failed for file load '{file_load_mapping.ref}' "
                    f"on {len(failed_rules)} rule(s): {', '.join(failed_rules)}"
                )

        logger.info(
            "Writing file load '%s' to table '%s'",
            file_load_mapping.ref,
            full_table_name,
        )
        delta_batch_update(
            df,
            full_table_name,
            mode=resolved_mode,
            batch_column=batch_column if resolved_mode == "replace" else None,
            batch_id=batch_id if resolved_mode == "replace" else None,
            evolve_schema=False,
        )

    def _get_required_field(
        self, definition: dict[str, Any], key: str, module_name: str
    ) -> Any:
        """Return one required nonblank mapping field."""
        value = definition.get(key)
        if value is None or not str(value).strip():
            raise ValueError(f"File load mapping '{module_name}' must provide '{key}'")

        return value

    def _resolve_normalization(
        self,
        raw_normalize: Any,
        module_name: str,
    ) -> FileLoadNormalization:
        """Validate and resolve an optional ``normalize`` definition."""
        if raw_normalize is None:
            return FileLoadNormalization()
        if not isinstance(raw_normalize, dict):
            raise TypeError(
                f"File load mapping '{module_name}' normalize must be a dict"
            )

        unknown_keys = sorted(set(raw_normalize) - _NORMALIZE_KEYS)
        if unknown_keys:
            raise ValueError(
                f"File load mapping '{module_name}' normalize contains unsupported field(s): "
                f"{', '.join(unknown_keys)}"
            )

        column_names = raw_normalize.get("column_names", False)
        if not isinstance(column_names, bool):
            raise TypeError(
                f"File load mapping '{module_name}' normalize.column_names must be a bool"
            )

        null_values: tuple[str, ...] | None = None
        if "null_values" in raw_normalize:
            raw_null_values = raw_normalize["null_values"]
            if not isinstance(raw_null_values, Collection) or isinstance(
                raw_null_values, (str, bytes, dict)
            ):
                raise TypeError(
                    f"File load mapping '{module_name}' normalize.null_values must be a collection of strings"
                )
            if any(not isinstance(value, str) for value in raw_null_values):
                raise TypeError(
                    f"File load mapping '{module_name}' normalize.null_values must contain only strings"
                )
            null_values = tuple(raw_null_values)

        return FileLoadNormalization(
            column_names=column_names,
            null_values=null_values,
        )

    def _resolve_rules(self, raw_rules: Any, module_name: str) -> tuple[Rule, ...]:
        """Validate and freeze the configured DataFrame validation rules."""
        if not isinstance(raw_rules, Sequence) or isinstance(raw_rules, (str, bytes)):
            raise TypeError(
                f"File load mapping '{module_name}' rules must be a sequence of Rule objects"
            )
        if any(not isinstance(rule, Rule) for rule in raw_rules):
            raise TypeError(
                f"File load mapping '{module_name}' rules must contain only Rule objects"
            )
        return tuple(raw_rules)

    def _resolve_write(
        self, definition: dict[str, Any], module_name: str
    ) -> FileLoadWrite:
        """Validate and resolve nested write behavior for one mapping."""
        raw_write = definition.get("write")
        if raw_write is None:
            write_definition: dict[str, Any] = {}
        elif isinstance(raw_write, dict):
            write_definition = dict(raw_write)
        else:
            raise TypeError(f"File load mapping '{module_name}' write must be a dict")

        unknown_keys = sorted(set(write_definition) - _WRITE_KEYS)
        if unknown_keys:
            raise ValueError(
                f"File load mapping '{module_name}' write contains unsupported field(s): "
                f"{', '.join(unknown_keys)}"
            )

        # Preserve existing mappings while directing new definitions to write.mode.
        legacy_mode = definition.get("mode")
        if legacy_mode is not None:
            if "mode" in write_definition:
                raise ValueError(
                    f"File load mapping '{module_name}' must not configure both mode and write.mode"
                )
            logger.warning(
                "File load mapping '%s' uses deprecated top-level mode; use write.mode instead",
                module_name,
            )
            write_definition["mode"] = legacy_mode

        raw_mode = write_definition.get("mode")
        resolved_mode = (
            str(raw_mode).strip().lower()
            if raw_mode is not None and str(raw_mode).strip()
            else _DEFAULT_MODE
        )
        if resolved_mode not in _SUPPORTED_MODES:
            supported_modes = ", ".join(sorted(_SUPPORTED_MODES))
            raise ValueError(
                f"File load mapping '{module_name}' write.mode must be one of: {supported_modes}"
            )

        raw_batch_column = write_definition.get("batch_column")
        if raw_batch_column is None:
            batch_column = None
        elif isinstance(raw_batch_column, str) and raw_batch_column.strip():
            batch_column = raw_batch_column.strip()
        else:
            raise TypeError(
                f"File load mapping '{module_name}' write.batch_column must be a non-empty string"
            )

        if resolved_mode == "replace" and batch_column is None:
            raise ValueError(
                f"File load mapping '{module_name}' must configure write.batch_column "
                "when write.mode='replace'"
            )

        return FileLoadWrite(mode=resolved_mode, batch_column=batch_column)


__all__ = [
    "FileLoadMapping",
    "FileLoadNormalization",
    "FileLoadWrite",
    "FileLoader",
]
