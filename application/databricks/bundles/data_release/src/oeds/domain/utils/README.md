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
| Databricks job-run metadata | [`databricks.databricks_utils`](databricks/databricks_utils.py) | `get_job_run_trigger_user`, `get_job_run_page_url` | [Integration tests](../../../../docs/guide/G401-integration-test-guide.md) | [Testbench task](../../../../jobs/service/tasks/testbench.py) | — |
| Environment-aware configuration | [`config.config_utils`](config/config_utils.py) | `ConfigManager`, `ModuleMap` | — | [Load a text resource](../../../../examples/config/load_config_resource.py), [bootstrap initialization](../../../../common.py) | — |
| Ingestion configuration and workflow | [`ingest.ingest_utils`](ingest/ingest_utils.py) | `load_config`, `DisConnectionOptions`, `FileVerificationOptions`, `IngestTaskResult`, `run_ingest` | [DataBridge client](../../../../docs/guide/G220-ingest-client-guide.md) | [Ingest task](../../../../jobs/dataflow/task_10_ingest.py) | — |
| Ingestion client and results | [`ingest.client.dis_client`](ingest/client/dis_client.py) | `DisClient`, `IngestResult`, `VerifyResult`, typed ingest exceptions | [DataBridge client](../../../../docs/guide/G220-ingest-client-guide.md) | [Ingest task](../../../../jobs/dataflow/task_10_ingest.py) | — |
| Datafile registry | [`datafile.datafile_utils`](datafile/datafile_utils.py) | `DatafileManager`, `DatafileRegistry` | [Datafile](../../../../docs/guide/G225-datafile-developer-guide.md) | [Registry lookup](../../../../examples/datafile/datafile_manager.py) | — |
| File loading | [`fileloader.fileloader_utils`](fileloader/fileloader_utils.py) | `FileLoader`, mapping dataclasses | [Fileloader](../../../../docs/guide/G226-fileloader-developer-guide.md) | [Load sample file](../../../../examples/fileloader/load_sample_file.py) | — |
| Schema registry | [`schema.schema_utils`](schema/schema_utils.py) | `SchemaManager`, `SchemaRegistry` | [Schema](../../../../docs/guide/G211-schema-guide.md) | [Registry lookup](../../../../examples/schema/schema_manager.py) | — |
| Schema deployment | [`schema.schema_deployment_utils`](schema/schema_deployment_utils.py) | `SchemaDeploymentManager` | [Schema](../../../../docs/guide/G211-schema-guide.md) | [Create tables](../../../../examples/release/release-0.0.0-11-create-tables.py), [create views](../../../../examples/release/release-0.0.0-12-create-views.py) | — |
| Operation status | [`operation.operation_utils`](operation/operation_utils.py) | `OperationStatusManager` | [Operation status](operation/README.md) | — | — |
| Unity Catalog permissions | [`permission.permission_utils`](permission/permission_utils.py) | `PermissionManager` | [Permissions](../../../../docs/guide/G212-schema-permission-guide.md) | [Apply permissions tool](../../../../tools/apply_permissions.py) | — |
| Email | [`email.email_utils`](email/email_utils.py) | `EmailManager`, `EmailProvider` | [Email](../../../../docs/guide/G303-email-developer-guide.md) | [Send email](../../../../examples/email/send_email.py) | — |
| Configured calendar | [`calendar.calendar_utils`](calendar/calendar_utils.py) | `CalendarManager` | [Calendar](../../../../docs/guide/G301-calendar-guide.md) | [Main task](../../../../jobs/dataflow/task_00_main.py) | — |
| Reference calendar data | [`reference.reference_utils`](reference/reference_utils.py) | `ReferenceManager` | [Calendar](../../../../docs/guide/G301-calendar-guide.md) | [Bootstrap configuration](../../../../common.py) | — |
| Time series | [`timeseries.timeseries_utils`](timeseries/timeseries_utils.py) | `TimeSeriesObservation`, `TimeSeriesUtils`; low-level `Freq`, `TimeSeriesCollection`, `TimeSeriesManager` | [Release workflow](../../../../docs/guide/G111-release-guide.md) | [Register](../../../../examples/timeseries/register_timeseries.py), [insert observations](../../../../examples/timeseries/insert_timeseries_observation.py), [load observation CSV](../../../../tools/load_timeseries_observations.py) | — |
| Testbench orchestration | [`testbench`](testbench/__init__.py) | `TestbenchRunner` | [Integration tests](../../../../docs/guide/G401-integration-test-guide.md) | [Testbench task](../../../../jobs/service/tasks/testbench.py) | — |
| Integration-test configuration | [`testbench.config`](testbench/config/__init__.py) | `load_test_case` | [Integration tests](../../../../docs/guide/G401-integration-test-guide.md) | [Testbench task](../../../../jobs/service/tasks/testbench.py) | — |
| Integration-test artifacts | [`testbench.artifact`](testbench/artifact/__init__.py) | `TableArtifactExport`, `TableArtifactExporter` | [Integration tests](../../../../docs/guide/G401-integration-test-guide.md) | [Export artifacts tool](../../../../tools/testbench_export_artifacts.py), [example case](../../../../examples/testbench/cases/default.json) | — |
| Integration-test environment | [`testbench.environment`](testbench/environment/__init__.py) | `ResourceUtils` | [Integration tests](../../../../docs/guide/G401-integration-test-guide.md) | [Testbench task](../../../../jobs/service/tasks/testbench.py), [manual teardown](../../../../tools/testbench_teardown.py) | — |
| Integration-test validation | [`testbench.validation`](testbench/validation/__init__.py) | `Validator`, `TableEqualsFileValidator`, `ValidationRunner` | [Integration tests](../../../../docs/guide/G401-integration-test-guide.md) | [Testbench task](../../../../jobs/service/tasks/testbench.py) | — |

