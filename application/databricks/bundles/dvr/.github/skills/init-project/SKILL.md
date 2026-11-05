---
name: init-project
description: Initialize a copied DataForge project once by generating databricks.yml from default and domain YAML templates, resolving project values, job selections, and final compute setup, and aligning common.py fallbacks. Remove copied source YAML templates only after successful validation. Use for new project initialization, not changes to existing project configuration.
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
- Require `default.databricks.yml`. Record its exact absolute path and those of
  all root-level domain `*.databricks.yml` files, including unselected domains.
  Verify every recorded file is a regular file directly within the resolved
  copied bundle root; reject symbolic links or reparse points. Do not include
  nested files or discover additional cleanup targets later.
- Keep these source files unchanged throughout generation and validation.

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

Use values in this precedence order:

1. Developer-provided values from the current request.
2. Domain-specific defaults from `<DOMAIN>.databricks.yml`, for example `FMD.databricks.yml` or `SUP.databricks.yml`.
3. Defaults from `default.databricks.yml`.

Treat the merge as recursive. If a higher-precedence file only defines one nested key, keep sibling keys from the lower-precedence file.

`default.databricks.yml` owns one complex `project` variable containing every
required project initialization input: `team`, `domain`, `tag`, `catalog`,
`dataset`, and `raw_path`. Resolve the complete object from explicit or
developer-confirmed inferred values; domain and target files must not override
it. The selected domain file may recursively override any declared non-project
bundle variable.

## Required Interaction Order

1. Display the available DataForge template provenance.
2. Resolve and confirm `bundle.name` and the complete `project` object.
3. Discover available job resource files, automatically enable every required
   job, display each job once in a checklist, and confirm the optional jobs
   through one response containing individual job keys or `none`. Required
   jobs remain enabled when the optional selection is none.
4. For each enabled job, present the uppercase inferred name and the inferred
   description as editable defaults. Uppercase a replacement name before
   confirming both complete values.
5. Resolve any remaining configuration values, then present the complete compute
   choice list from the Compute settings comments as the final configuration
   stage. After a classic compute choice, select the job cluster policy as
   described in Compute Setup. Apply the confirmed selections to every enabled
   job before validation.

Do not ask for identities belonging to disabled jobs.

## Job Resource Comment Contract

Every `resources/jobs/*.yml` file must begin with one contiguous metadata block
before `variables`:

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

Defer both `compute_config_name` occurrences to the final Compute Setup step.
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
writing files. Explicit input always wins when `input` is an allowed mode. A
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
inferred by an approved comment rule, or supplied by domain-specific defaults.
Values in `default.databricks.yml` may be shared platform or environment defaults used across domains. Keep those shared defaults unless the developer or selected domain file provides a more specific override.

## Job Selection

- Enumerate `resources/jobs/*.yml` at initialization time. Treat each file as
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

## Compute Setup

As the final configuration stage, read the `compute_setup` comment block
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
  template default; it does not override a runtime supplied by domain, target,
  or explicit configuration.
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
explicit or domain policy overrides, including target-specific overrides and
cluster definitions that bypass the selected policy, for resolution instead of
silently replacing them. Keep both classic cluster definitions' `policy_id`
references fixed at `${var.compute_classic_job_policy_id}` through the existing
anchor and merge in `resources/common.yml`; do not edit them during selection.
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
the expected configuration. Report conflicting explicit, domain, or target
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
  conflicting explicit, domain, or target runtime override for resolution.
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
runtime selector variable. Keep source YAML templates unchanged. Validate the
result before cleanup; later manual changes must update both the actual job
configuration and this informational comment.

## Workflow

1. Open `default.databricks.yml` as the editable skeleton. Do not serialize it through a YAML formatter if doing so would remove comments.
2. Resolve and confirm the bundle and project placeholders through their
   adjacent metadata contracts.
3. Select `<DOMAIN>.databricks.yml` by matching the confirmed `project.domain`
   value to the file name case-insensitively. Domain files do not own the
   `project` variable.
4. Discover available jobs and obtain the metadata-driven selection described
   in Job Selection.
5. Resolve the name and description for each enabled job. Uppercase inferred
   and provided names before confirmation, use inferred values as editable
   defaults, and skip disabled job identities.
6. Apply confirmed inferred values to the skeleton.
7. Apply domain overrides recursively onto the skeleton while keeping comments
   and section order from `default.databricks.yml`. Domain overrides are the
   final automatic layer over shared and inferred defaults.
8. Apply confirmed developer-provided values last.
9. Replace the skeleton's job includes with explicit entries for every required
   job and the selected optional jobs.
