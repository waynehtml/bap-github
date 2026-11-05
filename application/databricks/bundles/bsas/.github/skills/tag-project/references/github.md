# GitHub Annotated Tag API

Use this reference only when `origin` is on `github.com`. Parse the owner and
repository from the HTTPS or SSH remote and remove a trailing `.git`.

Use an available authenticated GitHub API mechanism that can create Git tag
objects and refs. A higher-level tool is acceptable only if it preserves the
exact object/ref semantics below. Creating a provider Release or a lightweight
tag is not equivalent.

Use the project name, version, branch, pinned commit, and annotation validated
by `SKILL.md`. URL-encode dynamic ref path components for HTTP requests;
branch names may contain slashes. JSON tag/ref values use the original names.
The branch check always targets the current branch, not the default branch.

## Request Configuration

- Base URL: `https://api.github.com/repos/{owner}/{repo}`
- Accept: `application/vnd.github+json`
- API version header: `X-GitHub-Api-Version: 2026-03-10`
- Creation permission: repository Contents write

Keep authentication in the chosen tool's secure credential mechanism. Never
place a token in output, logs, prompts, command arguments, or a repository
file.

## Read State

Read the remote current branch:

```text
GET /git/ref/heads/<branch>
```

Require `object.sha` to equal the full locally pinned commit.

List project release refs:

```text
GET /git/matching-refs/tags/releases/<project>-v
```

Accept only names matching `refs/tags/releases/<project>-v<stable-semver>` when comparing
versions. Compare numeric components, not strings. An empty result permits
an initial tag. Treat a malformed ref in this namespace as an error because ordering
would be ambiguous.

Check the exact proposed ref:

```text
GET /git/ref/tags/releases/<project>-v<version>
```

A 404 means absent. Any returned exact ref is a collision, regardless of its
target or object type.

## Create

Immediately repeat the remote-branch and exact-ref checks. Then create the
annotated tag object:

```text
POST /git/tags
{
  "tag": "releases/<project>-v<version>",
  "message": "<exact annotation>",
  "object": "<confirmed commit>",
  "type": "commit"
}
```

Record the returned tag-object `sha`. Create its ref:

```text
POST /git/refs
{
  "ref": "refs/tags/releases/<project>-v<version>",
  "sha": "<tag-object sha>"
}
```

Never call an update-ref endpoint and never use force semantics.

## Verify And Recover

Read the exact ref again. Require `object.type` to be `tag` and record its SHA.
Then read the tag object:

```text
GET /git/tags/<tag-object sha>
```

Require:

- Ref SHA equals the created tag-object SHA.
- Tag `object.type` is `commit`.
- Tag `object.sha` equals the confirmed commit.
- Tag `message` equals the exact annotation, ignoring only trailing line
  endings.

For a timeout or ambiguous response, perform these reads before any retry. If
the tag-object request succeeded but ref creation failed, report the known
orphaned tag-object SHA. Do not silently retry through Git or create a second
tag object. Treat 409 or 422 creation responses as collisions unless exact
read-back proves the requested tag already exists with the confirmed contents.
