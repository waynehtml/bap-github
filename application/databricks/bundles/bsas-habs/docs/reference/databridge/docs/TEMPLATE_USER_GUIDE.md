# DataBridge Templating User Guide

DataBridge has three template-rendering phases. Each phase uses distinct markers so
expressions intended for a later phase survive the earlier phases unchanged.

| Phase | When | Markers | Available values |
|---|---|---|---|
| 1. Client config rendering | Before the ingestion config is submitted | `[[ ... ]]`, `[% ... %]`, `[# ... #]` | Client `template_params` |
| 2. Service config rendering | After the DataBridge job starts and before task processing | `{{ ... }}`, `{% ... %}`, `{# ... #}` | `runtime` and DataBridge template functions |
| 3. Task-time rendering | At a task-defined point during processing | `<< ... >>`, `<% ... %>`, `<# ... #>` | A context supplied by the task, such as `runtime`, prior `task_results`, or newly available data |

The phases should be selected by when a value becomes available:

- Use client rendering for values already known by the caller.
- Use service rendering for job runtime values and DataBridge functions.
- Use task-time rendering for values that exist only while a task is running.

Task-time rendering is an opt-in capability. The engine does not automatically
apply it to every task or every field; task execution code invokes it at the
point where its late-bound context is available.

---

## Phase 1 - client config rendering: `[[ ... ]]`

Implemented in DataForge as `DisClient.resolve_config_template()` using Jinja with:
- `variable_start_string="[[", variable_end_string="]]"`
- `StrictUndefined` (**missing parameters fail fast**)

The client renders the raw template text. The result must be valid JSON before
it is submitted to `DisClient.ingest()`.

```python
resolved_config = client.resolve_config_template(
    config_template=config_template,
    template_params=config_params,
)

result = client.ingest(
    config=resolved_config,
    params=service_params,
    wait=True,
)
```

`template_params` supplies values used by `[[ ... ]]`. The separate
`params` argument to `ingest()` is sent to DataBridge and becomes
`runtime.job_params` during service rendering.

### How to reference parameters

When the client renders your config, it calls `template.render(parameters)` which means every key in your `parameters` dict becomes a top-level variable.

If you pass:
```json
{
  "env": "dev",
  "rundate": "2026-02-05",
  "source": {
    "host": "sftp.example.com",
    "port": 22
  }
}
```

You can reference them like:
```json
{
  "env": "[[ env ]]",
  "rundate": "[[ rundate ]]",
  "sftp_host": "[[ source.host ]]",
  "sftp_port": "[[ source.port ]]"
}
```

### What "parameters only" means

Use `[[ ... ]]` for **straight substitutions**. Avoid calling service template functions here.

Good:
- `[[ env ]]`
- `[[ source.host ]]`
- `[[ rundate ]]`

Do not use service template functions in client markers:
- `[[ delta(days=-1) ]]`  (wrong phase)
- `[[ keyvault(scope="x", key="y") ]]` (wrong phase)

> Tip: Using `[[ ... ]]` ensures service and task-time markers stay untouched until their own phases.

---

## Phase 2 - service config rendering: `{{ ... }}`

Implemented by `oedis.common.template_resolver.resolve_config()` using Jinja
default delimiters. The service calls it with:

- `StrictUndefined` (**missing values fail fast**)
- `runtime`
- template functions from `oedis.template_functions`: `delta`, `timestamp`,
  `epoch`, and `keyvault`

DataBridge parses the submitted JSON before this phase and then recursively renders
string values. Dictionary keys and existing non-string values are preserved.
Consequently, service blocks can control text inside a string, but they cannot
add or remove config keys, tasks, or list items.

### How to reference runtime parameters

DataBridge passes a `runtime` object (or dict-like) to templates.

You can refer to runtime attributes like:
- `{{ runtime.env }}`
- `{{ runtime.rundate }}`
- `{{ runtime.job_run_id }}` (if present in your runtime)
- `{{ runtime.job_params.key_name }}` for client-passed `params` values

