# Configuration and environment

## When to use this capability

Use `config_utils` to load checked-in or storage-backed JSON settings, `ENV` to read the active Databricks workspace/notebook context, and `misc_utils.param` to resolve a job parameter or widget value.

## Choose the public API

| Need | Choose |
| --- | --- |
| Load one JSON object, optionally inheriting from a parent | `load_json_config` |
| Read supported workspace settings or notebook/job metadata | The shared `ENV` instance |
| Resolve a Databricks task binding with widget fallback | `param` |
| Check whether text can be decoded as JSON | `is_valid_json` |
| Check basic email-address syntax | `is_valid_email` |
| Convert a scalar parameter to a Boolean, integer, float, date, or JSON value | `parse_bool`, `parse_int`, `parse_float`, `parse_date`, or `parse_json` |
| Add a caller name to diagnostics | `fn` |

`ENV` is the supported environment entry point; use its properties and configured attributes rather than creating another environment object.

## Restrictions and side effects

`load_json_config` accepts local, Workspace, Volume, and `abfss://` JSON files. An `extends` value must be one relative path in the same storage kind. Parent chains are recursive, circular chains are rejected, child values replace parent conflicts, and the returned mapping omits `extends`. ADLS reads use Spark credentials already configured in the session and add no retries or timeouts.

Most `ENV` values require Databricks notebook context. Configuration lookup is cached per process and fails if the current workspace is not configured. `ENV.PYTHON_VERSION` is runtime-independent; `ENV.SPARK_VERSION` requires an active Spark session. Do not log workspace IDs, user identities, storage account names, service URLs, or other environment values unless the data classification allows it.

`param(name: str, default: str | None = None) -> str | None` prefers Databricks job bindings over widgets and treats lookup failures as missing. Non-None values are converted to strings and stripped; missing or None values return the default. Names must be strings, and defaults must be strings or None; invalid types raise `TypeError`. It raises `ImportError` when `dbutils` is unavailable. Empty strings remain empty.

## Scalar parsing and validation

These `misc_utils` helpers use the Python standard library and do not require Spark or a Databricks runtime.

| Helper | Missing input and validation policy |
| --- | --- |
| `parse_bool` | None or unrecognized text/integer returns the Boolean default (False when omitted). Accepts strings, Booleans, and integers; rejects other types. |
| `parse_int` | None or blank text returns the integer/None default. Rejects Booleans, floats, and unsupported types; malformed base-10 text raises `ValueError`. |
| `parse_float` | None or blank text returns the numeric/None default, converted to float. Accepts scientific notation. Rejects Booleans, non-finite values, and overflow. |
| `parse_date` | None or an empty string returns the date/None default. Requires a non-empty Python format; whitespace is not stripped. Invalid dates raise `ValueError`. |
| `parse_json` | None or blank text raises `ValueError` unless a keyword default is supplied. Explicit `default=None` is supported. Malformed JSON raises `json.JSONDecodeError`; unsupported types raise `TypeError`, regardless of defaults. |
| `is_valid_json` | Returns a Boolean; non-string inputs are False. Uses Python decoder defaults, including acceptance of NaN and Infinity. |
| `is_valid_email` | Returns a Boolean for a basic syntax check: one at-sign, non-empty address parts, a dot in the domain, and no whitespace. Does not check full email standards, domain existence, or deliverability. |

Parser defaults are validated even when input is present. `parse_int` and `parse_float` reject Boolean defaults. JSON null decodes to None regardless of a supplied default; `parse_json` accepts NaN and Infinity under Python decoder defaults.

```python
from oeds.core.misc_utils import parse_float, parse_int, parse_json

retries = parse_int("3", default=0)
timeout = parse_float("1e2", default=30.0)
options = parse_json("", default={})
```

## Short example

```python
from oeds.core.config_utils import load_json_config
from oeds.core.env_utils import ENV
from oeds.core.misc_utils import param

config_path = f"{ENV.CURRENT_DIR}/config/customer.json"
config = load_json_config(config_path)
batch_name = param("batch_name", default="manual")

print(config["customer_name"], batch_name)
```

## Related examples

- [Configuration inheritance example](../../examples/config_utils/load_json_config.py)
- [Environment metadata example](../../examples/env_utils/inspect_environment.py)

- [Scalar validation and parsing notebook](../../examples/misc_utils/value_validation_and_parsing.py)