## Capability notes

Guide, example, and test links in the capability table apply to the modules
grouped below.

### Databricks

#### [`databricks/databricks_utils.py`](databricks/databricks_utils.py)

- **Purpose and use:** Read the trigger user and workspace page URL for a
  Databricks job run through the Databricks SDK.
- **Canonical module:** `oeds.domain.utils.databricks`.
- **Runtime and restrictions:** Requires standard Databricks workspace
  authentication. Invalid identifiers and SDK lookup failures raise; missing,
  blank, or non-string response properties return `None`.

### Configuration

#### [`config/config_utils.py`](config/config_utils.py)

- **Purpose and use:** Select environment-preferred Python configuration modules
  and text resources with shared-package fallback.
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
  synchronous ingestion and enabled verification succeed.

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
  environment-qualified Unity Catalog names, and render configured DDL bodies.
- **Canonical import:** `from oeds.domain.utils.schema.schema_utils import SchemaManager, SchemaRegistry`
- **Public APIs:** `SchemaRegistry.full_name`, `is_table`, and `is_view`;
  `SchemaManager.initialize`, `get_instance`, `get_module_map`, `find`,
  `render_table_sql`, and `render_view_sql`.
- **Runtime and restrictions:** Requires prior `ConfigManager` initialization
  for the same environment. Effective `oeds.config.schema` modules use
  active-environment precedence and require PySpark schema types. It does not
  execute SQL. Table rendering permits only the `{schema}` placeholder and
  validates identity-column and SQL-default metadata; view placeholders must
  name other schema refs. Each `common.py` run replaces the immutable
  `ModuleMap` snapshot, and every `get_instance()` call creates a caller-owned
  manager. Definitions are imported and validated only when requested by
  reference.

#### [`schema/schema_deployment_utils.py`](schema/schema_deployment_utils.py)

- **Purpose and use:** Execute the DDL rendered by `SchemaManager` during a
  controlled release.
- **Canonical import:** `from oeds.domain.utils.schema.schema_deployment_utils import SchemaDeploymentManager`
- **Public APIs:** `initialize`, `get_instance`, `create_table`, and
  `create_view`.
- **Runtime and restrictions:** Creates or reuses an active Spark session and
  executes Unity Catalog DDL. `initialize(env)` returns the manager class so
  callers can chain `.get_instance()`. Views are always created or replaced;
  table `replace` and `if_not_exists` options are mutually exclusive.

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

- **Purpose and use:** Resolve packaged environment/group permission config and
  grant `SELECT` or `MODIFY` on configured Unity Catalog objects.
- **Canonical import:** `from oeds.domain.utils.permission import PermissionManager`
- **Public APIs:** `initialize`, `get_instance`, `get_registry`,
  `built_view_dept`, and `apply_permissions`.
