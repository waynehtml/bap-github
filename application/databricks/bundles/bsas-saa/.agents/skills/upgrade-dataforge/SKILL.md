---
name: upgrade-dataforge
description: >-
  Upgrade the DataForge-managed .agents, .github, docs, examples, tools, and src trees
  and namespaced metadata in an existing generated project from a tagged
  DataForge release, then revise only project code demonstrably affected by
  changed library APIs. Use for partial DataForge source upgrades, not
  full-template synchronization, project initialization, DataForge release
  preparation, or deployment.
---

# Upgrade DataForge

Upgrade the generated project's DataForge-managed source and supporting
material without replacing its workflow, configuration, or business logic.

## Scope And Authorization

The managed roots are exactly:

- `.agents`
- `.github`
- `docs`
- `examples`
- `tools`
- `src`

Do not copy any other DataForge root into the project. In particular, do not
copy `jobs`, `conf`, `apps`, `releases`, `resources`, `script`, `common.py`,
`databricks.yml`, domain-specific bundle files, or the root `AGENTS.md`.
The only DataForge metadata edits outside the managed roots are updating
`.dataforge/manifest.yml` and refreshing `.dataforge/CHANGELOG.md` as
described below. Treat any `CHANGELOG.md` in the project root as project-owned;
never inspect, compare, create, modify, or delete it. Do not search for or use
alternative DataForge metadata paths.

Read this entire skill before resolving or applying an upgrade. Retain that
loaded snapshot as the authoritative workflow for the complete run. If the
target overlay updates `.agents/skills/upgrade-dataforge/SKILL.md`, do not
reload it or change the current run's rules midway through the upgrade.

A request to use this skill authorizes downloading and comparing a tagged
release. It does not authorize project-file changes until the developer has
reviewed and confirmed the proposed overlay and compatibility edits. It never
authorizes staging, committing, pushing, creating or merging a pull request,
deploying the bundle, or running a Databricks job.

## Required Inputs

Use this source repository:

```text
https://dev.azure.com/azdv-cac-npd-dorg-azcl01/_git/lake-oedataservices01
```

Require both:

- The target stable DataForge version or exact `releases/dataforge-v<version>` tag.
- The currently applied stable DataForge version or exact source tag for the
  six managed roots.

Normalize a supplied target version to `releases/dataforge-v<version>`. Do not
accept a target branch, commit, `HEAD`, prerelease, build metadata, or another
target tag family. Accept any exact tag name for the current baseline, but
never accept a current branch, commit, or `HEAD`. Offer
`.dataforge/manifest.yml` `last_applied_version` as the current-version default
and require developer confirmation. When the developer supplies an exact
current tag without a version, derive the version from that tag's canonical
manifest and require confirmation before continuing.

## Preflight

Run only in an initialized project generated from DataForge. Require:

- `.dataforge/manifest.yml` with non-empty `template.name`,
  `created_from_version`, and `last_applied_version` values, where the name is
  `dataforge`.
- `.dataforge/CHANGELOG.md` whose newest numbered release section matches the
  manifest's `last_applied_version`.
- An active `databricks.yml`; its presence distinguishes a generated project
  from the canonical template.
- A Git working tree with no staged, unstaged, or untracked changes inside the
  project root. Do not stash or discard existing work.
- The target version to be greater than the confirmed current managed-root
  version.

Read every applicable `AGENTS.md` before planning edits. Stop on malformed
metadata, a canonical template, a dirty project scope, an unavailable Git
client, or missing Azure DevOps authentication.

## Temporary Source Checkout

Create a unique direct child of the operating system's temporary directory,
named with a `dataforge-upgrade-` prefix and a random suffix. Place a marker
file in it before adding other content. Resolve and retain its absolute path;
never use an unresolved environment variable, wildcard, home directory, or
workspace root for cleanup.