10. Verify that root project initialization placeholders written as `{{name}}`
    are resolved, except `compute_config_name`, which is deferred to Compute
    Setup. These are template-time placeholders, not Databricks `${var.*}` references.
11. Verify that job identity placeholders are resolved only in enabled resource
    files.
12. Resolve all remaining configuration inputs, then perform Compute Setup as
    the final configuration stage, including the job cluster choice immediately
    after either classic compute choice. Resolve both `compute_config_name`
    occurrences, apply the selections and any central classic runtime change,
    and record the compute comment before writing the merged root configuration
    as `databricks.yml`.
13. Update the corresponding fallback `DEFAULT_*` constants in `common.py` from
    the same resolved initialization values.
14. Keep the recorded source YAML files unchanged until all validation passes
    and the final cleanup step runs.
15. Ignore files under `archive/` as sources for generation unless the developer
    explicitly asks to compare with archived output.
16. Verify that every active `${var.*}` reference in `databricks.yml`,
    `resources/common.yml`, and enabled job resource files is backed by a
    declaration under
    `variables` across the included bundle files.
17. Verify that every target resolves one complete `job_permissions` list and
    that every enabled job consumes that shared variable.
18. Verify that confirmed input values resolve every `project` field and
    that the selected domain supplies target values for `job_runas_account`,
    `job_alert_emails`, `job_permissions`, and `email_mappings`.
19. Verify that base parameters in `resources/common.yml` still align with
    parameters read by `common.py`.
20. Verify that `common.py` fallback defaults align with the generated
    `databricks.yml` values.
21. Preserve project-owned configuration under `conf/oeds/config/<area>` and
    verify that `common.py` exposes `<bundle_root>/conf` as `bundle_conf_dir`
    and adds both `conf` and `src` to the Python import path.

After completing this workflow, run every check in Validation before the
Final Cleanup step. If generation or validation fails, stop and retain all
source YAML files; report the failure and any generated files already written.

## Bundle Rules

- Discover initialization inputs from active `{{name}}` placeholders and their
  adjacent metadata, plus the `compute_setup` and `job_cluster_policy` comment
  contracts. Do not maintain a separate hard-coded choice list.
- Resolve the complete `project` object before applying the selected domain's
  overrides.
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
- Preserve the default `sync.exclude` entries for `apps/**` and
  `resources/apps/**`. Do not add an app resource include; Databricks Apps are
  deployed separately from this job bundle.
- Preserve non-job include entries from the default file. Replace job includes
  with the explicit selection produced during initialization.

## common.py Default Synchronization

`common.py` contains fallback values for direct notebook runs, tests, and missing task parameters. During init-project, update those fallbacks so they describe the initialized project instead of the generic template.

Update the matching constants when their source values are present in the
resolved bundle variables or selected domain target overrides:

- Project metadata: `DEFAULT_TEAM`, `DEFAULT_DOMAIN`, `DEFAULT_PROJECT_TAG`,
  `DEFAULT_CATALOG_TAG`, and `DEFAULT_DATASET`.
- Date, geography, and runtime defaults when overridden: `DEFAULT_TIMEZONE`, `DEFAULT_HUMAN_DATE_FORMAT`, `DEFAULT_PYTHON_DATE_FORMAT`, `DEFAULT_SPARK_DATE_FORMAT`, `DEFAULT_HOLIDAY_GROUP`, `DEFAULT_DBK_RUNTIME_VERSION`, `DEFAULT_NEXUS_URL`, `DEFAULT_NEXUS_INIT_PATH`.
- Project Databricks resources: `DEFAULT_CATALOG`, `DEFAULT_LAND_ROOT`, `DEFAULT_CONFIG_ROOT`, `DEFAULT_RAW_ROOT`, `DEFAULT_SECRETE_SCOPE`, `DEFAULT_OEDS_SECRETE_SCOPE`.
- Integration defaults: `DEFAULT_SERVICE_SPN_ID_KEY`,
  `DEFAULT_SERVICE_SPN_SECRETE_KEY`, `DEFAULT_DIS_AV_ROOT`,
  `DEFAULT_DIS_OEDISEXT_CLIENT_ID_KEY`, `DEFAULT_DIS_OEDISEXT_CLIENT_SECRET_KEY`,
  `DEFAULT_EMAIL_SERVICE_URL_KEY`, and `DEFAULT_EMAIL_MAPPINGS`.
- OEDS integration secret-key defaults: update each `DEFAULT_<CONTEXT_FIELD>_KEY` constant from
  the matching `<context_field>_key` bundle variables. Keep only secret key
  names in these constants; never resolve secrets during project initialization
  or copy their values into YAML or Python. Runtime context retains both the
  `_key` fields and resolved values under their original unsuffixed names.
  Preserve `compute_classic_job_policy_id` as a deployment-time ID; do not copy
  it into `common.py`.

