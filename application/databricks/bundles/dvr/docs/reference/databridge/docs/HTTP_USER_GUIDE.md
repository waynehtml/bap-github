# HTTP handler

Handler: `oedis.handler.http.request`

Executes sequential HTTP requests, uploads inbox files, and optionally saves
responses. This is a separate handler; the existing `rest` handlers, schemas,
and examples keep their current contracts.

## Quick start

```json
{
  "id": "download_report",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "base_url": "https://api.vendor.example.com/v1",
      "auth": {
        "type": "bearer",
        "token": "{{ keyvault(scope=\"dis-secrets\", key=\"http-token\") }}"
      }
    },
    "requests": [
      {
        "method": "POST",
        "path": "reports",
        "body": {"type": "json", "value": {"date": "{{ runtime.rundate }}"}},
        "response": {"expected_status": [200, 201], "save_to": "raw/report.json"}
      }
    ]
  }
}
```

## Connection and request configuration

| Field | Default | Meaning |
| --- | --- | --- |
| `connection.base_url` | none | Required when using request `path`. Absolute HTTP(S) URL without query, fragment, or embedded credentials. |
| `connection.timeout_sec` | `60` | Positive connect/read inactivity timeout, also used for token requests. This is not a total transfer deadline. |
| `connection.headers` | `{}` | Shared HTTP headers; values must be strings. |
| `connection.auth` | `{"type":"none"}` | Authentication shared by requests in this task. |
| `connection.retry` | one attempt | Default retry settings; see below. |
| `requests` | required | Non-empty array, executed in order. |
| `requests[].id` | `request_1`, etc. | Identifier used in logs and errors. |
| `requests[].method` | `GET` | HTTP method. Set `POST`, `PUT`, or `PATCH` explicitly for uploads. |
| `requests[].url` | none | Absolute HTTP(S) URL. Choose exactly one of `url` and `path`. |
| `requests[].path` | none | Relative reference resolved against `base_url`. |
| `requests[].params` | `{}` | Query overrides; scalar values or arrays of scalars. |
| `requests[].headers` | `{}` | Request headers override connection and auth headers case-insensitively. |
| `requests[].body` | omitted | Optional body, described below. |
| `requests[].response` | all 2xx accepted | Optional status validation and saved response. |
| `requests[].retry` | connection values | Per-field overrides of retry settings. |

With `base_url: "https://host.example/v1"`, `path: "reports"` resolves to
`https://host.example/v1/reports`; `path: "/reports"` resolves to
`https://host.example/reports`. Absolute URLs and network references such as
`//other.example` are invalid in `path`. A request `url` uses its own host.
Only configure trusted endpoints for a connection's credentials.

Request query parameters replace matching query keys already in the URL.
Unmodified repeated query keys are retained. Query API keys take precedence
over both the URL and request parameters.

Headers merge as connection headers, built-in auth headers, then request
headers. Use `auth.type: "none"` for fully manual authentication. Requests does
not substitute ambient netrc credentials. Server cookies are not carried from
one request to another; multi-step cookie login is outside this contract.

## Request bodies

Omit `body` for no body. Body variants have strict fields to catch incompatible
combinations; generic connection/request objects permit extension properties.
Legacy `file` and `fault_tolerant` keys are rejected rather than silently ignored.

| `body.type` | Required fields | Behavior |
| --- | --- | --- |
| `json` | `value` | Any JSON value, including `null`, encoded as UTF-8 JSON. |
| `form` | `value` | Object of scalar form fields, URL encoded. |
| `text` | `value` | UTF-8 string. |
| `file` | `path` | One inbox file sent as the full binary body. |
| `multipart` | `files` | Non-empty array of file parts with optional scalar `fields`. |

`json`, `form`, `text`, and `file` accept optional `content_type`. An explicit
header takes precedence. JSON defaults to `application/json`; text defaults to
`text/plain; charset=utf-8`. Form encoding uses
`application/x-www-form-urlencoded`. Set a MIME type for raw file uploads when
required by the endpoint.

```json
{
  "method": "PUT",
  "path": "archives/daily",
  "body": {
    "type": "file",
    "path": "prepared/report.zip",
    "content_type": "application/zip"
  },
  "response": {"save_to": "receipts/archive.json"}
}
```

