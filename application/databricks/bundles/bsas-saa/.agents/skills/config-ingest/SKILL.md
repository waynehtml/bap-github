---
name: config-ingest
description: >-
  Create a DataForge ingestion JSON configuration with a download task, optional
  ordered file transformations or validation, and an upload task. Use when a
  developer wants to compose a configuration under conf/oeds/config/ingest;
  do not use for runtime handler implementation or deployment.
---

# Create Ingestion Configuration

Compose one ingestion configuration using the project's DataBridge contract
snapshot. Paths below are relative to the DataForge or generated project root,
except Markdown links, which are relative to this skill. Work in the selected
project, including when DataForge is nested inside a larger repository.

## References

Start with the [DataBridge overview](../../../docs/reference/databridge/docs/README.md),
[templating guide](../../../docs/reference/databridge/docs/TEMPLATE_USER_GUIDE.md),
and [ingestion client guide](../../../docs/guide/G220-ingest-client-guide.md).
Inspect the chosen ingestion file and project bundle configuration for local
conventions and resolved project settings.

Read only the selected handler's guide under
[DataBridge docs](../../../docs/reference/databridge/docs/) and matching
[examples](../../../docs/reference/databridge/examples/) before composing its
parameters. For transformations, use the
[GPG](../../../docs/reference/databridge/docs/GPG_USER_GUIDE.md),
[archive](../../../docs/reference/databridge/docs/ARCHIVE_USER_GUIDE.md), and
[file](../../../docs/reference/databridge/docs/FILE_USER_GUIDE.md) guides.
For HTTP transfers, use the
[HTTP guide](../../../docs/reference/databridge/docs/HTTP_USER_GUIDE.md).

These vendored references are the contract for standalone projects. Do not
require sibling source repositories, synchronize references, or invent missing
handler contracts. Report missing or conflicting documentation and leave the
unsupported step unresolved.

## Guided Conversation

Use answers already supplied. Ask the remaining questions in the following
order, grouping related handler settings into focused questions. Wait for the
developer's answers before selecting operations or generating the file.

1. **Filename.** Ask for a filename, defaulting to `default.json` under
   `conf/oeds/config/ingest/`. Accept a stem by adding `.json`; keep the target
   inside that directory. If it exists, show its path and ask whether to replace
   it or choose another filename. Do not overwrite without that choice; check
   a replacement filename for collisions too.
2. **Pipeline name.** Ask for the display/logging name, offering the resolved
   `bundle.name` from the project's bundle configuration. If it is still a
   template such as `{{bundle_name}}`, ask for a name instead of treating that
   template as a service-time expression.
3. **Download.** Ask for the source protocol and select its documented handler.
   Default the task ID to `download`. Collect required connection and auth
   settings, source location, file filters, and local staging destination as
   supported by that handler. Do not silently choose a protocol.
4. **Transformations.** Ask which ordered operations are needed, allowing none.
   Offer decrypt, extract/compress, copy, move/rename, flatten, delete, and
   validate where documented. For each selected operation, collect its task ID,
   required parameters, input paths/filters, and output location. Offer a
   descriptive ID such as `decrypt`, `extract`, or `validate`; suffix repeated
   defaults with `_2`, `_3`, and so on. Allow repeated handler types and ask
   whether to add another step until the developer finishes. File operations
   and validation belong in this same sequence, not a separate mandatory phase.
5. **Upload.** Ask for the destination protocol and select its documented
   handler. Default the task ID to `upload`. Collect connection/auth settings,
   destination, and source selection for the final staged files.

Ask for missing required values, including secret key names, but never secret
contents. If the developer cannot provide a value, use a conspicuous
`TODO_<FIELD>` placeholder and report it as unresolved. For required non-string
values, use a quoted placeholder so the draft remains valid JSON, explicitly
noting the required type and that it cannot pass contract validation yet.
Do not substitute plausible numeric values or claim a draft is runnable.

## Composition Rules

