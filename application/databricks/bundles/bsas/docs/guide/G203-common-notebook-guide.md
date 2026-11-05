# Common Notebook Guide

This guide explains how [common.py](../../common.py) works in the template bundle and how developers should customize it for a real project.

`common.py` is the shared runtime bootstrap for template notebooks. Dataflow,
curation, integration, service, and operation tasks, release notebooks, tool
notebooks, and examples run it at the beginning of the notebook so they all
start with the same job context and shared utilities.

## Location

The shared notebook is located at:

```text
application/databricks/bundles/dataforge/common.py
```

In a copied project bundle, keep it at the bundle root so notebooks can load it with a short relative `%run` path.

## Load Pattern

Run `common.py` before task logic, imports from the project `src` folder, or use of shared utilities.

For notebooks under `jobs/dataflow`, `jobs/curation`, `jobs/service`, or
`jobs/operation`:

```python
# MAGIC %run ../../common
```

For tool notebooks under `tools`:

```python
# MAGIC %run ../common
```

Interactive development widgets should be defined before `%run`, because `common.py` reads widget values while it builds the initial context and initializes shared services.

```python
dbutils.widgets.text("debug", "True")
dbutils.widgets.text("rundate", "")

# MAGIC %run ../../common

job_ctx = get_job_context()
```

## What It Does

`common.py` prepares the runtime environment in a fixed order:

1. Sets the default workflow task value `flow_action` to `continue`.
2. Builds the job context through `get_job_context()`.
3. Adds the bundle `conf` and `src` directories to `sys.path` so project
   configuration and reusable modules can be imported, then invalidates Python
   import-discovery caches.
4. Initializes logging.
5. Initializes `ConfigManager` for the active environment.
6. Initializes `SchemaManager`.
7. Configures `DatafileManager`.
8. Configures `ReferenceManager`.
9. Configures `CalendarManager`.
10. Configures the Logic App `EmailManager`.

After `%run`, a notebook can use:

- `get_job_context()` to read the current run context.
- `logger` through normal Python logging.
- `SchemaManager.get_instance()` and `DatafileManager.get_instance()` for
  reference-driven schema and source-file resolution.
- `CalendarManager.get_instance()` for holiday and business-date logic.
- `EmailManager.get_instance()` for configured email delivery.
- `OperationStatusManager()` to create an operation-status utility for writes
  and queries.
- helper functions such as `parse_bool`, `parse_date`, and `parse_json`.

## Job Context Model

The main job of `common.py` is to build a structured dictionary for the current notebook run. Template notebooks usually bind it like this:

```python
job_ctx = get_job_context()
```

The context is intentionally broad enough for all notebook types:

- Workflow tasks use it for run dates, storage roots, environment, DataBridge settings, and task decisions.
- Curation tasks use it for run dates, shared task values, logging, and project
  configuration.
- Integration tasks use it for run dates, shared task values, logging, and
  project configuration.
- Service tasks use it for bundle paths and shared operational configuration.
- Operation tasks use it for dataset identity, project paths, and shared services.
- Release notebooks use it for schema, permission, and deployment-time configuration.
- Tool notebooks use it for local bundle paths, storage locations, logging, and configured managers.

`task` and `args` are included in `job_ctx` and forwarded when the service
dispatcher invokes a target notebook. SERVICE forwards direct integration
values and existing secret-key fields. The child notebook reads the forwarded
direct values and resolves Datamart endpoints from the forwarded key while
rebuilding its context.

Unity Catalog parameters are shared through `common_base_parameters` and
`job_ctx`: `fmd_catalog`, `cur_catalog`, `bap_catalog`,
`sup_catalog`, `metadata_catalog`, `reference_catalog`,
`application_catalog`, and `internal_catalog`.
The four domain catalogs use the financial markets, currency, banking and
payments, and oversight catalog names for the deployment environment.

