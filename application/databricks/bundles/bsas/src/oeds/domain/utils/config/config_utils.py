"""Resolve packaged configuration for the active runtime environment.

``ConfigManager`` keeps the active environment process-wide and creates a new
caller-owned manager for each request. Module discovery returns an independent
``ModuleMap`` snapshot, while text resources remain uncached. A package can
provide Python registry modules or text resources beneath an environment
subpackage or directory. Text uses UTF-8 by default, environment content takes
precedence, and missing entries fall back to the shared package root.
"""

from __future__ import annotations

import codecs
import importlib
import logging
import pkgutil
import re
from collections.abc import Iterator, Mapping
from importlib.resources import files
from pathlib import PurePosixPath, PureWindowsPath
from types import MappingProxyType, ModuleType
from typing import ClassVar

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError

logger = logging.getLogger(__name__)

_CONFIG_TEMPLATE_ENVIRONMENT = Environment(
    undefined=StrictUndefined,
    variable_start_string="[[",
    variable_end_string="]]",
    block_start_string="[%",
    block_end_string="%]",
    comment_start_string="[#",
    comment_end_string="#]",
    autoescape=False,
)

_ENVIRONMENT_PATTERN = re.compile(r"^[a-z0-9_-]+$")
_PACKAGE_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$"
)
_PUBLIC_MODULE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class ModuleMap(Mapping[str, str]):
    """Read-only map of logical names to full dotted module names.

    The map owns no imported module objects. Iteration follows sorted logical
    module-name order, and modules are imported only when requested.
    """

    def __init__(
        self,
        *,
        full_module_name_map: Mapping[str, str],
    ) -> None:
        """Create one discovered logical-to-full-name snapshot."""
        if not isinstance(full_module_name_map, Mapping):
            raise TypeError("full_module_name_map must be a mapping")
        normalized_full_name_map = {
            _normalize_public_module_name(module_name): _normalize_full_module_name(
                full_module_name
            )
            for module_name, full_module_name in full_module_name_map.items()
        }
        self._full_module_name_map = MappingProxyType(
            dict(sorted(normalized_full_name_map.items()))
        )

    def __getitem__(self, module_name: str) -> str:
        """Return the full module name for one exact logical name."""
        return self._full_module_name_map[module_name]

    def __iter__(self) -> Iterator[str]:
        """Iterate over logical module names in sorted order."""
        return iter(self._full_module_name_map)

    def __len__(self) -> int:
        """Return the number of effective configuration modules."""
        return len(self._full_module_name_map)

    def get_full_module_name(self, module_name: str) -> str:
        """Return the selected full dotted name for one logical module.

        Args:
            module_name: Direct public module basename without a package prefix.

        Returns:
            The full environment module name when an override exists;
            otherwise the full shared module name.

        Raises:
            TypeError: If ``module_name`` is not a string.
            ValueError: If ``module_name`` is empty, private, nested, or unsafe.
            ModuleNotFoundError: If this snapshot does not contain the module.
        """
        normalized_module_name = _normalize_public_module_name(module_name)
        full_module_name = self._full_module_name_map.get(normalized_module_name)

        if full_module_name is None:
            raise ModuleNotFoundError(
                f"Config module '{normalized_module_name}' was not found in "
                "this module map."
            )

        return full_module_name

    def import_module(self, module_name: str) -> ModuleType:
        """Import one effective configuration module by logical name.

        Args:
            module_name: Direct public module basename without a package prefix.

        Returns:
            The imported environment override or shared module. Normal Python
            ``sys.modules`` behavior applies.

        Raises:
            TypeError: If ``module_name`` is not a string.
            ValueError: If ``module_name`` is empty, private, nested, or unsafe.
            ModuleNotFoundError: If this snapshot does not contain the module.
        """
        full_module_name = self.get_full_module_name(module_name)
        return importlib.import_module(full_module_name)


