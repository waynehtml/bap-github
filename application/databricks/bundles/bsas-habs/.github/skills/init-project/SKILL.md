---
name: init-project
description: Initialize a copied DataForge project once by generating databricks.yml from default.databricks.yml, adjacent comment mappings, and confirmed inputs, running General, optional Job (including compute), and optional App setup, and aligning common.py fallbacks. Remove only the copied default.databricks.yml after successful validation. Use for new project initialization, not changes to existing project configuration.
---

# Init Project

Create `databricks.yml` in the bundle root by layering values onto `default.databricks.yml`.

## Initialization Scope And Preflight

Run only in a copied project bundle, never in the canonical DataForge template.
Establish the copied project root from repository context before writing files;
if it cannot be distinguished from the canonical template, stop and report the
ambiguity. Preserve every source YAML file in the canonical template.

Before asking for initialization values:

- If `databricks.yml` already exists, stop without overwriting it or deleting
  source templates. For subsequent changes, edit the project configuration and
  corresponding `common.py` fallbacks directly. This also applies after an
  interrupted initialization; report the existing output for review instead of
  automatically restarting or cleaning it up.
- Require `default.databricks.yml`. Record its exact absolute path.
  Verify it is a regular file directly within the resolved copied bundle root;
  reject symbolic links or reparse points. It is the only cleanup target.
- Keep this source file unchanged throughout generation and validation.
- Do not discover, read, merge, validate, or delete legacy domain YAML files.
  Preserve them and all other unrelated YAML files if present in a copied project.

## Template Provenance

Before asking for initialization values, check for `.dataforge/manifest.yml`
in the project root. When it exists, validate that `template` contains non-empty
`name`, `created_from_version`, and `last_applied_version` strings, then show:

```text
DataForge template: <name>
Created from version: <created_from_version>
Last applied version: <last_applied_version>
```

Stop and report malformed metadata instead of displaying an unreliable
version. When the file is absent, state that DataForge version metadata is
unavailable and continue initialization. Treat the file
as standalone provenance rather than Databricks Asset Bundle configuration.
Never create, update, or delete `.dataforge/manifest.yml` during project
initialization.

## Inputs

Use `default.databricks.yml` as the configuration source and apply confirmed
user inputs to unmapped values, preserving unspecified sibling keys and target
overrides in that configuration. Adjacent comment mappings are authoritative
for mapped variables; report conflicting explicit values instead of replacing
the mapped values. Select mapping entries using confirmed `project.domain`,
not a domain filename.

`default.databricks.yml` owns one complex `project` variable containing every
required project initialization input: `team`, `domain`, `tag`, `catalog`,
`dataset`, and `raw_path`. Resolve the complete object from explicit or
developer-confirmed inferred values; target overrides must not redefine it.

## Required Interaction Order

Run General, Job, then App. Ask whether to enable each optional section immediately
before starting it; honor an explicit yes/no already provided. A declined section
must not block the next section. Both may be declined.

### 1. General (Always)

Display provenance, confirm `bundle.name` and the complete `project` object,
then apply confirmed explicit inputs. Resolve shared configuration,
including the literal domain mappings in default.databricks.yml, using Variable
Mappings before optional setup. Always include
`resources/script.yml` for shared hooks and DataBench config publishing.
Preserve inherited job defaults without prompting for job-only values.

### 2. Job (Optional)

Ask "Set up jobs?" before discovering or validating job files. If yes, run Job
Selection, resolve Variable Mappings in common.yml, confirm enabled job identities, then run Compute Setup and any classic
cluster policy selection. Include `resources/jobs/common.yml` exactly once plus
explicit selected job files. Required jobs, including SERVICE, are mandatory only
within enabled Job Setup.

If no, omit all job includes including common.yml, leave job files unchanged, and
skip job discovery, identities, permissions, compute and policy prompts and checks.
Resolve remaining root `compute_config_name` placeholders from the respective
`compute_setup.defaults` folder, including target placeholders, without a compute
choice or confirmation. Require nonempty single-folder defaults with no slashes,
backslashes, or dot segments. Preserve concrete path/runtime/policy overrides and
do not write a selected-compute comment. Keep root variable declarations and
inherited values; report missing required root values rather than inventing job
identities. Proceed to App Setup.

### 3. App (Optional)

Ask "Set up a Databricks App?" after Job Setup completes or is declined. Follow
App Setup only when enabled. App-only and general-only initialization are valid.
After both decisions, write and validate configuration, synchronize existing
`common.py` fallbacks, and perform the existing final cleanup.