Clone the source repository into that directory without modifying the project.
Prefer a filtered, no-checkout clone and sparse checkouts when the server and
Git version support them. Fetch the target tag and source tags needed to
resolve the current baseline. Resolve each selected tag to a full commit SHA
and pin those commits for the rest of the run. Do not re-resolve a moving ref
after confirmation.

When the developer supplies only the current version, try these exact current
tag names in order:

1. `releases/dataforge-v<current-version>`
2. `dataforge-v<current-version>`

If both exist and resolve to different commits, stop and ask the developer to
select the exact current tag. If neither exists, ask for the exact current tag
instead of guessing from other repository tags. A developer-supplied current
tag may use any name.

At both commits, require `application/databricks/bundles/dataforge`, a valid
`.dataforge/manifest.yml`, and a `.dataforge/CHANGELOG.md` whose newest
numbered release section matches the manifest. Require the target canonical
manifest version to match its `releases/dataforge-v<version>` tag. Require the
current canonical manifest version to match the confirmed current version
regardless of the current tag's name. Stop when a tag is missing, resolves
ambiguously, has inconsistent metadata, or the current commit is not an
ancestor of the target commit.

Materialize only the canonical DataForge subtree needed for comparison. The
six managed roots beneath that subtree are the source snapshots, while the
two `.dataforge` files are the pinned metadata sources.

## Overlay Comparison

Compare files recursively by relative path and byte content. Detect Git
renames between the confirmed current and target tags when possible. Do not
follow symbolic links; report them as unsupported before project mutation.

Classify every relevant path before changing the project:

- **Add:** Present in the target and absent from the project and current
  release. Copy it from the target.
- **Overwrite:** Present in both the current and target releases while the
  project copy is absent or has different content. The target copy wins,
  including when the project changed or deleted the file. Show these paths
  explicitly because project changes and deletions will be replaced.
- **Unchanged:** Target and project content match. Make no change.
- **Project-only:** Absent from both DataForge snapshots but present in the
  project. Preserve it unchanged, including custom `.github/workflows`, pull
  request templates, automation, skills, prompts, instructions, and project
  documentation.
- **Removed upstream:** Present in the current release and absent from the
  target. Delete it only when the project copy still matches the current
  release. Preserve and report a modified project copy.
- **Add/add collision:** Absent from the current release but independently
  present in both the target and project with different content. Treat this as
  a blocking conflict; do not assume either copy wins.

Do not delete a managed root or replace it wholesale. Copy and remove only
classified files whose resolved paths remain within one of the six managed
roots. Preserve project-only files and directories.

## Instruction Migration

Compare instruction files in both release snapshots with those in the project.
If instructions removed from a managed root have moved to excluded paths such
as root `AGENTS.md`, `jobs/AGENTS.md`, or `conf/oeds/config/AGENTS.md`, identify
the replacement paths and any guidance the project would lose. Include this
gap and the required separate migration in the preview. Do not copy excluded
instructions or treat upgrade confirmation as authorization to migrate them.
If ownership or the effect of a removal is unclear, resolve it before applying
the upgrade. Continue to preserve modified removed files under the overlay rules.

## Compatibility Impact Analysis

After constructing the proposed overlay, inspect the current-to-target source
diff for changes to public imports, exports, classes, functions, methods,
parameters, return contracts, exceptions, and supported configuration consumed
by code.

Also inspect the target versions of `examples`, `tools`, and `src` for new
imports, configuration modules, resource paths, or other dependencies outside
the managed roots. Report a missing non-managed dependency as a blocker. Do not
silently expand the copy scope; propose the smallest compatibility addition or
ask the developer to handle it separately. Check changed local links in `docs`
and report links whose targets are outside the overlay and unavailable in the
project.

Search project code outside the managed roots for affected imports and usage,
including `common.py`, `jobs`, `apps`, `releases`, `conf`, `script`, and tests.
Do not copy corresponding files from the DataForge release. Propose only the
minimum compatibility edits required by a concrete changed contract.