- Write a JSON object with `pipeline` and ordered `tasks`. Each task has a
  unique non-empty `id`, the exact `oedis.handler.*` identifier, and documented
  `params`. Keep the legacy namespace unchanged.
- The first task downloads files and the last uploads them. Intermediate tasks
  are the selected transformations in order. HTTP uses
  `oedis.handler.http.request`: configure a saved response for downloading and
  a documented file or multipart request body for uploading. Do not invent
  `http.download` or `http.upload` handlers. Preserve explicitly selected
  supported legacy REST contracts rather than mixing their parameters with HTTP.
- Connect steps through their documented staging paths and file-selection
  rules. A task ID does not automatically pass files to the next task; do not
  add dependency fields or assume prior `TaskResult.outputs` are consumed.
- Trace each operation's expected output directory and names into the next
  operation's input selection. Validation leaves files in place. Distinguish
  remote connection roots from inbox-relative paths. Respect each handler's
  recursion and basename-versus-relative-path matching behavior.
- Select only the intended final files for upload; avoid accidentally including
  encrypted inputs, source archives, or intermediate copies. Do not copy
  destructive cleanup settings from examples unless requested.
- File validation supports `count` and per-file byte `size` rules. Collect the
  requested bounds, use unique rule names, and require non-negative integer
  bounds with at least one of `min` or `max` and `min <= max` when both exist.
  Do not imply support for file-content or schema validation.
- For copy/move renaming, `dst_name` requires exactly one matched file. If that
  cannot be established, explain the restriction and obtain a narrower
  selection or leave the rename unresolved. Apply documented flatten collision
  and path constraints when that operation is selected.
- Keep tasks required by default. Do not add `optional: true`, hooks, runtime
  changes, or unrelated operations to bypass failures.

## Secrets and Templates

Resolve the project's configured `secrete_scope`, including applicable bundle
includes and target overrides. Initialization resolves the `{{secrete_scope}}`
placeholder using the domain mappings beside `secrete_scope` in
`default.databricks.yml`; do not derive it from the project tag. In an initialized
project, use the configured value in `databricks.yml`. If the target or scope
remains ambiguous or unresolved, ask for it; if unavailable, use a clearly
reported placeholder. Preserve the existing `secrete_scope` spelling.

Place credentials in their documented fields as literal service expressions:

```json
"{{ keyvault(scope='lake-kv-triton-scope', key='ddap-oeds-services-client-cert') }}"
```

This illustrates syntax, not universal scope or key defaults. Obtain the actual
key name for each password, token, certificate, private key, or passphrase.
An unresolved secret can use `{{ keyvault(scope='TODO_SECRET_SCOPE', key='TODO_SECRET_KEY') }}`.
Do not retrieve, print, or embed secret values, and do not copy example secret
names as real project settings.

Preserve `[[ ... ]]` client expressions, `{{ ... }}` service expressions, and
`<< ... >>` task expressions. Use task expressions only in fields documented to
support them. Do not render expressions during authoring. Ensure JSON quoting
and escaping remain valid; do not insert unresolved bundle `${var...}` references
into ingestion JSON and assume that DataBridge resolves them.

## Write, Validate, and Hand Off

Create or replace only the selected ingestion JSON file once the conversation
is complete and any existing-file replacement is authorized. Do not change job
wiring, package files, bundle settings, runtime code, or vendored references.

Check the authored configuration without network access or secret resolution:

1. Parse as JSON; verify the top-level shape and unique task IDs.
2. Verify download first, upload last, and the chosen transformation order.
3. Compare each handler's required fields, types, and operations against its
   selected guide and examples. Identify placeholder-related failures separately.
4. Trace staging paths, output names, filters, and final upload selection. Check
   rename and validation constraints where applicable.
5. Confirm credentials remain literal secret expressions, template delimiters
   are preserved, and every unresolved value is listed in the handoff.

Report the clickable absolute output path, ordered task sequence, checks
performed, and any unresolved fields or assumptions. Label incomplete output
as a draft. Static validation does not verify credentials, remote connectivity,
file availability, or successful ingestion. Stop without running or deploying
an ingestion job.
