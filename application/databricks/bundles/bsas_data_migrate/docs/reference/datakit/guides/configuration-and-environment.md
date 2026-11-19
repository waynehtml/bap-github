# Configuration and environment

## When to use this capability

Use `config_utils` to load checked-in or storage-backed JSON settings, `ENV` to read the active Databricks workspace/notebook context, and `misc_utils.param` to resolve a job parameter or widget value.

## Choose the public API

| Need | Choose |
| --- | --- |
| Load one JSON object, optionally inheriting from a parent | `load_json_config` |
| Read supported workspace settings or notebook/job metadata | The shared `ENV` instance |
| Resolve a Databricks task binding with widget fallback | `param` |
| Validate an arbitrary JSON string | `is_valid_json` |
| Add a caller name to diagnostics | `fn` |

`ENV` is the supported environment entry point; use its properties and configured attributes rather than creating another environment object.

## Restrictions and side effects

`load_json_config` accepts local, Workspace, Volume, and `abfss://` JSON files. An `extends` value must be one relative path in the same storage kind. Parent chains are recursive, circular chains are rejected, child values replace parent conflicts, and the returned mapping omits `extends`. ADLS reads use Spark credentials already configured in the session and add no retries or timeouts.

Most `ENV` values require Databricks notebook context. Configuration lookup is cached per process and fails if the current workspace is not configured. `ENV.PYTHON_VERSION` is runtime-independent; `ENV.SPARK_VERSION` requires an active Spark session. Do not log workspace IDs, user identities, storage account names, service URLs, or other environment values unless the data classification allows it.

`param` prefers Databricks job bindings over widgets, strips string values, and treats lookup failures as missing. It raises `ImportError` when `dbutils` is unavailable.

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
