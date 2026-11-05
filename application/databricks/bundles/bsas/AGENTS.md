# Project Instructions

These instructions apply both to the DataForge template and to standalone
projects generated from it. When maintaining DataForge inside a larger source
repository, also follow any applicable ancestor instructions.

## DataBridge naming

- DataBridge is the current name for the ingestion project and service formerly
  called DIS/OEDIS. Its sibling source folder is `databridge`, and its vendored
  contract snapshot is under `docs/reference/databridge`.
- DataBridge intentionally retains the legacy `oedis` Python package,
  `oedis.handler.*` contracts, schema identifiers, DIS-prefixed client APIs and
  variables, and OEDIS-named infrastructure. Treat those as compatibility
  identifiers, not as the current service name.

## DataKit naming

- DataKit is the current name for the shared-library project formerly called
  Common/OEDS Common. Its sibling source folder is `datakit`, and its vendored
  reference is under `docs/reference/datakit`.
- DataKit intentionally retains the `oeds-common` distribution, `oeds.core`
  import namespace, package version, public APIs, and `python-wheel` artifact.

## Generated project identity and documentation

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

## Project catalogs

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

## Project configuration

- Keep project-owned configuration under `conf/oeds/config/<area>` and import
  it through `oeds.config.<area>`.
- Treat `conf` as a Python source root and keep `conf/oeds` as a namespace
  package without an `__init__.py`.
- Keep reusable workflow code under `src/oeds/domain`; do not place project
  configuration back under `src/oeds/domain`.
- Keep secrets, credentials, and environment-specific sensitive values outside
  source-controlled configuration.

## Synchronized dependency references

- Treat `docs/reference/datakit/api/`,
  `docs/reference/datakit/guides/`, `docs/reference/databridge/docs/`, and
  `docs/reference/databridge/examples/` as vendored snapshots owned by their
  source projects. Do not edit files in those directories directly.
- Synchronize or verify those snapshots only when the developer explicitly
  requests `/sync-references`. A DataKit or DataBridge code or documentation
  change does not authorize synchronization into DataForge.
- The synchronization skill requires sibling DataKit and DataBridge source
  projects.
  Report unavailable or stale sources instead of guessing or fetching them.

## DataKit library API reference

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

## DataBridge reference

- Before changing DataBridge client integration, handler configuration, or
  task-result handling, start with `docs/reference/databridge/docs/` and
  consult the matching examples under `docs/reference/databridge/examples/`.
- Treat those files as the DataBridge server contract snapshot. Report missing,
  stale, or conflicting behavior instead of inferring an undocumented contract.

# Common Instructions

## Instruction hierarchy

- Before editing inside a subdirectory, check for a nearer `AGENTS.md`.
- Follow the nearest `AGENTS.md` together with this file.
- More specific nested instructions override this guidance for that area.

## Change scope

- Prefer minimal, targeted changes.
- Do not refactor unrelated code unless explicitly requested.
- Preserve existing behavior unless the task explicitly requires a logic
  change.
- Distinguish clearly between required fixes and optional cleanup.

## General engineering

- Reuse existing patterns before introducing new ones.
- Validate inputs and configuration instead of relying on implicit
  assumptions.
- Raise exceptions for real failures rather than returning partial success.
- Preserve useful error context and stack traces.
- Avoid swallowing exceptions unless there is a clear recovery path.
- Never log secrets, credentials, tokens, or sensitive payload contents.

## Configuration

- Keep configuration structures consistent across handlers and bundle projects.
- Validate resolved configuration before execution where possible.
- Avoid handler-specific configuration patterns unless necessary and clearly
  documented.

## Logging and error handling

- Log major execution steps, path resolution, verification, and external I/O.
- Use `debug` for verbose diagnostics and `info` for major lifecycle events.
- Keep logs actionable and include task or handler identifiers where possible.
- Use project-specific exception types where available.
- Preserve useful stack traces, especially for Databricks job runs.
- Never log secrets, credentials, tokens, or sensitive payload contents.

## Storage and Databricks behavior