Example:
```json
{
  "landing_path": "abfss://landing@acct.dfs.core.windows.net/raw/{{ runtime.env }}/{{ runtime.rundate }}/"
}
```

When the client supplies `params` to the job, DataBridge stores them under `runtime.job_params`.
If a value is purely a client input (not a runtime macro or secret), prefer resolving it in
Phase 1 with `[[ ... ]]` to avoid mixing phases and fail earlier on missing values.

### Using macros / functions

Macros are called inside `{{ ... }}` like normal Jinja expressions.

Example:
```json
{
  "partition": "{{ delta(base=runtime.rundate, days=-1, format='YYYYMMDD') }}",
  "file": "extract_{{ timestamp() }}.json",
  "message_id": "{{ epoch() }}"
}
```

---

## Service template function reference

### `delta(...) -> str`

Creates a formatted date string by shifting a base date.

Signature:
```python
delta(
  base: date | None = None,
  format: str = "YYYYMMDD",   # Pendulum tokens
  days: int = 0,
  months: int = 0,
  years: int = 0,
  bday: bool = False,         # True = business days, False = calendar days
  tz: str = "America/Toronto",
  uppercase: bool = True
) -> str
```

Behavior:
- All arguments are keyword-only (use `delta(days=-1)`, not positional args).
- If `base` is not provided, it uses "today" in `tz`.
- Applies `months`/`years` via `pandas.DateOffset`.
- Applies `days` via:
  - `pandas.offsets.BDay(days)` if `bday=True`
  - calendar `Timedelta(days=days)` if `bday=False`
- Formats with **Pendulum** date tokens (e.g. `YYYY-MM-DD`, `YYYYMMDD`)
  (strftime tokens like `%Y-%m-%d` are not supported).
- Uppercases the result by default (`uppercase=True`).

Examples:
```jinja
{{ delta(days=-1) }}
```
Yesterday (calendar day) based on today in `America/Toronto`.

```jinja
{{ delta(base=runtime.rundate, days=-1, bday=True, format="YYYY-MM-DD") }}
```
Previous **business day** relative to `runtime.rundate`.

```jinja
{{ delta(base=runtime.rundate, months=1, format="YYYYMM") }}
```
One month after `runtime.rundate`, formatted as `YYYYMM`.

---

### `timestamp(...) -> str`

Formats the current timestamp in the requested timezone.

Signature:
```python
timestamp(
  format: str = "YYYY-MM-DD_HH-mm-ss",
  tz: str = "America/Toronto",
  uppercase: bool = True
) -> str
```

Behavior:
- All arguments are keyword-only.
- Uses the current time in `tz`.
- Formats with **Pendulum** datetime tokens.
- Uppercases the result by default (`uppercase=True`).

Examples:
```jinja
{{ timestamp() }}
```
Current timestamp using the default format `YYYY-MM-DD_HH-mm-ss`.

```jinja
{{ timestamp(format="YYYYMMDDHHmmss") }}
```
Current timestamp with a compact filename-friendly format.

```jinja
{{ timestamp(tz="UTC") }}
```
Current UTC timestamp.

---

### `epoch(...) -> str`

Returns the current Unix epoch time.

Signature:
```python
epoch(unit: str = "seconds") -> str
```

Behavior:
- All arguments are keyword-only.
- `unit` supports `seconds` and `milliseconds`.
- Uses the current UTC time.

Examples:
```jinja
{{ epoch() }}
```
Current Unix epoch in seconds.

```jinja
{{ epoch(unit="milliseconds") }}
```
Current Unix epoch in milliseconds.

---

### `keyvault(scope, key) -> str`

Fetches a Databricks secret using `dbutils.secrets.get`.

Signature:
```python
keyvault(scope: str, key: str) -> str
```