## Job Resource Comment Contract

When Job Setup is enabled, every `resources/jobs/*.yml` file except
`common.yml` must begin with one contiguous metadata block before `variables`.
The shared common.yml file is not a selectable job and is exempt:

```yaml
# purpose: Runs one concise, user-facing type of work; select it when applicable.
# required: false
variables:
```

Interpret the fields as follows:

- `purpose` must be a non-empty, single-line statement that explains the job's
  purpose and, for optional jobs, when to select it.
- `required` must be the lowercase literal `true` or `false`. Automatically
  enable `true` jobs and do not allow the developer to deselect them.
- Each field must appear exactly once in the leading block. Stop and report the
  file when either field is missing, empty, duplicated, or malformed.

Treat this metadata as the authoritative selection contract. Do not infer a
job's required status from its file name or resource key. Show every discovered
job's purpose and required or optional status during selection.

## Placeholder Comment Contract

Every template-time `{{name}}` initialization placeholder must have an adjacent
comment block in this form:

```yaml
# name: derived_name
# description: Project value derived from another confirmed field or entered.
# required: true
# value:
#   modes: ["infer", "input"]
#   infer: From confirmed source_name using the documented transformation.
#   input_example: "sample-name"
derived_name: "{{derived_name}}"
```

Interpret the fields as follows:

- `name` must exactly match the placeholder inside `{{...}}`.
- `description` explains the business meaning and any format restriction.
- `required: true` requires one confirmed concrete value in the generated
  project. `required: false` allows omission only when the target structure has
  a documented default or omission behavior. Never leave an in-scope
  initialization placeholder unresolved.
- `value.modes` is a non-empty list containing `options`, `infer`, or `input`.
- `value.options` is required only for `options` mode and is the finite
  allowlist presented to the developer.
- `value.infer` is required only for `infer` mode and is the only approved
  inference rule. Do not extrapolate a new mapping from an example.
- `value.input_example` is optional for `input` mode and contains one sample
  value. Never treat it as a default or approved project value.

The comment metadata next to each placeholder is the authoritative input
contract. Do not duplicate per-variable options, mappings, or examples in this
skill.

Defer `compute_config_name` placeholders to Compute Setup. Defer only
placeholders owned by `resources/apps/main.yml` to optional App Setup.
The shared `app_secrete_scope` placeholder in `default.databricks.yml` belongs
to General and must resolve even when App Setup is declined.
When jobs are declined, resolve the unused compute paths as specified above.
Their adjacent metadata scopes each value to its owning path variable, so they
may resolve to different folder names. The single confirmed compute choice
resolves these inferred values without another input or confirmation prompt.

Resolve all other placeholders as follows:

1. Use an explicit developer value when it is valid for an allowed mode.
2. With no explicit value, apply `infer` when allowed and its source values
   produce one unambiguous result.
3. Otherwise, ask the developer to choose from `options` when allowed.
4. Otherwise, request a value using `input_example` as optional guidance when
   `input` is allowed.
5. Stop when a required value cannot be resolved through an allowed mode.

Show inferred values and their sources to the developer for confirmation before
writing files, except automatic variable mappings, app SPN mappings, and unused compute paths when
Job Setup is declined. Explicit input wins when `input` is an allowed mode. A
value supplied for an `options`-only field must match the allowlist.

For an enabled job name, uppercase every cased character in the complete value
after resolving `infer` or `input` and before showing it for confirmation or
writing it. Preserve punctuation, digits, separators, and whitespace, and do not
change the casing of job descriptions or source project fields. Treat the
uppercase inferred name as the editable default shown to the developer.
Replacing it selects `input` mode; uppercase the replacement and show the
normalized value in the existing confirmation step. Disabled job files are
outside the resolution scope and may retain their template placeholders.

Do not invent project identity, catalog, secret scope, run-as account,
workspace, resource ID, email, or Datamart values when they are not provided,
inferred by an approved comment rule, or supplied by adjacent domain mappings.
Values in `default.databricks.yml` may be shared defaults. Preserve them unless
overridden, except adjacent mappings remain authoritative for mapped variables.

## Job Selection

- Only when jobs are enabled, enumerate `resources/jobs/*.yml`, excluding
  common.yml before metadata validation. Treat each remaining file as
  one selectable job definition and use its declared `resources.jobs` key as
  the user-facing label.
- Before prompting, verify that every discovered file has valid leading job
  metadata, declares exactly one unique job key, and has valid `name` and
  `description` placeholder contracts. Reject missing, malformed, or duplicate
  metadata and job keys instead of hiding an invalid file from the choices.