- Prefer shared helpers for path normalization.
- Be explicit about local paths, `file:`, `dbfs:`, `/Volumes`, and cloud URIs.
- Do not mix path conventions or filesystem APIs without a clear need.
- Keep notebook and task return payloads compact and structured.
- Put detailed diagnostics in logs rather than notebook exit payloads.
- Design for Databricks job-output limits and storage semantics.

## PR workflow

### Provider selection

- Determine the repository provider from `git remote get-url origin`.
- Treat `github.com` origins as GitHub repositories.
- Treat `dev.azure.com`, `visualstudio.com`, and `ssh.dev.azure.com` origins as
  Azure DevOps repositories.
- If the provider cannot be determined, stop and ask the user.
- Do not infer the source repository provider from pipeline files in the
  repository.

### Shared workflow

- Keep the flow compact:
  1. Run only the necessary validation for the changed files.
  2. Summarize the completed changes and validation results, then wait for the
     user's explicit confirmation before staging, committing, pushing, creating
     a PR, or merging.
  3. After confirmation, stage and commit the intended files.
  4. Push the current branch to origin.
  5. Create or reuse an active PR from the current branch to `main`.
  6. Complete or merge the PR, then poll briefly until it is merged or a
     policy/merge error is returned.
  7. After a successful merge, delete the remote source branch.
  8. Switch back to `main`, fast-forward pull, delete the local source branch,
     and prune deleted remote branches.
- Use PowerShell-native scripts and command sequencing.
- Do not run repeated `git status`, `git diff`, or validation checks unless the
  previous step failed or new changes appeared.
- If completion succeeds, report the PR ID, source commit, merge commit, and
  final local branch status.

### GitHub repositories

- Use the GitHub connector to create, inspect, and merge pull requests.
- Do not use `gh` unless the connector is unavailable and the user explicitly
  approves the fallback.
- Pin the expected head commit when merging.
- Delete the remote source branch after a successful merge.

### Azure DevOps repositories

- Use the Azure DevOps REST API directly with cached Git Credential Manager
  credentials.
- Do not use Azure CLI.
- Avoid exploratory CLI attempts unless the REST API fails.
- Retrieve credentials once per PR flow and never print usernames, passwords,
  PATs, or authorization headers.
- Immediately complete the PR with `deleteSourceBranch=true`.
- If Azure DevOps returns `queued`, poll every 2 seconds for up to 60 seconds
  before reporting a policy or merge delay.

## Shell and tool fallbacks

- Use PowerShell-native syntax for command sequencing; do not use `&&`.
- Do not try `apply_patch` since it is blocked by policy.


## Code Style and Formatting

- **MUST** use meaningful, descriptive variable, function, and class names.
- **MUST** follow PEP 8 style guidelines.
- **MUST** use 4 spaces for indentation. Never use tabs.
- Limit line length to 88 characters (Ruff formatter standard).
- Use `snake_case` for functions and variables.
- Use `PascalCase` for classes.
- Use `UPPER_CASE` for constants.
- Use English in all code, comments, docstrings, logs, and documentation.
- **NEVER** use emoji or Unicode characters that emulate emoji (for example `✓` or `✗`). The only exception is tests that intentionally verify multibyte character handling.

## Comments and Documentation

- Prefer clear docstrings over redundant inline comments.
- **MUST** avoid comments that simply restate what the code already makes obvious.
- Remove comments that are tautological or self-documenting.
- **MUST NOT** include comments that:
  - Reveal the original user prompt.
  - Expose agent instructions or implementation guidance.
  - Describe what the file contains when it is already obvious.
  - Leak internal reasoning or generation context.

## Code Organization

- Favor readability and maintainability over clever or overly compact code.
- Do not extract a helper function solely to reduce the length of another function.
- Prefer inline code when the logic is:
  - Short
  - Readable
  - Used only once
- Create helper functions when they:
  - Eliminate meaningful duplication.
  - Represent a real domain concept.
  - Isolate complex path, file system, or storage behavior.
  - Follow an existing local pattern in the codebase.
- Avoid layers of small wrapper functions that make control flow harder to follow.
