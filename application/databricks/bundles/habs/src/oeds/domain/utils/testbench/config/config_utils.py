"""Load and resolve Testbench case definitions from a Unity Catalog Volume.

Cases may inherit through the shared JSON configuration loader. After merging,
declared string variables are rendered into the complete case document with
optional runtime overrides supplied by the caller.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateError
from oeds.core.config_utils import load_json_config

logger = logging.getLogger(__name__)

_CASE_CONFIG_DIRECTORY = "cases"
_CASE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_CASE_VARIABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CASE_VARIABLE_REFERENCE_PATTERN = re.compile(r"\{\{\s*[A-Za-z_][A-Za-z0-9_]*\s*\}\}")
_CASE_VARIABLES_FIELD = "variables"
_CASE_VARIABLE_RESERVED_NAMES = frozenset(
    {"true", "false", "none", "True", "False", "None", "not"}
)

# Only ``{{ variable }}`` interpolation is intended for case JSON. Custom block
# and comment delimiters prevent ordinary Jinja control syntax from becoming an
# undocumented second configuration language.
_CASE_VARIABLE_ENVIRONMENT = Environment(
    undefined=StrictUndefined,
    variable_start_string="{{",
    variable_end_string="}}",
    block_start_string="<%case-block%>",
    block_end_string="<%end-case-block%>",
    comment_start_string="<#case-comment#>",
    comment_end_string="<#end-case-comment#>",
    autoescape=False,
)


def load_test_case(
    case_name: str,
    case_root: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load one Volume-backed integration-test case by name.

    Case definitions live under ``<case_root>/cases``. The resolved Volume
    path is delegated to :func:`oeds.core.config_utils.load_json_config` so
    relative parent inheritance remains available.

    Args:
        case_name: Case filename without the ``.json`` suffix.
        case_root: Shared Unity Catalog Volume root containing case
            definitions and test artifacts.
        context: Optional runtime values that override matching variables
            declared by the case.

    Returns:
        Merged and variable-resolved integration-test configuration.

    Raises:
        TypeError: If ``case_name`` or ``case_root`` is not a string,
            ``context`` or ``variables`` is not an object, or a declared
            variable default or matching context override is not a string.
        ValueError: If ``case_name`` is empty or unsafe, ``case_root`` is not
            an absolute Unity Catalog Volume path, or case variables are
            invalid or cannot be resolved.
        FileNotFoundError: If the case config or one of its parents is missing.
        Exception: Propagates JSON, inheritance, filesystem, and storage errors
            from the Common configuration loader.
    """
    resolved_case_name = _validate_case_name(case_name)
    resolved_case_root = _validate_case_root(case_root)
    config_path = (
        resolved_case_root
        / _CASE_CONFIG_DIRECTORY
        / f"{resolved_case_name}.json"
    )
    if not Path(str(config_path)).is_file():
        raise FileNotFoundError(
            f"Integration test case '{resolved_case_name}' does not exist at "
            f"'{config_path}'."
        )

    logger.info(
        "Loading integration test case '%s' from '%s'",
        resolved_case_name,
        config_path,
    )
    config = load_json_config(str(config_path))
    resolved_config = _resolve_case_variables(config, context=context)
    logger.info("Loaded integration test config keys: %s", sorted(resolved_config))
    return resolved_config


def _resolve_case_variables(
    config: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve merged case variables with optional runtime overrides."""
    raw_variables = config.get(_CASE_VARIABLES_FIELD, {})
    if not isinstance(raw_variables, dict):
        raise TypeError("Integration test config field 'variables' must be an object.")
    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise TypeError("Integration test case context must be an object.")

    case_variables: dict[str, str] = {}
    for variable_name, variable_value in raw_variables.items():
        is_valid_variable_name = isinstance(variable_name, str) and (
            _CASE_VARIABLE_NAME_PATTERN.fullmatch(variable_name) is not None
        )
        if not is_valid_variable_name:
            raise ValueError(
                f"Invalid integration test case variable name {variable_name!r}. "
                "Names must start with a letter or underscore and contain only "
                "letters, numbers, or underscores."
            )
        if variable_name in _CASE_VARIABLE_RESERVED_NAMES:
            raise ValueError(
                f"Integration test case variable name '{variable_name}' is "
                "reserved by Jinja2."
            )
        if not isinstance(variable_value, str):
            raise TypeError(
                f"Integration test case variable '{variable_name}' must be a string."
            )
        if _CASE_VARIABLE_REFERENCE_PATTERN.search(variable_value):
            raise ValueError(
                f"Integration test case variable '{variable_name}' cannot "
                "reference another case variable."
            )
        # Runtime context can override declared variables but cannot introduce
        # undeclared template values into the case contract.
        context_value = context.get(variable_name)
        if context_value is not None:
            if not isinstance(context_value, str):
                raise TypeError(
                    "Integration test case context value for variable "
                    f"'{variable_name}' must be a string or null."
                )
            variable_value = context_value
        case_variables[variable_name] = variable_value

    if case_variables:
        logger.info(
            "Resolved %s integration test case variable(s): %s",
            len(case_variables),
            sorted(case_variables),
        )

    runtime_config = {
        key: value for key, value in config.items() if key != _CASE_VARIABLES_FIELD
    }
    # Rendering happens over serialized JSON. Escape each value as JSON content
    # before interpolation so quotes and control characters remain valid data.
    escaped_variables = {
        name: json.dumps(value)[1:-1] for name, value in case_variables.items()
    }
    try:
        rendered_config = _CASE_VARIABLE_ENVIRONMENT.from_string(
            json.dumps(runtime_config)
        ).render(escaped_variables)
        return json.loads(rendered_config)
    except (TemplateError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Failed to resolve integration test case variables: {exc}"
        ) from exc


def _validate_case_name(case_name: str) -> str:
    """Require a safe case filename without a file suffix."""
    if not isinstance(case_name, str):
        raise TypeError("case_name must be a string")

    resolved_case_name = case_name.strip()
    if not resolved_case_name:
        raise ValueError("case_name is required")
    if not _CASE_NAME_PATTERN.fullmatch(resolved_case_name):
        raise ValueError(
            "case_name must start with a letter or number and contain only "
            "letters, numbers, underscores, or hyphens"
        )
    return resolved_case_name


def _validate_case_root(case_root: str) -> PurePosixPath:
    """Require an absolute Unity Catalog Volume root."""
    if not isinstance(case_root, str):
        raise TypeError("case_root must be a string")

    case_root_value = case_root.strip()
    if not case_root_value:
        raise ValueError("case_root is required")

    case_root_path = PurePosixPath(case_root_value)
    case_root_parts = case_root_path.parts
    parsed_root = urlsplit(case_root_value)
    if (
        parsed_root.scheme
        or parsed_root.netloc
        or parsed_root.query
        or parsed_root.fragment
        or not case_root_path.is_absolute()
        or case_root_parts[0] != "/"
        or len(case_root_parts) < 5
        or case_root_parts[1] != "Volumes"
        or ".." in case_root_parts
        or "*" in case_root_value
        or "\\" in case_root_value
        or "\x00" in case_root_value
    ):
        raise ValueError(
            "case_root must be an absolute "
            "/Volumes/<catalog>/<schema>/<volume>/... path"
        )
    return case_root_path


__all__ = ["load_test_case"]