- Show every discovered job exactly once in a Markdown task list, grouped under
  `Required` and `Optional`. Include each job's key, status, and purpose in this
  format:

  ```text
  Required:
  - [x] <JOB_KEY> (required, locked) - <purpose>

  Optional:
  - [ ] <JOB_KEY> (optional) - <purpose>
  ```

  Show `- None.` when either group is empty. Mark required jobs as selected and
  locked. Do not present required jobs as choices, construct combined job
  labels, enumerate job combinations, or repeat a job in multiple choices.
- If the client provides a native multiple-selection control, give it one item
  per optional job key. Otherwise, use the Markdown task list as the visual
  selection list. Ask the developer to reply once with zero or more optional
  job keys separated by commas, or `none`; state which required jobs, if any,
  are already enabled. Treat the response as the complete optional selection.
  A response of `none` selects no optional jobs; required jobs remain enabled.
- Write explicit include entries for required jobs sorted by job key, followed
  by selected optional jobs sorted by job key. Never emit
  `resources/jobs/*.yml` in generated configuration.
- Leave disabled optional job resource files unchanged and exclude them from
  generated configuration and deployment validation.

## Variable Mappings

Use the same adjacent-mapping contract in both setup sections:

- General always resolves mapped variables in `default.databricks.yml`, before
  Job and App decisions. These remain required when both optional sections are
  declined. All values in these shared mappings must be literal strings without
  `${...}` expressions; project.tag changes must not change mapped values.
- Job resolves mappings in `resources/jobs/common.yml` only when enabled. If
  declined, skip those mappings entirely and leave common.yml unchanged/excluded.

Read each structured `mapping` comment block beside its owning variable
declaration. Strip comment prefixes and parse only the mapping block, stopping
before adjacent placeholder metadata such as `name`, `description`, or `value`.
Each variable owns its domain/target values and explanatory constraints. Do not
maintain a duplicate mapping in this skill or separate configuration files.

Follow each placeholder's adjacent inference contract and match confirmed
`project.domain` case-insensitively. Support two mapping shapes:

- Domain -> scalar: resolve the variable's default directly from that scalar.
  All targets inherit it; do not generate target overrides or require target keys.
- Domain -> target -> value: select each exact target and populate its value.
  If a root default has a mapped placeholder, resolve it from dev only when its
  contract specifies that fallback; never use it in place of another target entry.

Do not leave active defaults unresolved. Validate the shape required by the
adjacent contract rather than interpreting a malformed target mapping as a scalar.

Reject duplicate YAML keys, ambiguous domain matches, missing domain/target
entries, empty required values, and unresolved `{{...}}` or `REPLACE_ME_` values.
Validate against the variable declaration and explanatory comments. Preserve
native YAML types, identifiers, list order, permission entries, and levels.
Keep `email_mappings` a JSON string and validate its contents as JSON; do not
convert it to a YAML object. Report the specific variable/domain/target path on
failure before writing or cleanup; never invent values or retrieve secrets.

Resolve automatically without separate value-entry or confirmation prompts;
domain confirmation authorizes the inference. For mappings read from
`default.databricks.yml`, write resolved defaults and target values only into
generated `databricks.yml`; keep the source default unchanged until cleanup.
For enabled Job mappings, update the copied `resources/jobs/common.yml` in place
and retain its declarations and comments. Mappings are authoritative: report conflicting
explicit or target values instead of silently substituting them.
Unresolved template placeholders are not overrides. Unselected domains are not
resolved. Preserve comments in generated output for later manual maintenance.

## Compute Setup

Only when Job Setup is enabled, read the `compute_setup` comment block
in the Compute settings section of `default.databricks.yml`. Strip the comment
prefix and interpret the block as YAML metadata, not bundle variables. It owns
the choice list and the defaults used by the adjacent `compute_config_name`
placeholder contracts. Do not duplicate choices in this skill or discover
additional configurations from DataBoot, a workspace, or outside the copied
project. The source template catalog is maintained against DataBoot separately.

Require one non-empty `recommended` choice, a non-empty `options` list, and a
`defaults` mapping for `classic-central` and `serverless-central`. Every option
must have a unique non-empty `choice` and one supported `type`:

- `classic-local`: require a non-empty relative `path`. The choice must be
  `classic-local-` followed by the first two dot-separated components
  (major.minor) of `compute_classic_runtime_version.default` from the source
  template. Keep the full runtime value unchanged. This label describes the
  template default; it does not override a runtime supplied by target or
  explicit configuration.
