# Init Project Guide

This guide is a developer reference for starting a new Databricks project from the template bundle. Use it when copying the template into a real project and initializing `databricks.yml` either manually or with GitHub Copilot.

The initialization flow has three goals:

1. Create a project folder whose name can be used as the bundle name.
2. Generate a project-specific `databricks.yml` from template defaults, domain
   target overrides, and explicit or confirmed inferred values.
3. Keep the fallback defaults in `common.py` aligned with the generated bundle variables.

## 1. Copy And Rename The Template Folder

Start from the template bundle folder:

```text
application/databricks/bundles/dataforge
```

Copy the whole folder to a sibling folder under `application/databricks/bundles`, then rename the copied folder to the intended project or dataset name.

Example:

```powershell
Copy-Item -Recurse application/databricks/bundles/dataforge application/databricks/bundles/my_dataset
```

The copied `.dataforge/manifest.yml` records the DataForge release from which
the project was created and the most recently applied release. The
`/init-project` skill displays these values before asking for project inputs
and preserves the file unchanged. Projects without the file can still be
initialized; the skill reports that version metadata is unavailable before
continuing.

The new folder name is usually also the Databricks Asset Bundle name. For example, a copied folder named `my_dataset` should normally produce:

```yaml
bundle:
  name: "my_dataset"
```

Use a different `bundle.name` only when the project explicitly requires a different deployed bundle identity.

## 2. Template Bundle Overview

The copied project keeps the same high-level structure as the template:

- `.dataforge/manifest.yml`: standalone template provenance containing the
  original and last-applied DataForge release versions. It is not DAB
  configuration.
- `.dataforge/CHANGELOG.md`: DataForge template release history. A root
  `CHANGELOG.md` belongs to the generated project and is not managed by
  DataForge.
- `default.databricks.yml`: commented skeleton used to create `databricks.yml`.
- `<DOMAIN>.databricks.yml`: recursively applied non-project defaults and target
  overrides, such as `FMD.databricks.yml` or `CUR.databricks.yml`. Project
  identity is not defined in these files.
- `common.py`: shared notebook bootstrap and fallback defaults for direct notebook runs, tests, and missing task parameters.
- `resources/common.yml`: shared complex variables for job clusters and
  notebook base parameters.
- `resources/jobs/*.yml`: job-specific variables, definitions, task graphs,
  parameters, and application of the shared permission profile.
- `jobs`: dataflow, curation, service, and operation task
  notebooks.
- `src/oeds/domain`: reusable workflow code and packaged project configuration.
- `releases`, `examples`, `tests`, `apps`, `cluster`, `script`, and `tools`: supporting assets for release, validation, app deployment, cluster setup, and maintenance.

`databricks.yml` is the generated project file. It should be created in the copied project root from `default.databricks.yml`, the selected domain file, and project-specific values.

## 3. Gather Initialization Values

Before creating `databricks.yml`, gather explicit values and resolve inferable
values from approved sources. Every initialization placeholder has adjacent
comment metadata that is the authoritative input contract:

```yaml
# name: <placeholder name>
# description: <business meaning and format>
# required: true
# value:
#   modes: ["input"]
#   input_example: "sample-value"
```

Each placeholder lists only its applicable mode details. `options` requires a
listed selection, `infer` applies only its documented rule, and `input` requests
a free-form value using its optional example as guidance. An example is never a
default.
Show inferred values and their sources for confirmation before writing files.

Read the current placeholder details directly in `default.databricks.yml` and
`resources/jobs/*.yml`. Do not maintain a second mapping table in this guide.
Do not invent project identity, secret scope, service principal, workspace,
resource ID, email, or Datamart values. Keep shared defaults from
`default.databricks.yml` only when they are intentional platform defaults.

Every job resource file also begins with its selection contract:

```yaml
# purpose: <concise purpose and selection guidance>
# required: <true|false>
```