- **Runtime and restrictions:** Each consumer calls `initialize(env)` before
  `get_instance()`; the permissions tool owns this lifecycle. Every getter
  creates a caller-owned manager. Requires prior `ConfigManager`
  initialization for the same environment.
  Permission JSON is loaded from `oeds.config.permission` with
  active-environment precedence and shared fallback; alternate files are
  selected per registry or apply operation.
  Requires Spark and live Unity Catalog metadata. View dependencies are
  inferred from fully qualified names in `SHOW CREATE TABLE` output and limited
  to configured catalogs. Write grants are rejected for views. `execute=False`
  suppresses `GRANT` execution but still queries live objects and logs the
  prepared SQL; statements are not returned.

### Email, calendar, and reference data

#### [`email/email_utils.py`](email/email_utils.py)

- **Purpose and use:** Send registry-based or direct HTML messages, including
  transport-neutral attachments, through a configured Logic App or Microsoft
  Graph transport.
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

#### [`calendar/calendar_utils.py`](calendar/calendar_utils.py)

- **Purpose and use:** Configure and create caller-owned workflow calendars.
- **Canonical import:** `from oeds.domain.utils.calendar import CalendarManager`
- **Public APIs:** `initialize` and `get_instance`.
- **Runtime and restrictions:** `common.py` registers one holiday group and
  timezone per driver without loading data. Each `get_instance()` call creates a
  new ReferenceManager, loads holidays with a contains match, and returns a new
  immutable `CalendarUtils`. An empty holiday group skips the reference query.

#### [`reference/reference_utils.py`](reference/reference_utils.py)

- **Purpose and use:** Load holiday dates used to create workflow calendars.
- **Canonical import:** `from oeds.domain.utils.reference.reference_utils import ReferenceManager`
- **Public APIs:** `initialize`, `get_instance`, and `get_holidays`.
- **Runtime and restrictions:** `common.py` configures the active reference
  catalog, and each `get_instance()` call creates a caller-owned manager.
  Initialization does not access Spark; `get_holidays` creates or reuses a Spark
  session, queries the reference catalog's standardized
  date/observance/holiday tables, and collects distinct dates to the driver.
  Matching is case-insensitive containment by default; pass `exact=True` for
  equality.

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
  environment-specific packaged JSON config with shared fallback, renders it
  with client-supplied parameters, and expects fully qualified destination table
  names. Provider, dataset, and series entries may set boolean `create` to
  `false` to skip their registration independently. Enabled registration deletes
  matching entries before recreating them; providers are identified by
  `short_name_en`. Time-series writes accept a sequence of `TimeSeriesObservation`
  mappings. Each mapping requires `time_series_name` and `value`; optional `date`
  and `missing_value_label` values override the current local date and `"ND"`
  defaults. Writes create an audit record, append each observation as a new
  record, and append a transaction log. The bounded CSV loader under
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

### Integration-test support

#### [`testbench`](testbench/)

- **Purpose and use:** Execute one Testbench case through load, setup, run,
  validation, teardown, and report stages while retaining service, case, and
  target-job state in one context.
- **Canonical import:** `from oeds.domain.utils.testbench import RunnerContext,`
  `TestbenchRunner`; reporting is available from
  `oeds.domain.utils.testbench.report import ReportUtils`.
- **Public API:** `TestbenchRunner(dataset=..., case_name=..., case_root=...,`
  `args=None, service_job_ctx=...).execute()`, returning the absolute
  execution-log path; `RunnerContext`; and `ReportUtils.compose_subject`,
  `compose_body`, and `report`.
- **Runtime and restrictions:** Accepts `skip_setup`, `skip_run`,
  `skip_validate`, and `skip_teardown` as binary integers or booleans in `args`.
  It writes propagated Python logs directly beneath `case_root/logs`, preserves
  the first lifecycle failure while attempting teardown and reporting, and does
  not receive a Spark session. Reporting always logs a concise status and sends
  one direct email when the service run creator is available. Delivery failures
  do not change the case result. These APIs submit jobs, may send email, and may
  create or remove live Unity Catalog resources.

#### [`testbench/config`](testbench/config/)

- **Purpose and use:** Validate and load a Volume-backed integration-test case
  JSON config by name.
- **Canonical import:** `from oeds.domain.utils.testbench.config import`
  `load_test_case`.
- **Public API:** `load_test_case(case_name, case_root, context=None)`, returning
  the merged and case-variable-resolved JSON config as a dictionary.