Notebook-bound values remain strings in `job_ctx`. In particular, `rundate`,
`debug`, `args`, `email_mappings`, `datamart_endpoints`, and both DataBridge job IDs are
parsed only by consumers that require typed values.

The derived bundle paths include `bundle_conf_dir`, `bundle_src_dir`, and
`bundle_cluster_dir`. `bundle_conf_dir` resolves to `<bundle_root>/conf` and is
the source root for the `oeds.config` namespace.

Project metadata in `job_ctx` keeps the flat notebook parameter names `team`,
`domain`, `dataset`, and `catalog`. The resource-naming value `project.tag` and
job classification values such as `type` and `criticality` are owned by bundle
resources and job tags; they are not part of the shared notebook context.

When `bundle_root` is not supplied, `common.py` searches the current notebook
directory and its ancestors for the nearest bundle-level `common.py`. This works
for notebooks under jobs, tools, examples, releases, and deeper directories.

## Parameter Priority

Task parameters are read through the shared `param()` helper from the DataKit
utility library. For secret-backed fields, this selects the secret key before
resolving the context value. The priority is:

1. Databricks notebook bindings, including values passed from [resources/jobs/common.yml](../../resources/jobs/common.yml) through `common_base_parameters` and shared run parameters such as `rundate` and `debug`.
2. Interactive widgets, usually created in development cells before `%run`.
3. Fallback defaults defined in [common.py](../../common.py).

This makes the same notebook work in three modes:

- A scheduled or manually triggered Databricks job gets values from the deployed bundle and run parameters.
- An interactive notebook run can override values with widgets.
- A direct Databricks notebook run can fall back to `common.py` defaults when neither bindings nor widgets provide a value.

## Bundle Parameters

Bundle defaults start in [default.databricks.yml](../../default.databricks.yml),
which owns the complete complex `project` object and all project-derived
resource values. Adjacent comment mappings supply literal domain scopes and
domain/target service SPN keys and email mappings. When jobs are enabled,
adjacent mappings in `resources/jobs/common.yml` supply run-as accounts,
notification recipients, and permission lists for each target.
[resources/jobs/common.yml](../../resources/jobs/common.yml) defines
`common_base_parameters` as a complex variable, and each job resource passes it
to notebooks:

```yaml
base_parameters: ${var.common_base_parameters}
```

The flat notebook parameter `catalog` receives `${var.catalog}`. That bundle
variable expands the input tag in `project.catalog` into the fully qualified
`${var.env}_${var.project.catalog}_cat` catalog name.

At runtime, `common.py` reads direct integration parameters and resolves
Datamart endpoints from the OEDS secret scope into `job_ctx`. This is why project identity, environment, storage roots, secret scopes, workspace references, DataBridge job IDs, email mappings, and Datamart endpoints should be configured in bundle files instead of hardcoded inside task notebooks.

## Direct Integration Values

Azure subscription and tenant IDs, internal and external Databricks workspace
URLs and resource IDs, both DataBridge job IDs, and both SQL warehouse IDs use
direct bundle variables and notebook parameters without a `_key` suffix:

- `azure_subscription_id`, `azure_tenant_id`
- `internal_databricks_workspace_url`, `internal_databricks_resource_id`
- `external_databricks_workspace_url`, `external_databricks_resource_id`
- `internal_dis_job_id`, `external_dis_job_id`
- `sql_warehouse_serverless_large_id`, `sql_warehouse_classic_medium_id`

`default.databricks.yml` supplies values for dev, stg, and prd.
`resources/jobs/common.yml` forwards them through `common_base_parameters`.
`get_job_context()` reads the direct parameters into the same context fields,
keeping values as trimmed strings. Individual `DEFAULT_*` constants provide
dev defaults for interactive runs. These ten settings do not read secrets or
accept their former `_key` parameters. Update existing bundle overrides and
interactive widgets to use the direct parameter names.

## OEDS Integration Secrets

