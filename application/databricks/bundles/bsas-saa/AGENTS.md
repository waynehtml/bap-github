# DataForge Instructions

## Scope and instruction hierarchy

These instructions apply both to the DataForge template and to standalone
projects generated from it. When maintaining DataForge inside a larger source
repository, also follow any applicable ancestor instructions. Keep this file
complete for standalone use; do not replace its general instructions with links
to files outside the copied project.

Before editing a subdirectory, check for a nearer `AGENTS.md`. Follow all
applicable instructions; more specific rules override general guidance.

## Project names and responsibilities

### DataBridge

- DataBridge is the current name for the ingestion project and service formerly
  called DIS/OEDIS. Its sibling source folder is `databridge`, and its vendored
  contract snapshot is under `docs/reference/databridge`.
- DataBridge intentionally retains the legacy `oedis` Python package,
  `oedis.handler.*` contracts, schema identifiers, DIS-prefixed client APIs and
  variables, and OEDIS-named infrastructure. Treat those as compatibility
  identifiers, not as the current service name.

### DataKit

- DataKit is the current name for the shared-library project formerly called
  Common/OEDS Common. Its sibling source folder is `datakit`, and its vendored
  reference is under `docs/reference/datakit`.
- DataKit intentionally retains the `oeds-common` distribution, `oeds.core`
  import namespace, package version, public APIs, and `python-wheel` artifact.

### DataSuite

- DataSuite contains shared Workspace libraries in the sibling `datasuite`
  project. Its API snapshot is managed under `docs/reference/datasuite/api/`.
- This snapshot documents DataSuite APIs; it does not migrate DataForge's local
  libraries or configure a DataSuite runtime dependency.

### Responsibilities and shared contracts

- Keep business-pipeline behavior and DataBridge client integration in this
  project. Keep server-side ingestion runtime and orchestration in DataBridge.
- Reuse documented DataKit APIs for generic, domain-neutral behavior. Do not
  copy shared library implementations into this project or make DataKit depend
  on project-specific code.
- Treat DataBridge request, response, task-result, and error structures as
  compatibility contracts. Reuse existing models, helpers, and exception types;
  do not introduce client-only interpretations or one-off output shapes.
- In DataBridge client APIs, use typed exceptions to distinguish invalid
  inputs, client-side failures, and service-side failures.
- Keep client verification explicit and testable, with its assumptions visible
  to callers. Keep it separate from job submission unless the API explicitly
  combines them.
- Preserve backward compatibility unless a breaking change is explicitly
  authorized. When a change requires a dependency contract update, coordinate
  it with the owning project and affected consumers. If that source is not
  available, report the required change rather than guessing its behavior.

## Project configuration and documentation

### Generated project identity and documentation

- When a project is created or initialized from DataForge, the copied
  `dataforge` folder is renamed to the approved project bundle name. Treat the
  directory containing this `AGENTS.md` as the bundle root and resolve paths
  relative to it; do not assume the folder is still named `dataforge`.
- In generated projects, preserve the original documentation inherited from
  DataForge under `docs/`. Do not edit, rename, move, or delete those documents
  as part of project initialization or project-specific development.
- Keep all project-specific documentation under `docs/project/`, creating the
  directory when needed. Document project behavior, configuration, and
  differences from the template there, linking to inherited documentation
  instead of modifying it.
- Keep the required README catalogs as concise indexes; link to
  `docs/project/` for project-specific details.
- These documentation rules apply to generated projects. They do not prevent
  maintaining documentation in the original DataForge template.

### Project catalogs

- Maintain `src/oeds/domain/README.md` whenever a top-level domain package or
  module is added, removed, renamed, or changes the location of its detailed
  context.
- Maintain `conf/oeds/config/README.md` whenever a configuration area under
  `conf/oeds/config/` is added, removed, renamed, or changes its purpose or
  detailed context.
- Maintain `src/oeds/domain/utils/README.md` whenever a module under
  `src/oeds/domain/utils/` is added, removed, renamed, or changes its public
  APIs, Databricks assumptions, dependencies, side effects, restrictions, or
  linked guide, example, and test coverage.
- Keep the catalog concise, document public APIs only, and preserve valid
  relative links.

### Configuration layout

- Keep project-owned configuration under `conf/oeds/config/<area>` and import
  it through `oeds.config.<area>`.
- Treat `conf` as a Python source root and keep `conf/oeds` as a namespace
  package without an `__init__.py`.
- Keep reusable workflow code under `src/oeds/domain`; do not place project
  configuration back under `src/oeds/domain`.
- Keep secrets, credentials, and environment-specific sensitive values outside
  source-controlled configuration.

## Dependencies and API selection

### Synchronized references

- Treat `docs/reference/datakit/api/`,
  `docs/reference/datakit/guides/`, `docs/reference/databridge/docs/`,
  `docs/reference/databridge/examples/`, and `docs/reference/datasuite/api/` as vendored snapshots owned by their
  source projects. Do not edit files in those directories directly.
