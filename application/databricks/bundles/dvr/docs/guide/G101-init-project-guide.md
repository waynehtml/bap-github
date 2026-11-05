# Init Project Guide

This guide is a developer reference for starting a new Databricks project from
the DataForge template and initializing it with GitHub Copilot. Use the bundled
`/init-project` skill to create `databricks.yml` once and align the
fallback values in `common.py`. After all validation succeeds, it removes the
copied default and all domain YAML files, including unselected domains. The
canonical DataForge template retains these files.

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
   the copied source YAML templates.
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
The default and domain YAML files are removed after successful initialization:

- `.dataforge/manifest.yml`: standalone template provenance containing the
  original and last-applied DataForge release versions. It is not DAB
  configuration.
- `.dataforge/CHANGELOG.md`: DataForge template release history. A root
  `CHANGELOG.md` belongs to the generated project and is not managed by
  DataForge.
- `default.databricks.yml`: commented skeleton Copilot uses to create
  `databricks.yml`.
- `<DOMAIN>.databricks.yml`: recursively applied non-project defaults and target
  overrides, such as `FMD.databricks.yml` or `CUR.databricks.yml`. Project
  identity is not defined in these files.
- `common.py`: shared notebook bootstrap and fallback defaults for direct
  notebook runs, tests, and missing task parameters.
- `resources/common.yml`: shared complex variables for job clusters and
  notebook base parameters.
- `resources/jobs/*.yml`: job-specific variables, definitions, task graphs,
  parameters, and workflow-selection metadata.
- `jobs`: dataflow, curation, service, and operation task notebooks.
- `src/oeds/domain`: reusable workflow code and packaged project configuration.
- `releases`, `examples`, `tests`, `apps`, `cluster`, `script`, and `tools`:
  supporting assets for release, validation, app deployment, cluster setup,
  and maintenance.

`databricks.yml` is the generated project file. Copilot creates it in the project bundle
root from `default.databricks.yml`, the selected domain file, and
confirmed project-specific values.

## 3. Start Copilot Initialization

The template includes Copilot-specific instructions for one-time generation of
`databricks.yml` and alignment of `common.py`:

- `.github/copilot-instructions.md`: directs Copilot to the bundled project and
  cluster initialization skills.
- `.github/skills/init-project/SKILL.md`: defines how to resolve placeholders,
  apply domain target overrides, select workflows, generate `databricks.yml`,
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

DataForge provides four workflow definitions:

- `DATAFLOW` is optional and can implement ingestion, curation, and integration
  in one staged workflow.
- `CURATION` is optional and can implement curation, integration, or both under
  an independent job identity and release lifecycle.
- `OPERATION` is optional and supports general single-task operational work.
- `SERVICE` is required and automatically included for release and maintenance
  utilities, regardless of which processing workflows are selected.

Copilot discovers the workflow definitions from `resources/jobs/*.yml` and
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

Copilot resolves configuration in this precedence order:

1. Confirmed explicit and inferred project values.
2. Domain-specific non-project overrides from the selected
   `<DOMAIN>.databricks.yml`.
3. Shared defaults from `default.databricks.yml`.

The `project` variable contains the complete project input set: `team`,
`domain`, `tag`, `catalog`, `dataset`, and `raw_path`. Copilot uses the confirmed
`project.domain` to select the matching domain file. `raw_path` must be relative,
must not begin with `/`, and must not contain empty, `.` or `..` path segments.

The selected domain file supplies target values for `job_runas_account`,
`job_alert_emails`, `job_permissions`, and `email_mappings`. It must not define
project identity. Copilot applies domain values recursively so an override of
one nested key does not remove sibling defaults.

For enabled workflows, Copilot resolves the required job names and descriptions
using their documented `infer` or `input` modes. It uppercases every job name
before confirmation and writing without changing description casing. Disabled
workflow files remain unchanged.

### Final Configuration Step: Compute Setup