`purpose` must be a non-empty single-line statement, and `required` must be the
lowercase literal `true` or `false`. Each field must appear exactly once before
`variables`. This metadata is authoritative for job selection. The current
DATAFLOW, CURATION, SERVICE, and OPERATION definitions are all
optional.

After confirming the bundle and project values, discover job definitions from
`resources/jobs/*.yml`. Display every job exactly once in a Markdown task list,
grouped under `Required` and `Optional`, with its key, status, and purpose.
Required jobs are selected and locked; they are not choices. Never construct
combined job labels or enumerate job combinations. Ask for the complete optional
selection in one response containing comma-separated job keys or `none`. The
developer may select no optional jobs, including a selection that enables no
jobs. If the client provides a native multiple-selection control, it must
contain one item per optional job. On refresh, mark optional job includes from
`databricks.yml` as initially selected. Each resource file must have valid job
metadata, declare exactly one unique job, and have valid name and description
placeholder contracts. Do not ask for disabled-job identities.

## 4. Manually Create `databricks.yml`

Create `databricks.yml` in the copied project root by layering values in this precedence order:

1. Developer-provided project values.
2. Domain-specific non-project overrides from the selected `<DOMAIN>.databricks.yml`.
3. Shared defaults from `default.databricks.yml`.

Use `default.databricks.yml` as the editable skeleton because it contains the full section order and comments. Apply the selected domain file recursively: if the domain file defines only one nested key, keep sibling keys from `default.databricks.yml`.

Preserve non-job includes and add explicit includes for every required job and
selected optional job. List required jobs first and optional jobs second, with
each group sorted by job key. Do not copy the
`resources/jobs/*.yml` discovery pattern into generated configuration.
Keep the default `sync.exclude` entries for `apps/**` and
`resources/apps/**`, and do not add an app resource include. Databricks Apps
are deployed separately from this job bundle.

For a project that selects DATAFLOW, the generated list is:

```yaml
include:
  - resources/common.yml
  - resources/jobs/dataflow.yml
```

Selecting no jobs is also valid. In that case, the generated list contains only
`resources/common.yml`.

`default.databricks.yml` owns one complex `project` variable with `team`,
`domain`, `tag`, `catalog`, `dataset`, and `raw_path` initialization
placeholders. This object is the complete list of required project inputs for
developers and initialization tools. Resolve it from explicit or confirmed
inferred inputs; never add a `project` object to a domain or target override.
The default file supplies shared derivations for workspace roots, catalog
names, volume paths, secret scopes, service-principal keys, and antivirus paths.
The selected domain file may recursively override any declared non-project
bundle variable.

