# Permission Module Developer Guide

`oeds.domain.utils.permission.PermissionManager` applies direct Unity Catalog
object grants from packaged configuration. It resolves configured objects and
environment-specific groups, then grants `SELECT` or table-only `MODIFY`.
Apply permissions after creating the target tables and views, using the Python
API or the release notebook example.

## Key Locations

- [Permission implementation](../../src/oeds/domain/utils/permission/permission_utils.py)
- [Default permission registry](../../conf/oeds/config/permission/default.json)
- [Schema configuration](../../conf/oeds/config/schema)
- [Release notebook example](../../examples/release/release-0.0.0-13-apply-permissions.py)

## Permission Config Contract

Permission files remain under `oeds.config.permission`. `ConfigManager` first
looks for `<env>/<filename>` and falls back to the shared `<filename>`. The
normal filename is `default.json`; an alternate file can be selected per API
operation. Configuration is reloaded on each registry or apply call.

A registry defines group aliases for each environment and grants for logical
schema references. For example:

```json
{
  "groups": {
    "dev": {
      "consumer": "lake_customer_consumer_rusr_inda",
      "maintainer": "lake_customer_maintainer_rusr_inda"
    },
    "prd": {
      "consumer": "lake_customer_consumer_rusr_inpa",
      "maintainer": "lake_customer_maintainer_rusr_inpa"
    }
  },
  "permissions": {
    "tbl_customer": {
      "read": ["consumer", "maintainer"],
      "write": ["maintainer"]
    },
    "vw_customer_summary": {
      "read": ["consumer"]
    }
  }
}
```

| Field | Contract |
| --- | --- |
| `groups` | Object mapping environments to non-empty alias/full-group-name mappings. The active environment must exist. |
| `permissions` | Object or non-empty list of objects mapping schema references to `read`/`write` alias lists. |

The registry contains `groups` and `permissions`. Physical catalog names come
from schema definitions and SchemaManager's runtime bindings. Every configured
entry is processed unless the API selects a single reference. A table or view
in another catalog is not skipped.

### Group Aliases And Object References

Use stable aliases such as `consumer` in permission entries; the manager selects
the full group name from `groups[env]`. Define aliases for every environment you
use. Alias and reference matching are case-sensitive, and unknown aliases fail
validation. Groups must already exist; this module does not create them.

Each permission key names a reference in the configured schema registry, normally
the module basename under `conf/oeds/config/schema`. For example,
`tbl_customer.py` defines the `tbl_customer` reference. A reference identifies
one table or view, not an entire SQL schema.

`permissions` can also be a list of objects to group related entries:

```json
"permissions": [
  {"tbl_customer": {"read": ["consumer"], "write": ["maintainer"]}},
  {"vw_customer_summary": {"read": ["consumer"]}}
]
```

List entries are flattened into one registry; repeated references across the
list raise an error. Omitted or null `read`/`write` fields mean no grants of that
kind. An empty permission object is accepted and produces no grants; an empty
permission list is rejected. Use a non-empty registry for an operational run.

## Direct Object Grants

| Entry field | Privilege | Supported target |
| --- | --- | --- |
| `read` | `SELECT` | Configured table or view itself |
| `write` | `MODIFY` | Configured table only |

For a table resolved to `dev_application_cat.sales_db.tbl_customer`, a read
entry for `consumer` produces:

```sql
GRANT SELECT ON dev_application_cat.sales_db.tbl_customer TO `lake_customer_consumer_rusr_inda`;
```

A view receives `SELECT` only on the view itself. The manager does not inspect
view definitions or traverse dependencies. Underlying tables receive grants
only when they have their own configured entries. Write groups do not
implicitly receive read access; include them in both lists when needed.

The manager grants access only. It does not create objects, revoke access, grant
`USE CATALOG` or `USE SCHEMA`, or reconcile all existing permissions. Removing
configuration does not revoke previously applied grants.

### Runtime Prerequisites

Initialize `ConfigManager` and `SchemaManager` before creating a permission
manager, as provided by [common.py](../../common.py). The permission and config
manager environments must match. Spark is required; the manager reuses an
active session or creates one. The executing principal needs authority to grant
the configured privileges, and target objects must exist when applying grants.