Requirements:
- Must run inside Databricks runtime where `dbutils` is available.
- Both `scope` and `key` must be non-empty strings.
- Raises an error if secret lookup fails (Strict / fail-fast behavior).

Example:
```jinja
{{ keyvault(scope="my-kv-scope", key="sftp-private-key") }}
```

For SFTP key auth, that secret may contain a raw PEM string or a base64-encoded PEM string.

---

## Phase 3 - task-time rendering: `<< ... >>`

Task-time rendering resolves values at a task-defined point during execution.
It is intended for information that did not exist when the client or service
rendered the ingestion config.

Typical late-bound values include:

- results produced by earlier tasks
- per-item or per-message metadata discovered during processing
- task-local calculated values
- status and error details available to completion hooks
- content loaded by a task after the ingestion config was resolved

### Markers

Task-time rendering uses a separate set of Jinja markers:

| Construct | Markers |
|---|---|
| Variable | `<< ... >>` |
| Block | `<% ... %>` |
| Comment | `<# ... #>` |

For example:

```jinja
<< task_results.download.metrics.total_items >>
```

```jinja
<% if task_results.download.status == "success" %>
Processing completed successfully.
<% endif %>
```

The distinct markers allow task-time expressions to pass through client and
service rendering without being consumed.

### How task-time rendering works

Task-time rendering is provided by:

```python
from oedis.common.template_resolver import resolve_task

resolved_value = resolve_task(
    template_value,
    render_context={
        "runtime": ctx.runtime,
        "task_results": ctx.task_results,
        "item": item_context,
    },
)
```

The calling task owns two decisions:

1. **When to render.** Rendering should happen only after all required values
   are available.
2. **What to expose.** The keys in `render_context` are the complete public
   context for that template.

The resolver does not have a fixed list of task-time variables. Names such as
`runtime` and `task_results` are conventions supplied by the caller, while a
task can add a well-defined context such as `item`, `event`, or `metadata`.

`task_results` contains results already recorded by the engine. During normal
sequential processing, that means a task can read preceding task results but
not its own result, which is stored only after the task returns.

### Recursive resolution

`resolve_task()` can render:

- a string
- string values nested in dictionaries
- string items nested in lists
- dataclass values after conversion to dictionaries

Non-string values are preserved. Dictionary keys are not rendered.

For example:

```python
raw_params = {
    "name": "<< item.name >>",
    "labels": [
        "run-<< runtime.job_run_id >>",
        "<< item.category >>",
    ],
    "options": {
        "enabled": True,
        "attempts": 3,
    },
}
```

The strings are rendered recursively, while `True` and `3` keep their
original types.

### Strict failure behavior

Task-time rendering uses Jinja `StrictUndefined`. Referencing a missing value
raises an exception instead of producing an empty string.

```jinja
<< item.missing_value >>
```

The task should let a genuine rendering failure propagate through the normal
task error handling path. If a context value is optional, make that explicit in
the template or normalize the context before rendering.

Templates are rendered with autoescaping disabled. A task that uses rendered
text in HTML, SQL, shell commands, paths, or another sensitive output format
must apply validation or escaping appropriate to that destination.

### What task-time templating can do

Task-time templates can:

- compose names, paths, messages, and other strings from late-bound values
- read standardized fields from prior `TaskResult` objects, including
  `status`, `outputs`, `metrics`, `error`, and `extras`
- use Jinja conditionals and loops in text content
- render a complete nested parameter structure or a single selected field
- render content loaded during task execution
- expose new domain-neutral context objects without changing the template
  resolver

Task-time templating does not itself:

- run automatically for every task
- discover context values
- render dictionary keys
- validate the meaning of a resolved value
- preserve a non-string type when the input itself is a template string

### Extending task-time templating

To add task-time templating to another processing path:

1. Identify the exact late-bound field or structure and the point when its
   required data becomes available.