class ConfigManager:
    """Manage environment-aware content for one configuration package.

    Call :meth:`initialize` with the runtime environment, then use
    :meth:`get_instance` with a full package such as ``oeds.config.schema``.
    Each package manager discovers direct Python modules from both
    ``<package>.<environment>`` and ``<package>``. Environment modules override
    shared modules with the same basename, and either package may contribute
    additional modules.

    Every :meth:`discover_module_map` call returns an independent, read-only
    :class:`ModuleMap`. The manager retains no mutable module-discovery state.
    """

    # One environment is shared by every package manager in the process.
    _environment: ClassVar[str | None] = None

    def __init__(self, *, package: str, environment: str) -> None:
        """Create a manager for one package and environment.

        Instances are normally created by :meth:`get_instance` after
        :meth:`initialize` fixes the process environment.

        Args:
            package: Full dotted name of the importable configuration package.
            environment: Environment used for module and resource precedence.

        Raises:
            TypeError: If an argument has an invalid type.
            ValueError: If an argument is empty or has an invalid format.
        """
        self.package = _normalize_package_name(package)
        normalized_environment = _normalize_environment(environment)
        if normalized_environment is None:
            raise ValueError("environment is required")

        self.environment = normalized_environment

    @classmethod
    def initialize(cls, environment: str) -> type[ConfigManager]:
        """Set the environment and invalidate Python import-discovery caches.

        Every call starts a new configuration lifecycle. Existing managers and
        module maps are not modified; callers receive fresh managers from
        :meth:`get_instance`. Invalidating import caches lets same-process
        notebook reruns discover added and removed modules. IPython autoreload
        is responsible for re-executing edited modules during interactive
        development.

        Args:
            environment: Non-empty environment name such as ``dev`` or ``prd``.

        Returns:
            The manager class so callers may chain :meth:`get_instance`.

        Raises:
            TypeError: If ``environment`` is not a string.
            ValueError: If ``environment`` is empty or unsafe.
        """
        if environment is None:
            raise TypeError("environment must be a string")

        normalized_environment = _normalize_environment(environment)
        if normalized_environment is None:
            raise ValueError("environment is required")

        cls._environment = normalized_environment
        importlib.invalidate_caches()
        logger.info(
            "Initialized ConfigManager for environment '%s' and invalidated "
            "Python import caches",
            normalized_environment,
        )
        return cls

    @classmethod
    def get_instance(cls, package: str) -> ConfigManager:
        """Create a caller-owned manager for one configuration package.

        Args:
            package: Full dotted package name, for example
                ``oeds.config.fileloader``.

        Returns:
            A new manager for ``package`` and the active environment.

        Raises:
            TypeError: If ``package`` is not a string.
            ValueError: If ``package`` is empty or is not a dotted Python name.
            RuntimeError: If :meth:`initialize` has not been called.
        """
        package_name = _normalize_package_name(package)

        environment = cls._environment
        if environment is None:
            raise RuntimeError(
                "ConfigManager is not initialized. Call "
                "ConfigManager.initialize(environment) first."
            )

        instance = cls(package=package_name, environment=environment)
        logger.info(
            "Created caller-owned ConfigManager for package '%s' and "
            "environment '%s'",
            package_name,
            environment,
        )
        return instance

    def discover_module_map(self) -> ModuleMap:
        """Discover the effective public configuration module names.

        Direct environment modules override shared modules by basename.
        Environment-only and shared-only modules are both retained. Missing or
        empty packages produce an empty map.

        Returns:
            A new read-only snapshot mapping logical module basenames to full
            dotted module names in sorted order.

        Raises:
            ValueError: If an existing target is a module instead of a package.
            Exception: Propagates imports that fail inside existing packages.
        """
        environment_package = f"{self.package}.{self.environment}"
        environment_modules = _discover_package_module_names(environment_package)
        shared_modules = _discover_package_module_names(self.package)

        # The union permits environment-only modules. Membership in the
        # environment set implements override precedence for matching names.
        full_module_name_map = {
            module_name: (
                f"{environment_package}.{module_name}"
                if module_name in environment_modules
                else f"{self.package}.{module_name}"
            )
            for module_name in sorted(environment_modules | shared_modules)
        }
        module_map = ModuleMap(
            full_module_name_map=full_module_name_map,
        )
        logger.info(
            "Discovered %s config module(s) for package '%s' and environment '%s'",
            len(module_map),
            self.package,
            self.environment,
        )
        return module_map

    def load_config_resource(
        self,
        resource: str,
        *,
        encoding: str = "utf-8",
        params: Mapping[str, object] | None = None,
    ) -> str:
        """Load an environment-specific or shared text resource.

        The method first checks ``<environment>/<resource>`` beneath the
        package, then falls back to ``<resource>`` at the package root. Resource
        directories do not need to be importable Python subpackages. UTF-8 is
        used unless the caller explicitly selects another Python text codec.

        When params is supplied (including an empty mapping), render once with
        Jinja2 using [[ variables ]], [% blocks %], and [# comments #]. Missing
        variables fail strictly and HTML autoescaping is disabled. Omitted or
        None params returns raw text. Parsing and domain validation belong to
        the caller.

        Args:
            resource: Safe package-relative path using forward slashes.
            encoding: Python text codec used to decode the selected resource.
            params: Optional template context with string keys.

        Returns:
            The decoded resource, optionally rendered using ``params``.

        Raises:
            TypeError: If resource or encoding is not a string, params is not
                a mapping, or a context key is not a string.
            ValueError: If resource is unsafe, resource or encoding is empty,
                or template rendering fails.
            LookupError: If ``encoding`` is not a registered Python codec.
            FileNotFoundError: If neither resource candidate exists.
            ModuleNotFoundError: If this manager's package cannot be imported.
            UnicodeDecodeError: If the resource is invalid for ``encoding``.
        """
        resource_parts = _validate_resource_path(resource)
        if params is not None:
            if not isinstance(params, Mapping):
                raise TypeError("params must be a mapping or None")
            if any(not isinstance(key, str) for key in params):
                raise TypeError("params keys must be strings")
        if not isinstance(encoding, str):
            raise TypeError("encoding must be a string")

        encoding_name = encoding.strip()
        if not encoding_name:
            raise ValueError("encoding is required")
        encoding_name = codecs.lookup(encoding_name).name

        # Text resources use directories, not import names, but follow the same
        # environment-first precedence as Python registry modules.
        candidates = [
            (self.environment, *resource_parts),
            resource_parts,
        ]

        package_root = files(self.package)
        attempted_resources: list[str] = []
        for candidate_parts in candidates:
            candidate_name = "/".join(candidate_parts)
            attempted_resources.append(candidate_name)
            config_resource = package_root.joinpath(*candidate_parts)
            if not config_resource.is_file():
                continue

            logger.info(
                "Loading config resource '%s' from package '%s'",
                candidate_name,
                self.package,
            )
            resource_text = config_resource.read_text(encoding=encoding_name)
            if params is None:
                return resource_text

            try:
                return _CONFIG_TEMPLATE_ENVIRONMENT.from_string(resource_text).render(
                    params
                )
            except TemplateError as exc:
                raise ValueError(
                    f"Failed to render config resource '{candidate_name}' "
                    f"from package '{self.package}'"
                ) from exc

        attempted = ", ".join(f"'{name}'" for name in attempted_resources)
        raise FileNotFoundError(
            f"Config resource '{resource}' was not found in package "
            f"'{self.package}'. Tried: {attempted}."
        )

