---
name: tag-project
description: >-
  Validate and publish an annotated release tag for a project initialized from
  DataForge, using committed project-root VERSION and CHANGELOG.md on the current
  pushed branch. Use after project release metadata is committed and pushed,
  not for canonical DataForge template tags, release preparation, or deployment.
---

# Tag Project

Publish one immutable `releases/<project>-v<version>` annotated Git tag from
committed project release metadata. This skill is read-only until tag
publication is confirmed. It does not edit files, prepare releases, switch or
create branches, commit, push branches, create or merge PRs, deploy, synchronize
references, or create provider Release objects.

## Project And Commit

Read the applicable `AGENTS.md` instructions. Starting at the developer's
requested location, or the current directory otherwise, walk upward to the
nearest project root containing `databricks.yml`, stopping at the Git root.
Do not select a sibling project automatically. Stop if no initialized project
is found; reject the uninitialized canonical DataForge template.

Require a concrete, non-empty `bundle.name` without initialization
placeholders. Infer the project name from the project root folder's basename,
not the Git root or a nested invocation directory. The folder and bundle names
may differ; display both and preserve their spelling. Do not rename either.

Require a clean repository working tree, including untracked files, and a
named current branch. Accept feature branches, `main`, and `develop`. Stop on
detached HEAD or pre-existing changes without stashing or discarding work.
Record the current branch and full HEAD commit SHA. The remote branch is the
same named branch on `origin`, regardless of upstream configuration. Require
its remote tip to equal the pinned local HEAD; do not push, fetch, merge, or
switch branches to resolve a mismatch.

Read project-root `VERSION` and `CHANGELOG.md` from the pinned commit using
their repository-relative paths with `git show <commit>:<path>`. Both must be
committed. If absent, direct the developer to `/release-project`, followed by
separate commit and push steps. Never derive or change the project version
from `.dataforge/`, library versions, or a user-supplied version override.

Require `VERSION` to contain exactly one stable `MAJOR.MINOR.PATCH` value and
a final newline (LF or CRLF). Components must be non-negative integers without
leading zeros; no prefix, prerelease identifier, build metadata, extra lines,
or surrounding whitespace is allowed. Require the first dated changelog
release section to match this version, appear exactly once, have a valid
`YYYY-MM-DD` date, and contain at least one change bullet. The release date
need not be today's date.

## Provider And Tag Checks

Determine the provider from `git remote get-url origin`: `github.com` means
GitHub; `dev.azure.com`, `visualstudio.com`, and `ssh.dev.azure.com` mean Azure
DevOps. Stop on an unsupported or ambiguous origin. Never display credentials,
tokens, authorization headers, or credential-helper output.

Derive `releases/<project>-v<version>` without normalizing the project name.
Validate the full ref with `git check-ref-format`; stop if it is invalid.
Inspect only this project's exact `refs/tags/releases/<project>-v` namespace.
Ignore unrelated projects and flat legacy tags. Require all primary remote refs
in that namespace to end in exact stable semantic versions; malformed refs
are an error. Compare version components numerically and require the proposed
version to exceed every existing version. An empty namespace permits an
initial tag from the committed metadata, without inventing a baseline.

Require the exact remote tag to be absent regardless of its target or type.
Require the local tag to be absent, except for an interrupted Azure DevOps
publication: reuse it only when annotated, pointing to the pinned commit, and
carrying the exact annotation below. A lightweight or nonmatching local tag is
a collision. Never force, move, replace, or delete a tag.

Read only the reference matching the provider:

- GitHub: [references/github.md](references/github.md).
- Azure DevOps: [references/azure-devops.md](references/azure-devops.md).

These references are part of this skill and require no canonical DataForge
checkout, sibling projects, or other tag skill.

## Annotation And Confirmation

Extract the complete matching changelog section from the pinned commit,
including its heading, through the next level-two heading (`## `) or end of
file. Exclude the preamble and other releases. Preserve its Markdown and
wording, normalize line endings to LF, and trim only leading and trailing
blank lines. Build the annotation as:

```text
<project> release <version>

<complete matching changelog release section>
```

Show the project name and root, bundle name, provider, current branch, version,
exact tag, full pinned commit, latest remote project tag version (or `none`),
local/remote branch alignment, local and remote tag state, and the complete
annotation. Obtain explicit confirmation before mutation unless the developer
already approved this exact tag, commit, and annotation. An initial request to
tag a project authorizes the checks, not an unspecified publication.

## Publish And Verify

After confirmation, repeat the local and remote checks. Require the project,
branch, HEAD, metadata, and rebuilt annotation to match the confirmed proposal.
If anything changed, stop and present the changed state for review.

Follow the selected provider reference. GitHub uses an authenticated API to
create an annotated tag object and its ref; Azure DevOps uses an annotated Git
tag and an exact-ref push. Do not use `gh`, Azure CLI, lightweight tags, broad
tag pushes, or provider Release objects.

Verify the exact remote tag object, pinned commit, and annotation. After a
timeout or ambiguous result, inspect remote state before deciding whether
publication succeeded. Report partial results, including orphaned GitHub tag
objects or retained Azure DevOps recovery tags. Do not retry while remote
state is unknown.

Report the project and version, provider and method, branch, tag, full tagged
commit, and verification result. State any pending recovery explicitly. Leave
the checkout and release metadata unchanged.