```json
{
  "method": "POST",
  "path": "uploads",
  "body": {
    "type": "multipart",
    "fields": {"reportDate": "{{ runtime.rundate }}"},
    "files": [
      {
        "name": "file",
        "path": "prepared/report.csv",
        "filename": "report.csv",
        "content_type": "text/csv"
      }
    ]
  },
  "response": {"expected_status": [200, 201], "save_to": "receipts/upload.json"}
}
```

Each multipart part requires `name` and `path`. `filename` defaults to the source
basename; `content_type` is optional. Repeated field names are supported. Do not
set a request or connection `Content-Type` for multipart: Requests generates it
with the matching boundary. Raw files stream from disk, while Requests buffers
multipart encoding in memory; size multipart uploads accordingly.

All file paths use the shared inbox rules: relative to `ctx.inbox`, with leading
`/` treated as inbox-rooted shorthand. Traversal, external paths, and symlinks
escaping the inbox are rejected. The runtime owns inbox initialization. A later
request can upload an earlier request's saved response.

## Response handling and retry behavior

`response.expected_status` accepts one integer or a non-empty integer list. The
default accepts all 2xx responses. A configured accepted status takes precedence
over retry settings, including when accepting an error status intentionally.
Redirects are never followed, including token requests. A 3xx response fails
unless its status is explicitly accepted; accepting it does not follow it.

`response.save_to` saves the response bytes to an inbox file. Responses are
streamed, including when only counting bytes for an action. HTTP content
compression is decoded by Requests. The handler writes a temporary file beside
the destination and replaces the destination only after the full body arrives.
Failed transfers remove the temporary file and preserve any existing destination.
A task with no file bodies or saved responses does not need an inbox.

| Retry field | Default | Meaning |
| --- | --- | --- |
| `max_attempts` | `1` | Total attempts, including the initial attempt. Minimum 1. |
| `interval_sec` | `0` | Non-negative seconds between attempts. |
| `status_codes` | `[]` | Response statuses eligible for retry. |

Connection retry settings merge with per-request overrides. An explicit `0`
interval or empty status list is respected. Timeouts, connection errors, and
interrupted chunked responses also retry within this limit. Each attempt reopens
upload files at byte zero. Sessions, responses, and file handles close on success
and failure. Token exchanges fail immediately and do not use API retry settings.

Enable retries for writes only when the API makes replay safe, for example with
an idempotency key. A timeout may happen after the server has performed an action.
Earlier requests and their saved outputs remain completed if a later request
fails; the handler does not roll back remote effects.

## Authentication

| `auth.type` | Required fields | Optional fields |
| --- | --- | --- |
| `none` | `type` | none |
| `basic` | `username`, `password` | none |
| `bearer` | `token` | none |
| `api_key` | `name`, `value` | `location`: `header` (default), `query`, or `cookie` |
| `oauth2_client_credentials` | `token_url`, `client_id`, `client_secret` | See below. |

See [HTTP authentication examples](HTTP_AUTH_EXAMPLES.md) for full task examples
for every authentication type, all API-key locations, both OAuth client methods,
and custom token response fields.

Use secret templates for credentials, as in the examples. API key header and
cookie values can be overridden by explicit per-request headers under the normal
header precedence rule. Query API keys override a matching request parameter.

### OAuth client credentials

| Field | Default | Meaning |
| --- | --- | --- |
| `client_auth_method` | `body` | Credentials in the form body, or `basic` for an Authorization header. |
| `scope` | omitted | Space-separated scopes. |
| `token_params` | `{}` | Extra scalar form fields, such as `audience` or `resource`. |
| `token_headers` | `{}` | Extra token request headers. |
| `access_token_field` | `access_token` | Top-level field containing a non-empty string token. |
| `expires_in_field` | `expires_in` | Top-level lifetime field, as a non-negative number or numeric string. |

