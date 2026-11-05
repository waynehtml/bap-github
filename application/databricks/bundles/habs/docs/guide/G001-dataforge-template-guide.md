# DataForge Template Project Guide

**DataForge** is the Databricks template project used to start standardized OEDS/DataBridge data engineering solutions.

The template provides a ready project shape for Databricks Asset Bundles, workflow orchestration, ingestion, transformation, Unity Catalog delivery, release operations, validation assets, and AI-assisted development. A new project should begin by copying this bundle, initializing project-specific configuration, then replacing the sample workflow pieces with real dataset logic.

This guide is an overview. It explains why the template exists, what components it contains, and how those components fit together. For step-by-step setup instructions, use the related guides linked at the end.

## DataBridge naming

DataBridge is the current name for the ingestion project and service formerly
called DIS/OEDIS. The sibling source project is stored in
`application/databricks/bundles/databridge`, and DataForge keeps its
synchronized contract snapshot under `docs/reference/databridge`.

Compatibility identifiers remain unchanged, including the `oedis` Python
package, `oedis.handler.*` handler and schema contracts, `DisClient` APIs,
DIS-prefixed variables, and OEDIS-named deployed infrastructure.

## Purpose

DataForge exists to make new Databricks data projects consistent from the first commit.

It gives developers a common foundation for:

- Databricks Asset Bundle deployment
- Environment-specific project configuration
- Dataflow, curation, integration, service, and operation workflow jobs
- DataBridge-backed ingestion
- Landing, raw, standardized, and curated processing stages
- Shared notebook runtime context
- Reusable Python workflow utilities
- Packaged configuration for schemas, permissions, email, files, file loading, and timeseries
- Unity Catalog table, view, and permission delivery
- Release and maintenance notebooks
- Examples and integration test assets
- Copilot prompts and skills that follow the project structure

The goal is not only to copy files faster. The goal is to reduce project-to-project variation so projects are easier to review, operate, enhance, and hand over.

## Design Principles

DataForge follows a few practical rules:

- Keep deployment configuration in bundle files and resource files.
- Keep workflow orchestration in `jobs`.
- Keep shared runtime setup in `common.py`.
- Keep reusable project code in `src/oeds/domain`.
- Keep operational configuration packaged under `conf/oeds/config`.
- Keep examples, tests, releases, and tools separate from production workflow tasks.
- Prefer extending existing registries, managers, and utility patterns before adding a new project-specific pattern.

These rules help both human developers and AI coding tools produce changes that are easy to locate and review.

## Project Lifecycle

A typical project starts from this sequence:

1. Copy `application/databricks/bundles/dataforge` to a new sibling folder.
2. Rename the copied folder to the intended project or dataset name.
3. Create `databricks.yml` from [default.databricks.yml](../../default.databricks.yml), the selected domain file, and project-specific values.
4. Align [common.py](../../common.py) fallback defaults with the generated bundle values.
5. Replace sample config and task logic with real dataset behavior.
6. Add or update schema, permission, email, fileloader, and timeseries config as needed.
7. Validate the Databricks Asset Bundle and project-specific tests before deployment.

The copied folder name normally becomes the bundle name. The initialized `databricks.yml` becomes the project-specific deployment descriptor.

## Component Map