Databricks bundle complex variables support nested references such as
`${var.project.tag}`. See the
[Databricks variables documentation](https://docs.databricks.com/gcp/en/dev-tools/bundles/variables)
and the
[Databricks CLI nested-field acceptance test](https://github.com/databricks/cli/blob/3b75fa4ad6fff0b87e19ebf16aea1e0fa3f87cb3/acceptance/bundle/variables/resolve-field-within-complex/databricks.yml).

For target-owned domain variables, the default file contains the declaration
and a commented sample but no active target override. The selected domain file
must provide `job_runas_account`, `job_alert_emails`, `job_permissions`, and
`email_mappings` for every target. Never copy a commented sample into generated
configuration unless it matches the approved domain value.

Resolve every root template-time placeholder in the generated `databricks.yml`
through a mode allowed by its adjacent comment metadata. Use the resolved
`project.domain` to select the matching `<DOMAIN>.databricks.yml` file. Do not
leave a required initialization placeholder unresolved.

Keep the standalone `variables.catalog` declaration. It converts the catalog
tag into the fully qualified `${var.env}_${var.project.catalog}_cat` value used
by Volume paths and the notebook `catalog` parameter. It is a derived bundle
variable, not an additional initialization input.

Resolve required name and description placeholders only in enabled job resource
files. Their `infer` modes produce the uppercase
`<DOMAIN>-<DATASET>-<JOB-TYPE>` name and the
`<dataset> <job-type> job` description; show these as editable defaults. Their
`input` modes accept confirmed complete values without enforcing the inferred
name structure. Uppercase every inferred, provided, or existing refresh job
name before confirmation and writing; do not change description casing. Leave
disabled job files unchanged.

Keep `variables.raw_root` derived as
`/Volumes/${var.env}_raw_cat/${var.project.raw_path}`. Do not replace it with a
complete project path during normal initialization. The supplied
`project.raw_path` must be relative, must not begin with `/`, and must not
contain empty, `.` or `..` path segments.

Keep these files unchanged unless the project explicitly updates shared defaults or domain target overrides:

- `default.databricks.yml`
- `<DOMAIN>.databricks.yml`

## 5. Manually Align `common.py`

After `databricks.yml` is created, update matching `DEFAULT_*` constants in `common.py` from the same resolved values.

At minimum, check these fallback groups:

- Project metadata: `DEFAULT_TEAM`, `DEFAULT_DOMAIN`, `DEFAULT_PROJECT_TAG`,
  `DEFAULT_CATALOG_TAG`, `DEFAULT_DATASET`.
- Date and runtime defaults: `DEFAULT_TIMEZONE`, `DEFAULT_HUMAN_DATE_FORMAT`, `DEFAULT_PYTHON_DATE_FORMAT`, `DEFAULT_SPARK_DATE_FORMAT`, `DEFAULT_HOLIDAY_GROUP`, `DEFAULT_DBK_RUNTIME_VERSION`, `DEFAULT_NEXUS_URL`, `DEFAULT_NEXUS_INIT_PATH`.
- Databricks resources: `DEFAULT_CATALOG`, `DEFAULT_LAND_ROOT`,
  `DEFAULT_OUTBOUND_ROOT`, `DEFAULT_CONFIG_ROOT`, `DEFAULT_CASE_ROOT`,
  `DEFAULT_RAW_ROOT`, `DEFAULT_SECRETE_SCOPE`, `DEFAULT_OEDS_SECRETE_SCOPE`.
- Integration defaults: Azure subscription and tenant IDs, service principal secret keys, workspace URLs and resource IDs, DataBridge job IDs, email service URL key, `DEFAULT_EMAIL_MAPPINGS`, and `DEFAULT_DATAMART_ENDPOINTS`.

When `common.py` has one fallback value for an environment-specific setting, use the resolved `dev` target value because `DEFAULT_ENV` is `"dev"`.

Preserve Python style for derived values. Convert Databricks variable references into Python f-string references instead of leaving `${var.*}` syntax in Python.

Example:

```python
DEFAULT_CATALOG = f"{DEFAULT_ENV}_{DEFAULT_CATALOG_TAG}_cat"
DEFAULT_LAND_ROOT = f"/Volumes/{DEFAULT_CATALOG}/reference_db/vol_{DEFAULT_PROJECT_TAG}_land/{DEFAULT_DATASET}"
DEFAULT_OUTBOUND_ROOT = (
    f"/Volumes/{DEFAULT_CATALOG}/reference_db/"
    f"vol_{DEFAULT_PROJECT_TAG}_land/outbound/{DEFAULT_DATASET}"
)
DEFAULT_CASE_ROOT = f"{DEFAULT_CONFIG_ROOT}/testbench"
```

Do not leave unresolved `{{...}}` placeholders in `common.py`.

## 6. Validate Manual Changes

Before continuing with project implementation, review the generated configuration:

- `databricks.yml` exists in the copied project root and has a final newline.
- `databricks.yml` explicitly includes every required job and only selected
  optional jobs, contains no job wildcard, and references each enabled job file
  once.
- `databricks.yml` does not include an app resource and keeps `apps/**` and
  `resources/apps/**` excluded from bundle synchronization.
- No required `{{...}}` placeholders remain in `databricks.yml`,
  enabled job resource files, or `common.py`. Disabled job files may retain
  placeholders.
- Every active `${var.*}` reference in `databricks.yml`,
  `resources/common.yml`, and enabled job resource files is backed by a
  declaration under
  `variables` across the included bundle files.
- Every target resolves one complete `job_permissions` list, and every enabled
  job references `${var.job_permissions}`.
- Confirmed values resolve the complete `project` object. The selected
  domain supplies target values only for `job_runas_account`,
  `job_alert_emails`, `job_permissions`, and `email_mappings`.
- Base parameters in `resources/common.yml` still align with values read by `common.py`.
- JSON-string variables such as `email_mappings` and `datamart_endpoints` remain valid JSON strings.
- `common.py` compiles as Python.
- The selected domain file name matches the confirmed
  `variables.project.domain` value.
- No secrets, passwords, tokens, or credential values were written to the repository.

## 7. Copilot Path

The template includes Copilot-specific instructions for generating or refreshing `databricks.yml` and aligning `common.py`.

Relevant Copilot files:

- `.github/copilot-instructions.md`: tells Copilot to use the bundled skills for project and cluster initialization.
- `.github/skills/init-project/SKILL.md`: durable instructions for creating `databricks.yml`, applying domain target overrides, resolving placeholders, and synchronizing `common.py`.
- [GitHub Copilot Guide](G002-github-copilot-guide.md): function and usage
  reference for all bundled Copilot customizations.

Use the skill directly. It discovers required inputs and resolution methods from
the placeholder comments:

```text
Use the /init-project skill to create databricks.yml.
Ask me for required values before writing the file.
```

Copilot should follow the same precedence order as the manual process:

1. Confirmed explicit and inferred project values.
2. Selected `<DOMAIN>.databricks.yml`.
3. `default.databricks.yml`.

Expected Copilot output:

- `databricks.yml` is created or refreshed in the copied project root.
- Comments and section order from `default.databricks.yml` are preserved.
- Explicit values are validated, and inferred values are shown with their
  sources and confirmed before files are written.
- Every required job and only the developer-selected optional jobs are included
  explicitly; selecting no optional jobs is valid.
- Domain-specific values are applied recursively.
- Shared platform defaults are inherited intentionally.
- `{{bundle_name}}`, `{{team}}`, `{{domain}}`, `{{tag}}`, `{{catalog}}`,
  `{{dataset}}`, and `{{raw_path}}` are resolved in `databricks.yml`.
- Enabled job names and descriptions are resolved through their documented
  `infer` or `input` modes. Every resolved job name is uppercase, including an
  existing name encountered during refresh; disabled job files remain
  unchanged.
- Matching `DEFAULT_*` constants in `common.py` are updated from the same resolved values.
- The result is checked against `resources/common.yml`, enabled job resource
  files, all job placeholder contracts, and `common.py`.

Always review the Copilot diff before committing. Pay special attention to comments, placeholder replacement, JSON string values, secret handling, and whether `common.py` still reflects the generated `databricks.yml`.

## 8. Common Mistakes

- Creating the project inside the original `dataforge` folder instead of copying it to a new sibling folder.
- Setting `bundle.name` to a value that does not match the copied folder name without a clear project reason.
- Updating `databricks.yml` but leaving stale template defaults in `common.py`.
- Reformatting `default.databricks.yml` and losing comments or section order.
- Treating `{{...}}` placeholders as Databricks runtime variables. They are initialization placeholders and must be resolved before deployment.
- Keeping `resources/jobs/*.yml` in generated configuration instead of writing
  explicit includes for required and selected optional jobs.
- Selecting a domain file that does not match the confirmed
  `variables.project.domain` value.
- Supplying a catalog name with an environment prefix or `_cat` suffix instead
  of the catalog tag.
- Committing real secrets instead of secret scope names, secret key names, or approved non-secret resource identifiers.