Treat `jobs/**/task_*.py` as project-owned business logic. Never replace a task
notebook with its DataForge counterpart. When a library change affects a task,
preserve its control flow and business transformations and revise only the
specific import, call signature, result handling, or exception handling needed
for compatibility. Report uncertain or behavioral migrations instead of
guessing.

Do not update a non-managed file merely because the target template changed
it. Formatting, cleanup, and unrelated template alignment are outside scope.

## Preview And Confirmation

Before editing, show:

- Source repository URL.
- Confirmed current and target tags, versions, and full commit SHAs.
- Added, overwritten, unchanged, project-only, removed, preserved-removed, and
  conflicting file counts for each managed root.
- Every overwritten project-modified or project-deleted path, preserved
  upstream removal, and add/add collision.
- Each affected non-managed code file, the changed library contract, and the
  exact compatibility revision proposed.
- Every new dependency or broken local documentation link introduced by the
  managed overlay.
- Any instruction migration gap, excluded replacement paths, and separate
  migration needed; explicitly state that this upgrade will not install them.
- Confirmation that task notebooks will not be synchronized from DataForge.
- Confirmation that the currently loaded upgrade skill remains authoritative
  if the overlay updates its on-disk `SKILL.md`.
- The current and target `.dataforge/manifest.yml` `last_applied_version`
  values and confirmation that `template.name` and `created_from_version` will
  remain unchanged.
- Confirmation that `.dataforge/CHANGELOG.md` will be replaced with the pinned
  target release copy, including whether the current project copy differs from
  its current release.

Resolve every add/add collision and ambiguous compatibility migration with the
developer before requesting final confirmation. Do not partially apply the
overlay while questions remain. Require explicit confirmation of the complete
pinned plan.

## Apply

Immediately before writing, verify that the project Git commit and scoped
working-tree state still match the preview. Follow the project's Git branch
instructions and never write directly to a protected default branch.

Apply only the confirmed file operations:

1. Copy target additions and overwrites without transforming their content.
2. Remove only confirmed, unmodified upstream removals.
3. Preserve project-only and modified-removed files.
4. Apply the confirmed minimal compatibility edits outside the managed roots.
5. Set the project's `.dataforge/manifest.yml` `last_applied_version` to the
   exact value read from the pinned downloaded target release after verifying
   that it matches the target tag. Preserve `template.name`,
   `created_from_version`, all other metadata, and the existing file format.
6. Replace `.dataforge/CHANGELOG.md` with the byte-identical file from the
   pinned target release.

Do not invoke `init-project`, change bundle configuration, or deploy the
project.

If a write fails, stop and report every completed and pending operation. Do not
roll back automatically or claim partial success.

## Validation And Completion

Before finishing:

- Recompare every target file against the project and require byte-identical
  content for all confirmed release additions and overwrites.
- Confirm every project-only and preserved-removed file is unchanged.
- Confirm no unapproved path outside the six managed roots and identified
  compatibility consumers changed except `.dataforge/manifest.yml` and
  `.dataforge/CHANGELOG.md`.
- Revalidate `.dataforge/manifest.yml`; require `template.name` and
  `created_from_version` to be unchanged and `last_applied_version` to match
  the validated target release version.
- Require `.dataforge/CHANGELOG.md` to be byte-identical to the pinned target
  copy and its newest numbered release section to match `last_applied_version`.
- Compile changed Python files and run applicable project-native tests or
  static checks that do not require a deployment.
- Run `git diff --check` and search for unresolved conflict markers, removed
  imports, obsolete call signatures, and other known affected API usage.
- Confirm target `examples`, `tools`, and `src` do not reference an unresolved
  non-managed dependency, and check changed local documentation links.
- Report changed files by managed root, compatibility edits separately, the
  `.dataforge/manifest.yml` version update, the refreshed
  `.dataforge/CHANGELOG.md`, preserved task notebooks, validation results, and
  remaining manual risks.

Do not stage or publish the result. After successful validation or developer
cancellation, remove only the exact marked temporary directory after verifying
that it is beneath the operating system temp directory. Retain and report the
temporary path when a failure requires investigation.