- `classic-central`: the choice is the exact configuration folder name and
  must start with `classic-`. Require a non-empty string `runtime_version`.
- `serverless-central`: the choice is the exact configuration folder name and
  must start with `serverless-`.

Central choices must be single folder names, without `/` or `\`. They do not
have a separate `config_name` or `path`. Reject duplicate YAML keys or choices,
unknown types, absolute local paths, and empty, `.` or `..` path segments. The
recommendation must name a declared choice, and each central default must name
an option of its corresponding type. Report malformed metadata before output.

Present every choice exactly as declared, in order, with its type, central
classic runtime when applicable, and recommendation marked. A recommendation
does not select a value. If the request already provides one exact valid choice,
acknowledge it without asking again; otherwise ask for one choice and wait.
Reject undeclared choices rather than guessing a mapping. Do not write generated
configuration or clean up source templates while the selection is invalid or
missing. One selection applies to all enabled jobs, including required jobs.

Immediately after selecting `classic-local` or `classic-central`, read the
`job_cluster_policy` comment block beside `compute_classic_job_policy_id` in
`default.databricks.yml`. Strip the comment prefix and parse it as YAML metadata.
It owns the job cluster choices and policy IDs; do not duplicate them in this
skill. Require a non-empty `options` list with unique non-empty `choice` values,
a non-empty `label` for each option, and a `policy_ids` mapping with non-empty
string IDs for dev, stg, and prd. Require `default` to name one declared choice.
Reject duplicate YAML keys or malformed metadata before writing configuration.

Present the labels in declared order, marking the option named by `default`.
Accept a declared choice key or its exact label. If the request already provides
one valid job cluster choice, acknowledge
it without asking again. Otherwise, ask for one choice and wait; marking regular
as the default does not replace a response. Reject invalid choices before
writing configuration or cleaning up source templates. Apply one confirmed
choice to all enabled jobs, including required jobs. Skip this interaction for
`serverless-central` and preserve the regular target defaults.

For either classic type, write the selected option's dev, stg, and prd IDs into
`targets.<target>.variables.compute_classic_job_policy_id` in generated
`databricks.yml`, replacing the shared regular target defaults. Report conflicting
explicit policy overrides, including target-specific overrides and
cluster definitions that bypass the selected policy, for resolution instead of
silently replacing them. Keep both classic cluster definitions' `policy_id`
references fixed at `${var.compute_classic_job_policy_id}` through the existing
anchor and merge in `resources/jobs/common.yml`; do not edit them during selection.
Retain the `job_cluster_policy` comment metadata in generated configuration.
The choice changes only the target policy IDs, not runtime, autoscaling, or
init-script settings.

Resolve both central path placeholders independently in the merged configuration:

- For `compute_classic_central_init_path`, use the selected choice when its type
  is `classic-central`; otherwise use `defaults.classic-central`. Substitute
  that folder into `${var.compute_central_root}/configuration/{{compute_config_name}}/init.sh`.
- For `compute_serverless_environment_path`, use the selected choice when its
  type is `serverless-central`; otherwise use `defaults.serverless-central`.
  Substitute that folder into
  `${var.compute_central_root}/configuration/{{compute_config_name}}/configuration.yml`.

Local classic resolves both paths from the central defaults. Scope replacement
to the owning variable, not a global replacement of `compute_config_name`.
Resolve matching placeholders in target overrides using the same type-specific
rule. Preserve central-root overrides and concrete path overrides that match
the expected configuration. Report conflicting explicit or target
path overrides instead of silently replacing them. The confirmed compute choice
also confirms these derived path values; do not request separate folder inputs.
Both central paths must be concrete after this step, even when unused.

Apply the selection to the merged configuration and every enabled job only:

- `classic-local`: set `compute_classic_local_init_path` to
  `${var.bundle_root}/` plus the declared path. Preserve the resolved runtime.
  Use `${var.compute_classic_local_cluster}` as the shared `Job_cluster` definition.
- `classic-central`: use `${var.compute_classic_central_cluster}` as the shared
  `Job_cluster` definition. Set `compute_classic_runtime_version` to the selected
  option's `runtime_version`, replacing the shared template default. Report a
  conflicting explicit or target runtime override for resolution.
  Synchronize `common.py`'s `DEFAULT_DBK_RUNTIME_VERSION` from the resulting
  runtime through the existing fallback synchronization step.
- For either classic type, notebook tasks use `job_cluster_key: Job_cluster`.
  Remove competing task-level `new_cluster`, `existing_cluster_id`, and
  `environment_key` settings and unused job-level `environments` assignments.
- `serverless-central`: preserve the unused classic runtime. Remove job-level
  `job_clusters`, set `environments: ${var.compute_serverless_environments}`,
  and replace every notebook task's classic compute references with
  `environment_key: ${var.compute_serverless_environment_key}`.

Leave condition tasks without compute references and preserve task dependencies,
parameters, scheduling, identities, and permissions. Disabled job files stay
unchanged. Retain all reusable compute definitions and nonconflicting target
overrides. Do not change package versions.

Add `# Selected compute: <choice>` immediately above the `compute_setup` block
in generated `databricks.yml`. Retain the choice metadata, and do not add a
runtime selector variable. Keep `default.databricks.yml` unchanged; apply
resource changes only to enabled copied job files. Validate the
result before cleanup; later manual changes must update both the actual job
configuration and this informational comment.

