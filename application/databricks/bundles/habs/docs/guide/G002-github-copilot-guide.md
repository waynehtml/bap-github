# GitHub Copilot Guide

DataForge includes repository instructions, skills, prompts, and path-specific
instructions that help GitHub Copilot work consistently with the template.
This guide explains the function and usage of every customization. The source
files under `.github/` remain authoritative for their detailed behavior.

## Repository Instructions

### `.github/AGENTS.md`

Source:
[`.github/AGENTS.md`](../../.github/AGENTS.md)

#### Function

Requires every Copilot customization to remain synchronized with this guide
and standardizes `conf/oeds/config/<area>` and `oeds.config.<area>` in
customization content.

#### Usage

Applies whenever a file under `.github` is changed. Update the corresponding
section in this guide and preserve the canonical configuration layout and
namespace.

### `copilot-instructions.md`

Source:
[`.github/copilot-instructions.md`](../../.github/copilot-instructions.md)

#### Function

Provides repository-wide DataForge context to Copilot. It directs Copilot to
follow the project `AGENTS.md` files, use the initialization, table-reference,
managed-source upgrade, DataForge release, and release-tagging skills,
invoke reference
synchronization only when explicitly
requested, keep bundle configuration aligned, preserve the `conf` and `src`
source-root boundaries, and verify DataKit and DataBridge contracts against the
vendored references. Invoking `/release-dataforge` counts as an explicit sync
request for that release preparation.

#### Usage

No explicit invocation is required. Copilot applies this file automatically
when working in the DataForge repository. Keep it focused on rules that should
apply broadly; use a skill for a task-specific workflow and a path-specific
instruction for rules that apply only to selected files.

## Skills

### `/init-project`

Source:
[`.github/skills/init-project/SKILL.md`](../../.github/skills/init-project/SKILL.md)

#### Function

Creates or refreshes `databricks.yml` by initializing the complex `project`
object, layering the selected domain's target overrides onto
`default.databricks.yml`, and resolving template placeholders. It interprets
each placeholder's standard comment metadata, including required status and
the allowed `options`, `infer`, or `input` modes. It discovers each job's
purpose and required status from leading comment metadata, automatically enables
required jobs, allows any number of optional selections, and writes explicit
job includes. The current DATAFLOW, CURATION, SERVICE, and OPERATION
definitions are all optional, so a project may select none. It
preserves the default file's comments, order, and app synchronization
exclusions; it never adds an app resource to the job bundle. It also
synchronizes matching `common.py` fallback values, preserves
`conf/oeds/config`, displays and preserves `.dataforge/manifest.yml`
provenance when available, and checks bundle, import-path, and enabled-job
consistency.

#### Usage

Ask Copilot to use `/init-project` when initializing a copied DataForge project
or refreshing its bundle configuration. Copilot discovers required values and
their allowed resolution methods from the comments beside each placeholder. It
first displays the created-from and last-applied DataForge versions when
`.dataforge/manifest.yml` exists, or reports that metadata is unavailable. It
validates choices, applies only documented inference rules,
requests remaining inputs, displays each job once in a required or optional
Markdown checklist, and asks for optional job keys as a comma-separated
response or `none`. It never constructs combined job choices. Copilot then
shows inferred identities for enabled jobs as editable defaults.
It also verifies that project configuration remains available through
`oeds.config` after initialization.

### `/upgrade-dataforge`

Source:
[`.github/skills/upgrade-dataforge/SKILL.md`](../../.github/skills/upgrade-dataforge/SKILL.md)

#### Function

Overlays the `.github`, `docs`, `examples`, `tools`, and `src` trees in an
initialized project from a developer-confirmed tagged DataForge release. It
overwrites matching managed files, preserves project-only files, safely
handles files removed upstream, restores managed files deleted from the
project, and checks code outside those roots for concrete library API impacts.
It updates `.dataforge/manifest.yml` `last_applied_version` while preserving
`created_from_version` and refreshes `.dataforge/CHANGELOG.md` from the
validated target release. It does not synchronize
bundle configuration, project configuration, job definitions, or task
notebooks, and it never reads or changes the project's root changelog.

#### Usage