After other values and enabled-job identities are resolved, Copilot presents
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
`${var.compute_classic_job_policy_id}` in `resources/common.yml`. The option
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
conflicting explicit, domain, or target path/runtime overrides require resolution.

The two `{{compute_config_name}}` placeholders are resolved separately during
this final step. The selected type uses the chosen folder name; the unused type
uses its default from `compute_setup.defaults`. Local classic uses both central
defaults. This preserves valid reusable paths without leaving placeholders or
requiring separate folder selections.

Generated `databricks.yml` records `# Selected compute: <choice>` above the
metadata. This is informational, not a runtime switch. Only a central classic
selection changes the runtime to match its declared configuration; package
versions remain unchanged. Validation and source-template cleanup happen only
after this final configuration step succeeds.

Copilot then:

- Creates `databricks.yml` while preserving the comments and
  section order from `default.databricks.yml`.
- Preserves non-job includes and adds explicit includes for `SERVICE` and the
  selected optional workflows. It does not copy the
  `resources/jobs/*.yml` discovery pattern into generated configuration.
- Keeps the default `sync.exclude` entries for `apps/**` and
  `resources/apps/**`; Databricks Apps are deployed separately.
- Applies the selected domain values recursively and retains intentional shared
  platform defaults.
- Keeps `variables.catalog` derived as
  `${var.env}_${var.project.catalog}_cat` and `variables.raw_root` derived as
  `/Volumes/${var.env}_raw_cat/${var.project.raw_path}`.
- Updates matching `DEFAULT_*` constants in `common.py` from the same resolved
  values, using the resolved `dev` value for environment-specific fallbacks.
- Converts Databricks variable references into Python f-string references where
  a matching derived fallback is required.
- Keeps the copied source YAML files unchanged until every validation check
  passes, then deletes `default.databricks.yml` and all recorded root-level
  domain YAML files, including unselected domains.
- Retains all source templates if generation or validation fails. If cleanup
  fails, reports completed and pending deletions without claiming success.

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
- [resources/common.yml](../../resources/common.yml) defines the local classic
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
`resources/common.yml`. DataBoot owns their deployed configuration and
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
- `databricks.yml` explicitly includes `resources/jobs/service.yml` and only the
  selected optional workflow files. It contains no job wildcard and references
  each enabled workflow once.
- Non-job includes are preserved, no app resource is included, and `apps/**`
  and `resources/apps/**` remain excluded from bundle synchronization.
- No required `{{...}}` placeholders remain in `databricks.yml`, enabled job
  resource files, or `common.py`. Disabled job files may retain placeholders.
- Every active `${var.*}` reference is backed by a declaration across the
  included bundle files.
- For classic compute, `compute_classic_job_policy_id` contains the confirmed
  option's dev/stg/prd IDs, and both shared cluster definitions reference it.
  The policy option metadata remains in `databricks.yml`; serverless preserves
  regular target defaults.
- Every target resolves one complete `job_permissions` list, and every enabled
  job references `${var.job_permissions}`.
- The complete `project` object contains confirmed values. Before cleanup,
  Copilot verifies that the selected domain file name matches
  `variables.project.domain`.
- After successful cleanup, the recorded default and domain YAML files are
  absent, while `databricks.yml` and resource YAML files remain.
- Base parameters in `resources/common.yml` align with values read by
  `common.py`.
- `email_mappings` remains a valid JSON string.
- OEDS integration `_key` variables, including `datamart_endpoints_key`, hold
  secret names matching their individual `DEFAULT_*_KEY` constants in
  `common.py`. Initialization
  must not resolve secrets or copy their values into YAML or Python. See
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
- Trying to deselect the required SERVICE workflow.
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
- Selecting a domain file that does not match the confirmed
  `variables.project.domain` value.
- Supplying a catalog name with an environment prefix or `_cat` suffix instead
  of the catalog tag.
- Committing real secrets instead of secret scope names, secret key names, or
  approved non-secret resource identifiers.