| Component | Location | Role |
| --- | --- | --- |
| Template provenance | [.dataforge/manifest.yml](../../.dataforge/manifest.yml) | Standalone metadata recording the DataForge release from which a project was created and the most recently applied release. |
| Template changelog | [.dataforge/CHANGELOG.md](../../.dataforge/CHANGELOG.md) | DataForge release history kept separate from the generated project's root changelog. |
| Bundle defaults | [default.databricks.yml](../../default.databricks.yml) | Commented source template used to generate project-specific `databricks.yml`. |
| Domain defaults | [FMD.databricks.yml](../../FMD.databricks.yml), [CUR.databricks.yml](../../CUR.databricks.yml), [BAP.databricks.yml](../../BAP.databricks.yml), [SUP.databricks.yml](../../SUP.databricks.yml) | Non-project defaults and target overrides layered recursively onto the default bundle skeleton. |
| Shared job configuration | [resources/common.yml](../../resources/common.yml) | Complex variables for shared cluster settings and notebook base parameters. |
| Job resources | [resources/jobs](../../resources/jobs) | Job-specific definitions, task graphs, parameters, and application of shared permissions. |
| App resources | [resources/apps/main.yml](../../resources/apps/main.yml) | Main Databricks App resource template, excluded from the default job bundle and deployed separately. |
| Runtime bootstrap | [common.py](../../common.py) | Builds the string-valued shared job context, resolves secrets, configures logging, and initializes shared services. |
| Dataflow workflow | [jobs/dataflow](../../jobs/dataflow) | Notebook tasks for main, ingest, land-to-raw, raw-to-standardized, standardized-to-curated, completion, and failure handling. |
| Curation workflow | [jobs/curation](../../jobs/curation) | Independent curated-layer tasks with optional dependency and integration stages, completion handling, and failure handling. |
| Service workflow | [jobs/service](../../jobs/service) | Service job entry point for release, utility, named task, or app-triggered operations, including DataForge Testbench. |
| Operation workflow | [jobs/operation](../../jobs/operation) | Fixed single-task job for a project-owned recurring or independently triggered operation. |
| Project configuration | [conf/oeds/config](../../conf/oeds/config) | Project-owned definitions and static resources imported through `oeds.config`. |
| Workflow package | [src/oeds/domain](../../src/oeds/domain) | Reusable Python modules used by notebooks and examples. |
| Vendored helpers | [src/databricks_tools_core](../../src/databricks_tools_core) | Databricks helper modules bundled with the template. |
| Examples | [examples](../../examples) | Runnable examples for Databricks helpers, datafile lookup, email, file loading, permissions, releases, schemas, and timeseries. |
| Release assets | [releases](../../releases) | Release notebook location for project initialization and deployment-time operations. |
| Integration-test storage | [Integration Test Guide](G401-integration-test-guide.md) | Volume-backed Testbench case definitions under `cases/`, with `fixtures/`, `inputs/`, and `expected/` artifacts beneath the same `case_root`. |
| App scaffold | [apps/main](../../apps/main) | Streamlit-style main Databricks App scaffold, excluded from default bundle synchronization. |
| Cluster setup | [cluster](../../cluster) | Cluster init script, environment file, and Python requirements. |
| Deployment hooks | [script](../../script) | Pre-deploy and post-deploy helper scripts. |
| Operator tools | [tools](../../tools) | Maintenance utilities such as file loading, wheelhouse cleanup, and cluster restart helpers. |
| Documentation | [docs](..) | Overview, setup guides, Copilot docs, and standards or practices. |

## Runtime Flow

The template provides `DATAFLOW`, `CURATION`, `SERVICE`, and `OPERATION` job
definitions. Each resource file declares its purpose and required status in
leading comment metadata. All four current definitions are optional, so the
developer may select any subset, including none. Project
initialization automatically enables any future job marked required. Future
resource files under `resources/jobs` automatically become additional choices.

`DATAFLOW` is the dataset pipeline. It is organized as a gated flow:

1. `task_00_main.py` builds context and prepares the run.
2. `task_10_ingest.py` calls DataBridge.
3. `task_20_land_to_raw.py` moves landed files into raw storage.
4. `task_30_raw_to_std.py` is the raw-to-standardized extension point.
5. `task_40_std_to_curated.py` is the standardized-to-curated extension point.
6. `task_50_integrate.py` is the downstream-integration extension point.
7. `task_90_on_complete.py` handles successful completion or controlled early exit.
8. `task_91_on_failure.py` handles failure notification.

`CURATION` is a gated curated-layer job that runs independently from
`DATAFLOW`. It validates shared inputs, optionally checks dependencies, runs
the project curation task, and optionally runs project integration. Successful,
disabled, controlled-completion, and failed paths reach the shared curation
lifecycle handlers.

`SERVICE` is the operational entry point. It can run release notebooks, utility notebooks, or named task notebooks by passing a task name or notebook path through job parameters.

`OPERATION` is a fixed single-task job for project-owned work that needs its own
job identity. It does not dispatch arbitrary notebook paths. Projects that
enable it must replace its successful no-op placeholder with the intended
operation logic.