When `common.py` has a single fallback for an environment-specific value, use
the generated `dev` target value because `DEFAULT_ENV` is `"dev"`. Preserve
the existing Python style for values that remain derived: build the full
catalog from `DEFAULT_ENV` and `DEFAULT_CATALOG_TAG`, and use
`DEFAULT_PROJECT_TAG` and `DEFAULT_DATASET` for derived paths, scopes, and
keys. When the selected domain supplies an explicit override, use its effective
resolved value instead of rebuilding the shared derivation. Do not leave
Databricks `${...}` syntax or unresolved `{{...}}` placeholders in Python code.

The runtime fallback `DEFAULT_DBK_RUNTIME_VERSION` maps to
`compute_classic_runtime_version`; keep the notebook parameter name
`dbk_runtime_version` unchanged. `DEFAULT_NEXUS_INIT_PATH` remains the local
cluster directory, not the full `compute_classic_local_init_path` script path.

## Validation

Before deleting any source YAML files, check:

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

- `.dataforge/manifest.yml` is unchanged when present, or its absence was
  reported.
- `databricks.yml` exists and has a final newline.
- Every active initialization placeholder in the template has the standard
  `name`, `description`, `required`, and `value` comment metadata, and each
  `name` matches its placeholder.
- Every discovered job resource file has exactly one non-empty leading
  `purpose`, one literal Boolean `required`, and exactly one unique job key.
- Every `value.modes` entry is supported, `options` and `infer` are present when
  required by their modes, and any `input_example` is a scalar string.
- `databricks.yml` includes every required job, includes only selected optional
  jobs, and has no job wildcard. Every included job path exists and appears
  once. Required SERVICE remains included even when no optional jobs are chosen.
- `databricks.yml` does not include a Databricks App resource and preserves the
  `apps/**` and `resources/apps/**` synchronization exclusions.
- No unresolved `{{...}}` initialization placeholders remain for required
  fields in `databricks.yml`, enabled job resource files, or `common.py`.
  Disabled job files may retain initialization placeholders.
- `email_mappings` remains valid JSON in both `databricks.yml` and `common.py`.
- `datamart_endpoints_key` and the other OEDS integration `_key` variables
  contain secret key names, matching their individual `DEFAULT_*_KEY` constants in `common.py`.
  Do not validate key names as JSON or replace them with resolved values.
- `common.py` compiles as Python after updating fallback constants.
- `conf/oeds/config` remains importable through the `oeds.config` namespace,
  with no configuration package recreated under `src/oeds/domain`.
- Domain override files may be intentionally sparse only for variables that
  have active shared defaults. Job policy IDs and OEDS integration secret-key
  names may inherit from `default.databricks.yml`. The secret-backed Azure,
  workspace, DataBridge, Datamart, and warehouse settings must use `_key`
  variables rather than literal target values.
- The complete `project` object must be resolved from explicit or confirmed
  inferred initialization values and must not be defined by a domain or target
  override.
  Every domain must provide target values for `job_runas_account`,
  `job_alert_emails`, `job_permissions`, and `email_mappings`; do not add
  `resources.jobs` permission overrides.
- `catalog`, `land_root`, `config_root`, and notebook base parameters must use
  the same fully qualified catalog value.
- `project.raw_path` must be fully resolved, and `raw_root` must remain derived
  from it rather than duplicating a complete project path.
- Every enabled job name and description must be fully resolved through an
  allowed mode. Every resolved job name must be uppercase, including explicit
  full-value inputs.
- Do not inherit a value only when it conflicts with a developer-provided value, conflicts with the selected domain file, still contains a placeholder, or the developer identifies it as domain-specific.

## Final Cleanup

Only after every validation check passes, remove the recorded source YAML
files from the copied project, including every unselected domain file.
Recheck that each exact absolute path is a regular file directly within the
resolved copied bundle root and is not a symbolic link or reparse point before
any deletion. Delete only those verified files using literal paths, without
wildcards or recursive removal. Never delete `databricks.yml`, resource YAML,
provenance, documentation, or canonical DataForge template files.

If cleanup fails, stop and report the error, completed deletions, and pending
paths. Do not claim initialization succeeded or automatically rerun generation.
After cleanup, verify every recorded source file is absent and the generated
`databricks.yml` remains. Report the generated configuration and removed files,
and explain that future configuration changes must keep `databricks.yml`, job
resources, and corresponding `common.py` fallbacks aligned directly.
