# DataForge Domain Utility Catalog

Use this catalog to find the supported DataForge domain capability before
adding workflow code or another utility. It is an index, not a complete API
reference. The linked source and its docstrings are authoritative for exact
signatures; guides describe the intended workflow.

`—` means that no dedicated guide, example, or automated test was found in the
DataForge template.

Configurable manager and factory APIs return their class from `initialize(...)`,
so callers may immediately chain `.get_instance()`. Bootstrap code may ignore
that return value when it only needs to configure future caller-owned instances.

## AI usage guidance

AI agents must:

1. Use this README to locate the appropriate capability.
2. Inspect the linked source and docstrings for exact signatures.
3. Review examples and tests when available.
4. Reuse existing public APIs instead of creating duplicate utilities.
5. Report missing or conflicting documentation before guessing behavior.

## Capability catalog

| Capability | Preferred module | Public APIs | Guide | Example | Tests |
|---|---|---|---|---|---|
| Databricks metadata and warehouse DDL | [`databricks.databricks_utils`](databricks/databricks_utils.py) | `get_job_run_trigger_user`, `get_job_run_page_url`, `get_job_task_keys`, `execute_ddl` | — | — | — |
| Environment-aware configuration | [`config.config_utils`](config/config_utils.py) | `ConfigManager`, `ModuleMap` | — | [Load a text resource](../../../../examples/config/load_config_resource.py), [bootstrap initialization](../../../../common.py) | — |
| Ingestion configuration and workflow | [`ingest.ingest_utils`](ingest/ingest_utils.py) | `load_config`, `DisConnectionOptions`, `FileVerificationOptions`, `IngestTaskResult`, `run_ingest` | [DataBridge client](../../../../docs/guide/G220-ingest-client-guide.md) | [Ingest task](../../../../jobs/dataflow/task_10_ingest.py) | — |
| Ingestion client and results | [`ingest.client.dis_client`](ingest/client/dis_client.py) | `DisClient`, `IngestResult`, `VerifyResult`, typed ingest exceptions | [DataBridge client](../../../../docs/guide/G220-ingest-client-guide.md) | [Ingest task](../../../../jobs/dataflow/task_10_ingest.py) | — |
| Datafile registry | [`datafile.datafile_utils`](datafile/datafile_utils.py) | `DatafileManager`, `DatafileRegistry` | [Datafile](../../../../docs/guide/G225-datafile-developer-guide.md) | [Registry lookup](../../../../examples/datafile/datafile_manager.py) | — |
| File loading | [`fileloader.fileloader_utils`](fileloader/fileloader_utils.py) | `FileLoader`, mapping dataclasses | [Fileloader](../../../../docs/guide/G226-fileloader-developer-guide.md) | [Load sample file](../../../../examples/fileloader/load_sample_file.py) | — |
| Schema registry | [`schema.schema_utils`](schema/schema_utils.py) | `SchemaManager`, `SchemaRegistry` | [Schema](../../../../docs/guide/G211-schema-guide.md) | [Registry lookup](../../../../examples/schema/schema_manager.py) | — |
| Schema deployment | [`schema.schema_deployment_utils`](schema/schema_deployment_utils.py) | `SchemaDeploymentManager` | [Schema](../../../../docs/guide/G211-schema-guide.md) | [Create tables](../../../../examples/release/release-0.0.0-11-create-tables.py), [create views](../../../../examples/release/release-0.0.0-12-create-views.py) | — |
| Operation status | [`operation.operation_utils`](operation/operation_utils.py) | `OperationStatusManager` | [Operation status](operation/README.md) | — | — |
| Unity Catalog permissions | [`permission.permission_utils`](permission/permission_utils.py) | `PermissionManager` | [Direct grants](../../../../docs/guide/G212-schema-permission-guide.md#direct-object-grants) | [Release example](../../../../examples/release/release-0.0.0-13-apply-permissions.py) | — |
| Email | [`email.email_utils`](email/email_utils.py) | `EmailManager`, `EmailProvider` | [Email](../../../../docs/guide/G303-email-developer-guide.md) | [Send email](../../../../examples/email/send_email.py) | — |
| Configured calendar | [`calendar.calendar_utils`](calendar/calendar_utils.py) | `CalendarManager` | [Calendar](../../../../docs/guide/G301-calendar-guide.md) | [Main task](../../../../jobs/dataflow/task_00_main.py) | — |
| Reference calendar data | [`reference.reference_utils`](reference/reference_utils.py) | `ReferenceManager` | [Calendar](../../../../docs/guide/G301-calendar-guide.md) | [Bootstrap configuration](../../../../common.py) | — |
| Time series | [`timeseries.timeseries_utils`](timeseries/timeseries_utils.py) | `TimeSeriesObservation`, `TimeSeriesUtils`; low-level `Freq`, `TimeSeriesCollection`, `TimeSeriesManager` | [Release workflow](../../../../docs/guide/G111-release-guide.md) | [Register](../../../../examples/timeseries/register_timeseries.py), [insert observations](../../../../examples/timeseries/insert_timeseries_observation.py), [load observation CSV](../../../../tools/load_timeseries_observations.py) | — |
| OTLP logging | [`otel_logging.otel_logging_utils`](otel_logging/otel_logging_utils.py) | `ZerobusLoggingConfig`, `configure_logging`, `initialize_logging` | [Logging guide](otel_logging/README.md) | [App](otel_logging/example_app.py), [notebook](otel_logging/example_notebook.py) | — |

## Capability notes

Guide, example, and test links in the capability table apply to the modules
grouped below.

### OTLP logging

#### [`otel_logging/otel_logging_utils.py`](otel_logging/otel_logging_utils.py)

- **Purpose and use:** Explicitly configure a process-owned Python logging bridge
  to Zerobus through OTLP/gRPC using Entra authentication.
- **Canonical module:** `oeds.domain.utils.otel_logging.otel_logging_utils`.
- **Runtime and restrictions:** Requires the utility's local
  [dependencies](otel_logging/requirements.txt), approved credentials, federation,
  and a prepared Unity Catalog table. Configuration attaches a handler and starts
  batched export; importing the package does not enable logging. Existing handlers
  and the global OpenTelemetry provider are preserved. Flush and shut down the
  returned runtime explicitly. Captures Python logging, not Spark executor logs.
  Local tests do not establish live workspace delivery.

### Databricks

#### [`databricks/databricks_utils.py`](databricks/databricks_utils.py)

- **Purpose and use:** Read the trigger user and workspace page URL for a
  Databricks job run through the Databricks SDK; execute warehouse DDL with
  `execute_ddl(sql, warehouse_id, *, catalog=None, schema=None, timeout_seconds=1800)`.
  DDL execution waits for success and returns `None`; it does not fetch rows or
  require Spark. Supply a warehouse that supports the requested DDL. Timeout and
  polling failures attempt cancellation without claiming confirmed cancellation.
  In-flight SDK requests can exceed the completion deadline. SDK authentication
  and submission errors propagate; failed execution raises `RuntimeError` and
  an expired deadline raises `TimeoutError`. SQL text is not logged.
- **Job task keys:** `get_job_task_keys(job_id)` returns top-level keys from
  the saved job in API order. Intended for at most 100 tasks; no additional pages
  are requested. Empty tasks return `[]`;
  malformed settings or keys raise. Referenced jobs and loops are not expanded.
- **Canonical module:** `oeds.domain.utils.databricks`.
- **Runtime and restrictions:** Requires standard Databricks workspace
  authentication. Invalid identifiers and SDK lookup failures raise; missing,
  blank, or non-string run metadata properties return `None`.

### Configuration

#### [`config/config_utils.py`](config/config_utils.py)

- **Purpose and use:** Select environment-preferred Python configuration modules
  and text resources with shared-package fallback and optional templating.
- **Canonical import:** `from oeds.domain.utils.config import ConfigManager, ModuleMap`.
- **Public APIs:** `ConfigManager.initialize`, `get_instance`,
  `discover_module_map`, and `load_config_resource`; `ModuleMap`,
  `get_full_module_name`, and `import_module`.
- **Runtime and restrictions:** `initialize` records the process environment and
  invalidates Python import-discovery caches. Each `get_instance(package)` call
  returns a cacheless caller-owned manager. Every `discover_module_map()` call
  returns a new read-only `ModuleMap` from logical names to full dotted module
  names with sorted iteration. Modules are imported only through
  `ModuleMap.import_module`; neither object caches module objects beyond normal
  Python `sys.modules` behavior. Existing managers and maps are not cleared by
  later initialization. Text resources are read on every call, and interactive
  code reloading remains the caller's responsibility.
- **Optional rendering:** `load_config_resource(resource, *, encoding="utf-8",
  params=None)` returns raw text by default. Pass a string-keyed mapping to render
  once with Jinja2, including `{}` for an empty context. Syntax uses `[[ value ]]`,
  `[% blocks %]`, and `[# comments #]`, with strict undefined variables and no
  HTML autoescaping. Invalid context types or keys raise `TypeError`; template
  failures raise `ValueError` with the original Jinja2 exception as the cause.
  Rendering failures do not fall back to shared resources. JSON parsing and
  domain validation remain the caller's responsibility. Jinja2 is declared in
  the bundle's cluster requirements.

### Ingestion

#### [`ingest/ingest_utils.py`](ingest/ingest_utils.py)

- **Purpose and use:** Load packaged ingestion JSON templates or run the complete
  synchronous DataForge ingestion workflow.
- **Canonical module:** `oeds.domain.utils.ingest.ingest_utils`.
- **Public APIs:** `load_config`, `DisConnectionOptions`,
  `FileVerificationOptions`, `IngestTaskResult`, and `run_ingest`.
- **Runtime and restrictions:** Requires prior `ConfigManager` initialization
  and the same Databricks runtime and Azure connection settings as `DisClient`.
  `load_config` reads environment-specific UTF-8 text from `oeds.config.ingest`
  with shared fallback and without rendering it. `run_ingest` accepts exactly
  one config source: `config_file` resolves within
  that package, while `config_template` accepts raw JSON template text. Debug
  mode and verification default to enabled. The function raises
  `IngestTaskError` for any unsuccessful workflow stage and returns only after
  synchronous ingestion and enabled verification succeed. DataBridge validation
  error markers are preserved in `IngestTaskError`; callers can identify the
  failing rule without changing the task-result contract.

#### [`ingest/client/dis_client.py`](ingest/client/dis_client.py)

- **Purpose and use:** Render DataForge `[[ ... ]]` templates, submit and poll a
  cross-workspace DataBridge Databricks job, and optionally verify landed file sizes.
- **Canonical import:** `from oeds.domain.utils.ingest.client.dis_client import DisClient`
- **Public APIs:** `DisClient.resolve_config_template`, `ingest`, and
  `verify_file_by_file_size`; `IngestBaseError`, `IngestValueError`,
  `IngestServiceError`, and `IngestVerifyError`.
- **Runtime and restrictions:** Requires the Databricks runtime `dbutils`, Azure
  service-principal/workspace settings, `DatabricksJobManager`, Jinja, and
  pydantic. `ingest` submits a remote job and can block while polling.
  Verification uses `dbutils.fs.ls`, checks path and byte size only, and treats
  directory-listing failures as unmatched files until success or timeout.

#### [`ingest/client/ingest_result.py`](ingest/client/ingest_result.py)

- **Purpose and use:** Expose normalized job/task state and parse plain or
  `zlib:<base64>` notebook result objects returned by DataBridge.
- **Canonical import:** `from oeds.domain.utils.ingest.client.ingest_result import IngestResult`
- **Public APIs:** Result fields; `get_status`, job/task getters,
  `get_task_notebook_output`, `get_nb_task_result`,
  `get_nb_task_result_dst`, and `get_nb_task_result_dst_path`.
- **Runtime and restrictions:** Uses `DatabricksJobManager` normalization and
  JMESPath queries but does not call Databricks itself. Notebook-output parsing
  is cached; `get_task_notebook_output` returns `None` when parsing fails.

#### [`ingest/client/verify_result.py`](ingest/client/verify_result.py)

- **Purpose and use:** Carry the final file-size verification state and matched
  or unmatched file metadata.
- **Canonical import:** `from oeds.domain.utils.ingest.client.verify_result import VerifyResult`
- **Public API:** Immutable `VerifyResult` fields and `is_success`.
- **Runtime and restrictions:** In-memory only. Status values are uppercase
  `SUCCESS` or `TIMEOUT`.

### Datafile registry and file loading

#### [`datafile/datafile_utils.py`](datafile/datafile_utils.py)

- **Purpose and use:** Discover packaged source-file definitions for callers
  that own path composition and file reading.
- **Canonical import:** `from oeds.domain.utils.datafile import DatafileManager, DatafileRegistry`
- **Public APIs:** `DatafileRegistry`; `DatafileManager.initialize`,
  `get_instance`, `get_module_map`, and `find`.
- **Runtime and restrictions:** Requires prior `ConfigManager` initialization
  for the same environment. `common.py` configures the environment, and every
  successful `initialize()` call replaces an immutable `ModuleMap` snapshot.
  Every `get_instance()` call creates a caller-owned manager that shares that
  snapshot and imports only requested definitions. Active-environment modules
  override shared modules by basename. Callers validate and compose registry
  paths before reading files.

#### [`fileloader/fileloader_utils.py`](fileloader/fileloader_utils.py)

- **Purpose and use:** Run the fixed read, normalize, transform, validate, and
  Delta-write sequence for configured one-file-to-one-table mappings. Use a
  dedicated task for joins, multiple outputs, or broader orchestration.
- **Canonical import:** `from oeds.domain.utils.fileloader import FileLoader, FileLoadMapping, FileLoadNormalization, FileLoadWrite`
- **Public APIs:** The four exported classes; `FileLoader.initialize`,
  `get_instance`, `get_module_map`, `find`, and `load_file`.
- **Runtime and restrictions:** Requires prior `ConfigManager`,
  `SchemaManager`, and `DatafileManager` initialization, plus PySpark, the
  shared strict reader, DataFrame normalization/validation, and Delta update
  utilities. `common.py` does not initialize FileLoader; each consumer calls
  `initialize(env)` before obtaining a caller-owned loader with fresh schema
  and Datafile dependencies. Effective `oeds.config.fileloader` modules use
  active-environment precedence and only the requested mapping is imported.
  Both the mapping ref and storage path are required. Validation gates writes,
  schema evolution is disabled, `replace` mode requires a batch column and
  batch ID, and `_runtime` is reserved in transform context.

### Schema, operation status, and permissions

#### [`schema/schema_utils.py`](schema/schema_utils.py)

- **Purpose and use:** Discover table/view definitions, resolve logical refs to
  runtime-qualified Unity Catalog names, and render configured DDL bodies.
- **Canonical import:** `from oeds.domain.utils.schema.schema_utils import SchemaManager, SchemaRegistry`
- **Public APIs:** `SchemaRegistry.full_name`, `short_name`, `is_table`, `is_view`,
  and `is_materialized_view` (kind `mv`);
  `SchemaManager.initialize`, `get_instance`, `get_module_map`, `resolve_catalog`, `find`,
  `render_table_sql`, and `render_view_sql`.
- **Runtime and restrictions:** Requires prior `ConfigManager` initialization
  for the same environment. Effective `oeds.config.schema` modules use
  active-environment precedence and require PySpark schema types. It does not
  execute SQL. Table rendering permits only the `{schema}` placeholder and
  validates identity-column and SQL-default metadata; view placeholders must
  name other schema refs. Each `common.py` run replaces the immutable
  `ModuleMap` snapshot, and every `get_instance()` call creates a caller-owned
  manager. Definitions are imported and validated only when requested by
  reference. `initialize(env, catalog_mapping=..., default_catalog=...)` requires
  a non-empty physical default catalog for definitions that omit `catalog`.
  Explicit catalog values use their mappings or `{env}_{catalog}`. The default
  is trimmed, never prefixed, and retained in each manager snapshot. `common.py`
  supplies it from the job context's `catalog`. Explicit `None` or blank catalogs
  remain invalid.
  String bindings are trimmed and copied into read-only snapshots retained by
  existing managers after reinitialization. Catalog names are not validated;
  callers supply trusted names compatible with unquoted SQL. The last entry
  wins when mapping keys become identical after trimming.
  `common.py` maps all four domain catalogs plus metadata, reference, application,
  and internal source catalogs to their corresponding job-context catalog
  parameters. `application_cat` uses `application_catalog`. View destinations
  and logical references share this resolution; hardcoded SQL is not rewritten.

#### [`schema/schema_deployment_utils.py`](schema/schema_deployment_utils.py)

- **Purpose and use:** Execute the DDL rendered by `SchemaManager` during a
  controlled release.
- **Canonical import:** `from oeds.domain.utils.schema.schema_deployment_utils import SchemaDeploymentManager`
- **Public APIs:** `initialize`, `get_instance`, `create_table`,
  `create_view`, `create_materialized_view`, and `refresh_materialized_view`.
- **Runtime and restrictions:** Table/view execution lazily creates or reuses
  Spark. Materialized views require kind `mv` and use `execute_ddl` when given a
  nonblank warehouse ID, otherwise an existing supported serverless Spark session.
  `timeout_seconds` applies only to warehouse execution. Refresh uses `SYNC`,
  with optional `full=True`; keep the creation compute type for refresh.
  Both materialized-view methods return `None` and propagate execution failures.
  No warehouse is inferred from job context; callers supply
  `ctx["sql_warehouse_serverless_large_id"]` when desired.
  `initialize(env)` returns the manager class so callers can chain `.get_instance()`. Views are always created or replaced;
  table and materialized-view `replace` and `if_not_exists` options are mutually
  exclusive.
- **Example:** [Materialized view](../../../../examples/schema/materialized_view.py).

#### [`operation/operation_utils.py`](operation/operation_utils.py)

- **Purpose and use:** Append successful dataset-operation records, lazily
  query the configured Delta table, or eagerly retrieve one typed latest
  record. Any stored row represents success.
- **Canonical import:** Import `OperationStatusManager`,
  `OperationStatusRecord`, `RegexFilter`, and `TimeFilter` from
  `oeds.domain.utils.operation`.
- **Public APIs:** The four exported types; `OperationStatusManager`,
  `record_status`, `find_statuses`, `find_latest_status`, and
  `resolve_dependency`.
- **Runtime and restrictions:** The manager is not shared. Construction accepts
  a logical table ref and resolves it through the current `SchemaManager`.
  Successful-operation writes extract the deployed schema and
  append one row with a Spark timestamp; writes are not deduplicated or
  retried. Queries are lazy and combine optional filters with AND. They return
  only the newest match by default; pass `latest_only=False` to return all
  matches with newest records first. `find_latest_status` is eager and returns
  the newest match as `OperationStatusRecord`, or `None` when no row matches.
  `resolve_dependency` eagerly returns the matching successful record or
  `None` when no record matches.

#### [`permission/permission_utils.py`](permission/permission_utils.py)

- **Purpose and use:** Apply direct `SELECT` grants to configured tables and
  views without expanding view dependencies; retain table-only `MODIFY` grants.
- **Canonical import:** `from oeds.domain.utils.permission import PermissionManager`.
- **Public APIs:** `initialize`, `get_instance`, `get_registry`, and
  `apply_permissions(schema=None, execute=True, *, config_file=None)`.
- **Runtime and restrictions:** Requires prior `ConfigManager` and `SchemaManager`
  initialization and Spark. Each `get_instance()` creates a caller-owned manager.
  Loads `oeds.config.permission` with environment-first resources and group
  aliases; alternate files apply only to the current operation. Processes every
  selected entry regardless of catalog. Configuration uses `groups` and
  `permissions`; object names resolve through SchemaManager's catalog bindings.
  Read grants do not inspect live metadata or view definitions; write grants
  check object type and reject views. Preview logs SQL without executing grants
  and does not prove read-target existence or grant authority. Errors propagate;
  earlier grants may remain applied after a later failure. No grants are revoked.
  Consumers must use compatible compute as described in the permission guide.
  The release example uses `default.json` and `execute=True`.

### Email, calendar, and reference data

#### [`email/email_utils.py`](email/email_utils.py)

- **Purpose and use:** Send registry-based or direct HTML messages, including
  transport-neutral attachments, through Logic App, Microsoft Graph, or a
  synchronous DataBridge email job.
- **Canonical import:** `from oeds.domain.utils.email import EmailManager`
- **Public APIs:** `EmailProvider`, `initialize`, `get_instance`,
  `get_email_registry`, `df_to_email_table`, `send_email`, and
  `send_direct_email`.
- **Runtime and restrictions:** Requires prior `ConfigManager` initialization.
  Email registry JSON and HTML templates use environment-specific resources
  with shared fallback. Every registry lookup reloads the JSON, and every send
  reloads both the registry and template. `initialize` stores one normalized
  configuration without creating a ConfigManager or transport; every
  `get_instance()` call creates a caller-owned manager, and every send creates
  a fresh provider client. Graph sends do not reuse Azure Identity's in-memory
  token cache, and credential cleanup relies on object finalization. Sending
  performs external I/O. PySpark DataFrames are collected with `toPandas`; raw
  string variables and direct HTML bodies are not HTML escaped. Graph direct
  attachments must be smaller than 3 MiB. Recipient address syntax is not
  validated, and email send methods return `None`.
- **DataBridge provider:** Opt in with `provider="databridge"`; existing providers
  remain unchanged. Its transport lives in
  [`email/databridge_email_client.py`](email/databridge_email_client.py).
  `connection.ingest_config_file` selects a packaged ingestion template separately
  from the email registry. Attachments require a shared Volume and use
  `<tmp_root>/<job_run_id>/<guid>/`. Submission uses `run_ingest` without file
  verification; all staged files remain for externally managed lifecycle cleanup.
  The DataBridge server trims inline body edges and does not guarantee attachment
  completeness. See the [email guide](../../../../docs/guide/G303-email-developer-guide.md#databridge-provider)
  and [example](../../../../examples/email/send_email_databridge.py).

#### [`calendar/calendar_utils.py`](calendar/calendar_utils.py)

- **Purpose and use:** Configure and create caller-owned workflow calendars.
- **Canonical import:** `from oeds.domain.utils.calendar import CalendarManager`
- **Public APIs:** `initialize` and `get_instance`.
- **Runtime and restrictions:** `common.py` registers one holiday group and
  timezone per driver without loading data. Each `get_instance()` call creates a
  new ReferenceManager, loads holidays with a contains match, and returns a new
  immutable `CalendarUtils`. An empty holiday group skips the reference query.

#### [`reference/reference_utils.py`](reference/reference_utils.py)

- **Purpose and use:** Load holiday dates used to create workflow calendars and
  LEI organization reference data.
- **Canonical import:** `from oeds.domain.utils.reference.reference_utils import ReferenceManager`
- **Public APIs:** `initialize`, `get_instance`, `get_holidays`, and `get_leis`.
- **Runtime and restrictions:** `common.py` configures the active reference
  catalog, and each `get_instance()` call creates a caller-owned manager.
  Initialization does not access Spark; `get_holidays` creates or reuses a Spark
  session, queries the reference catalog's standardized
  date/observance/holiday tables, and collects distinct dates to the driver.
  Matching is case-insensitive containment by default; pass `exact=True` for
  equality. `get_leis` creates or reuses a Spark session and returns the
  reference catalog's curated `tbl_itm_lei_organizations` table as a lazy Spark
  DataFrame without collecting it to the driver.

### Time series

#### [`timeseries/timeseries_utils.py`](timeseries/timeseries_utils.py)

- **Purpose and use:** Preferred project-facing facade for packaged dataset and
  series registration under configured providers and observation writes.
- **Canonical import:** `from oeds.domain.utils.timeseries import TimeSeriesUtils`;
  import `TimeSeriesObservation` only when callers want an explicit type annotation.
- **Public APIs:** `TimeSeriesObservation`; `register_time_series`,
  `write_observations`, and `publish_to_webmart`.
- **Runtime and restrictions:** Requires prior `ConfigManager` initialization,
  time-series metadata tables, and Spark/Delta. `register_time_series` loads an
  environment-specific packaged JSON config with shared fallback and renders it
  through `ConfigManager` with client-supplied parameters. It expects fully
  qualified destination table names. Provider, dataset, and series entries may
  set boolean `create` to
  `false` to skip their registration independently. Enabled registration deletes
  matching entries before recreating them; providers are identified by
  `short_name_en`. Time-series writes accept a sequence of `TimeSeriesObservation`
  mappings. Each mapping requires `time_series_name` and `value`; optional `date`
  and `missing_value_label` values override the current local date and `"ND"`
  defaults. Writes create a batch audit record and compare numeric and string
  values against the greatest `update_date` for each normalized
  `(time_series_name, UTC calendar date)`, ignoring the stored time of day.
  Calendar-date extraction uses the existing Spark session timezone, expected
  to be UTC; writes do not change that setting. Supplied dates use UTC midnight.
  The temporary calendar-date comparison column is not persisted.
  The write path supports serverless without Spark caching: changed rows are
  collected once and reused for the append and transaction logging. Submitted
  batches and their changed rows must fit in client memory.
  New and changed observations are appended;
  unchanged observations are skipped and historical rows are preserved.
  Transaction-log entries are appended only for series with appended rows.
  An unchanged batch still returns its audit key. The bounded CSV loader under
  `tools/load_timeseries_observations.py` converts configured source columns and
  the `ND`, `NA`, and `NC` missing-value labels into one observation batch. The AE
  time-series
  standard publishes registered transaction-log changes to WebMart automatically.
  `publish_to_webmart` remains available for special cases that require manual
  publishing; it accepts Datamart endpoints and service-principal credentials at
  call time.

#### [`timeseries/time_series_manager.py`](timeseries/time_series_manager.py)

- **Purpose and use:** Low-level time-series metadata, observation, audit, and
  HTTP publishing implementation. Prefer `TimeSeriesUtils` for normal project
  workflows.
- **Canonical import:** `from oeds.domain.utils.timeseries.time_series_manager import Freq, TimeSeriesCollection, TimeSeriesManager`
- **Public APIs:** `Freq`; `TimeSeriesCollection.add`,
  `get_unique_time_series_names`, and `to_list`; provider/dataset/series
  lookup, registration, and deletion methods on `TimeSeriesManager`;
  `create_audit_log`, `insert_observations`, deprecated
  `upsert_observations`, and
  `publish_batch_to_datamart`.
- **Runtime and restrictions:** Creates a Spark session and reads or mutates
  metadata, audit, transaction, and destination Delta tables. Registration
  requires referenced providers/datasets to exist and rejects duplicates;
  provider deletion identifies records by `short_name_en`.
  Normal writes rely on automatic WebMart publishing from the transaction log.
  The manual publishing API obtains scoped tokens and stops at the first HTTP
  200 response.

## Known coverage gaps

- Time-series utilities do not have a dedicated developer guide. Their current
  context is limited to examples and release/template guides.
- Ingestion and reference-data utilities do not have dedicated files under
  `examples`; the ingest task and shared initialization are the available usage
  context.
- The ingestion result modules lack module and public-method docstrings.
  Several utility methods and `SchemaRegistry` properties, plus `Freq`, also
  lack docstrings. The empty `ingest`, `ingest.client`,
  `reference`, and `schema` package initializers lack package docstrings.
- `DisClient.verify_file_by_file_size` describes lowercase result statuses in
  one docstring although `VerifyResult` uses uppercase values.
