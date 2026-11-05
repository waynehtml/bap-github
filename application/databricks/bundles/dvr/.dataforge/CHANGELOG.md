# DataForge Changelog

## 1.16.0 - 2026-10-14

Release tag: `releases/dataforge-v1.16.0`

### Major updates

- Add regular/default and high performance job cluster selection during initialization using one environment-specific policy variable.
- Rename `connection.email_config_file` to `connection.ingest_config_file`; existing custom configurations must update this setting.
- Exclude Hadoop checksum sidecars from email attachments.
- Correct the development DataBridge email sender address.

## 1.15.0 - 2026-10-09

Release tag: `releases/dataforge-v1.15.0`

### Major updates

- Add an optional DataBridge email provider while preserving existing EmailManager interfaces and providers.
- Add environment-specific email settings, shared temporary storage, and an initialization example.
- Support inline email bodies and Volume-staged attachments, with synchronous job completion and lifecycle-managed file retention.

## 1.14.0 - 2026-10-03

Release tag: `releases/dataforge-v1.14.0`

### Major updates

- Rebuild the app starter with reusable SQL/job clients and flat environment settings; existing app imports and configuration require migration.
- Move app configuration into bundle resources with secret bindings and target-specific management permissions.
- Organize deployment scripts and enable app secret-access repair before deployment and app startup afterward.
- Expose the classic medium SQL warehouse through OEDS secret-key configuration and job context.
- Move DataBench configuration paths to `databench_db`, organized by project domain and dataset.

## 1.13.0 - 2026-10-01

Release tag: `releases/dataforge-v1.13.0`

### Major updates

- Add classic runtime 16.4 and 17.3 central configuration choices that use Nexus when no wheelhouse is available.

## 1.12.0 - 2026-09-28

Release tag: `releases/dataforge-v1.12.0`

### Major updates

- Add configurable pre/post-deployment scripts and development DataBench configuration publishing.
- Align compute initialization with DataBoot configurations and improve serverless compatibility.
- Add optional configuration templating and use it for time-series registration.
- Append only new or changed time-series observations, comparing calendar dates and preserving history.

## 1.11.0 - 2026-09-24

Release tag: `releases/dataforge-v1.11.0`

### Major updates

- Add local classic, central classic and central serverless compute choices.
- Move integration settings to OEDS secret-key parameters; existing projects must migrate integration and compute configuration.
- Make project initialization one-time, removing copied YAML templates after successful validation.
- Replace local wheelhouse setup with direct Nexus installation and remove legacy cluster tooling.
- Adjust SDK and protobuf requirements.
- Refresh DataKit references to 2.2.0.

## 1.10.0 - 2026-09-21

Release tag: `releases/dataforge-v1.10.0`

### Major updates

- Make direct object grants the canonical permission workflow, remove the old tool and temporary `permission2` package, and add a release notebook.
- Add OTLP logging to Zerobus with Entra authentication and corrected workspace-ID handling.
- Add `get_job_task_keys()` for inspecting saved job tasks.
- Raise the minimum Databricks SDK version to `0.140.0`.

## 1.9.1 - 2026-09-10

Release tag: `releases/dataforge-v1.9.1`

### Major updates

- Add `job_run_curate` to support integration-only runs using existing curated data while preserving dependency checks, early stops, and failure handling.

## 1.9.0 - 2026-09-10

Release tag: `releases/dataforge-v1.9.0`

### Major updates

- Add materialized-view creation and synchronous refresh using SQL warehouses or supported serverless compute.
- Add `execute_ddl` for SQL warehouse execution.
- Add `SchemaRegistry.short_name` for two-part object names.
- Add a project release-tagging workflow.

## 1.8.2 - 2026-09-09

Release tag: `releases/dataforge-v1.8.2`

### Major updates

- Add paused weekday 10 a.m. schedules for DATAFLOW, OPERATION, and CURATION, independently managed per environment.
- Include full release changelog sections in annotated release tags.

## 1.8.1 - 2026-09-09

Release tag: `releases/dataforge-v1.8.1`

### Major updates

- Add runtime catalog mappings and require `default_catalog` for `SchemaManager`.
- Rename job-context keys `metadata_cat` and `reference_cat` to `metadata_catalog` and `reference_catalog`; existing callers must migrate.
- Add ingestion-configuration and project-release skills.
- Expose environment-specific serverless large SQL warehouse IDs through shared task parameters and job context.
- Refresh DataBridge references for missing-input handling and identifiable file-validation errors.

## 1.8.0 - 2026-09-04

Release tag: `releases/dataforge-v1.8.0`

### Major updates

- Add `ReferenceManager.get_leis()` to load LEI organization reference data as a Spark DataFrame.
- Refresh DataBridge references with HTTP configuration guides and authentication, download, and upload examples.

## 1.7.0 - 2026-09-02

Release tag: `releases/dataforge-v1.7.0`

### Major updates

- Removed the embedded TestBench implementation, configuration, service task,
  tools, examples, and documentation now that integration testing is owned by
  DataBench.
- Granted the environment-specific OED data-services principal permission to
  run jobs across all supported DataForge domain profiles.
- Expanded project initialization and workflow-selection guidance for
  ingestion, curation, and integration components with independent ownership
  and release lifecycles.