## App Setup

After Job Setup completes or is declined, ask:
"Set up a Databricks App?" Honor an explicit yes/no already supplied in the
request. Do not infer consent from the presence of the app template.

If declined, leave `resources/apps/main.yml` unchanged, omit its include, and
preserve the `apps/**` and `resources/apps/**` synchronization exclusions.
Do not ask for app identity or secret-key inputs; its placeholders are out of scope.
Apply Deployment Script Rules after the App decision to remove scripts whose
setup dependency is disabled.

If accepted:

1. Read `resources/apps/main.yml` and its adjacent placeholder metadata. Ask for
   the app name without the domain prefix, unless already supplied. Use the
   confirmed `project.domain`; do not ask for the domain again.
2. Trim the input and collapse whitespace. Generate the full name and description
   using their comment contracts. Do not mutate `project.domain`.
3. Show both lowercase values together and require explicit confirmation or
   revisions. Accept full-value replacements through `input` mode, lowercase
   them, and show revised values for confirmation before writing. Require a
   nonempty domain and app input. The full name must contain only ASCII lowercase
   letters, digits, and hyphens and be 2-30 characters; the description must be
   nonempty and at most 500 characters. Ask for a correction instead of silently
   truncating or deleting unsupported characters.
4. Read the commented `app_spn_keys` mapping in `resources/apps/main.yml` by
   stripping the comment prefix and parsing its mapping block as YAML metadata,
   not bundle variables. Match confirmed `project.domain` case-insensitively;
   reject duplicate YAML keys and ambiguous case-insensitive domain matches.
   The selected domain must contain dev, stg, and prd, each with nonempty string
   values for `app_spn_tenantid_key`, `app_spn_id_key`, and `app_spn_secret_key`.
   Reject values containing `REPLACE_ME_` or unresolved `{{...}}` placeholders.
   If the selected mapping is missing, incomplete, or unresolved, stop before
   writing app configuration or cleaning up templates. Report the exact mapping
   paths requiring manual replacement; do not request key values interactively.
   Unselected domains may retain replacement placeholders. If app setup is
   declined, skip mapping parsing and validation entirely.
   This mapping is authoritative over explicit or target overrides
   for these three variables. Report conflicting concrete values for resolution
   rather than silently overriding them or falling back to input mode. Template
   placeholders are pending values, not conflicting overrides.
   Resolve all nine target placeholders automatically from the selected mapping,
   without key-entry or key-confirmation prompts. Domain selection authorizes
   this inference. Never retrieve secret values or create secrets.
5. Once app identity is confirmed and the mapping is valid, populate the app variable defaults and target key
   names in the copied app YAML. Include `resources/apps/main.yml` exactly once
   in generated `databricks.yml`; an existing matching include must not be
   duplicated. Remove only `apps/**` and `resources/apps/**` from generated
   `sync.exclude` so the app source can synchronize. Preserve unrelated exclusions.

The app YAML owns its deployment scripts under top-level `scripts`. Apply
Deployment Script Rules to the merged selections after either App decision.

Preserve the app's command, source path, permissions, SPN bindings, and direct
workspace/warehouse variable bindings. Do not deploy or start the app during
initialization. Include enabled app variables and placeholders in validation;
missing inputs or failed validation prevent source-template cleanup.

## Deployment Script Rules

Read the `script_rules` comment block adjacent to each of `pre_deploy_scripts`
and `post_deploy_scripts` in `default.databricks.yml`. Strip comment prefixes and
parse only the structured block as YAML metadata. These comments own the script
names and conditions; do not maintain a second script-specific rule list here.
Preserve them in generated configuration.