Ask Copilot to use `/upgrade-dataforge` and provide the target stable DataForge
version or `releases/dataforge-v<version>` tag. Confirm the version currently
applied to the five managed roots or provide its exact source tag. Current
baselines may use the namespaced tag, the legacy `dataforge-v<version>` tag, or
any other exact developer-supplied tag whose canonical metadata matches the
confirmed version. The generated project and both compared releases must
already contain `.dataforge/manifest.yml` and `.dataforge/CHANGELOG.md`;
alternative metadata layouts are unsupported. Review the pinned commit
summary, overwritten or restored project files, upstream removals, collisions,
the proposed `last_applied_version` and DataForge changelog updates, and
compatibility edits before confirming application. Copilot preserves the
business logic in `jobs/**/task_*.py` and changes a task only when a specific
upgraded library contract requires a minimal compatibility edit. If the overlay
updates this skill, the instructions loaded at the start remain authoritative
until the current run completes.

### `/create-table`

Source:
[`.github/skills/create-table/SKILL.md`](../../.github/skills/create-table/SKILL.md)

#### Function

Creates one table reference under `conf/oeds/config/schema` after at most
three quick questions: an optional `tbl_<reference_name>` reference, a full
table name, and an optional schema. The reference is the code-facing name for
the actual table and can resolve to its full table name. A supplied full name
uses `catalog.database.table` form, and a leading `{env}_` catalog prefix is
stripped. The skill parses schema formats with best effort, adds the five
standard audit columns, and changes no dependent project files.

#### Usage

Ask Copilot to use `/create-table`. For the first prompt, provide the code
reference, such as `tbl_customer`, or reply `no` to use `tbl_table_name`. For
the second, provide `catalog.database.table` or reply `no` to use location
placeholders. A leading `{env}_` catalog prefix is stripped. For the third,
paste SQL DDL, Spark `StructType`, JSON, Avro, a column list, or another
schema; reply `no` to create only the audit fields. Copilot creates the
reference without more questions and leads its completion message with the
exact file path. It protects an existing target rather than overwriting it.

### `/create-view`

Source:
[`.github/skills/create-view/SKILL.md`](../../.github/skills/create-view/SKILL.md)

#### Function

Creates one view reference under `conf/oeds/config/schema` after three quick
questions: the code-facing reference, full view name, and SELECT query. The
`vw_` and `vwu_` prefixes are preferred, but any lowercase `snake_case` name
is allowed. The skill strips a leading `{env}_` catalog prefix, validates
registered schema placeholders, and uses a safe empty-result TODO query when
supplied SQL is missing or unusable.

#### Usage

Ask Copilot to use `/create-view`. Provide a lowercase `snake_case` reference,
then a `catalog.database.view` name, and finally one `SELECT` query or a `WITH`
query ending in `SELECT`. Prefer `vw_` or `vwu_`, but alternate prefixes and
unprefixed names are preserved. Paste only the query body because DataForge
generates the `CREATE OR REPLACE VIEW` statement. The skill rejects DDL, DML,
multiple statements, wildcard projections, and unknown schema placeholders.
It creates one reference file, reports its exact path, and does not deploy it.

### `/release-dataforge`

Source:
[`.github/skills/release-dataforge/SKILL.md`](../../.github/skills/release-dataforge/SKILL.md)

#### Function

Prepares and merges a release of the canonical DataForge template. It
determines the current release baseline, recommends the next semantic version,
synchronizes the vendored DataKit and DataBridge references, drafts
major-update notes for confirmation, updates `.dataforge/CHANGELOG.md` and
`.dataforge/manifest.yml`, validates the result, and completes the release pull
request. It never creates the release tag or handles release notebooks in
generated projects.

#### Usage

Ask Copilot to use `/release-dataforge`. Accept or replace its recommended
version, review and confirm the proposed major-update bullets, then review the
validated final file summary. A separate final confirmation authorizes the
skill to stage, commit, push, and merge the release pull request. After the
merge, invoke `/tag-dataforge` as a separate step.

### `/tag-dataforge`

Source:
[`.github/skills/tag-dataforge/SKILL.md`](../../.github/skills/tag-dataforge/SKILL.md)

#### Function

Publishes the annotated `releases/dataforge-v<version>` tag for the DataForge
version already merged on `main`. It validates `.dataforge/manifest.yml`,
`.dataforge/CHANGELOG.md`, local and remote main alignment, version ordering,
and exact-tag absence without changing tracked files. GitHub publication uses
the provider API, while Azure DevOps uses a local annotated tag and an exact
Git refspec push.

#### Usage

Ask Copilot to use `/tag-dataforge` after the release pull request is
merged and local `main` is clean and synchronized. Review the derived version,
exact tag, annotation, and full pinned commit, then explicitly confirm tag
publication. On Azure DevOps, the skill verifies the local tag object and
remote peeled commit through Git and can reuse an exact matching local tag from
an interrupted push. The skill does not prepare releases, change metadata,
create a provider Release object, or deploy DataForge.

