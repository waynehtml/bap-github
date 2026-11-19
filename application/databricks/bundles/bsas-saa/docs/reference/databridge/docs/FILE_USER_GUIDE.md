# file

Handlers:

- `oedis.handler.file.copy`
- `oedis.handler.file.move`
- `oedis.handler.file.flatten`
- `oedis.handler.file.delete`
- `oedis.handler.file.validate`

Performs file operations and non-mutating validation inside the staging area
using Python filesystem functions (`pathlib`, `shutil`).

## Configuration

### Task parameters (`params`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `requests` | Yes | list | n/a | One or more file operation specs. |

### Copy and move request spec (`requests[]`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `src_dir` | No | string | `""` | Inbox-relative source directory. Empty or omitted means `ctx.inbox`. |
| `recursive` | No | bool | `false` | When `true`, traverse subdirectories under `src_dir`; otherwise only direct children of `src_dir` are considered. |
| `include` | No | string or list[string] | `["*"]` | Glob patterns matched against each candidate path relative to `src_dir`. For nested discovery, prefer `recursive: true` with patterns like `"*.csv"` only when matching by relative path is sufficient. |
| `exclude` | No | string or list[string] | `[]` | Glob patterns matched against each candidate path relative to `src_dir`; matching entries are skipped. |
| `dst_dir` | No | string | `""` | Inbox-relative destination directory. Empty or omitted means `ctx.inbox`. |
| `dst_name` | No | string | n/a | Override only the final destination file name. Relative parent directories from `src_dir` are still preserved. Allowed only when exactly one file matches. |

### Flatten request spec (`requests[]`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `src_dir` | No | string | `""` | Source directory relative to `ctx.inbox`. Empty or omitted means `ctx.inbox`. Files are always collected recursively. |
| `dst_dir` | No | string | `""` | Destination directory relative to `ctx.inbox`. Empty or omitted means `ctx.inbox`. Must not normalize to the same path as `src_dir`. |
| `include` | No | string or list[string] | `["*"]` | Glob patterns matched against each collected file path relative to `src_dir`. |
| `exclude` | No | string or list[string] | `[]` | Glob patterns matched against each collected file path relative to `src_dir`; matching entries are skipped. |
| `operation` | No | string | `move` | One of `move` or `copy`. |
| `on_collision` | No | string | `error` | One of `error`, `overwrite`, or `rename`. |

### Delete request spec (`requests[]`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `src_dir` | No | string | `""` | Inbox-relative source directory. Empty or omitted means `ctx.inbox`. |
| `recursive` | No | bool | `false` | When `true`, traverse subdirectories under `src_dir`; otherwise only direct children of `src_dir` are considered. |
| `include` | No | string or list[string] | `["*"]` | Glob patterns matched against each candidate path relative to `src_dir`. |
| `exclude` | No | string or list[string] | `[]` | Glob patterns matched against each candidate path relative to `src_dir`; matching entries are skipped. |

### Validate request spec (`requests[]`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `src_dir` | No | string | `""` | Inbox-relative source directory. Empty or omitted means `ctx.inbox`. |
| `recursive` | No | bool | `false` | When `true`, traverse subdirectories under `src_dir`; otherwise only direct child files are considered. |
| `include` | No | string or list[string] | `["*"]` | Glob patterns matched against each candidate path relative to `src_dir`. |
| `exclude` | No | string or list[string] | `[]` | Glob patterns matched against each candidate path relative to `src_dir`; matching files are skipped. |
| `rules` | Yes | list | n/a | One or two rule objects. Supported rule names are `count` and `size`, and names must be unique within the request. |

Each rule contains:

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `name` | Yes | string | `count` validates the selected file count; `size` validates each selected file size in bytes. |
| `min` | Conditional | integer | Inclusive non-negative minimum. At least one of `min` or `max` is required. |
| `max` | Conditional | integer | Inclusive non-negative maximum. At least one of `min` or `max` is required. |

When both bounds are supplied, `min` must not exceed `max`. Equal bounds
require an exact value.

## Path rules

All paths are resolved relative to `ctx.inbox`.

- Empty `src_dir` resolves to `ctx.inbox`.
- Empty `dst_dir` resolves to `ctx.inbox` for `copy`, `move`, and `flatten`.
- `flatten` allows empty `dst_dir`, but `src_dir` and `dst_dir` must resolve to different inbox paths.
- Paths that resolve outside `ctx.inbox` are rejected.
- `src_dir` must exist and must be a directory.

## Matching behavior

Candidate entries are selected from `src_dir` and then filtered as follows:

1. Build the candidate set.
2. Keep only candidates matching at least one `include` pattern.
3. Remove candidates matching any `exclude` pattern.

Pattern matching uses `fnmatch` against the candidate path relative to `src_dir` and normalized to POSIX style (`/` separators). It does not do separate basename matching.

Examples of relative paths seen by pattern matching:

- `report.csv`
- `nested/a/report.csv`

Notes:

- `include` defaults to `["*"]`.
- `exclude` defaults to `[]`.
- `copy`, `move`, and `flatten` operate on files only.
- `validate` selects and inspects files only and never modifies them.
- `delete` operates on files and directories.
- For `delete`, directories are deleted deepest-first so nested content is removed safely.
- `flatten` always walks `src_dir` recursively.
- Preferred style for handlers that support basename matching is `recursive: true` with `include: ["*.csv"]`, but the local file handlers match relative paths only, so nested files may still need path-aware patterns.

## Validation rules

### `copy` and `move`

- If `dst_name` is provided, exactly one file must match.

### `flatten`

- `src_dir` and `dst_dir` must normalize to different inbox-relative paths.
- Destination paths are planned before any writes are performed.
- Matched files are sorted by relative path before collision handling and writes.

