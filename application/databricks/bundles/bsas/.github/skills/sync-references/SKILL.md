---
name: sync-references
description: >-
  Synchronize or verify DataForge's vendored DataKit and DataBridge reference
  documentation from sibling source projects. Use only when a developer
  explicitly asks to run /sync-references, synchronize dependency references,
  or check their synchronization state; do not invoke automatically after
  DataKit or DataBridge changes.
---

# Sync References

Maintain DataForge's vendored dependency references without relying on a
platform-specific synchronization script.

## Modes

- Use **check mode** when the developer asks to check, verify, or compare the
  references without updating them. Do not create, edit, or delete files.
- Use **sync mode** only when the developer explicitly asks to synchronize or
  refresh the references.

## Repository discovery

Resolve paths from the repository layout instead of using machine-specific
absolute paths. Starting from the DataForge project, locate the bundle-project
directory that contains sibling `dataforge`, `databridge`, and `datakit`
projects.
The DataKit Python project is `datakit/utility/python` beneath that directory.

Do not search outside the available workspace, clone missing projects, or fetch
documentation from a remote repository. Stop and identify every missing source
when the sibling layout is unavailable.

## Managed mappings

Compare and synchronize every file recursively by its relative path and byte
content:

| Source | DataForge destination |
| --- | --- |
| DataKit `docs/api` | `docs/reference/datakit/api` |
| DataKit `docs/guides` | `docs/reference/datakit/guides` |
| DataBridge `docs` | `docs/reference/databridge/docs` |
| DataBridge `examples` | `docs/reference/databridge/examples` |

Copy files unchanged. Do not rewrite Markdown links or include DataKit
`examples`. Treat symbolic links as unsupported and stop instead of following
them outside a managed tree.

## Preflight

Before changing any destination:

1. Confirm that all four source directories exist and are readable.
2. Confirm that each resolved destination is inside the DataForge project and
   exactly matches one of the four managed destinations.
3. Run DataKit's `tools/generate_api_reference.py --check` with an available
   Python interpreter. Use check mode only; do not regenerate DataKit from this
   skill.
4. Build the complete source and destination inventories so missing, changed,
   unchanged, and destination-only files are known before sync mode writes.

Stop without changing DataForge when any preflight check fails or DataKit's API
reference is stale.

## Check mode

Compare all four mappings without writing. Report missing, changed,
destination-only, and unchanged file counts for each mapping and in total. List
the relative paths that prevent synchronization. A missing destination counts
as missing files, not permission to create it in check mode.

## Sync mode

After successful preflight:

1. Create a managed destination directory only when it is missing.
2. Copy missing and changed source files without transforming their content.
3. Delete destination-only files only inside the corresponding managed
   destination.
4. Remove empty subdirectories only below a managed destination. Never delete
   or replace a managed destination root, its parent, or any other DataForge
   content.
5. Recompare every mapping after the changes and treat any remaining difference
   as a failure.

Use filesystem operations appropriate for the current platform. Prefer a
single-platform operation from discovery through deletion, and validate every
resolved deletion target before removing it.

## Completion report

Report the resolved source projects, mode, and added, updated, removed, and
unchanged counts for each mapping and in total. In sync mode, state whether the
final comparison is clean. Do not claim success after a partial copy or failed
verification.