View readers still need `USE CATALOG` and `USE SCHEMA` on the view's parents;
the view owner must retain access to underlying objects. SQL warehouses and
standard compute support this view-access model. Dedicated compute requires
Databricks Runtime 15.4 LTS or later and a workspace enabled for serverless
compute. See [Databricks view permissions](https://docs.databricks.com/aws/en/views).
The module does not configure or verify these consumer-compute prerequisites.

## Python API

After loading `common.py`, initialize the manager for the job environment:

```python
from oeds.domain.utils.permission import PermissionManager

job_ctx = get_job_context()
permission_manager = PermissionManager.initialize(job_ctx.get("env")).get_instance()
```

`initialize(env)` records the environment and returns the class for chained
creation. Each `get_instance()` creates a fresh caller-owned manager; existing
instances are unaffected by later initialization. `get_registry(config_file=None)`
returns the raw JSON object without normalizing its permission entries.

```python
# Apply all configured entries from the default registry.
permission_manager.apply_permissions()

# Preview one configured reference without executing grants.
permission_manager.apply_permissions(schema="vw_sample", execute=False)

# Preview an alternate packaged registry for this operation only.
permission_manager.apply_permissions(execute=False, config_file="release.json")
```

The signature is
`apply_permissions(schema=None, execute=True, *, config_file=None) -> None`.
`schema` selects one configured object reference; `None` selects all entries.
`config_file=None` selects `default.json` using environment-first resolution.
Blank strings are invalid API selectors; the release example converts a blank
`schema_ref` argument to `None`.

Preview logs the prepared SQL and suppresses grant execution. Read-only entries
do not query live object metadata, so preview does not prove object existence
or grant authority. Write entries still inspect live object type to reject
views. Statements and applied references are logged, not returned.

## Resolution And Failures

Each apply operation loads and validates the registry, resolves group aliases,
selects all entries or one reference, and resolves each object through
SchemaManager. Read grants apply to that object; write grants first check its
type. Configuration validation covers the entire registry, so an invalid entry
can block a targeted run even if that entry was not selected.

| Condition | Behavior |
| --- | --- |
| Missing file or invalid JSON | Propagates the resource or JSON parsing error. |
| JSON root is not an object | Raises `ValueError`. |
| Missing/invalid groups or active-environment mapping | Raises `ValueError`. |
| Empty alias/name or unknown grant alias | Raises `ValueError`. |
| Missing/invalid permission entries, empty references, or duplicate list references | Raises `ValueError`. |
| Non-list `read`/`write`, other than null | Raises `ValueError`. |
| Empty or unknown selected reference | Raises `ValueError`. |
| Object reference cannot be resolved | Propagates the schema lookup error. |
| Write groups configured for a view | Raises `ValueError`. |
| Metadata lookup or grant execution fails | Propagates the original exception. |

Grants execute sequentially and are not transactional. A later error, including
view-write rejection, can leave earlier grants applied. Exceptions stop the
release step rather than reporting partial success. Correct the failure and
rerun the intended scope; handle any revocations separately.

## Release Notebook Example

Copy [release-0.0.0-13-apply-permissions.py](../../examples/release/release-0.0.0-13-apply-permissions.py)
into `releases/`, rename it for the release, and include it in the release
document after object-creation steps. Its `%run ../common` assumes that location.
Deploy the bundle with `SERVICE` enabled before running the release notebook.

```text
task: releases/release-0.0.0-13-apply-permissions.py
args: {"schema_ref":""}
```

The sample calls `apply_permissions(schema=schema_ref)` and uses the manager's
defaults: `default.json` and `execute=True`. Running it applies grants. Omit or
leave `schema_ref` empty to process all configured entries, or select one:

```text
args: {"schema_ref":"vw_sample"}
```

The sample's only functional argument is `schema_ref`. For preview or another
packaged registry, adapt its Python call to pass `execute=False` or
`config_file` explicitly; these are manager API options, not sample arguments.

## Migration

Callers previously importing `oeds.domain.utils.permission2` must use
`oeds.domain.utils.permission`; the temporary package has no compatibility alias.
Existing `permission` callers now receive direct object grants without catalog
filtering or dependency expansion. The dependency-discovery API and the former
permission service tool are removed. Use the Python API or release notebook
instead. Existing group aliases and permission entries remain valid. Previously
applied grants are retained; any removal of earlier dependency grants requires
a separate release action.

## Related Guides

- [Schema Developer Guide](G211-schema-guide.md): define target tables and views.
- [Service Job Guide](G202-service-job-guide.md): run release notebooks through `SERVICE`.
- [Release Guide](G111-release-guide.md): deploy and order release steps.