2. Define a small, stable render-context contract. Reuse `runtime` and
   `task_results` where applicable and add only clearly named task-specific
   objects.
3. Call `resolve_task()` on the narrowest useful value or structure.
4. Validate the resolved result before external I/O or other side effects.
5. Document the supported fields, context keys, and rendering frequency.
6. Add tests for successful substitution, missing values, nested structures,
   and unsafe or invalid resolved values.

Prefer exposing structured objects:

```python
render_context = {
    "runtime": ctx.runtime,
    "task_results": ctx.task_results,
    "item": {
        "name": item.name,
        "content_type": item.content_type,
    },
}
```

This produces readable templates:

```jinja
<< item.name >>
<< item.content_type >>
```

Avoid flattening unrelated values into many top-level variables. Also avoid
placing credentials or sensitive payload contents in the context unless the
task requires them, and never log fully resolved secrets.

### Three-phase composition

A single string can intentionally contain expressions for all three phases:

```json
{
  "artifact_name": "[[ source ]]_{{ runtime.job_run_id }}_<< item.category >>.json"
}
```

It resolves in order:

1. The client replaces `[[ source ]]`.
2. The service replaces `{{ runtime.job_run_id }}`.
3. The task replaces `<< item.category >>` after `item` becomes available.

Each phase ignores the other phases' markers.

---

## Client and service config example

### 1) Author a config template

```json
{
  "pipeline": "sftp_ingest",
  "tasks": [
    {
      "id": "download",
      "handler": "oedis.handler.sftp.download",
      "params": {
        "connection": {
          "hostname": "[[ sftp.host ]]",
          "port": "[[ sftp.port ]]",
          "auth": {
            "type": "key",
            "username": "[[ sftp.username ]]",
            "private_key": "{{ keyvault(scope='[[ kv.scope ]]', key='[[ kv.private_key_name ]]') }}"
          }
        },
        "requests": [
          {
            "src_dir": "/out/{{ delta(base=runtime.rundate, days=-1, format='YYYYMMDD') }}/",
            "file": "extract_{{ timestamp() }}.json",
            "include": ["*"],
            "recursive": false
          }
        ]
      }
    }
  ]
}
```

### 2) Resolve client parameters

```json
{
  "sftp": { "host": "sftp.example.com", "port": 22, "username": "svc_user" },
  "kv": { "scope": "dept-a-kv", "private_key_name": "sftp-private-key" }
}
```

After client rendering, DataBridge receives:

```json
{
  "connection": {
    "hostname": "sftp.example.com",
    "port": 22,
    "auth": {
      "type": "key",
      "username": "svc_user",
      "private_key": "{{ keyvault(scope='dept-a-kv', key='sftp-private-key') }}"
    }
  },
  "requests": [
    {
      "src_dir": "/out/{{ delta(base=runtime.rundate, days=-1, format='YYYYMMDD') }}/",
      "file": "extract_{{ timestamp() }}.json",
      "include": ["*"],
      "recursive": false
    }
  ]
}
```

### 3) Resolve the service config at job startup

- `runtime.rundate` is provided by DataBridge runtime
- `keyvault(...)` fetches the secret
- `delta(...)` computes the date string
- `timestamp(...)` computes the current timestamp string
- `epoch(...)` computes the current Unix epoch string

---

## Common pitfalls

- **Choosing the wrong phase**: use `[[ ... ]]` for client-known values,
  `{{ ... }}` for service runtime values and functions, and `<< ... >>` for
  values made available during task processing.
- **Assuming task-time rendering is global**: a task must explicitly invoke
  `resolve_task()` and define its supported context and fields.
- **Missing parameters**: all three phases use **StrictUndefined**, so missing
  variables fail in the phase that owns them.
- **Quoting**: if your placeholder is meant to render a string, keep JSON quotes around it (as shown above).
- **Secrets**: `keyvault()` only works inside Databricks with a configured secret scope.