### `/init-cluster`

Source:
[`.github/skills/init-cluster/SKILL.md`](../../.github/skills/init-cluster/SKILL.md)

#### Function

Configures workspace or volume-backed init scripts and optional Nexus
wheelhouse caching. It keeps `cluster/env.sh` and `resources/common.yml`
consistent with the selected init script location.

#### Usage

Ask Copilot to use `/init-cluster`, select `workspace` or `volume`, and state
whether the Nexus wheelhouse cache should be enabled. Workspace is the default.
Provide `CLUSTER_BASE_PATH` only for volume init scripts or wheelhouse caching.
Copilot updates `cluster/env.sh` and `resources/common.yml` together and does not
run Databricks deployment commands unless explicitly requested.

### `/sync-references`

Source:
[`.github/skills/sync-references/SKILL.md`](../../.github/skills/sync-references/SKILL.md)

#### Function

Synchronizes or verifies DataForge's vendored DataKit API and guide directories
and its DataBridge documentation and examples. It discovers sibling source projects,
checks that DataKit's generated API reference is current, performs exact
recursive comparisons, and limits stale-file removal to four managed
destinations. The skill contains instructions only and uses filesystem
operations appropriate for the current platform.

#### Usage

Explicitly ask Copilot to use `/sync-references` and state whether to sync
or check only. Sync mode copies changed and missing files unchanged, removes
destination-only files inside the managed directories, and verifies the final
state. Check mode reports differences without writing. Do not invoke this skill
automatically after a DataKit or DataBridge change.

## Prompt Files

### `/init-cluster-form`

Source:
[`.github/prompts/init-cluster.prompt.md`](../../.github/prompts/init-cluster.prompt.md)

#### Function

Provides a reusable fill-in form for the `/init-cluster` skill. It collects the
init script location, optional volume base path, and wheelhouse caching
decision.

#### Usage

Run `/init-cluster-form`, select `workspace` or `volume`, and answer yes or no
for Nexus wheelhouse caching. When a volume base path is required, provide it
explicitly; it must not be inferred from examples or placeholders.

## Path-Specific Instructions

Path-specific instructions are applied automatically when Copilot works on a
file matching the `applyTo` pattern in the instruction's frontmatter.

### `shared-apis.instructions.md`

Source:
[`.github/instructions/shared-apis.instructions.md`](../../.github/instructions/shared-apis.instructions.md)

#### Function

Guides API discovery and ownership for Python and notebook changes. It directs
Copilot to prefer DataForge domain utilities for project-specific behavior and
documented `oeds.core` APIs for generic shared behavior before creating a new
implementation.

#### Usage

Applies automatically to `**/*.py` and `**/*.ipynb`. When selecting an API,
Copilot checks the DataForge utility catalog, the versioned DataKit reference,
the project configuration catalog, relevant source, examples, and tests. It
distinguishes reusable APIs from project definitions and reports missing or
conflicting contracts instead of guessing an API.

### `project-config.instructions.md`

Source:
[`.github/instructions/project-config.instructions.md`](../../.github/instructions/project-config.instructions.md)

#### Function

Defines the ownership, package layout, validation, security, and documentation
rules for project configuration.

#### Usage

Applies automatically to files under `conf/oeds/config/`. Copilot keeps
configuration importable through `oeds.config`, places reusable behavior under
`src/oeds/domain/utils`, and updates the configuration catalog and owning
developer guide when contracts change.

### `task-00-main.instructions.md`

Source:
[`.github/instructions/task-00-main.instructions.md`](../../.github/instructions/task-00-main.instructions.md)

#### Function

Defines the orchestration boundary for the dataflow workflow task. It keeps
run-level decisions, processing dates, shared paths, early completion, and
downstream task values in the main task.

#### Usage

Applies automatically to `jobs/dataflow/task_00_main.py`. Copilot reads the job
definition and dataflow workflow guide before changing the task. Calendar behavior
also requires the calendar guide. Processing work belonging to downstream
stages must not be added here.

### `task-10-ingest.instructions.md`

Source:
[`.github/instructions/task-10-ingest.instructions.md`](../../.github/instructions/task-10-ingest.instructions.md)

#### Function

Defines the ingestion task boundary and its configuration sources of truth. It
keeps DataBridge orchestration separate from DataForge client preparation,
submission, result handling, and verification.

#### Usage