def _validate_resource_path(resource: str) -> tuple[str, ...]:
    """Validate and split one safe package-relative resource path."""
    if not isinstance(resource, str):
        raise TypeError("resource must be a string")

    resource_name = resource.strip()
    if not resource_name:
        raise ValueError("resource is required")
    if "\\" in resource_name:
        raise ValueError("resource must use forward slashes")
    if (
        PurePosixPath(resource_name).is_absolute()
        or PureWindowsPath(resource_name).is_absolute()
    ):
        raise ValueError("resource must be a relative path")

    resource_parts = tuple(resource_name.split("/"))
    if any(part in {"", ".", ".."} for part in resource_parts):
        raise ValueError("resource must not contain empty, '.' or '..' path segments")

    return resource_parts


def _normalize_environment(environment: str | None) -> str | None:
    """Validate and normalize an optional environment directory name."""
    if environment is None:
        return None
    if not isinstance(environment, str):
        raise TypeError("environment must be a string or None")

    normalized_environment = environment.strip().lower()
    if not normalized_environment:
        raise ValueError("environment cannot be empty")
    if not _ENVIRONMENT_PATTERN.fullmatch(normalized_environment):
        raise ValueError(
            "environment must contain only lowercase letters, digits, '_' or '-'"
        )

    return normalized_environment


def _normalize_package_name(package: str) -> str:
    """Validate and normalize one full importable package name."""
    if not isinstance(package, str):
        raise TypeError("package must be a string")

    package_name = package.strip()
    if not package_name:
        raise ValueError("package is required")
    if not _PACKAGE_PATTERN.fullmatch(package_name):
        raise ValueError("package must be a dotted Python package name")

    return package_name


def _normalize_full_module_name(full_module_name: str) -> str:
    """Validate and normalize one fully qualified module name."""
    if not isinstance(full_module_name, str):
        raise TypeError("full_module_name must be a string")

    normalized_full_module_name = full_module_name.strip()
    if not normalized_full_module_name:
        raise ValueError("full_module_name is required")
    if not _PACKAGE_PATTERN.fullmatch(normalized_full_module_name):
        raise ValueError("full_module_name must be a dotted Python module name")

    return normalized_full_module_name


def _normalize_public_module_name(module_name: str) -> str:
    """Validate and normalize one public direct-child module name."""
    if not isinstance(module_name, str):
        raise TypeError("module_name must be a string")

    normalized_module_name = module_name.strip()
    if not normalized_module_name:
        raise ValueError("module_name is required")
    if not _PUBLIC_MODULE_PATTERN.fullmatch(normalized_module_name):
        raise ValueError(
            "module_name must be a public Python module name containing only "
            "letters, digits, or '_'"
        )

    return normalized_module_name


def _discover_package_module_names(package_name: str) -> set[str]:
    """Return direct public modules, treating a missing package as empty.

    A package that does not exist is an optional empty configuration source.
    Import failures raised by code inside an existing package are preserved.
    """
    try:
        package_module = importlib.import_module(package_name)
    except ModuleNotFoundError as exc:
        missing_name = exc.name
        # Only suppress failure to resolve the requested package or one of its
        # parents. A different missing name came from package code and is real.
        if missing_name and (
            package_name == missing_name
            or package_name.startswith(f"{missing_name}.")
        ):
            logger.debug("Config package '%s' does not exist", package_name)
            return set()
        raise

    package_paths = getattr(package_module, "__path__", None)
    if package_paths is None:
        raise ValueError(f"Config package '{package_name}' is not a package")

    return {
        module_info.name
        for module_info in pkgutil.iter_modules(package_paths)
        if not module_info.ispkg
        and _PUBLIC_MODULE_PATTERN.fullmatch(module_info.name)
    }


__all__ = ["ConfigManager", "ModuleMap"]