Every enabled job receives common base parameters from [resources/common.yml](../../resources/common.yml) through its definition in [resources/jobs](../../resources/jobs). Those parameters are read by [common.py](../../common.py), which gives notebooks one shared runtime context.

## Configuration Model

DataForge keeps project configuration outside task notebooks whenever possible.

Packaged configuration lives under [conf/oeds/config](../../conf/oeds/config):

- `ingest`: DataBridge ingestion request templates.
- `datafile`: file definitions, schemas, and reader options.
- `fileloader`: file-to-table load mappings.
- `schema`: Unity Catalog table and view definitions.
- `permission`: catalog, schema, table, and view grant rules.
- `email`: email registry entries and HTML templates.
- `timeseries`: provider, dataset, series, and publishing metadata.

The bundle treats `conf` as a Python source root and imports these areas
through `oeds.config.<area>`.

Reusable managers and utilities live under [src/oeds/domain/utils](../../src/oeds/domain/utils). The intent is for project notebooks to call these utilities instead of embedding large blocks of configuration or orchestration logic directly in notebooks.

## Deployment Configuration

The template is initialized from:

- [default.databricks.yml](../../default.databricks.yml)
- one selected domain file, such as [FMD.databricks.yml](../../FMD.databricks.yml) or [CUR.databricks.yml](../../CUR.databricks.yml)
- explicit or confirmed inferred project values

The initialized output is `databricks.yml` in the project root. That generated
file defines bundle identity, includes the shared and job-specific resource
files, and configures variables, targets, environment-specific overrides,
workspace paths, service principals, notification emails, Databricks workspace
references, DataBridge job IDs, and Datamart endpoints. The default file declares the
shared `job_permissions` contract, each domain file supplies one profile per
target, and every included job applies the resolved profile.

The generated include list is explicit. It contains every job whose metadata
marks it required and only the optional jobs selected during initialization; it
never uses the `resources/jobs/*.yml` wildcard.

Required project identity, resource naming, and raw-path inputs are initialized
once in the complex `project` variable. The `{{team}}`, `{{domain}}`,
`{{tag}}`, `{{catalog}}`, `{{dataset}}`, and `{{raw_path}}` placeholders live
only in `default.databricks.yml` and are resolved from explicit or confirmed
inferred values. Each initialization placeholder has adjacent `name`,
`description`, `required`, and `value` comment metadata. The `value` metadata
lists its allowed resolution modes and only the applicable options, inference
rule, or optional input example. An example is not a default. `project.domain`
selects the matching
`<DOMAIN>.databricks.yml`; domain files do not redefine the `project` object.

Workspace roots, catalog names, volume paths, secret scopes, service-principal
keys, and antivirus paths have shared derivations from `project.tag`,
`project.catalog`, and `project.dataset` in the default file. Every domain file
provides `job_runas_account`, `job_alert_emails`, `job_permissions`, and
`email_mappings` for each target and may override any other declared
non-project bundle variable when its conventions differ from the shared
values.

Each job resource file begins with `purpose` and `required` selection metadata
and owns required name and description placeholders with the same initialization
comment schema. Their `infer` rules produce uppercase
`<DOMAIN>-<DATASET>-<JOB-TYPE>` names and `<dataset> <job-type> job`
descriptions. Their `input` mode lets a project provide either complete value
without enforcing the inferred name structure; initialization uppercases the
complete job name while preserving the description. Initialization asks only
for enabled job identities, so disabled resource files remain unchanged.

After `databricks.yml` is created, [common.py](../../common.py) must be aligned with the same project values so direct notebook runs and tests do not fall back to stale template defaults.

## AI-Assisted Development

The template includes GitHub Copilot guidance so generated changes follow the same project structure:

- [.github/copilot-instructions.md](../../.github/copilot-instructions.md)
- [.github/prompts](../../.github/prompts)
- [.github/skills](../../.github/skills)
- [GitHub Copilot Guide](G002-github-copilot-guide.md)
- [DataKit API reference](../reference/datakit/README.md)

Use these files when asking Copilot to initialize a project, refresh bundle variables, configure cluster init scripts, or extend the template. The Copilot docs are intentionally separate from this overview so the overview can stay focused on the project itself.

