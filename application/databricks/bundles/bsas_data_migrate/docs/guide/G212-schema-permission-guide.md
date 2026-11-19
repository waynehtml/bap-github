# Permission Module Developer Guide

This guide explains how developers configure and apply Unity Catalog grants in Dataforge. The permission config is the source of grant intent; the permission module validates that config, resolves environment-specific objects and groups, and generates the corresponding `GRANT` statements. The `apply_permissions` service tool provides the standard operational entry point.

Apply permissions after the target tables and views have been created. Runtime pipeline tasks should rely on existing objects and grants rather than changing access during data processing.

## Module Responsibilities

| Concern | Owner |
| --- | --- |
| Allowed catalog scope | `permission/default.json` → `catalogs` |
| Environment-specific group names | `permission/default.json` → `groups` |
| Read and write grant intent | `permission/default.json` → `permissions` |
| Logical reference to physical object resolution | `SchemaManager` |
| Config validation and `GRANT` generation | `PermissionManager` |
| On-demand execution and preview | `tools/apply_permissions.py` |

The module grants access only. It does not create tables or views, create account groups, revoke permissions, or reconcile the complete current grant state. It grants only `SELECT` and `MODIFY`; required `USE CATALOG`, `USE SCHEMA`, ownership, or other privileges must already exist or be managed separately.

> Removing a group or permission entry from the config does not revoke a grant that was previously applied. Handle revocation as an explicit release action.

## Key Locations

- [default.json](../../conf/oeds/config/permission/default.json): packaged permission registry.
- [schema config](../../conf/oeds/config/schema): table and view definitions referenced by permission entries.
- [permission_utils.py](../../src/oeds/domain/utils/permission/permission_utils.py): `PermissionManager` implementation.
- [apply_permissions.py](../../tools/apply_permissions.py): service tool for previewing and applying grants.

## Permission Config Contract

Permission files are packaged under `oeds.config.permission`. `ConfigManager`
first looks for `<env>/<filename>` and falls back to the shared `<filename>`.
The standard shared file is `default.json`:

```json
{
  "catalogs": [
    "application_cat"
  ],
  "groups": {
    "dev": {
      "aeeng": "lake_aeengsupport_rusr_inda",
      "dataopen": "lake_dataopen_rusr_inda"
    },
    "stg": {
      "aeeng": "lake_aeengsupport_rusr_inpa",
      "dataopen": "lake_dataopen_rusr_inpa"
    },
    "prd": {
      "aeeng": "lake_aeengsupport_rusr_inpa",
      "dataopen": "lake_dataopen_rusr_inpa"
    }
  },
  "permissions": [
    {
      "tbl_customer": {
        "read": ["dataopen", "aeeng"],
        "write": ["aeeng"]
      },
      "vw_customer_summary": {
        "read": ["dataopen", "aeeng"]
      }
    }
  ]
}
```

| Top-level field | Type | Purpose |
| --- | --- | --- |
| `catalogs` | Non-empty list of strings | Catalog allowlist, expressed without environment prefixes. |
| `groups` | Object keyed by environment | Maps short aliases used in permission entries to Databricks account group names. |
| `permissions` | Object or non-empty list of objects | Maps schema references to `read` and `write` grant intent. Production config should contain at least one entry. |

Keep the config declarative. Physical object location belongs in schema config, and environment-specific group names belong under `groups` rather than in individual permission entries. Permission files must be valid JSON, so comments and trailing commas are not supported.

## Catalog Allowlist

`catalogs` defines the only catalogs that the module may grant against. Configure base names without an environment prefix:

```json
"catalogs": [
  "application_cat",
  "reference_cat"
]
```

At runtime, `PermissionManager` lowercases the active environment and prefixes every configured catalog with `{env}_`:

| Config value | Environment | Runtime catalog |
| --- | --- | --- |
| `application_cat` | `dev` | `dev_application_cat` |
| `application_cat` | `stg` | `stg_application_cat` |
| `reference_cat` | `prd` | `prd_reference_cat` |

Do not include `dev_`, `stg_`, or `prd_` in the config value. For example, configuring `dev_application_cat` in `dev` would normalize to `dev_dev_application_cat`.

After a schema reference is resolved, its physical catalog is compared with this normalized allowlist. A reference outside the allowlist is skipped and logged; it is not treated as an error. Review preview logs carefully so an unintended catalog mismatch is not mistaken for a successful grant.

The same allowlist limits view dependency grants. Dependencies found in catalogs that are not configured are omitted.

## Environment Group Aliases

`groups` separates stable permission intent from environment-specific Databricks group names:

```json
"groups": {
  "dev": {
    "consumer": "lake_customer_consumer_rusr_inda",
    "maintainer": "lake_customer_maintainer_rusr_inda"
  },
  "stg": {
    "consumer": "lake_customer_consumer_rusr_inpa",
    "maintainer": "lake_customer_maintainer_rusr_inpa"
  },
  "prd": {
    "consumer": "lake_customer_consumer_rusr_inpa",
    "maintainer": "lake_customer_maintainer_rusr_inpa"
  }
}
```

