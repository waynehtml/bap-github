---
name: release-dataforge
description: >-
  Prepare and merge a canonical DataForge template release by recommending a
  semantic version, synchronizing vendored references, drafting confirmed
  changelog updates, and updating standalone provenance metadata. Use for DataForge
  template releases, not release notebooks or releases of projects copied from
  DataForge.
---

# Release DataForge

Prepare and merge a DataForge template release without creating its tag. A
direct request authorizes `sync-references` in sync mode and the confirmed
release-file updates. Git publication remains gated by the final validated
summary and a separate explicit confirmation. This skill never authorizes a
Git tag or deployment.

## Preflight

Read these files before making changes:

- `.dataforge/manifest.yml`
- `.dataforge/CHANGELOG.md`
- `default.databricks.yml`
- `.agents/skills/sync-references/SKILL.md`

Run only in the canonical `dataforge` template directory. Confirm that the
directory is named `dataforge`, `default.databricks.yml` still contains its
initialization placeholders, and no generated `databricks.yml` is active in
the directory. Stop when invoked from a copied project.

Validate `.dataforge/manifest.yml` as standalone metadata, not as Databricks
Asset Bundle configuration. It must have this shape:

```yaml
template:
  name: dataforge
  created_from_version: "<stable-semver>"
  last_applied_version: "<stable-semver>"
```

Require the two versions to match in the canonical template. Require the first
`## <version> - <date>` section in `.dataforge/CHANGELOG.md` to match
`last_applied_version`. Require clean local `main` and require provider
remote `main` to equal
local HEAD before release analysis. Stop and report pre-existing developer
changes; do not stash or discard them. After the version is confirmed and
before changing files, create
`code/release-dataforge-<version>`; stop if that branch already exists.

## Release Baseline

Prefer the commit referenced by `releases/dataforge-v<current-version>` as
the release comparison baseline. When that tag is missing, infer the baseline from Git
history in this order:

1. The unique commit that changed `.dataforge/manifest.yml` to the current
   `last_applied_version`.
2. For releases before the manifest existed, the unique commit that changed
   `source_template_version` to the current version.
3. The unique commit that introduced the matching changelog section.

Use an inferred commit only when the version transition is unambiguous. Stop
and report the candidate commits when none or more than one qualify. Inspect
the DataForge diff and commit history after the baseline, together with current
DataForge working-tree changes. Stop when there is no meaningful change to
release.

Follow Git renames when inspecting manifest and changelog history so baseline
discovery remains valid across canonical repository moves.

## Version Recommendation

Recommend the next stable semantic version and give a short rationale:

- Increment major when a copied-project contract is removed or changed in a
  way that requires migration.
- Increment minor for backward-compatible jobs, configuration, utilities, or
  initialization capabilities.
- Increment patch for compatible fixes, documentation, or reference-only
  updates.

Use the highest applicable impact when changes are mixed. Ask the developer to
accept the recommendation or provide another version. Require an exact
`MAJOR.MINOR.PATCH` value greater than the current version. Do not add a `v`
prefix, prerelease identifier, or build metadata.

## Reference Synchronization

After the version is confirmed, invoke `sync-references` in sync mode.
Complete all of that skill's preflight and final-comparison requirements. If
synchronization fails, report any reference changes already made and stop
without updating `.dataforge/manifest.yml` or `.dataforge/CHANGELOG.md`. Do not
roll back pre-existing or synchronized files automatically.

## Release Notes And Metadata

Build concise, user-facing major-update bullets from the release diff and the
completed reference synchronization. Exclude trivial formatting, merge-only
commits, and implementation details that do not change the template experience.
Mention reference synchronization only when it changed managed files.

Show the proposed bullets and obtain developer confirmation before writing the
release section. Insert the confirmed section immediately after the
`.dataforge/CHANGELOG.md` title without rewriting existing releases:

```markdown
## <version> - <YYYY-MM-DD>

Release tag: `releases/dataforge-v<version>`

### Major updates

- <confirmed update>
```

Use the current local date. Do not add release commit hashes. Update both
version fields in the canonical `.dataforge/manifest.yml` to the confirmed
release version. The two fields are seed values for newly copied projects; an
upgrade workflow for an existing generated project must preserve
`created_from_version` and update only `last_applied_version`.

## Validation

Before requesting Git publication:

- Revalidate the manifest shape, exact stable versions, and final newline.
- Confirm the new changelog section is first, unique, dated correctly, and
  matches both manifest versions.
- Confirm `.dataforge/manifest.yml` is not referenced by the DAB `include`
  section.
  It may remain eligible for normal bundle file synchronization.
- Confirm `source_template_name` and `source_template_version` are absent
  from active bundle configuration.
- Re-run the reference comparison and require a clean result.
- Run `git diff --check`.
- Report all changed files, the prior and new versions, the baseline used,
  validation results, and the intended
  `releases/dataforge-v<version>` tag.

Show the final changed-file list, diff summary, validation results, release
version, proposed `chore(dataforge): release <version>` commit message, pull
request title, current branch, and intended tag. Require explicit confirmation
before staging, committing, pushing, creating a pull request, or merging.

## Pull Request Publication

After confirmation, repeat the relevant validation and require the branch,
HEAD, and scoped working-tree state to match the approved summary.

1. Stage only the confirmed release and synchronized-reference files.
2. Commit with `chore(dataforge): release <version>` and record the full
   source commit SHA.
3. Determine the provider from `origin` and push the current branch.
4. Create or reuse the active pull request from the current branch to `main`
   with title `Release DataForge <version>`.
5. Pin the expected source commit when merging, delete the remote source
   branch, and poll briefly until the provider reports a merge commit or a
   policy error.
6. Switch to `main`, fast-forward pull, delete the local release branch, and
   prune deleted remote branches.

Use the GitHub connector for GitHub pull requests. For Azure DevOps, use the
REST API with cached Git Credential Manager credentials and
`deleteSourceBranch=true`; do not use Azure CLI. Never display credentials.

If any publication step fails, stop and report completed and pending actions.
Do not create a tag, deploy the template, or roll back developer changes.

## Completion

Report the pull request ID, source commit, merge commit, released version,
validation results, and final local `main` status. Tell the developer that
tagging is a separate step and that the next explicit action is
`/tag-dataforge`.
