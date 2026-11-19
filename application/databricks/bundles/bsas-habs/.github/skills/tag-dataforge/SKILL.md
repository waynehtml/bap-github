---
name: tag-dataforge
description: >-
  Validate and publish an annotated DataForge release tag for the version
  already merged on main. Use after release-dataforge completes its pull
  request, not to prepare a release, change tracked files, deploy the project,
  or create a provider Release object.
---

# Tag DataForge

Publish one immutable `releases/dataforge-v<version>` annotated Git tag for
the DataForge version already merged on `main`. This skill is read-only
except for explicitly confirmed tag publication.

It does not edit, stage, or commit tracked files; publish a branch or pull
request; create a GitHub Release, Azure DevOps release, or pipeline run; or
deploy the project.

## Adapt To The Provider

For GitHub, use the first capable authenticated API mechanism available: a
provider-native connector, a generic authenticated HTTP tool, or a local HTTP
client using already-approved credentials. For Azure DevOps, use Git with the
configured `origin` credentials instead of the REST API.

Do not use `gh`, Azure CLI, or provider-native Release objects. Never display
credentials, tokens, authorization headers, or credential-helper output.

The optional
[`scripts/check-local-release.ps1`](scripts/check-local-release.ps1) helper
performs deterministic local checks without changing files. Run it when
PowerShell is available. Otherwise reproduce its checks with the available
file and Git tools.

## Authorization Boundary

A request to use this skill authorizes only non-mutating checks. Display the
complete proposal and require explicit confirmation of the exact tag and full
pinned commit before any provider mutation.

After confirmation, use only the publication method prescribed for the
detected provider. Never force, replace, move, or delete a local or remote tag.

## Check

Require all of the following:

- Run only in the canonical DataForge template, not a generated project.
- Read the version from `.dataforge/manifest.yml`; require `template.name` to be
  `dataforge` and require `created_from_version` and
  `last_applied_version` to contain the same stable version.
- Require the newest numbered `.dataforge/CHANGELOG.md` section to match that
  version.
- Derive the version from that canonical metadata. Do not ask for or accept a
  version override.
- Require a clean local `main`, a full HEAD commit SHA, and a supported
  GitHub or Azure DevOps `origin`.
- Require the provider's remote `main` to equal local HEAD.
- Require the derived version to be numerically greater than every exact
  stable version under
  `refs/tags/releases/dataforge-v<stable-semver>`.
- Reject malformed refs inside that project namespace.
- Require the exact remote `refs/tags/releases/dataforge-v<version>` ref to be
  absent. Require the local ref to be absent except for an Azure DevOps
  recovery tag that is annotated and exactly matches the derived commit and
  annotation. Treat every other local tag as a collision.
- Ignore flat legacy tags such as `dataforge-v<version>`; do not use them as
  baselines or collisions for this namespace.

Select and read only the provider reference matching `origin`:

- GitHub: [`references/github.md`](references/github.md)
- Azure DevOps:
  [`references/azure-devops.md`](references/azure-devops.md)

## Tag Annotation

Read `.dataforge/CHANGELOG.md` from the pinned commit, using its repository-relative
path with `git show <commit>:<path>`. Extract the complete matching numbered
release section, including its heading, through the next level-two heading
(`## `) or end of file. Exclude the changelog preamble and other releases.
Require exactly one matching section and at least one change bullet. Preserve
its Markdown and wording; normalize line endings to LF and trim only leading
and trailing blank lines. Do not summarize or invent changes.

Build the annotation as the release title, one blank line, and that section.
Include the complete annotation in the proposal and use the same text for
publication, local recovery checks, and remote verification.

Before requesting confirmation, display:

- Provider and derived DataForge version.
- Proposed `releases/dataforge-v<version>` tag.
- Full pinned commit SHA.
- Latest existing version in this project tag namespace, or `none`.
- Local and remote `main` alignment.
- Local and remote exact-tag absence.
- This exact annotation:

```text
DataForge release <version>

<matching changelog release section>
```

## Publish

After explicit confirmation, repeat every local and remote check and require
HEAD to equal the confirmed commit. Rebuild the annotation and require it to
match the confirmed text. Follow the selected provider reference.

For GitHub, create and verify the annotated tag through the provider API. For
Azure DevOps, create or reuse the matching local annotated tag, push only its
exact refspec, and verify the remote tag object and peeled commit through Git.

If a mutation times out or returns an ambiguous response, read the exact remote
state before deciding whether it succeeded. Do not retry while remote state is
unknown. If GitHub creates a tag object without its ref, report the orphaned
object SHA. If an Azure DevOps push fails while the remote ref remains absent,
retain and report the matching local tag.

## Completion

Report the provider, publication method, project version, tag, confirmed
commit, and verification result. Also report any orphaned GitHub tag object or
retained local Azure DevOps tag after failure.

Do not modify tracked files or invoke the release preparation skill as part of
tag publication.
