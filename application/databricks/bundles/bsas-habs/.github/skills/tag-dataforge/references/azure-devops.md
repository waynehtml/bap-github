# Azure DevOps Annotated Git Tags

Use this reference only when `origin` is on `dev.azure.com`, `visualstudio.com`,
or `ssh.dev.azure.com`.

Use Git with the configured `origin` credentials for every remote check and
publication action. Do not use the Azure DevOps REST API, Azure CLI, a
pipeline/build release, or a broad tag push. Never display credential-helper
output.

## Read State

Read remote `main`:

```text
git ls-remote --heads origin refs/heads/main
```

Require exactly one `refs/heads/main` result whose SHA equals the full locally
pinned commit.

List DataForge release refs:

```text
git ls-remote --tags origin "refs/tags/releases/dataforge-v*"
```

Accept primary refs matching
`refs/tags/releases/dataforge-v<stable-semver>`. Ignore only the corresponding
`^{}` peeled companion for a valid primary ref. Treat every other primary ref
in this namespace as malformed.

Check the proposed ref and its peeled companion:

```text
git ls-remote --tags origin "refs/tags/releases/dataforge-v<version>" "refs/tags/releases/dataforge-v<version>^{}"
```

Require no output before publication. Any exact primary ref is a collision.

## Local Tag State

The normal starting state has no local proposed tag. If the local ref already
exists from an interrupted Azure DevOps publication, inspect it with:

```text
git cat-file -t "refs/tags/releases/dataforge-v<version>"
git rev-parse "refs/tags/releases/dataforge-v<version>^{}"
git for-each-ref "--format=%(contents)" "refs/tags/releases/dataforge-v<version>"
git rev-parse "refs/tags/releases/dataforge-v<version>"
```

Reuse it only when its type is `tag`, its peeled commit equals the confirmed
commit, and its annotation equals the complete confirmed annotation after ignoring
trailing line endings. Record the final command's SHA as the local tag-object
SHA. Treat every lightweight or nonmatching local tag as a collision.

## Create And Push

Immediately repeat all local and remote checks and require `HEAD` to equal the
confirmed commit. Write the complete confirmed annotation to a temporary UTF-8
file without a BOM outside the working tree, preserving LF line endings. If no
matching local tag exists, create it with:

```text
git tag -a releases/dataforge-v<version> <confirmed-commit> --cleanup=verbatim -F "<annotation-file>"
```

Repeat the local type, peeled-commit, annotation, and tag-object checks before
pushing only the exact refspec:

```text
git push origin refs/tags/releases/dataforge-v<version>:refs/tags/releases/dataforge-v<version>
```

Never use `--force`, `--tags`, a wildcard refspec, or tag deletion.

## Verify And Recover

Read the exact remote primary and peeled refs again. Require the primary SHA to
equal the recorded local tag-object SHA and the peeled SHA to equal the
confirmed commit. Matching the tag-object SHA also proves that the verified
local annotation is the annotation stored remotely.

If the push fails or returns an ambiguous result, perform this verification
before deciding whether it succeeded. Treat matching refs as success. If both
remote refs remain absent, retain and report the matching local tag. Treat any
other remote state as a collision and do not retry automatically.