Each block maps exact script names to conditions. `targets` is an optional
nonempty list of declared target names; `requires` is an optional setup name,
`job` or `app`. Both conditions must pass when present. Reject missing blocks,
duplicate keys, empty rules, unknown condition fields, malformed target lists,
and unsupported setup names before writing configuration or cleaning up sources.
Rules apply only to their adjacent selection variable. Unlisted scripts have no
additional filter; they must still exist in included script definitions.

After applying confirmed explicit inputs and target overrides and completing both
setup decisions, resolve each target's effective comma-separated selection (a target override replaces the root
default). Filter exact tokens by that target and the confirmed setup decisions;
trim whitespace, ignore empty tokens, preserve order and repetitions, and write
an empty string when nothing remains. Never add scripts, including scripts whose
conditions pass but were not selected. Write the filtered effective selections
explicitly for each target, so root inheritance cannot reintroduce excluded names.
Compute these from the original merged selections before changing root defaults.
In root defaults, remove scripts with unmet setup dependencies or a target
restriction that does not cover every declared target. Preserve unrelated names.

Validate every target's final selections against the metadata and included script
definitions. Do not run scripts during initialization. Future changes to script
names, target restrictions, or supported setup dependencies belong in YAML metadata.

## Workflow

1. Use `default.databricks.yml` as the skeleton, preserving comments and order.
   Follow the three sections in Required Interaction Order; do not discover jobs
   or resolve app inputs before their respective setup decisions.
2. In General, confirm project identity and apply confirmed explicit values
   to unmapped variables. Resolve General Variable Mappings before
   optional setup; report conflicting mapped values. Ignore `archive/` unless requested.
3. Complete or skip Job Setup, then complete or skip App Setup. Apply conditional
   includes and Deployment Script Rules before writing generated `databricks.yml`.
   Resolve all active root placeholders, including unused compute paths when jobs
   are disabled. Disabled resource files may retain placeholders.
4. Synchronize existing `common.py` fallbacks from effective dev values (target
   overrides over resolved root defaults), even for
   app-only or general-only projects. Preserve `conf/oeds/config`, its namespace,
   and the existing `conf` and `src` import paths.
5. Validate included resources, variable declarations, and shared scripts. When
   jobs are enabled, verify job identities, permissions, compute configuration,
   and common base parameters against `common.py`.
6. Run Validation before Final Cleanup. Preserve recorded sources until all
   applicable checks pass. On failure, retain sources and report output already
   written; never claim partial initialization succeeded.

## Bundle Rules

- Discover initialization inputs from active `{{name}}` placeholders and their
  adjacent metadata, plus the `compute_setup` and `job_cluster_policy` comment
  contracts. Do not maintain a separate hard-coded choice list.
- Resolve the complete `project` object before looking up its domain in mappings.
- Keep each job's name and description placeholders in its own resource YAML.
  Resolve their documented `infer` mode to the uppercase
  `<DOMAIN>-<DATASET>-<JOB-TYPE>` name and the
  `<dataset> <job-type> job` description. When `input` is selected, accept a
  complete value without imposing the inferred structure, but uppercase the
  complete job name before confirmation and writing.
- Resolve job identities only after selection and only for enabled files.
- Keep the standalone `catalog` variable as the fully qualified derived value
  `${var.env}_${var.project.catalog}_cat`; do not replace it with another
  initialization input or inline that expression in its consumers.
- Keep `raw_root` derived as
  `/Volumes/${var.env}_raw_cat/${var.project.raw_path}`.
- Keep the comments from `default.databricks.yml` for each key.
- Apply app includes and synchronization exclusions conditionally through App
  Setup. Keep app identity placeholders in its resource YAML, like job identities.
- Preserve shared script and unrelated includes. Replace job includes
  with the explicit selection produced during initialization.

## common.py Default Synchronization

`common.py` contains fallback values for direct notebook runs, tests, and missing task parameters. During init-project, update those fallbacks so they describe the initialized project instead of the generic template.

Update the matching constants when their source values are present in the
resolved bundle variables or target overrides in the generated configuration:

- Project metadata: `DEFAULT_TEAM`, `DEFAULT_DOMAIN`, `DEFAULT_PROJECT_TAG`,
  `DEFAULT_CATALOG_TAG`, and `DEFAULT_DATASET`.