Permission entries use `consumer` and `maintainer`; the module selects the full names under the active environment. Every environment to which the bundle is deployed must have a non-empty group mapping, and every alias referenced by a permission entry must exist in that environment. Alias matching is case-sensitive.

Use aliases that describe access roles rather than a specific environment or physical group name. This keeps the permission section identical across environments.

## Permission Entries

Each permission key is a schema reference. With the standard tool, it must exactly match a module name under `conf/oeds/config/schema` without `.py`:

```text
conf/oeds/config/schema/tbl_customer.py  →  tbl_customer
conf/oeds/config/schema/vw_customer.py   →  vw_customer
```

An entry supports two optional lists:

| Field | Unity Catalog privilege | Supported target |
| --- | --- | --- |
| `read` | `SELECT` | Tables and views |
| `write` | `MODIFY` | Tables only |

Schema reference matching is case-sensitive. An omitted `read` or `write` field is normalized to an empty list.

### Table Permissions

```json
"tbl_customer": {
  "read": ["consumer", "maintainer"],
  "write": ["maintainer"]
}
```

If `tbl_customer` resolves to `dev_application_cat.sales_db.tbl_customer`, the config produces grants equivalent to:

```sql
GRANT SELECT ON dev_application_cat.sales_db.tbl_customer TO `lake_customer_consumer_rusr_inda`;
GRANT SELECT ON dev_application_cat.sales_db.tbl_customer TO `lake_customer_maintainer_rusr_inda`;
GRANT MODIFY ON dev_application_cat.sales_db.tbl_customer TO `lake_customer_maintainer_rusr_inda`;
```

The module does not infer that a write group should also receive read access. Include the alias in both lists when both privileges are required.

### View Permissions

```json
"vw_customer_summary": {
  "read": ["consumer", "maintainer"]
}
```

For a view, `read` applies `SELECT` to the view and to detected table or view dependencies in allowed catalogs. This lets a consumer query the final view when Unity Catalog requires access to its underlying objects.

Do not configure `write` for a view. The module rejects it because `MODIFY` is supported only for tables.

### Multiple Permission Objects

`permissions` may be one object or a list of objects. A list can keep related entries together:

```json
"permissions": [
  {
    "tbl_customer": {
      "read": ["consumer"]
    },
    "vw_customer_summary": {
      "read": ["consumer"]
    }
  },
  {
    "tbl_customer_control": {
      "read": ["maintainer"],
      "write": ["maintainer"]
    }
  }
]
```

All list items are flattened into one registry. A schema reference may appear only once across the entire list.

## View Dependency Behavior

To apply read permissions for a view, `PermissionManager`:

1. Loads the live definition with `SHOW CREATE TABLE`.
2. Detects fully qualified `catalog.schema.object` references in the SQL.
3. Keeps only dependencies whose catalogs are in the normalized allowlist.
4. Recursively expands dependent views.
5. Removes duplicate and cyclic references.
6. Grants `SELECT` on dependencies before the target view.

Dependency detection relies on fully qualified names in the rendered view definition. Review the preview output when a view uses unusual SQL or indirect references. An unqualified object name is not detected as a dependency by the permission module.

Even in preview mode, the target objects must already exist because the module inspects object types and view definitions through Spark.

## Config Resolution Flow

For each run, `PermissionManager` follows this sequence:

1. Load the selected JSON file through `ConfigManager`, using the active
   environment override before the shared file.
2. Validate the root config, catalog values, active-environment groups, and permission entries.
3. Normalize catalog names with the active environment prefix.
4. Resolve group aliases for the active environment.
5. Select all permission entries or one requested `schema_ref`.
6. Resolve each schema reference through `SchemaManager`.
7. Skip objects outside the configured catalog allowlist.
8. Resolve read targets and reject write access for views.
9. Log each generated `GRANT` statement and execute it when enabled.

Errors propagate to the calling notebook so the service job fails visibly. Grant execution is sequential and is not transactional: if a later statement fails, grants executed earlier in the run remain in place. Correct the config or access issue and rerun the intended scope.

## Validation And Failure Reference

| Condition | Behavior |
| --- | --- |
| Permission file is missing or contains invalid JSON | Propagates the file or JSON parsing error. |
| Permission file is not a JSON object | Raises `ValueError`. |
| `catalogs` is missing, empty, or contains an empty value | Raises `ValueError`. |
| `groups` is not an object | Raises `ValueError`. |
| Active environment has no non-empty group mapping | Raises `ValueError`. |
| Group alias or full group name is empty | Raises `ValueError`. |
| A permission references an unknown alias | Raises `ValueError`. |
| `permissions` is missing or is an empty list | Raises `ValueError`. An empty object is accepted but generates no grants and should not be used as production config. |
| A permission reference is empty or duplicated | Raises `ValueError`. |
| `read` or `write` is not a list | Raises `ValueError`. |
| Requested `schema_ref` is absent from permission config | Raises `ValueError`. |
| Schema reference cannot be resolved | Propagates the schema lookup error. |
| Resolved object is outside configured catalogs | Skips the entry and logs the reason. |
| `write` is configured for a view | Raises `ValueError`. |
| Target object or dependency cannot be inspected | Propagates the Spark or catalog error. |
| Caller cannot grant on a target object | Propagates the SQL execution error. |