`datamart_endpoints_key` remains a secret-key parameter, defaulting to
`datamart-endpoints` in `oeds_secrete_scope` (by default,
`lake-kv-oedataservices-scope`). Each environment must provide this secret and
allow the notebook run identity to read it. `get_job_context()` retains the key
and resolves its value into `datamart_endpoints` on every call through
`resolve_secret(key, scope)`. Forwarding a resolved `datamart_endpoints` value
does not override that lookup.

Blank scopes or keys raise `ValueError`; missing secrets and permission
failures propagate without falling back to embedded values. Datamart JSON
remains a string with surrounding whitespace stripped. Do not log resolved
secrets. Existing credential and email secret-key settings retain their current
behavior. `compute_classic_job_policy_id` remains a deployment setting with
environment-specific IDs.

## Flow Action

`common.py` sets:

```python
dbutils.jobs.taskValues.set(key="flow_action", value="continue")
```

That is the default path through the workflow. A task can change it to `complete` when the job should stop gracefully, for example on a holiday or when there is no source data to process.

The `DATAFLOW` and `CURATION` condition tasks read this task value to decide
whether downstream stages continue or whether the workflow moves to completion
handling. Their definitions are in
[resources/jobs/dataflow.yml](../../resources/jobs/dataflow.yml) and
[resources/jobs/curation.yml](../../resources/jobs/curation.yml).

## Shared Utilities

### Logging

`common.py` configures Python logging once, using `debug` from the job context:

```python
debug_enabled = parse_bool(_ctx.get("debug"), default=False)
log_level = "debug" if debug_enabled else "info"
```

Use `logging.getLogger(__name__)` in notebooks after `%run`. Avoid logging secrets or full payloads that may contain credentials or sensitive data.

### Local Python Libraries

`common.py` adds the bundle `conf` and `src` folders to `sys.path`. This lets
notebooks import project configuration and reusable modules such as:

```python
import oeds.config.schema
from oeds.domain.utils.email.email_utils import EmailManager
```

Keep project-owned configuration under
[conf/oeds/config](../../conf/oeds/config), reusable project logic under
[src/oeds/domain](../../src/oeds/domain), and import both from notebooks instead
of copying definitions or helper code between tasks.

`ConfigManager` selects effective modules for schema, datafile, and fileloader
registries. Active-environment modules override shared modules with the same
basename; environment-only and shared-only modules remain available. Its
`initialize` method defensively invalidates Python import caches again, and each
`get_instance(package)` call creates a cacheless caller-owned manager. Every
module discovery returns an independent, read-only `ModuleMap` from logical
names to full dotted module names. Registry consumers import modules explicitly
through that map. Text resources are not cached.

### Schema And Datafile Managers

After adding the local package roots, `common.py` initializes `ConfigManager`,
then configures `SchemaManager` and `DatafileManager` with the resolved
environment. Each initialization discovers and stores an immutable `ModuleMap`;
it does not import definition modules. Every `get_instance()` call returns a
new caller-owned object using that snapshot, and every `find(ref)` imports only
the requested definition. Re-running the bootstrap replaces the snapshots used
by future objects without modifying existing ones. Calling a dependent module
before running `common.py` raises a clear runtime error. FileLoader consumers
initialize FileLoader explicitly after bootstrap.

`OperationStatusManager` is created on demand rather than stored globally.
Construct it without arguments to use the default `tbl_operation_status` ref,
or pass another logical ref through `table_ref`.

### Calendar

`common.py` configures `ReferenceManager` and `CalendarManager` without starting
Spark or querying data. Each calendar access creates a caller-owned object and
loads the configured holiday group, or creates a calendar without holiday
exclusions when the group is empty. Workflow tasks retrieve it after `%run`:

```python
from oeds.domain.utils.calendar import CalendarManager

calendar = CalendarManager.get_instance()
rundate = parse_date(job_ctx["rundate"], job_ctx["python_date_format"])
if calendar.is_holiday(rundate):
    dbutils.jobs.taskValues.set(key="flow_action", value="complete")
```