- Date, geography, and runtime defaults when overridden: `DEFAULT_TIMEZONE`, `DEFAULT_HUMAN_DATE_FORMAT`, `DEFAULT_PYTHON_DATE_FORMAT`, `DEFAULT_SPARK_DATE_FORMAT`, `DEFAULT_HOLIDAY_GROUP`, `DEFAULT_DBK_RUNTIME_VERSION`, `DEFAULT_NEXUS_URL`, `DEFAULT_NEXUS_INIT_PATH`.
- Project Databricks resources: `DEFAULT_CATALOG`, `DEFAULT_LAND_ROOT`, `DEFAULT_CONFIG_ROOT`, `DEFAULT_RAW_ROOT`, `DEFAULT_SECRETE_SCOPE`, `DEFAULT_OEDS_SECRETE_SCOPE`.
- Integration defaults: `DEFAULT_SERVICE_SPN_ID_KEY`,
  `DEFAULT_SERVICE_SPN_SECRETE_KEY`, `DEFAULT_DIS_AV_ROOT`,
  `DEFAULT_DIS_OEDISEXT_CLIENT_ID_KEY`, `DEFAULT_DIS_OEDISEXT_CLIENT_SECRET_KEY`,
  `DEFAULT_EMAIL_SERVICE_URL_KEY`, and `DEFAULT_EMAIL_MAPPINGS`.
- Direct integration defaults: synchronize `DEFAULT_AZURE_SUBSCRIPTION_ID`,
  `DEFAULT_AZURE_TENANT_ID`, internal/external workspace URL and resource ID
  constants, both `DEFAULT_*_DIS_JOB_ID` constants, and both
  `DEFAULT_SQL_WAREHOUSE_*_ID` constants from their matching direct bundle
  variables. These settings do not use `_key` variables or secret lookups.
- Datamart and credential secret-key defaults: keep secret names in their
  matching `DEFAULT_*_KEY` constants. Never resolve secrets during project
  initialization or copy their values into YAML or Python.
  Preserve `compute_classic_job_policy_id` as a deployment-time ID; do not copy
  it into `common.py`.

When `common.py` has a single fallback for an environment-specific value, use
the generated `dev` target value because `DEFAULT_ENV` is `"dev"`. Preserve
the existing Python style for values that remain derived: build the full
catalog from `DEFAULT_ENV` and `DEFAULT_CATALOG_TAG`, and use
`DEFAULT_PROJECT_TAG` and `DEFAULT_DATASET` for derived paths, scopes, and
keys. For mapped variables, use their resolved dev literals rather than rebuilding
tag-based scope or SPN key patterns. Synchronize DEFAULT_SECRETE_SCOPE,
DEFAULT_SERVICE_SPN_ID_KEY, DEFAULT_SERVICE_SPN_SECRETE_KEY, and
DEFAULT_EMAIL_MAPPINGS accordingly. App scope has no common.py fallback.
For other explicit overrides, use the effective resolved value. Do not leave
Databricks `${...}` syntax or unresolved `{{...}}` placeholders in Python code.

The runtime fallback `DEFAULT_DBK_RUNTIME_VERSION` maps to
`compute_classic_runtime_version`; keep the notebook parameter name
`dbk_runtime_version` unchanged. `DEFAULT_NEXUS_INIT_PATH` remains the local
cluster directory, not the full `compute_classic_local_init_path` script path.

## Validation

Before deleting the copied `default.databricks.yml`, check:

- General ran and both setup decisions are reported in the completion summary.
  General-only, job-only, app-only, and combined configurations are supported.
- `resources/script.yml` is included once. Selected pre/post script names exist
  across included files, satisfy adjacent script_rules for every target and setup
  decision, and preserve unrelated script order and repetitions.
- If jobs are disabled, no job files (including common.yml) are included or
  changed. Skip job-specific checks below except verifying concrete root compute
  paths. No job or cluster-policy prompts were issued.

Apply the following compute checks only when Job Setup is enabled:

- The compute metadata is valid and the selected choice is declared. The
  generated selection comment matches the applied configuration.
- Every enabled job uses the selected compute type. Classic notebook tasks
  reference the declared shared cluster; serverless notebook tasks reference
  the declared environment key and contain no classic compute references.
  Condition tasks contain no compute assignments.
- The job cluster policy metadata is valid and remains in generated configuration.
  For classic compute, the choice is confirmed and each target's
  `compute_classic_job_policy_id` matches the selected option's ID for dev, stg,
  and prd. Both shared classic cluster definitions retain
  `${var.compute_classic_job_policy_id}`. Serverless skips the job cluster prompt
  and preserves regular target defaults. No separate policy variable is added.