- Synchronize or verify those snapshots only when the developer explicitly
  requests `/sync-references` or invokes `release-dataforge`, which includes
  sync mode after release-version confirmation. A DataKit, DataBridge, or
  DataSuite code or documentation change does not authorize synchronization
  into DataForge.
- The synchronization skill requires sibling DataKit, DataBridge, and DataSuite
  source projects. Copy only DataSuite API docs, excluding its guide, dependency
  references, and vendored tools.
  Report unavailable or stale sources instead of guessing or fetching them.

### DataKit API reference

- DataForge consumes the `oeds-common` package version declared in
  `cluster/requirements.txt`; a sibling DataKit source project is not available
  in standalone projects.
- Before using or changing code that imports `oeds.core`, start with
  `docs/reference/datakit/README.md`. Use the generated API index and module
  pages under `docs/reference/datakit/api/` for the complete public
  inventory, exact signatures, and source docstrings, and use
  `docs/reference/datakit/guides/` for operational guidance.
- Use only public APIs documented in that reference. Do not infer missing
  functions, parameters, return behavior, exceptions, or runtime assumptions.
- Confirm that the reference version is compatible with the package requirement
  before relying on it. Report a missing, stale, or conflicting contract rather
  than guessing.

### DataBridge reference

- Before changing DataBridge client integration, handler configuration, or
  task-result handling, start with `docs/reference/databridge/docs/` and
  consult the matching examples under `docs/reference/databridge/examples/`.
- Treat those files as the DataBridge server contract snapshot. Report missing,
  stale, or conflicting behavior instead of inferring an undocumented contract.

### API selection

- Before adding Python or notebook processing code, search the
  [DataForge utilities catalog](src/oeds/domain/utils/README.md) and the
  [DataKit reference](docs/reference/datakit/README.md). Inspect the selected
  local source or documented public signature and relevant examples or tests.
- Reuse DataForge APIs for pipeline-specific behavior and DataKit APIs for
  generic behavior. Extend a compatible API in its owning project before
  creating a new implementation; explain any missing capability.
- Use documented public package imports only. Do not use private members,
  import directly from a DataKit checkout, or add forwarding-only wrappers.
- Treat `oeds.config` definitions as project configuration, not reusable APIs.

## Task skills and project lifecycle

Read the applicable skill before its workflow. These links identify
workflow instructions; slash-command discovery depends on the agent in use.

| Skill | Purpose |
|---|---|
| [init-project](.agents/skills/init-project/SKILL.md) | Initialize once; stop if `databricks.yml` exists. |
| [upgrade-dataforge](.agents/skills/upgrade-dataforge/SKILL.md) | Confirmed partial template upgrade. |
| [create-table](.agents/skills/create-table/SKILL.md) | Create one table reference. |
| [create-view](.agents/skills/create-view/SKILL.md) | Create one view reference. |
| [config-ingest](.agents/skills/config-ingest/SKILL.md) | Compose ingestion configuration. |
| [sync-references](.agents/skills/sync-references/SKILL.md) | Explicitly requested reference synchronization/check. |
| [release-dataforge](.agents/skills/release-dataforge/SKILL.md) | Template release, including reference sync; confirm publication. |
| [tag-dataforge](.agents/skills/tag-dataforge/SKILL.md) | Confirmed tag after the template release merges. |
| [release-project](.agents/skills/release-project/SKILL.md) | Prepare project release metadata. |
| [tag-project](.agents/skills/tag-project/SKILL.md) | Confirmed project release tag. |

### Initialization and subsequent edits

After initialization, edit `databricks.yml` and job resources directly. Keep
`common.py` fallbacks and `resources/jobs/common.yml` aligned. Initialization
uses `default.databricks.yml` and adjacent comment mappings and removes only
the copied default after successful validation. Do not read or remove legacy
domain YAML files as initialization inputs or cleanup targets.

## Working principles

- Evaluate requests independently for incorrect premises, logical gaps,
  ambiguity, missing information, and hidden risks. Recommend safer, simpler,
  or more maintainable approaches when appropriate.
- Distinguish confirmed facts, reasonable inferences, and unverified
  assumptions. Verify technical claims against available evidence and
  authoritative sources; never fabricate details or results.
- Ask focused questions when missing information could materially change the
  outcome. For minor, low-risk gaps, proceed with stated assumptions.
- Assess maintainability, compatibility, security, operational impact,
  reversibility, and effects on existing systems or users before changing them.
- Keep analysis proportional and changes targeted. Preserve behavior unless a
  logic change is requested; avoid unrelated refactoring and distinguish
  required fixes from optional cleanup.
- Run necessary validation, then report changes, confirmed results, remaining
  assumptions, risks, and follow-up actions.

## Engineering and code organization

- Reuse existing patterns and validate inputs and configuration explicitly.
- Raise exceptions for real failures rather than returning partial success.
  Preserve useful error context and stack traces; swallow exceptions only
  when there is a clear recovery path.