Applies automatically to `jobs/dataflow/task_10_ingest.py` and ingestion JSON
configuration under `conf/oeds/config/ingest/`. Copilot checks the
workflow and DataBridge client guides, the default configuration, and version-matched
DataBridge schemas before changing ingestion behavior.

### `task-20-land-to-raw.instructions.md`

Source:
[`.github/instructions/task-20-land-to-raw.instructions.md`](../../.github/instructions/task-20-land-to-raw.instructions.md)

#### Function

Defines the land-to-raw stage boundary and preserves the required
validate-before-copy behavior. It keeps parsing, standardization, business
validation, and table loading in later stages.

#### Usage

Applies automatically to `jobs/dataflow/task_20_land_to_raw.py`. Copilot uses the
workflow guide, land-to-raw guide, landing-zone practices, and current task
implementation to select supported validation and copy behavior. Landing files
are copied, not moved or deleted.

### `task-30-raw-to-std.instructions.md`

Source:
[`.github/instructions/task-30-raw-to-std.instructions.md`](../../.github/instructions/task-30-raw-to-std.instructions.md)

#### Function

Defines the raw-to-standardized stage order: read, transform, add audit data,
validate, then load. It preserves registered source and target contracts,
required and recommended audit columns, and idempotent batch behavior.

#### Usage

Applies automatically to `jobs/dataflow/task_30_raw_to_std.py`. Copilot consults
the workflow, raw-to-standardized, datafile, and DataFrame validation guides
before selecting documented APIs. Parsing, transformation, or validation
failures must occur before writing.

### `task-40-std-to-curated.instructions.md`

Source:
[`.github/instructions/task-40-std-to-curated.instructions.md`](../../.github/instructions/task-40-std-to-curated.instructions.md)

#### Function

Defines the standardized-to-curated boundary while preventing Copilot from
inventing business rules. It requires an explicit source, target, output grain,
transformation, and write contract.

#### Usage

Applies automatically to `jobs/dataflow/task_40_std_to_curated.py`. Copilot uses
the workflow guide, template guide, registered schemas, and developer
requirements. It asks for missing curated requirements instead of deriving
them from filenames or neighboring tasks.

### `task-50-integrate.instructions.md`

Source:
[`.github/instructions/task-50-integrate.instructions.md`](../../.github/instructions/task-50-integrate.instructions.md)

#### Function

Defines the DataFlow integration boundary while preserving the successful
no-op placeholder until the source, consumer, output contract, delivery target,
and retry behavior are explicit.

#### Usage

Applies automatically to `jobs/dataflow/task_50_integrate.py`. Copilot uses the
DataFlow workflow and template guides, and consults the DataBridge reference
before adding DataBridge delivery. It keeps curated transformations in
`std_to_curated` and does not copy the independent Curation integration task.

### `task-90-on-complete.instructions.md`

Source:
[`.github/instructions/task-90-on-complete.instructions.md`](../../.github/instructions/task-90-on-complete.instructions.md)

#### Function

Defines the successful-completion handler boundary. It limits the task to
idempotent completion actions such as notification, audit recording, safe
cleanup, or explicitly requested downstream triggers.

#### Usage

Applies automatically to `jobs/dataflow/task_90_on_complete.py`. Copilot checks the
workflow definition and dataflow workflow guide. When email is requested, it also
uses the email guide and DataForge example rather than constructing transport
payloads directly.

### `task-91-on-failure.instructions.md`

Source:
[`.github/instructions/task-91-on-failure.instructions.md`](../../.github/instructions/task-91-on-failure.instructions.md)

#### Function

Defines the failure-handler boundary and preserves the original processing
failure as the primary troubleshooting signal. It limits added behavior to
failure notification, incident or audit recording, and safe cleanup.

#### Usage

Applies automatically to `jobs/dataflow/task_91_on_failure.py`. Copilot checks the
workflow and dataflow workflow guide. Email behavior also requires the email guide
and example. Notification or cleanup failures must not obscure the original
pipeline failure.

## Maintaining This Guide

The [Copilot customization instructions](../../.github/AGENTS.md) require this
guide to be updated whenever `copilot-instructions.md`, a skill, a prompt, or a
path-specific instruction is added, changed, renamed, or removed.

For each customization:

1. Keep its source link accurate.
2. Describe what it controls under `Function`.
3. Describe how it is invoked or automatically applied under `Usage`.
4. Include required inputs and expected results when they help a developer use
   the customization.
5. Keep detailed implementation rules in the authoritative `.github` source
   file rather than copying them into this guide.
