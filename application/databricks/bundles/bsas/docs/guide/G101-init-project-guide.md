# Init Project Guide

This guide is a developer reference for starting a new Databricks project from
the DataForge template and initializing it with GitHub Copilot. Use the bundled
`/init-project` skill to create `databricks.yml` once and align the
fallback values in `common.py`. After all validation succeeds, it removes the
copied `default.databricks.yml` only. The canonical DataForge template retains
that file. Legacy domain YAML files, if present, are neither read nor removed.

The initialization flow has four goals:

1. Create a uniquely named project bundle from a stable DataForge release.
2. Resolve project values from template metadata and approved sources.
3. Select the workflows that implement the project's data lifecycle.
4. Generate and validate project-specific bundle configuration while keeping
   `common.py` aligned.

## 1. Create A Bundle

1. In the project repository in Azure DevOps, create a project branch. Use
   GitHub Desktop or another Git client to clone the repository to a folder on
   your local laptop and check out that branch.
2. Clone the
   [DataForge repository](https://dev.azure.com/azdv-cac-npd-dorg-azcl01/_git/lake-oedataservices01)
   into a temporary folder. Check out the newest stable release tag named
   `releases/dataforge-v<version>` so the new bundle does not include
   unreleased template changes.
3. Copy the DataForge folder at
   `application/databricks/bundles/dataforge` from the temporary clone into the
   project repository's `application/databricks/bundles/` folder.
4. Rename the copied folder using the approved bundle name.
5. Open the project repository in VS Code. In GitHub Copilot Chat, invoke the
   `/init-project` skill from the new bundle folder.
6. Answer Copilot's questions for the domain, dataset name, workflow selection,
   and other required project values. After the questions are complete,
   Copilot creates and validates the customized `databricks.yml`, then removes
   only the copied `default.databricks.yml`.
7. Review the generated changes, commit the new bundle, and push the commit to
   the remote project branch in Azure DevOps.
8. Begin development in VS Code or the Databricks web UI.

The new bundle's `.dataforge/manifest.yml` records the stable DataForge release
from which the project was created and the most recently applied release. The
`/init-project` skill displays these values before asking for project inputs
and preserves the file unchanged. Projects without the file can still be
initialized; Copilot reports that version metadata is unavailable before
continuing.

### Bundle Naming Convention

Consult the project manager to define the standard lowercase dataset name. The
dataset name normally matches the dataset folder in the raw zone.

The Databricks Asset Bundle name identifies one unique deployment package in
the project. The project bundle folder name and `bundle.name` must match exactly
and must be unique within the project. Name the bundle according to its primary
purpose:

- Use `{dataset}` when `DATAFLOW` is enabled for ingestion. For example, use
  `cds` or `corra`.
- Use `{dataset}-curation` when curation is the bundle's primary purpose, even
  when the `CURATION` workflow also includes integration.
- Use `{dataset}-integration` when integration is the bundle's only purpose.

`project.dataset` is distinct from the bundle name. It contains the approved
business dataset name without the `-curation` or `-integration` bundle suffix
and is used to name dataset folders in the antivirus (AV) and landing zones.
For example, a `corra-integration` bundle still uses `corra` as
`project.dataset`.

### Job Naming Convention

Every enabled workflow has an uppercase Databricks job display name derived
from the confirmed `project.domain` and `project.dataset` values:

- `DATAFLOW`: `<DOMAIN>-<DATASET>-DATAFLOW`
- `CURATION`: `<DOMAIN>-<DATASET>-CURATION`
- Integration-only use of `CURATION`: `<DOMAIN>-<DATASET>-INTEGRATION`
- `OPERATION`: `<DOMAIN>-<DATASET>-OPERATION`
- `SERVICE`: `<DOMAIN>-<DATASET>-SERVICE`

The default job names use the domain and dataset values, not the bundle folder
name. For an integration-only bundle, the `CURATION` workflow initially infers
`<DOMAIN>-<DATASET>-CURATION`. Use its documented custom-input mode during
initialization to supply `<DOMAIN>-<DATASET>-INTEGRATION` instead. Copilot
uppercases every inferred or supplied job name before confirmation and writing.

## 2. Review The Template Bundle

Before initialization, the copied bundle has the following template structure.
Only `default.databricks.yml` is removed after successful initialization:

- `.dataforge/manifest.yml`: standalone template provenance containing the
  original and last-applied DataForge release versions. It is not DAB
  configuration.
- `.dataforge/CHANGELOG.md`: DataForge template release history. A root
  `CHANGELOG.md` belongs to the generated project and is not managed by
  DataForge.
- `default.databricks.yml`: commented skeleton Copilot uses to create
  `databricks.yml`.
- `common.py`: shared notebook bootstrap and fallback defaults for direct
  notebook runs, tests, and missing task parameters.
- `resources/jobs/common.yml`: shared complex variables for job clusters and
  notebook base parameters.
- `resources/jobs/*.yml`: job-specific variables, definitions, task graphs,
  parameters, and workflow-selection metadata.
- `jobs`: dataflow, curation, service, and operation task notebooks.
- `src/oeds/domain`: reusable workflow code and packaged project configuration.
- `releases`, `examples`, `tests`, `apps`, `cluster`, `script`, and `tools`:
  supporting assets for release, validation, app deployment, cluster setup,
  and maintenance.

`databricks.yml` is the generated project file. Copilot creates it in the project bundle
root from `default.databricks.yml`, adjacent comment mappings, and
confirmed project-specific values.

## 3. Start Copilot Initialization

The template includes Copilot-specific instructions for one-time generation of
`databricks.yml` and alignment of `common.py`:

- `.github/copilot-instructions.md`: directs Copilot to the bundled project and
  cluster initialization skills.
- `.github/skills/init-project/SKILL.md`: defines how to resolve placeholders,
  resolve adjacent domain mappings, select workflows, generate `databricks.yml`,
  and synchronize `common.py`.
- [GitHub Copilot Guide](G002-github-copilot-guide.md): describes all bundled
  Copilot customizations.

From the project bundle root, ask Copilot to use the skill:

```text
Use the /init-project skill to create databricks.yml.
Ask me for required values before writing the file.
```

Copilot reads the current input contracts directly from
`default.databricks.yml` and `resources/jobs/*.yml`. Each initialization
placeholder has adjacent comment metadata describing its business meaning,
required status, allowed resolution modes, and optional example:

```yaml
# name: <placeholder name>
# description: <business meaning and format>
# required: true
# value:
#   modes: ["input"]
#   input_example: "sample-value"
```

`options` requires a listed selection, `infer` uses only its documented rule,
and `input` requests a free-form value. An example is guidance, not a default.
Copilot must show inferred values and their sources for confirmation before it
writes files.

Do not ask Copilot to invent project identity, secret scope, service principal,
workspace, resource ID, email, or Datamart values. Keep shared values from
`default.databricks.yml` only when they are intentional platform defaults.

## 4. Select Workflows For The Data Lifecycle

Choose workflows based on the complete data process and the ownership and
release timeline of each stage. The process has three stages:

| Stage | Typical owner | Responsibility |
| --- | --- | --- |
| Ingestion | Data engineers | Ingest data from source systems, preserve it in the raw zone of the data lake, and load standardized tables in Unity Catalog. |
| Curation | Business data analysts | Apply business curation logic to standardized data and write curated tables in Unity Catalog. |
| Integration | Data engineers | Disseminate curated data to downstream consumers such as the AE time-series system, internal systems such as SAP, or external systems such as Stanscan. |

After General resolves project identity and shared domain mappings, Copilot asks
"Set up jobs?" If declined, it skips job discovery, job inputs, compute and policy
prompts, and all job includes including `resources/jobs/common.yml`. Unused root
compute-path placeholders resolve from declared defaults without a prompt;
concrete overrides remain unchanged. App Setup follows independently.

When Job Setup is enabled, DataForge provides four workflow definitions:

- `DATAFLOW` is optional and can implement ingestion, curation, and integration
  in one staged workflow.
- `CURATION` is optional and can implement curation, integration, or both under
  an independent job identity and release lifecycle.
- `OPERATION` is optional and supports general single-task operational work.
- `SERVICE` is required and automatically included for release and maintenance
  utilities, regardless of which processing workflows are selected.

Copilot discovers workflow definitions from `resources/jobs/*.yml`, explicitly
excluding `common.yml` from discovery and job metadata checks, and
shows each one once in its selection checklist, with SERVICE locked as required.
Reply with optional job keys or `none`; SERVICE remains enabled. Choose
`DATAFLOW`, `CURATION`, and `OPERATION` according to
the project design; any combination of these optional processing workflows is
valid.

Use one of these three common project patterns:

1. **One Dataflow bundle.** Use one bundle with `DATAFLOW` when curation is
   straightforward, depends mainly on the current dataset, and can share the
   ingestion release timeline. Implement ingestion, curation, and integration
   as stages of the same workflow.
2. **Separate Dataflow and Curation bundles.** Keep ingestion and
   standardization in a Dataflow bundle, and put complex or multi-dataset
   curation in a separately released bundle with `CURATION`. This supports a
   business data analyst release timeline. Integration normally stays with the
   curation it consumes, allowing data engineers and business data analysts to
   own different tasks in the same Curation bundle.
3. **Legacy curation with an integration-focused Curation bundle.** When
   curation remains in standalone legacy notebooks, create a separate bundle
   with `CURATION` for integration. The legacy curation logic can later be
   migrated into the same workflow so curation and integration share one
   lifecycle.

See the [Dataflow Job Guide](G201-dataflow-job-guide.md),
[Curation Job Guide](G206-curation-job-guide.md),
[Service Job Guide](G202-service-job-guide.md), and
[Operation Job Guide](G204-operation-job-guide.md) for workflow details.

## 5. Confirm Values And Let Copilot Generate The Project

Copilot starts with `default.databricks.yml` and applies confirmed explicit or
inferred project values. Adjacent mappings are authoritative for mapped
variables: conflicting explicit or target values must be resolved before
initialization continues. Unmapped variables retain shared defaults and target
overrides unless explicitly changed.

The `project` variable contains the complete project input set: `team`,
`domain`, `tag`, `catalog`, `dataset`, and `raw_path`. Copilot uses the confirmed
`project.domain` to select adjacent mapping entries case-insensitively. `raw_path` must be relative,
must not begin with `/`, and must not contain empty, `.` or `..` path segments.

Supported domains are `FMD`, `CUR`, `BAP`, `SUP`, and `OEDS`. Use `OEDS`
for team projects. Its inferred tag is `oedataservices` and its catalog is
`application`, producing `<env>_application_cat`. The project and app secret
scopes are `lake-kv-oedataservices-scope` and
`lake-kv-oedataservicesapp-scope` respectively. OEDS uses the shared team
service principals, job permissions, and failure notifications for each target.
Email aliases include `DDA` in dev and `DDA` plus `DM` in staging and production.
App credential-key mappings use the existing team app principals; staging and
production app credentials are distinct from the job service principals.

The main configuration retains target metadata and unrelated overrides, without
redefining project identity. General setup resolves app/project secret scopes, service SPN
key names, and email_mappings from literal mappings beside their
variables in default.databricks.yml. This happens even when Job and App setup
are declined. Scopes use domain-only scalar mappings to fill their defaults,
which all targets inherit without overrides. SPN keys and email mappings retain
domain/target mappings: root defaults use dev and every target receives its own
value. Changing project.tag does not change mapped scopes or keys. Email mappings
remain valid JSON strings, and common.py fallbacks use the resolved dev literals. The three job variables (`job_runas_account`, `job_alert_emails`, and
`job_permissions`) are declared in `resources/jobs/common.yml`. Structured `mapping` comments beside each variable declaration contain its
domain/target values and explanatory comments describe its expected type. When Job Setup is enabled,
Copilot selects the confirmed domain case-insensitively and fills that file's
dev/stg/prd variables automatically, preserving native YAML lists and existing
permission entries. No separate profile prompts are needed. Missing or malformed
selected mappings and conflicting overrides stop initialization. Declining Job
Setup skips job mapping resolution and validation; General mappings still apply.
Explicit changes to an unmapped nested key preserve sibling defaults.

For enabled workflows, Copilot resolves the required job names and descriptions
using their documented `infer` or `input` modes. It uppercases every job name
before confirmation and writing without changing description casing. Disabled
workflow files remain unchanged.

### Compute Setup

Only when Job Setup is enabled, after job identities are resolved, Copilot presents
all choices from the `compute_setup` comment block in the default YAML's Compute
settings section. Central choices are the exact DataBoot configuration folder
names. The local choice is `classic-local-` followed by the template runtime's
major.minor version, such as `classic-local-16.4`. The full runtime value remains
unchanged. The catalog also declares central classic runtimes and default
configurations for unused central paths. No sibling DataBoot checkout or
workspace discovery is needed.

Select one choice for every enabled job, including SERVICE. Copilot marks the
recommended choice but waits for your selection. If your request already names
a valid choice, it uses that choice without asking again. Undeclared choices
and malformed metadata stop initialization before output or template cleanup.

After either classic compute choice, select the job cluster policy from the
`job_cluster_policy` comment metadata beside `compute_classic_job_policy_id`:

- Regular job cluster (default).
- High performance job cluster.

Copilot uses a valid choice key or label already supplied in your request;
otherwise it presents both options and waits for your response. One choice
applies to every enabled job, including SERVICE. The selected option supplies
the dev/stg/prd values for the single `compute_classic_job_policy_id` variable
in generated `databricks.yml`. Serverless skips this prompt and preserves regular
target defaults. Both local and central classic clusters keep referencing
`${var.compute_classic_job_policy_id}` in `resources/jobs/common.yml`. The option
metadata remains available in generated configuration for later reference.
This choice changes only target policy IDs; runtime, autoscaling, and init-script
settings follow the compute configuration. Conflicting explicit or domain policy
overrides require resolution before validation.

Local classic uses the project's init script and preserves its resolved runtime.
Central classic uses the selected DataBoot folder and its declared runtime,
including the matching `common.py` fallback. Central serverless uses the selected
folder's environment configuration and replaces classic cluster references in
enabled notebook tasks. Condition tasks and disabled job files stay unchanged.
Reusable compute definitions and nonconflicting target overrides remain available;
conflicting explicit or target path/runtime overrides require resolution.

The two `{{compute_config_name}}` placeholders are resolved separately during
this compute step. The selected type uses the chosen folder name; the unused type
uses its default from `compute_setup.defaults`. Local classic uses both central
defaults. This preserves valid reusable paths without leaving placeholders or
requiring separate folder selections.

Generated `databricks.yml` records `# Selected compute: <choice>` above the
metadata. This is informational, not a runtime switch. Only a central classic
selection changes the runtime to match its declared configuration; package
versions remain unchanged. Validation and source-template cleanup happen only
after compute and optional app setup succeed.

### Optional Databricks App Setup

After Job Setup completes or is declined, Copilot asks whether
to set up a Databricks App. If yes, provide an app name without the domain
prefix. Copilot uses the confirmed project domain and presents a lowercase name
and description for confirmation or revision. For example, `FMD` and
`Client Portal` produce `fmd-client-portal` and `fmd client portal app`.

Confirm both identity values. SPN key names for dev, stg, and prd are selected
automatically from the commented `app_spn_keys` mapping in
`resources/apps/main.yml`, matching the project domain case-insensitively.
Before enabling the app, manually replace the selected domain's `REPLACE_ME_...`
entries with existing secret key names, not secret values. No separate key-entry
or confirmation prompts are used. Missing, incomplete, or unresolved selected
mappings stop setup and identify the entries to fix; unselected domains may keep
placeholders. Conflicting concrete overrides must be resolved rather than
silently replacing the mapping. Declining setup skips mapping validation.
Copilot populates `resources/apps/main.yml`, includes it exactly once,
and removes the two app synchronization exclusions in generated configuration.
It preserves the app's direct workspace and warehouse variable bindings.
The app YAML also includes its access-repair and startup scripts. Declining App
Setup removes their names from pre/post deployment selections, preserving unrelated
scripts. Both Job and App may be declined for general-only initialization.
Initialization does not deploy the app. If you decline, app files remain
unchanged and excluded, and no app-specific inputs are requested.

Copilot then:

- Creates `databricks.yml` while preserving the comments and
  section order from `default.databricks.yml`.
- Always includes `resources/script.yml`. When jobs are enabled, includes
  `resources/jobs/common.yml`, `SERVICE`, and the
  selected optional workflows. It does not copy the
  `resources/jobs/*.yml` discovery pattern into generated configuration.
- Keeps `apps/**` and `resources/apps/**` synchronization exclusions only
  when app setup is declined; confirmed app setup includes the app YAML.
- Applies the selected domain values recursively and retains intentional shared
  platform defaults.
- Keeps `variables.catalog` derived as
  `${var.env}_${var.project.catalog}_cat` and `variables.raw_root` derived as
  `/Volumes/${var.env}_raw_cat/${var.project.raw_path}`.
- Updates matching `DEFAULT_*` constants in `common.py` from the same resolved
  values, using the resolved `dev` value for environment-specific fallbacks.
- Converts Databricks variable references into Python f-string references where
  a matching derived fallback is required.
- Keeps the copied `default.databricks.yml` unchanged until every validation
  check passes, then deletes only that recorded file. Other YAML files, including
  legacy domain files, remain untouched.
- Retains the source default if generation or validation fails. If cleanup
  fails, reports the error and pending source path without claiming success.

The skill stops if `databricks.yml` already exists, including after an
interrupted initialization. Review any partial output directly instead of
rerunning initialization. For later configuration changes, edit
`databricks.yml` and job resources directly and keep corresponding `common.py`
fallbacks aligned; do not rerun `/init-project`.

### Local Cluster Initialization

Local classic compute uses a static, project-owned init script to install
Python dependencies directly from the corporate Nexus repository on each node.

#### Files and Configuration

- [cluster/init.sh](../../cluster/init.sh) runs the installation.
- [cluster/requirements.txt](../../cluster/requirements.txt) declares dependencies.
- [resources/jobs/common.yml](../../resources/jobs/common.yml) defines the local classic
  cluster and attaches the init script from workspace files.

The bundle variable `compute_classic_local_init_path` defaults to
`${var.bundle_root}/cluster/init.sh` and includes the filename. The cluster uses:

```yaml
init_scripts:
  - workspace:
      destination: ${var.compute_classic_local_init_path}
```

Bundle synchronization deploys the script and requirements together. Keep
`requirements.txt` beside the script. No deployment preparation or separate
Volume publication is needed for local initialization.

Workspace init scripts require a compatible cluster access mode; standard
access mode does not support workspace init scripts. Use the separate central
classic configuration when a supported Volume-backed script is required.

#### Installation Behavior

The script locates requirements relative to its own directory and checks that
the requirements file and `/databricks/python/bin/pip` are available. It installs
from the fixed corporate Nexus URL, passing the trusted host to that invocation
without modifying global pip configuration.

Each pip invocation uses `--retries 2` and `--timeout 60`. If installation fails,
the script waits three seconds and makes one more attempt. Pip diagnostics remain
visible in the init logs; exhausted attempts return a nonzero exit status.

Local initialization does not create or consume a wheelhouse. It requires Nexus
connectivity whenever it installs dependencies. To change project dependencies,
edit the requirements file, deploy the bundle, and start a new job cluster.

#### Central Compute Configurations

Central classic and serverless configurations remain separate alternatives in
`resources/jobs/common.yml`. DataBoot owns their deployed configuration and
wheelhouses. The local init script neither publishes nor modifies those files.
The final compute selection applies the chosen configuration to every enabled
job. For later manual changes, follow the commented alternatives in the job YAML
files and update the selected-compute comment in `databricks.yml`.

#### Troubleshooting

- Missing requirements: verify that the deployed script and requirements file
  are in the same directory and readable during initialization.
- Missing pip: verify the selected classic runtime provides the expected
  Databricks Python executable.
- Nexus installation failure: inspect pip output for network, repository,
  dependency-resolution, or package compatibility errors.
- Init script access failure: verify the workspace path, permissions, cluster
  policy, and access mode permit the configured script.

## 6. Review The Copilot Result

Always review Copilot's diff before committing. Confirm that:

- `databricks.yml` exists in the project bundle root and has a final newline.
- With Job Setup enabled, `databricks.yml` includes `resources/jobs/common.yml`,
  `resources/jobs/service.yml`, and only the
  selected optional workflow files. It contains no job wildcard and references
  each enabled workflow once.
- With Job Setup declined, no job YAML is included or changed and unused root
  compute paths are concrete without prompts. Shared script includes are preserved. Enabled app setup includes the app YAML once,
  resolves its identity and target key names, and removes app synchronization
  exclusions. Disabled setup leaves the app unchanged, excluded, and unprompted.
- No required `{{...}}` placeholders remain in `databricks.yml`, enabled job
  resource files, or `common.py`. Disabled job files may retain placeholders.
- Every active `${var.*}` reference is backed by a declaration across the
  included bundle files.
- With Job Setup enabled and classic compute, `compute_classic_job_policy_id` contains the confirmed
  option's dev/stg/prd IDs, and both shared cluster definitions reference it.
  The policy option metadata remains in `databricks.yml`; serverless preserves
  regular target defaults.
- With Job Setup enabled, every target resolves `job_permissions`, and every enabled
  job references `${var.job_permissions}`.
- The complete `project` object contains confirmed values. Mapping lookup uses
  that confirmed domain case-insensitively.
- After successful cleanup, only the recorded `default.databricks.yml` is
  absent; generated configuration, resource YAML, and unrelated files remain.
- When jobs are enabled, base parameters in `resources/jobs/common.yml` align with
  `common.py`.
- `email_mappings` remains a valid JSON string.
- Azure IDs, workspace URLs and resource IDs, DataBridge job IDs, and SQL
  warehouse IDs use direct target values and matching `DEFAULT_*` constants
  in `common.py`. See
  [Direct Integration Values](G203-common-notebook-guide.md#direct-integration-values).
- `datamart_endpoints_key` and credential `_key` variables retain secret names
  matching their `DEFAULT_*_KEY` constants. Initialization must not resolve
  secrets or copy their values into YAML or Python. See
  [OEDS Integration Secrets](G203-common-notebook-guide.md#oeds-integration-secrets).
- `common.py` compiles as Python.
- No secrets, passwords, tokens, or credential values were written to the
  repository.

Pay particular attention to comments, placeholder replacement, JSON string
values, workflow includes, secret handling, and whether `common.py` reflects
the generated `databricks.yml`.

## 7. Common Mistakes

- Creating the bundle in the temporary DataForge clone instead of copying it
  into the project repository's `application/databricks/bundles/` folder.
- Copying the DataForge default branch instead of checking out the newest
  stable `releases/dataforge-v<version>` tag.
- Using a bundle folder name that does not exactly match `bundle.name` or is not
  unique within the project.
- Adding `-curation` or `-integration` to `project.dataset`; those suffixes
  belong only to the bundle folder and `bundle.name`.
- Keeping the inferred `<DOMAIN>-<DATASET>-CURATION` job name when integration
  is the bundle's only purpose instead of supplying
  `<DOMAIN>-<DATASET>-INTEGRATION`.
- Trying to deselect SERVICE within enabled Job Setup; decline Job Setup to omit all jobs.
- Choosing one Dataflow bundle when complex, multi-dataset curation requires a
  separate owner or release timeline.
- Separating integration from its curated source without an operational or
  legacy reason.
- Updating `databricks.yml` while leaving stale fallback values in `common.py`.
- Reformatting `default.databricks.yml` and losing comments or section order.
- Treating `{{...}}` placeholders as Databricks runtime variables. They are
  initialization placeholders and must be resolved before deployment.
- Keeping `resources/jobs/*.yml` in generated configuration instead of explicit
  includes for `SERVICE` and the selected optional workflows.
- Using mapping entries that do not match the confirmed
  `variables.project.domain` value.
- Supplying a catalog name with an environment prefix or `_cat` suffix instead
  of the catalog tag.
- Committing real secrets instead of secret scope names, secret key names, or
  approved non-secret resource identifiers.