The token URL must use HTTPS. Token requests always use form encoding and the
client credentials grant. `token_params` cannot override `grant_type`,
`client_id`, `client_secret`, or `scope`; configure their dedicated fields.
`token_headers.Authorization` is rejected; use `client_auth_method` instead.
A supplied token `Content-Type` must be `application/x-www-form-urlencoded`.
Basic client credentials are individually form-encoded before Base64 encoding,
as specified by [OAuth 2.0 section 2.3.1](https://www.rfc-editor.org/rfc/rfc6749.html#section-2.3.1).

Tokens are cached only within this handler invocation, checked before each API
attempt, and refreshed before expiry (10% of lifetime, capped at 30 seconds).
Tokens with missing or zero lifetime are fetched again on the next attempt.
Negative, malformed, and non-finite lifetimes fail. There is no automatic 401
refresh or refresh-token grant. Separate tasks use separate authentication state.

## Results, logs, and limitations

The handler returns the standard `TaskResult`. Ordinary requests produce one
output. Uploads produce one output per source file, with `src.type: "file"`.
Without a saved response, `dest` is a `response` endpoint containing URL, status,
and byte count. With `save_to`, `dest` is a file endpoint. For downloads without
uploads, `src.path` is the request URL. The metrics are `total_items`,
`total_requests`, and `total_duration_sec`.

Every query value in logged and returned URLs is redacted. The handler does not
log headers, auth values, request payloads, or response payloads. Transport errors
report the request identifier and exception class; their original message chains
are detached because Requests can include credential-bearing URLs. The handler
also suppresses urllib3 connection/retry diagnostics on its calling thread while
a session is active, then restores normal logging. HTTP status
errors include the status but omit response contents.

This handler does not implement pagination, asynchronous polling, extracted
response variables, resumable uploads, browser login, vendor signing, or automatic
redirect handling. Use a dedicated extension for those workflows. See
[Requests advanced usage](https://requests.readthedocs.io/en/stable/user/advanced/)
for the underlying streaming and multipart behavior.

## Examples and tests

The `examples/http_request_download_*.json` and
`examples/http_request_upload_*.json` files cover JSON with bearer authentication,
form/text, Basic auth, all three API-key locations, both OAuth client methods,
raw files, and multipart uploads with saved responses. The
[authentication example catalogue](HTTP_AUTH_EXAMPLES.md) links additional
scenarios for every authentication type.

See [HTTP downloads with OAuth 2.0](HTTP_DOWNLOAD_EXAMPLES.md) for file downloads,
JSON/form export requests, and sequential downloads with token reuse.

See [HTTP file upload examples](HTTP_UPLOAD_EXAMPLES.md) for complete multipart
OAuth 2.0 and binary API-key upload tasks.

Filenames use
`http_request_{download/upload}_{authentication}_{method}[_{body_type}].json`.
The authentication segment includes API-key placement or the OAuth client
credential method where relevant, such as `api_key_header` or `oauth_basic`.
Optional scenario suffixes distinguish exports, ZIP files, and multiple reports.
For tasks with helper requests, the method describes the main transfer.

Examples:

- `http_request_download_basic_get.json`
- `http_request_download_basic_post_form.json`
- `http_request_upload_api_key_header_put_file.json`
- `http_request_upload_oauth_body_post_multipart.json`

Download examples retrieve or save reports, including report requests with JSON
or form bodies. Upload examples send files or submit content without saving a
report. An upload that saves a receipt remains an upload example.

From the repository root, in a Python environment with `requests`, `jsonschema`,
and `pytest` installed:

```powershell
python -m pytest application/databricks/bundles/databridge/tests/unit/test_http.py
```

These tests inspect actual Requests-prepared messages using a fake transport;
they do not require vendor credentials or make external API calls.

## Internal module layout

- `oedis/handler/http.py` owns task configuration validation, inbox path
  resolution, request ordering, and `TaskResult` construction.
- `oedis/handler/lib/http_auth.py` owns Basic, bearer, API-key, and OAuth
  authentication, including the connection's token lifecycle.
- `oedis/handler/lib/http_client.py` owns sessions, header merging, body
  encoding, retries, transfer cleanup, and sanitized response metadata.

The library modules accept explicit configuration and resolved filesystem paths;
they do not depend on `ctx` or `TaskResult`. The client accepts an authentication
callback, and the authentication module uses the client's session helpers for
OAuth token requests. Existing REST handlers retain their independent implementation.