## 1.6.0 - 2026-08-31

Release tag: `releases/dataforge-v1.6.0`

### Major updates

- Replaced the legacy Integrify workflow and integration-test package paths
  with Testbench and its structured load, setup, run, validate, teardown, and
  report lifecycle.
- Added Volume-backed Testbench case management with default case-root
  configuration, runtime variable overrides, reusable environment setup, and
  table-to-artifact validation.
- Added SQL-driven artifact export and manual teardown tools for preparing
  fixtures, expected results, and recovering from skipped or failed cleanup.
- Added runner context and HTML email reporting, including direct email
  delivery to valid run-trigger users and Databricks job-run metadata links.
- Centralized environment-specific catalog configuration and expanded
  Testbench developer documentation and examples.

## 1.5.0 - 2026-08-28

Release tag: `releases/dataforge-v1.5.0`

### Major updates

- Standardized configurable managers around caller-owned instances,
  reference-driven discovery, module maps, and chainable
  `initialize(...).get_instance()` lifecycles.
- Aligned `SchemaDeploymentManager` with the shared initialization and
  instance-construction pattern.
- Moved datafile path composition to callers and added optional
  `file_base_uri` support throughout FileLoader tooling, examples, jobs, and
  documentation.
- Improved manager initialization consistency with atomic configuration,
  stateless discovery, and deferred registry loading.

## 1.4.0 - 2026-08-27

Release tag: `releases/dataforge-v1.4.0`

### Major updates

- Added shared environment-aware configuration discovery and resource loading,
  initialized automatically by the common notebook and adopted across
  DataForge utilities.
- Added a shared `PermissionManager` lifecycle with environment-aware registry
  loading and per-operation configuration selection.
- Namespaced DataForge provenance under `.dataforge/` and strengthened
  initialization, upgrade, release, and tag workflows, including Azure DevOps
  tag publishing.

## 1.3.0 - 2026-08-26

Release tag: `releases/dataforge-v1.3.0`

### Major updates

- Added an optional DataFlow integration stage with independent rerun control,
  downstream-delivery guidance, and completion/failure routing.
- Standardized initialized and refreshed job display names to uppercase and
  aligned template development defaults with current integration settings.
- Added guarded workflows for preparing releases, publishing annotated release
  tags, and upgrading managed files in generated DataForge projects.

## 1.2.2 - 2026-08-24

Release tag: `dataforge-v1.2.2`

### Major updates

- Expanded time-series management with provider lifecycle controls, insert-only
  observation batches, transaction-log-driven publishing, per-record dates and
  missing-value labels, and a bounded CSV loading tool.
- Added guided DataForge skills for creating schema-backed Delta tables and
  views.
- Simplified ingestion execution through the shared runner and improved failure
  diagnostics.
- Standardized audit timestamp column names across configuration, jobs,
  examples, and documentation.
- Adopted DataKit and DataBridge naming throughout template guidance and
  reference locations while preserving legacy runtime compatibility contracts.

## 1.2.1 - 2026-08-18

Release tag: `dataforge-v1.2.1`

### Major updates

- Added BAP domain configuration with environment-specific run identities,
  shared OEDS secret scope, and service-principal key mappings.
- Expanded project initialization so domain files can override declared
  non-project variables after inferred defaults while explicit developer values
  retain highest precedence.

## 1.2.0 - 2026-08-18

Release tag: `dataforge-v1.2.0`

### Major updates

- Made DATAFLOW, CURATION, SERVICE, and OPERATION independently selectable
  through metadata-driven project initialization.
- Separated Databricks App and job deployment while reorganizing the shared
  Azure DevOps deployment pipelines and project-specific connections.
- Added reusable ingestion execution, curation modes, outbound paths, and
  common file-writing support.
- Added operation success tracking and dependency checks for coordinating
  dataflow and curation runs.
- Improved shared manager lifecycles, deferred secret resolution, and
  revision-aware time-series publishing.
- Added explicit synchronization of the version-matched Common and DataBridge
  reference documentation included with generated projects.

## 1.1.0 - 2026-08-09

### Major updates

- Adopted the `oeds` namespace and moved project-owned configuration under
  `conf/oeds/config`.
- Updated the template to consume OEDS Common 2.0 and moved generic file,
  calendar, validation, and email behavior into the shared library.
- Expanded DataForge-owned ingestion, datafile, fileloader, reference,
  permission, schema, email, and time-series capabilities and documentation.
- Added case-based Integrify workflows, fixtures, validation, and service-task
  execution for integration testing.
- Added standalone agent and Copilot instructions, API references, and domain
  catalogs for generated projects.
- Added the OPERATION job and extended domain-aware project initialization and
  workspace configuration.

## 1.0.0 - 2026-07-16

### Major updates

- Introduced the DataForge Databricks Asset Bundle template with MAIN and
  SERVICE workflows and development, staging, and production configuration.
- Added common notebook context, reusable workflow utilities, ingestion and
  transformation examples, release notebooks, and integration-test assets.
- Added schema, permission, email, file, calendar, reference, and time-series
  configuration and examples.
- Added project and cluster initialization guidance, deployment hooks,
  engineering standards, and AI-assisted development instructions.
- Included a Databricks App starter and vendored Databricks tooling for common
  workspace and resource-management tasks.