- The selected path resolves to the declared configuration for dev, stg, and
  prd, honoring central-root overrides without conflicting path overrides.
- Both central path placeholders are resolved using their own type's selected
  or default configuration, including when local classic is selected.
- Central classic uses its declared runtime across targets, with the matching
  `common.py` fallback. Local classic and serverless preserve resolved runtimes.
- All reusable compute variables remain declared, disabled jobs are unchanged,
  and package versions are unchanged by compute selection.

General and conditional resource checks:

- `.dataforge/manifest.yml` is unchanged when present, or its absence was
  reported.
- `databricks.yml` exists and has a final newline.
- Every active initialization placeholder in the template has the standard
  `name`, `description`, `required`, and `value` comment metadata, and each
  `name` matches its placeholder.
- When jobs are enabled, every discovered job file except common.yml has one leading
  `purpose`, one literal Boolean `required`, and exactly one unique job key.
- Every `value.modes` entry is supported, `options` and `infer` are present when
  required by their modes, and any `input_example` is a scalar string.
- When jobs are enabled, `databricks.yml` includes common.yml once, every
  required job, and only selected optional
  jobs, and has no job wildcard. Every included job path exists and appears
  once. Required SERVICE remains included even when no optional jobs are chosen.
- If app setup is enabled, `resources/apps/main.yml` is included exactly once,
  its source directory exists, and app synchronization exclusions are removed.
  Both lowercase identity values are confirmed and valid, every target has
  concrete SPN key names matching the selected domain mapping without replacement
  placeholders, and every app variable reference has a declaration.
  If disabled, the app file is unchanged and excluded from includes, its
  placeholders are out of scope, and both app synchronization exclusions remain.
- No unresolved `{{...}}` initialization placeholders remain in active YAML
  values in `databricks.yml`, included resource files (including common.yml when
  jobs are enabled), or `common.py`. Validate parsed YAML values separately from
  instructional comments: preserved metadata and unselected-domain mapping
  comments may contain placeholders. Disabled resource files are out of scope.
- `email_mappings` remains valid JSON in both `databricks.yml` and `common.py`.
- `datamart_endpoints_key` and credential `_key` variables contain secret key
  names, matching their individual `DEFAULT_*_KEY` constants in `common.py`.
  Do not validate key names as JSON or replace them with resolved values.
- `common.py` compiles as Python after updating fallback constants.
- `conf/oeds/config` remains importable through the `oeds.config` namespace,
  with no configuration package recreated under `src/oeds/domain`.
- Job policy IDs, direct integration values, and secret-key names may inherit
  from `default.databricks.yml`. Azure IDs,
  workspace URLs and resource IDs, DataBridge job IDs, and SQL warehouse IDs
  use direct target values. Datamart and credential settings retain `_key`
  variables.
- The complete `project` object must be resolved from explicit or confirmed
  inferred initialization values and must not be defined by a target override.
  General mappings supply domain-only scope defaults and target-specific SPN
  keys and JSON email_mappings. Scope variables have no target overrides. When jobs are enabled,
  common.yml supplies mapped job variables and target values from each variable's
  adjacent mapping; validate types and equality to the selected domain/target values.
  Do not add `resources.jobs` permission overrides.
- `catalog`, `land_root`, `config_root`, and notebook base parameters must use
  the same fully qualified catalog value.
- `project.raw_path` must be fully resolved, and `raw_root` must remain derived
  from it rather than duplicating a complete project path.
- Every enabled job name and description must be fully resolved through an
  allowed mode. Every resolved job name must be uppercase, including explicit
  full-value inputs.
- Do not inherit a value only when it conflicts with a developer-provided value, conflicts with the selected domain mapping, still contains a placeholder, or the developer identifies it as domain-specific.

## Final Cleanup

Only after every validation check passes, remove the recorded copied
`default.databricks.yml`. Recheck that its exact absolute path is a regular file
directly within the resolved copied bundle root and is not a symbolic link or
reparse point before deletion. Delete only that verified file using its literal
path, without wildcards or recursive removal. Never delete other YAML files,
including legacy domain files, `databricks.yml`, or resource YAML. Preserve
provenance, documentation, and canonical DataForge template files.

If cleanup fails, stop and report the error and the pending source path. Do not
claim initialization succeeded or automatically rerun generation.
After cleanup, verify the recorded `default.databricks.yml` is absent and the
generated `databricks.yml` remains. Report the generated configuration and removed
file, and explain that future configuration changes must keep `databricks.yml`, job
resources, and corresponding `common.py` fallbacks aligned directly.
