# Copilot Instructions

Follow the repository-wide [DataForge instructions](../AGENTS.md), including
the Git workflow, engineering, code style, and pull-request requirements.
Before editing in a subdirectory, also follow any nearer `AGENTS.md`.

DataBridge is the current name for the ingestion project and service formerly
called DIS/OEDIS. Its sibling source folder is `databridge`, and its vendored
reference is `docs/reference/databridge`. Preserve legacy compatibility names,
including the `oedis` Python package, `oedis.handler.*` contracts, schema IDs,
DIS-prefixed APIs and variables, and OEDIS-named infrastructure.

DataKit is the current name for the shared-library project formerly called
Common/OEDS Common. Its sibling source folder is `datakit`, and its vendored
reference is `docs/reference/datakit`. Preserve the `oeds-common` distribution,
`oeds.core` imports, package version, public APIs, and `python-wheel` artifact.

Use the `/init-project` skill once when creating `databricks.yml` in a copied
DataForge project. It removes the copied default and domain YAML files only
after successful validation and stops if `databricks.yml` already exists.

Use the `/upgrade-dataforge` skill in a generated project when overlaying the
`.github`, `docs`, `examples`, `tools`, and `src` trees from a
`releases/dataforge-v<version>` tag and revising only code demonstrably
affected by changed library APIs.
It does not synchronize task notebooks or perform a full-template upgrade.

Use the `/create-table` skill when creating one table reference under
`conf/oeds/config/schema`. It asks at most three quick questions for the
optional `tbl_<reference_name>`, full table name, and schema, parses supplied
values with best effort, adds the standard five audit columns, and reports the
created path.

Use the `/create-view` skill when creating one standard or user-facing view
reference under `conf/oeds/config/schema`. It asks three quick questions for
the reference, full view name, and SELECT query. The `vw_` and `vwu_` prefixes
are preferred but not required. The skill reports the created path without
deploying the view.

Use the `/release-dataforge` skill only when preparing and merging a release
of the canonical DataForge template. A direct request to use that skill is an
explicit request to run `/sync-references` in sync mode as part of release
preparation. The skill requires a final confirmation before it stages, pushes,
or merges the release pull request, and it never creates the release tag.

Use the `/tag-dataforge` skill only after the release pull request is
merged. It reads the version already recorded on clean, synchronized `main`
and publishes `releases/dataforge-v<version>` only after explicit
confirmation of the exact tag and commit.

Use the `/sync-references` skill only when the developer explicitly asks to
synchronize or verify the vendored DataKit and DataBridge reference
documentation.

After initialization, edit `databricks.yml` and job resources directly, keeping
the corresponding `common.py` fallbacks and shared job context in
`resources/common.yml` aligned. Source default and domain YAML files are
initialization inputs, not ongoing project configuration.

Keep project-owned configuration under `conf/oeds/config/<area>` and import it
through `oeds.config.<area>`. Treat `conf` and `src` as separate Python source
roots: configuration belongs under `conf`, while reusable DataForge workflow
code belongs under `src/oeds/domain`.

Before using an `oeds.core` API, start with
`docs/reference/datakit/README.md`, select the owning module, and read its
page under `docs/reference/datakit/api/` for the complete public inventory,
exact signature, and source docstring. Use the matching file under
`docs/reference/datakit/guides/` for operational guidance. Treat the
vendored reference as the supported DataKit contract for this standalone
project. Use only documented public APIs, confirm compatibility with
`cluster/requirements.txt`, and report missing or conflicting documentation
instead of inventing an API.

Before changing DataBridge client integration, handler configuration, or
task-result handling, consult `docs/reference/databridge/docs/` and the matching
configuration examples under `docs/reference/databridge/examples/`. Report
missing or conflicting
server contracts instead of guessing.
