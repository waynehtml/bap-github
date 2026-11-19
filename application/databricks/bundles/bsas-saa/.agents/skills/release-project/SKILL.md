---
name: release-project
description: >-
  Prepare VERSION and CHANGELOG.md for a project generated from DataForge,
  recommending a semantic version and confirmed release notes from committed
  changes on the current branch. Use for project release metadata, not canonical
  DataForge template releases, tagging, deployment, or release notebooks.
---

# Release Project

Prepare project release metadata from the current checkout's committed changes.
Follow applicable project branch rules before recording the analysis baseline;
create a required task branch from the current HEAD, preserving those changes.
Then stay on that branch and leave the files uncommitted. Do not commit, push,
create pull requests, merge, tag, deploy, or synchronize references.
No provider detection, target branch, or remote branch alignment is required.

## Project And Checkout

Read the applicable `AGENTS.md` instructions. Starting at the developer's
requested location, or the current directory otherwise, walk upward to the
nearest project root containing `databricks.yml`, stopping at the Git root.
Do not select a sibling project automatically. If no initialized project is
found, report that initialization or an explicit project location is needed.
Reject the uninitialized canonical DataForge template.

Require `databricks.yml` to have a concrete, non-empty `bundle.name` without
initialization placeholders. Infer the project name from the project root
folder's basename, not the Git repository root or a nested invocation folder.
The folder name need not equal `bundle.name`; display both without renaming
or modifying either. Use the inferred project name consistently in release
metadata and baseline lookup. Do not infer the project version from the
DataForge manifest or bundled library version files.

Require a named current branch and a clean repository working tree, including
untracked files, before preparation or branch setup. Stop on pre-existing changes
or detached HEAD; do not stash, discard, or commit developer work. The starting
branch may be a feature branch, `main`, or `develop`. Complete any branch setup
required by the applicable `AGENTS.md`, then record the resulting branch and full
HEAD SHA. Use this recorded state for analysis, writing, and validation.

Read project-root `VERSION` and `CHANGELOG.md` when present:

- If both are absent, use the initial-release workflow.
- If only one exists, stop and report incomplete release metadata.
- If both exist, require `VERSION` to contain exactly one stable
  `MAJOR.MINOR.PATCH` value with a final newline. Require the first dated
  changelog release section to match it. Stop on malformed or conflicting
  metadata. Version components are non-negative integers without leading zeros;
  prefixes, prerelease identifiers, and build metadata are not accepted.

## Release Baseline And Version

For an initial release, inspect committed project capabilities and project Git
history at the recorded HEAD. Recommend `1.0.0` and explain the initial scope.
Do not invent a previous release or comparison baseline.

For subsequent releases, prefer the local Git tag
`releases/<project>-v<current-version>`, resolved to its commit. If absent, use
Git history to find the unique commit that introduced the current value of the
project-root `VERSION`, following renames. Do not use `.dataforge/` or library
version transitions as the project baseline. Stop and report candidates if
baseline discovery is ambiguous or unsuccessful. Require the selected baseline
to be an ancestor of the recorded HEAD; do not silently replace an unrelated
or invalid tag with another baseline. This workflow uses available local Git
history and does not fetch or publish remote refs.

Inspect the project-scoped diff and commit history from the baseline through
HEAD, following project renames where relevant. Include committed feature-branch
changes. Exclude sibling-project changes. Stop if there is no meaningful project
change to release.

Recommend the highest applicable semantic-version impact:

- Major for incompatible public APIs, configuration, schemas, job parameters,
  or other deployed contracts requiring migration.
- Minor for backward-compatible pipeline capabilities, optional configuration,
  utilities, or operational features.
- Patch for compatible fixes, documentation, examples, or maintenance.

Ask the developer to accept the recommendation or supply another exact stable
version. Require subsequent versions to be numerically greater than the current
version. Draft concise, user-facing major-update bullets from verified initial
capabilities or the committed release diff. Describe behavior and compatibility
changes; omit merge-only commits and formatting without user impact. Confirm
the version and proposed notes before writing either release file. Confirmation
already supplied for the exact version and notes need not be requested again.

## Write Release Metadata

Before writing, require the current branch, HEAD, and clean working tree to
match the analyzed state. If they changed during review, stop and report that
release analysis must be refreshed.

Write only project-root `VERSION` and `CHANGELOG.md`. Preserve `.dataforge/`,
bundled library versions, configuration, dependencies, vendored references,
and all other project files. If another fix is needed, report it separately.

For an initial release, create the changelog title `# <project> Changelog`.
Otherwise preserve its existing title and historical entries. Insert the new
section before existing release sections:

```markdown
## <version> - <YYYY-MM-DD>

### Major updates

- <confirmed update>
```

Use the current local date. Do not add tag lines or commit hashes to the
changelog. Write the confirmed version to `VERSION` with a final newline.

## Validate And Report

- Verify the exact confirmed stable version and final newline in `VERSION`.
- Verify that the matching changelog section is first, unique, correctly dated,
  and contains the confirmed notes, with prior history preserved.
- Check the complete working-tree change list, including new untracked files,
  and require only the two project-root release files to have changed.
- Run `git diff --check` and inspect newly created release files explicitly.
- Confirm the source branch and HEAD are unchanged. Metadata-only preparation
  does not require running Databricks jobs or the runtime test suite.

Report the project name and root, changed files, previous and new versions
(or initial-release status), baseline when applicable, source branch, full
source commit SHA, and validation results. State that release metadata is
prepared and remains uncommitted; do not claim a published release. After the
release metadata is committed and pushed, use
[`/tag-project`](../tag-project/SKILL.md) as a separate step. Tagging,
publication, deployment, and release notebook preparation or execution are
separate actions. On failure, report any files already written and outstanding
validation without rolling back or concealing partial work.