See [Calendar Guide](G301-calendar-guide.md) for date calculation patterns.

### Email Manager

`common.py` resolves the configured email service URL secret and configures the
Logic App provider with the email mappings. Consumers import `EmailManager` and
call `get_instance()` to create caller-owned managers for workflow completion,
failure handling, release notebooks, or tools. Configuration does not create a
ConfigManager or transport client and does not load the email registry. Each
registry lookup and send reloads the configured registry, each send reloads its
HTML template, and each send constructs a fresh Logic App client.

See the [Email Module Developer Guide](G303-email-developer-guide.md) for registry definitions, recipient mappings, HTML templates, DataFrame tables, attachments, and Logic App or Microsoft Graph providers.

## Customization

Each project can customize `common.py`, but keep it focused on shared runtime setup. Good customization candidates are:

- Additional project-wide context values used by many notebooks.
- Shared global variables that are stable for the whole notebook run.
- Shared utility instances, such as clients or managers used across workflow and release notebooks.
- Additional parsing or validation for project-level configuration.

Avoid putting task-specific processing logic in `common.py`. If only one notebook needs a value or helper, keep it in that notebook or in a focused module under `src/oeds/domain`.

For example, the service dispatcher validates `args` from `job_ctx`. A normal
timeseries notebook only writes observations; the manager registers successful
changes in the transaction log, and the AE time-series standard publishes them
to WebMart automatically. `datamart_endpoints` and service-principal credentials
remain available for special cases that require manual publishing. DataBridge
clients convert their selected job ID to an integer at construction time.

## Adding A Context Value

When a new shared value is needed across notebooks:

1. Add or update the bundle variable in `default.databricks.yml` and the project `databricks.yml`.
2. Pass it through `common_base_parameters` in `resources/jobs/common.yml` when every task should receive it.
3. Add a `DEFAULT_*` fallback in `common.py`.
4. Read it in `get_job_context()` with `param("name", DEFAULT_VALUE)`.
5. Keep notebook-bound values as strings in `job_ctx`.
6. Parse it at the use site when a consumer requires a typed value.

For secrets, pass secret scope and key names through the bundle and resolve the
values at the consumer boundary. Use a shared lazy resolver only when many
notebooks need the same secret. Never put resolved secrets in `job_ctx` or log
their values.

## Developer Checklist

- Define development widgets before `%run`.
- Call `%run` before using `job_ctx`, `calendar`, `email_manager`, or local `src` imports.
- Use `job_ctx = get_job_context()` in each notebook that needs context.
- Put environment and project configuration in bundle variables, not scattered through notebooks.
- Keep `common.py` defaults aligned with the generated project `databricks.yml`.
- Add shared context only when more than one notebook needs it.
- Keep detailed diagnostics in logs and keep notebook exit payloads compact.


## Optional DataBridge email settings

The bundle exposes `tmp_root` immediately after `land_root` and passes it through
shared task parameters into `job_ctx`. Its default is
`/Volumes/${var.catalog}/reference_db/vol_${var.project.tag}_land/tmp/${var.project.dataset}`.

Under **Email service settings**, the `DataBridge email service` block follows
`email_service_url_key`. The context exposes `databridge_email_tenant_id_key`,
`databridge_email_client_id_key`, `databridge_email_client_secret_key`, and
`databridge_email_sender_account`. These values default to empty strings and
are checked only when opting into DataBridge. Initialization passes the existing
`job_ctx["oeds_secrete_scope"]` directly as the provider's `graph_secret_scope`;
there is no separate email secret-scope variable.

The common notebook continues initializing the Logic App provider. To opt in,
use the [DataBridge email example](../../examples/email/send_email_databridge.py)
and the [email guide](G303-email-developer-guide.md#databridge-provider).
The ingestion template is `oeds.config.ingest/email.json`; it is separate from
the `oeds.config.email/default.json` registry.