- **Runtime and restrictions:** Requires an absolute Unity Catalog Volume
  `case_root` and resolves `cases/<case_name>.json` beneath it. The config is
  loaded through Common's `load_json_config`, including relative `extends`
  inheritance, then applies non-null string values from the optional context to
  matching declared `variables` before one Jinja2 render pass over the merged
  JSON document. Missing and null context values retain case defaults; unrelated
  keys are ignored, and empty strings are explicit overrides. Variable defaults
  must be literal strings. References inside definitions and undefined
  `{{ name }}` config references raise `ValueError`; invalid containers,
  defaults, and matching context value types raise `TypeError`. Case definitions
  and test data share the run's `case_root` path in a Unity Catalog Volume.

#### [`testbench/artifact`](testbench/artifact/)

- **Purpose and use:** Export configured Spark SQL results as a Testbench setup
  fixture or expected dataset.
- **Canonical import:** `from oeds.domain.utils.testbench.artifact import`
  `TableArtifactExporter`.
- **Public APIs:** `TableArtifactExporter(case_root=..., spark=None)`,
  `export_configured_artifact(test_config=..., artifact_name=...,`
  `overwrite=False)`, and `export_sql(sql=..., output_path=...,`
  `export_mode="data", overwrite=False)`, returning `TableArtifactExport`.
- **Runtime and restrictions:** Validates the case's complete top-level
  `artifacts` list and writes Parquet only beneath `fixtures/` or `expected/`
  in an absolute Unity Catalog Volume `case_root`. `schema` mode exports a
  zero-row DataFrame retaining the SQL result schema; `data` mode exports the
  complete result and schema. SQL is passed directly to Spark and may have side
  effects. Existing output is rejected unless `overwrite=True`.

#### [`testbench/environment`](testbench/environment/)

- **Purpose and use:** Materialize and tear down the Unity Catalog environment
  and fixture files described by an integration-test config.
- **Canonical import:** `from oeds.domain.utils.testbench.environment`
  `import ResourceUtils`.
- **Public APIs:** `create_resources`, `drop_resources`, `drop_all`; schema,
  table, volume, and file create/drop helpers; `resolve_test_path`,
  `spark_source_path`, `local_source_path`, and `spark_option_value`.
- **Runtime and restrictions:** Accepts an absolute `/Volumes/...` `case_root`,
  obtains the active Spark session internally, and reads
  `environment.catalogs` plus top-level `setup` and `teardown`. Relative file,
  table-source, and expected-result paths resolve beneath `case_root`; absolute,
  URI-style, backslash, and parent traversal paths are rejected. Volume
  destinations use `to`. Table data must be Parquet and conventionally live
  under `fixtures/<table>/`; input data lives under `inputs/`, and expected data
  uses `expected/<verification-name>/`. These APIs create, replace,
  upload, and delete live Unity Catalog resources. `drop_all` force-deletes
  managed catalogs; for a shared catalog (`create: false`), it drops every
  schema in that catalog. The manual teardown tool reloads a selected case with
  its original variable arguments and calls the safer `drop_resources` method.

#### [`testbench/validation/validator.py`](testbench/validation/validator.py)

- **Purpose and use:** Define the interface for integration-result validators.
- **Canonical import:** `from oeds.domain.utils.testbench.validation import Validator`
- **Public API:** `Validator.validate`, which subclasses must implement.
- **Runtime and restrictions:** Requires a Spark session and raises
  `NotImplementedError` in the base class.

#### [`testbench/validation/table_equals_file.py`](testbench/validation/table_equals_file.py)

- **Purpose and use:** Assert exact equality between a Unity Catalog table and
  an expected CSV, Parquet, or Delta dataset.
- **Canonical import:** `from oeds.domain.utils.testbench.validation import TableEqualsFileValidator`
- **Public API:** `validate`.
- **Runtime and restrictions:** Reads the live table and expected files, can
  filter the actual table and ignore configured columns, and runs several Spark
  actions. Column names/types, counts, duplicates, missing rows, and unexpected
  rows must match; mismatches raise `AssertionError`.

#### [`testbench/validation/validation_utils.py`](testbench/validation/validation_utils.py)

- **Purpose and use:** Dispatch enabled validation entries from the integration
  config.
- **Canonical import:** `from oeds.domain.utils.testbench.validation import ValidationRunner`
- **Public API:** `run`.
- **Public construction:** `ValidationRunner(spark=None)` obtains the active
  Spark session when no session is supplied.
- **Runtime and restrictions:** Currently registers only `table_equals_file`.
  Invalid or unknown config raises `ValueError`, and validator failures
  propagate.

## Known coverage gaps

- Testbench orchestration has focused unit coverage. Other DataForge utilities
  do not have committed Python unit tests, and integration case definitions and
  fixture data share the configuration Volume.
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