- Never log secrets, credentials, tokens, or sensitive payload contents.
- Favor readable, maintainable code. Keep short, clear, single-use logic inline;
  do not extract helpers merely to shorten a function.
- Create helpers when they remove meaningful duplication, name a domain
  concept, isolate complex path or storage behavior, or follow a local pattern.
  Avoid layers of small wrappers that obscure control flow.

### Configuration, logging, and Databricks runtime

- Keep configuration structures consistent across handlers and bundles.
  Validate resolved configuration before execution; introduce handler-specific
  patterns only when necessary and clearly documented.
- Log major execution steps, path resolution, verification, and external I/O.
  Use `debug` for verbose diagnostics and `info` for lifecycle events. Include
  task or handler identifiers where possible and keep logs actionable.
- Use project-specific exception types where available and preserve useful
  stack traces, especially for Databricks jobs.
- Prefer shared path-normalization helpers. Distinguish local paths, `file:`,
  `dbfs:`, `/Volumes`, and cloud URIs; do not mix path conventions or filesystem
  APIs without a clear need.
- Keep notebook and task return payloads compact and structured; put detailed
  diagnostics in logs. Design for Databricks job-output limits and storage
  semantics.

### Python style

- Use meaningful variable, function, and class names. Follow PEP 8 with
  four-space indentation, no tabs, and an 88-character line limit.
- Use `snake_case` for functions and variables, `PascalCase` for classes, and
  `UPPER_CASE` for constants.
- Do not use emoji or Unicode characters that emulate emoji, except in tests
  intentionally verifying multibyte character handling.

## Python documentation and comments

- Use English in code, comments, docstrings, logs, and documentation.
- These rules apply to all Python files, regardless of directory, including
  application code, scripts, tools, tests, and existing `__init__.py` files.
- Whenever creating or editing a Python file, ensure it has a meaningful
  module docstring describing its purpose and responsibilities.
- When adding or modifying public classes, functions, methods, or properties,
  create or update their docstrings. Document parameters, returns, important
  exceptions, and side effects where relevant.
- Prefer clear docstrings and use comments to explain non-obvious logic,
  decisions, assumptions, constraints, and workarounds. Remove comments that
  merely repeat obvious code behavior.
- Apply these requirements to files being created or edited; do not backfill
  unrelated Python files solely to satisfy these rules.
- Do not put the original user prompt, agent instructions, implementation
  guidance, internal reasoning, or generation context in code comments.

## Databricks notebook structure

- When creating or editing notebooks, organize processing into functional
  steps, with each step in its own code cell and related statements together.
- Immediately precede each step's code cell with a Markdown cell containing
  an unnumbered, descriptive heading and a concise explanation of its purpose
  and behavior. Use inline comments for non-obvious logic.
- Preserve execution order, dependencies, and behavior when splitting cells.
  Do not restructure unrelated notebooks solely to satisfy these rules.

## Git and PR workflow

### Branches and tools

- Create a new branch before making changes for a new task or thread. Use a
  short, descriptive `code/` name, such as `code/fix-login-timeout`; do not
  commit directly to `main`.
- Use PowerShell-native scripts and command sequencing; do not use `&&`.
- Do not try `apply_patch`; it is blocked by policy.
- Do not repeat `git status`, `git diff`, or validation unless the previous
  step failed or new changes appeared.

### Provider selection

- Determine the provider from `git remote get-url origin`, not pipeline files.
  Use GitHub for `github.com`; use Azure DevOps for `dev.azure.com`,
  `visualstudio.com`, or `ssh.dev.azure.com`. If unclear, stop and ask.

### Shared workflow

1. Run only necessary validation for the changed files. Summarize changes and
   results, then wait for explicit user confirmation before staging,
   committing, pushing, creating a PR, or merging.
2. After confirmation, stage and commit the intended files, push the current
   branch to origin, and create or reuse an active PR to `main`.
3. Complete or merge the PR using the provider rules below. Poll briefly until
   the merge succeeds or a policy/merge error is returned. Delete the remote
   source branch only after successful merge, or through the provider's
   completion option.
4. Switch to `main`, fast-forward pull, delete the merged local source branch,
   and prune deleted remote branches.
5. Report the PR ID, source commit, merge commit, and final local branch status.

### GitHub

- Use the GitHub connector to create, inspect, and merge PRs. Use `gh` only if
  the connector is unavailable and the user explicitly approves the fallback.
- Pin the expected head commit when merging. Delete the remote source branch
  after successful merge.

### Azure DevOps

- Use the REST API directly with cached Git Credential Manager credentials;
  do not use Azure CLI. Avoid exploratory CLI attempts unless REST fails.
- Retrieve credentials once per PR flow. Never print usernames, passwords,
  PATs, or authorization headers.
- Immediately complete the PR with `deleteSourceBranch=true`. If completion
  is `queued`, poll every 2 seconds for up to 60 seconds before reporting a
  policy or merge delay.