## What Developers Usually Customize

For a real project, the common customization points are:

1. Project identity and deployment variables in generated `databricks.yml`.
2. Matching fallback defaults in `common.py`.
3. Ingestion requests under `conf/oeds/config/ingest`.
4. File and file load definitions under `conf/oeds/config/datafile` and `conf/oeds/config/fileloader`.
5. Schema definitions under `conf/oeds/config/schema`.
6. Permission rules under `conf/oeds/config/permission`.
7. Email registry and templates under `conf/oeds/config/email`.
8. Timeseries registration config under `conf/oeds/config/timeseries`, when needed.
9. Task-specific notebook logic in `jobs/dataflow`, `jobs/curation`, and
   `jobs/operation`.
10. Release, example, and test assets that prove the project behavior.

The `DATAFLOW` transformation placeholders are `task_30_raw_to_std.py` and
`task_40_std_to_curated.py`. Its integration placeholder is
`task_50_integrate.py`. `CURATION` retains its separate `task_20_curate.py` and
`task_30_integrate.py` entry points. The two workflows do not share task
implementations.

## Related Guides

- [Init Project Guide](G101-init-project-guide.md): copy the template and initialize `databricks.yml` manually or with Copilot.
- [Dataflow Job Guide](G201-dataflow-job-guide.md): understand and customize the dataflow Databricks workflow.
- [Curation Job Guide](G206-curation-job-guide.md): configure independently
  runnable curated-layer processing and its optional integration stage.
- [Operation Job Guide](G204-operation-job-guide.md): configure the fixed
  project operation job and replace its placeholder logic.
- [Datafile Module Developer Guide](G225-datafile-developer-guide.md): define source file locations, reader options, and source schemas.
- [Fileloader Developer Guide](G226-fileloader-developer-guide.md): normalize, transform, validate, and write registered files to registered tables.
- [Land To Raw Flow Guide](G230-land-to-raw-flow-guide.md): validate and copy landing batches into raw while preserving landing files.
- [Raw To Standardized Flow Guide](G240-raw-to-standardized-flow-guide.md): strictly read, transform, validate, and load raw batches into standardized tables.
- [DataFrame Validator Guide](G245-dataframe-validator-guide.md): define and interpret standardized-record validation rules.
- [Email Module Developer Guide](G303-email-developer-guide.md): configure registries, templates, recipients, attachments, and email providers.
- [Service Job Guide](G202-service-job-guide.md): use the service job for release notebooks and named service tasks.
- [Integration Test Guide](G401-integration-test-guide.md): define integration cases and
  organize `fixtures/`, `inputs/`, and `expected/` data in a configuration-zone
  Volume.
- [Common Notebook Guide](G203-common-notebook-guide.md): understand shared notebook context, parameter priority, and runtime utilities.
- [Deployment Guide](G112-deployment-guide.md): understand Databricks Asset Bundle deployment, Azure DevOps parameters, and pre/post deployment hooks.
- [Release Guide](G111-release-guide.md): enable the service job, create release notebooks, deploy the bundle, and run releases.
- [Init Cluster Guide](G102-init-cluster-guide.md): configure cluster init scripts and optional Nexus wheelhouse support.
- [Schema Guide](G211-schema-guide.md): define Unity Catalog tables and views in the packaged schema registry.
- [Permission Module Developer Guide](G212-schema-permission-guide.md): configure Unity Catalog grants and apply them with the permission tool or release notebooks.
- [Calendar Guide](G301-calendar-guide.md): initialize the calendar from reference holidays and calculate workflow dates.
- [GitHub Copilot Guide](G002-github-copilot-guide.md): use the bundled
  Copilot instructions, skills, and prompt files.
- [Landing Zone Best Practices](../standards-and-practices/landing_zone_best_practices.md): follow landing-zone conventions.

## Summary

DataForge is the starting foundation for OEDS/DataBridge Databricks data products. It gives each project the same deployment shape, runtime context, workflow layout, configuration model, support tooling, and AI guidance.

Use this guide to understand the template at a high level. Use the focused guides when you are ready to initialize, configure, or extend a copied project.