### `delete`

- `dst_dir` and `dst_name` are forbidden.

### `validate`

- Each request discovers its files once, then evaluates `count` before `size`
  regardless of rule order.
- A count rule applies after include and exclude filtering.
- A size rule applies independently to every matched file.
- A size rule fails when no files match.
- Duplicate rule names and unsupported rule names are rejected.
- A missing `src_dir` is treated as zero matching files when the runtime inbox
  exists and is a directory. Count-only rules that allow zero pass; size rules
  still fail on zero matches.
- Validation mismatches raise `RuntimeError` with stable message prefixes:
  `DATABRIDGE_VALIDATION_COUNT_ERROR:` or `DATABRIDGE_VALIDATION_SIZE_ERROR:`.
  Both include `request_index=<index>; matched_count=<count>;`
  before the detailed explanation. Count runs before size, so only the first
  failing rule is reported.
- Invalid paths, non-directory sources, missing/invalid inboxes, and filesystem
  errors still fail without a validation-rule marker. Configuration errors
  remain separate from validation mismatches.
- To recognize zero files, match the count marker and
  `matched_count=0;` together. The count marker alone also covers too few or too
  many files. For example:
  `DATABRIDGE_VALIDATION_COUNT_ERROR: request_index=0; matched_count=0;`.
- Place a required validation task before upload to stop processing on missing
  input. DataBridge still reports failure and runs failure/completion hooks;
  clients receive the marker through the existing wrapped error message. See
  [`file_validate_required.json`](../examples/file_validate_required.json).
- Validation logs the task lifecycle, resolved directory, matched count, rule
  outcomes, and file sizes without logging file contents.

## Destination rules for `copy` and `move`

For each matched file:

1. Start with the file path relative to `src_dir`.
2. If `dst_name` is set, replace only the final file name in that relative path.
3. Resolve the destination as `dst_dir / <resulting relative path>`.

Parent directories are created automatically as needed.

## Destination rules for `flatten`

For each matched file:

1. Collect all files recursively under `src_dir`.
2. Sort matches by relative path for deterministic behavior.
3. Flatten each file into `dst_dir` using only `src_path.name`.
4. Apply `on_collision` to source-name collisions before any writes happen.

Collision handling:

- `error`: fail if multiple matched files would map to the same flattened destination path.
- `overwrite`: later files in sorted order win.
- `rename`: keep the first file name unchanged, then rename later collisions as `basename_1.ext`, `basename_2.ext`, and so on.

When the planned destination file already exists in `dst_dir`, `copy` and `move` overwrite it.

## Outputs

Each handler returns a `TaskResult` with:

- `status="success"` on success
- `outputs`: one entry per processed item
- `metrics.total_items`: number of processed items
- `metrics.total_duration_sec`: total handler wall-clock duration

### Output entry shape

Each output entry contains:

- `src.type`: always `"file"`
- `src.path`: source path
- `dest.type`: always `"file"`
- `dest.path`: destination path for `copy`, `move`, and `flatten`, empty string for `delete`
- `duration_sec`: per-item execution duration in seconds

For `validate`, every matched file appears once per request after all rules
pass. `src.path` and `dest.path` are identical because the file is validated in
place, and both endpoints contain its byte size. Files selected by multiple
requests appear multiple times. If any rule fails, the handler raises and the
engine records a failed result with an empty `outputs` list.

Successful validation result:

```json
{
  "task_id": "validate_download",
  "handler": "oedis.handler.file.validate",
  "status": "success",
  "error": null,
  "outputs": [
    {
      "src": {
        "type": "file",
        "path": "/job/inbox/raw/report_20260820.csv",
        "size": 4200
      },
      "dest": {
        "type": "file",
        "path": "/job/inbox/raw/report_20260820.csv",
        "size": 4200
      },
      "duration_sec": 0.001
    }
  ],
  "metrics": {
    "total_items": 1,
    "total_duration_sec": 0.003
  },
  "extras": null
}
```

If a count rule expects exactly one file but none match, the handler raises:

```text
RuntimeError: requests[0] count rule failed for '/job/inbox/raw': expected exactly 1 file(s), found 0
```

The engine records the failure before propagating a `TaskException` for a
required task:

```json
{
  "task_id": "validate_download",
  "handler": "oedis.handler.file.validate",
  "status": "failed",
  "error": "requests[0] count rule failed for '/job/inbox/raw': expected exactly 1 file(s), found 0",
  "outputs": [],
  "metrics": {},
  "extras": null
}
```

## Examples

### Copy matching files recursively

```json
{
  "id": "file-copy-basic",
  "handler": "oedis.handler.file.copy",
  "params": {
    "requests": [
      {
        "src_dir": "staged",
        "include": ["*.csv"],
        "recursive": true,
        "dst_dir": "archive"
      }
    ]
  }
}
```

### Flatten matched files into a single directory

```json
{
  "id": "file-flatten-basic",
  "handler": "oedis.handler.file.flatten",
  "params": {
    "requests": [
      {
        "src_dir": "staged",
        "include": ["daily_report.csv"],
        "exclude": ["*.txt"],
        "dst_dir": "archive",
        "operation": "move",
        "on_collision": "error"
      }
    ]
  }
}
```

### Validate at least two non-empty CSV files

```json
{
  "id": "file-validate-basic",
  "handler": "oedis.handler.file.validate",
  "params": {
    "requests": [
      {
        "src_dir": "raw",
        "include": ["*.csv"],
        "exclude": ["*.tmp"],
        "recursive": false,
        "rules": [
          {"name": "count", "min": 2},
          {"name": "size", "min": 1}
        ]
      }
    ]
  }
}
```