## Apply Permissions With The Tool

Use the Dataforge `SERVICE` job to run the standard tool:

```text
task: tools/apply_permissions
args: {"schema_ref":"","execute":true,"config_file":""}
```

Tool arguments:

| Argument | Type | Default | Purpose |
| --- | --- | --- | --- |
| `schema_ref` | String | Empty | Apply one configured reference; empty applies all entries. |
| `execute` | Boolean | `true` | Execute grants when true; generate and log them without executing when false. |
| `config_file` | String | Empty | Select another packaged permission JSON file; empty uses `default.json`. |

### Preview All Permissions

```text
task: tools/apply_permissions
args: {"schema_ref":"","execute":false,"config_file":""}
```

Preview mode validates config, resolves groups and objects, inspects views, and logs the generated SQL. It skips only the final Spark calls that submit the `GRANT` statements.

### Apply One Permission Entry

```text
task: tools/apply_permissions
args: {"schema_ref":"vw_customer_summary","execute":true,"config_file":""}
```

Use a targeted run when introducing or correcting one entry. The reference must still exist in the selected permission config.

### Use An Alternate Packaged Config

```text
task: tools/apply_permissions
args: {"schema_ref":"tbl_customer","execute":false,"config_file":"migration.json"}
```

Alternate files may be deployed in `conf/oeds/config/permission` for shared use
or its active-environment subdirectory for an environment override. Keep
`default.json` as the normal project contract; use another file only for a
deliberate release or migration scope.

### Tool Result

The tool returns compact JSON metadata:

```json
{
  "tool": "apply_permissions",
  "status": "completed",
  "env": "dev",
  "schema_ref": "tbl_customer",
  "config_file": "default.json",
  "execute": true
}
```

Detailed object resolution, skipped references, and generated SQL remain in the job logs. A completed result means the module finished without raising an exception; inspect logs for catalog-allowlist skips.

## Use `PermissionManager` Directly

Release notebooks can call the module directly when orchestration requires more than the standard tool:

```python
from oeds.domain.utils.permission import PermissionManager

args = parse_json(job_ctx.get("args"))
if not isinstance(args, dict):
    raise TypeError("args must be a JSON object")

schema_ref = str(args.get("schema_ref") or "").strip() or None
config_file = str(args.get("config_file") or "").strip() or None
execute = args.get("execute", True)

permission_manager = PermissionManager.initialize(
    job_ctx.get("env")
).get_instance()
permission_manager.apply_permissions(
    schema=schema_ref,
    execute=execute,
    config_file=config_file,
)
```

Each consumer initializes `PermissionManager` for its runtime environment after
`common.py` initializes `ConfigManager` and `SchemaManager`. The standard
`tools/apply_permissions.py` tool performs this initialization itself. Each
`get_instance()` call creates a new caller-owned manager. An alternate
`config_file` applies only to that operation and does not change the configured
environment or future config selection.

## Developer Workflow

1. Create or update the target definition under `conf/oeds/config/schema`.
2. Add every target catalog base name to `catalogs`.
3. Define stable aliases under every deployable environment in `groups`.
4. Add one permission entry per schema reference.
5. Create tables first and views second.
6. Deploy the bundle so schema and permission config changes are packaged.
7. Run `tools/apply_permissions` with `execute=false` and review all generated SQL and skip logs.
8. Rerun with `execute=true` after the preview is correct.
9. Verify access with the intended Databricks principal when the release requires it.
10. Use an explicit release action for any revoked access; config deletion alone is insufficient.

## Developer Checklist

- Catalogs are unprefixed base names and cover every intended target and view dependency.
- Group aliases are stable and defined for `dev`, `stg`, and `prd` as applicable.
- Full group names match existing Databricks account groups.
- Each permission key matches a deployed schema reference.
- Table groups receive `read`, `write`, or both intentionally.
- Views use `read` only.
- No schema reference appears more than once.
- Target objects exist before preview or execution.
- Preview logs show the expected physical objects, groups, and SQL.
- Catalog skips are understood and intentional.
- Required revocations are handled separately.

## Related Guides

- [Schema Developer Guide](G211-schema-guide.md): define and deploy the tables and views referenced by permission config.
- [Service Job Guide](G202-service-job-guide.md): run tools and release notebooks through the Dataforge `SERVICE` job.
- [Release Guide](G111-release-guide.md): order schema and permission operations during a release.
