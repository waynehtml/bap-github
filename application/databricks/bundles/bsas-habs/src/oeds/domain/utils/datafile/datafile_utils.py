"""Datafile registry helpers for template bundle datasets.

This module discovers Datafile definitions from the project ``oeds.config``
package so callers can import and use them as normal Python modules instead of
relying on Databricks notebook ``%run`` side effects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, ClassVar

import oeds.domain.utils.config.config_utils as config_utils

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PACKAGE = "oeds.config.datafile"


@dataclass(frozen=True)
class DatafileRegistry:
    """Resolved Datafile registry entry for one source dataset."""

    ref: str
    path: str | None = None
    format: str | None = None
    options: dict[str, Any] | None = None
    schema: Any | None = None


class DatafileManager:
    """Resolve caller-requested Datafile definitions for one environment."""

    _configuration: ClassVar[tuple[str, config_utils.ModuleMap] | None] = None

    def __init__(self, env: str, module_map: config_utils.ModuleMap) -> None:
        """Create a caller-owned manager from one configuration snapshot."""
        self.env = self._normalize_env(env)
        if not isinstance(module_map, config_utils.ModuleMap):
            raise TypeError("module_map must be a ModuleMap")
        self._module_map = module_map

    @classmethod
    def initialize(cls, env: str) -> type[DatafileManager]:
        """Build the module map and return the class for chained creation."""
        normalized_env = cls._normalize_env(env)
        config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )
        if config_manager.environment != normalized_env:
            raise RuntimeError(
                "DatafileManager environment "
                f"'{normalized_env}' does not match ConfigManager environment "
                f"'{config_manager.environment}'"
            )
        module_map = config_manager.discover_module_map()
        cls._configuration = (normalized_env, module_map)
        logger.info(
            "Configured DatafileManager for env '%s' with %s Datafile reference(s)",
            normalized_env,
            len(module_map),
        )
        return cls

    @classmethod
    def get_instance(cls) -> DatafileManager:
        """Create a caller-owned manager from the configured snapshot."""
        configuration = cls._configuration
        if configuration is None:
            raise RuntimeError(
                "DatafileManager is not initialized. "
                "Call DatafileManager.initialize(env) first."
            )

        environment, module_map = configuration
        config_manager = config_utils.ConfigManager.get_instance(
            _DEFAULT_CONFIG_PACKAGE
        )
        if config_manager.environment != environment:
            raise RuntimeError(
                "DatafileManager environment "
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

    def find(self, name: str) -> DatafileRegistry:
        """Import and resolve one Datafile registry by reference."""
        logger.debug("Looking up Datafile registry '%s'", name)
        if not name or not str(name).strip():
            raise ValueError("name is required")

        datafile_ref = str(name).strip()
        if datafile_ref not in self._module_map:
            raise ValueError(f"Datafile registry for '{datafile_ref}' not found")

        module = self._module_map.import_module(datafile_ref)
        full_module_name = module.__name__
        definition = getattr(module, "DEFINITION", {})
        if definition is None:
            definition = {}
        if not isinstance(definition, dict):
            raise ValueError(
                f"Unable to resolve Datafile definition from '{full_module_name}'. "
                "Expected 'DEFINITION' to be a dict when provided."
            )

        relative_path = definition.get("path")
        registry = DatafileRegistry(
            ref=datafile_ref,
            path=str(relative_path) if relative_path is not None else None,
            format=definition.get("format"),
            options=definition.get("options"),
            schema=definition.get("schema"),
        )
        logger.debug(
            "Resolved Datafile module '%s' as ref '%s' for source '%s'",
            full_module_name,
            datafile_ref,
            relative_path if relative_path is not None else "<none>",
        )
        return registry

__all__ = ["DatafileManager", "DatafileRegistry"]
