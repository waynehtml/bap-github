# HTTP and configuration guide for DataBridge

This guide explains HTTP concepts and how to configure requests, authentication,
uploads, and downloads in DataBridge. Each example connects configuration to the
HTTP message sent to an API and the response received from it.

## The HTTP handler

`oedis.handler.http.request` sends HTTP requests, uploads inbox files, and
optionally saves response bodies. HTTP is the protocol used to exchange
requests and responses. OAuth is an authorization framework used to obtain
access tokens for those requests.

| Concern | HTTP configuration |
| --- | --- |
| Entry point | `oedis.handler.http.request` |
| Default method | GET, including when a body is configured |
| Target | Absolute `url`, or `connection.base_url` plus request `path` |
| Bodies | `json`, `form`, `text`, `file`, `multipart` |
| Save response | `response.save_to` |
| Retry settings | `connection.retry`, overridden by request `retry` |

The same entry point handles downloads, uploads, and API actions. Body format,
authentication, and response handling are configured independently. The inbox is
the working area containing files available to a task; upload and download paths
in this guide are relative to that area.

**How to read examples:** complete tasks contain `id`, `handler`, and `params`
and belong in a pipeline's `tasks` array. Smaller JSON blocks are explicitly
identified as fragments. Conceptual HTTP/1.1 blocks show the meaningful message
fields, omitting automatic headers and framing unless relevant. `[file bytes]`
and `<access-token>` are explanatory placeholders, not literal data to send.
Assume the run date is 2026-09-04. Hosts and secret references are illustrative.

## 1. From configuration to an HTTP exchange

An HTTP request contains a method, a target URL, headers, and an optional body.
The URL identifies the server and resource path, with optional query parameters.
Authentication supplies the credentials required by the API. Timeout and retry
settings control how long to wait and when another attempt is allowed; they are
not normally sent as HTTP fields.

```text
Configure the request
    -> fill in template values and secret references
    -> obtain an access token if OAuth is selected
    -> send the HTTP request
    -> receive a status code, headers, and body
    -> accept the configured status
    -> save the response body if a destination is configured
```

These concerns are independent: a POST can request a downloadable CSV, and a
PUT can send a ZIP and receive a JSON receipt. OAuth can authorize either
operation. The method describes the operation; the body describes the content
being sent. Saving the response is a separate configuration choice.

### Templates and secret references

Use templates for values that change between runs:

| Template | Example use |
| --- | --- |
| `{{ runtime.rundate }}` | Run date in query parameters, body values, or filenames |
| `{{ runtime.job_params.report_id }}` | A job parameter identifying the requested report |
| `{{ keyvault(scope='demo-secrets', key='api-token') }}` | A secret-store reference for an existing API token |

Use the full `runtime.rundate` name for date templates. Supply the referenced
job parameters and secrets before running the task. A secret reference supplies
a stored value; choosing OAuth separately requests an access token from a
token endpoint.

For example, this is a `connection.auth` fragment:

```json
{
  "type": "bearer",
  "token": "{{ keyvault(scope='demo-secrets', key='api-token') }}"
}
```

The token is used as a credential. The secret reference belongs in configuration;
the conceptual HTTP examples below show only synthetic token values.

## 2. Methods and common request shapes

| Method | Usual purpose |
| --- | --- |
| GET | Retrieve a representation of a resource |
| POST | Ask a resource to process submitted content |
| PUT | Create or replace the representation at a known target |
| PATCH | Apply a partial modification using the API's patch format |
| DELETE | Request removal of the target resource |

HTTP does not forbid every unusual method/body combination. However, GET and
DELETE content have no generally defined semantics; servers or intermediaries
may reject it. Follow the vendor contract. PUT and DELETE have idempotent
semantics: repeating the same request is intended to have the same effect as
sending it once. That does not make every application workflow safe to replay.
See [HTTP method semantics](https://www.rfc-editor.org/rfc/rfc9110.html#section-9)
and [PATCH](https://www.rfc-editor.org/rfc/rfc5789.html#section-2).

The following are HTTP `requests[]` fragments. Further complete task examples,
including authentication and responses, appear in section 12.

### GET with query parameters and no body

```json
{
  "method": "GET",
  "url": "https://api.vendor.example/reports",
  "params": {"date": "{{ runtime.rundate }}", "format": "csv"}
}
```

```http
GET /reports?date=2026-09-04&format=csv HTTP/1.1
Host: api.vendor.example
```

### POST with JSON

```json
{
  "method": "POST",
  "url": "https://api.vendor.example/reports/export",
  "body": {"type": "json", "value": {"reportDate": "{{ runtime.rundate }}"}}
}
```

```http
POST /reports/export HTTP/1.1
Host: api.vendor.example
Content-Type: application/json

{"reportDate": "2026-09-04"}
```

### POST with URL-encoded form data

```json
{
  "method": "POST",
  "url": "https://api.vendor.example/reports/export",
  "body": {"type": "form", "value": {"name": "daily report", "format": "csv"}}
}
```

```http
POST /reports/export HTTP/1.1
Host: api.vendor.example
Content-Type: application/x-www-form-urlencoded

name=daily+report&format=csv
```

### POST with multipart files

```json
{
  "method": "POST",
  "url": "https://api.vendor.example/uploads",
  "body": {
    "type": "multipart",
    "files": [{"name": "file", "path": "prepared/report.csv"}]
  }
}
```

```http
POST /uploads HTTP/1.1
Host: api.vendor.example
Content-Type: multipart/form-data; boundary=example-boundary

--example-boundary
Content-Disposition: form-data; name="file"; filename="report.csv"

[file bytes]
--example-boundary--
```

### PUT with a file as the complete body

```json
{
  "method": "PUT",
  "url": "https://api.vendor.example/archives/daily",
  "body": {
    "type": "file",
    "path": "prepared/report.zip",
    "content_type": "application/zip"
  }
}
```

```http
PUT /archives/daily HTTP/1.1
Host: api.vendor.example
Content-Type: application/zip

[ZIP bytes, without multipart wrappers]
```

### DELETE without a body

```json
{
  "method": "DELETE",
  "url": "https://api.vendor.example/reports/obsolete",
  "response": {"expected_status": 204}
}
```

```http
DELETE /reports/obsolete HTTP/1.1
Host: api.vendor.example
```

A 204 response has no response content. Usually omit `response.save_to` when
the API returns 204.

## 3. URL construction and query encoding

HTTP accepts exactly one of absolute `url` or relative `path`. A `path` requires
`connection.base_url`. With `base_url = https://api.vendor.example/v1`:

| Configured path | Resolved target |
| --- | --- |
| `reports` | `https://api.vendor.example/v1/reports` |
| `/reports` | `https://api.vendor.example/reports` |
| `reports/{{ runtime.job_params.report_id }}` | Templated resource path |

Use HTTP or HTTPS URLs without embedded credentials, fragments, whitespace, or
backslashes. Configure authentication separately. A `path` must refer to the
configured base URL rather than name another host. Keep query parameters out of
`connection.base_url`; put them in the request URL or `params`.

Template rendering is not URL-component encoding. A value containing `/`, `?`,
or `&` can change the URL structure if inserted directly into a path. Supply
appropriately encoded path segments or constrain their allowed characters.
Use `params` for query values so the client performs query encoding.

Query values are URL-encoded. For example, a space becomes `+`, and a literal
`+` becomes `%2B`. Put unencoded values in `params` so they are encoded once.

| Situation | HTTP behavior |
| --- | --- |
| Matching key in URL and `params` | Configured `params` replaces all existing values for that key |
| Repeated URL keys not overridden | Retained |
| List-valued `params` | Each scalar array item becomes a repeated query pair |
| Structured API-key query collision | The authentication value wins |

For example, `?tag=a&tag=b&format=json` with
`params = {"format": "csv", "region": ["east", "west"]}` becomes
`?tag=a&tag=b&format=csv&region=east&region=west`.

For a signed URL, the query is part of the authorization. Use the method and
headers required by its provider and avoid adding `params`: changing query
values or their encoding can invalidate a signature. See section 7.

## 4. Headers and their precedence

| Header | Purpose |
| --- | --- |
| `Authorization` | Carries credentials such as a bearer token |
| `Accept` | States preferred response media types |
| `Content-Type` | Describes the content carried by this message |
| `X-API-Key` or vendor equivalent | Carries a vendor-defined credential |
| `X-Request-ID` or vendor equivalent | Correlates a request with logs or support records |
| Response `Content-Disposition` | Suggests attachment handling and a filename |
| `Content-Length` | States the message content length in octets when provided |

These fields do not choose a local destination. In particular, `Accept` does not
save or convert data. Normally leave `Content-Length` out of configuration so it
matches the content sent. With content compression, the length on the wire may
differ from the size of the decompressed file. See
[HTTP representation metadata](https://www.rfc-editor.org/rfc/rfc9110.html#section-8).

Headers are merged in this order:

1. `connection.headers`
2. Structured authentication headers
3. `requests[].headers`

**Request headers override generated authentication headers.** Header names are
case-insensitive: request-level `authorization` replaces `Authorization`
generated from bearer authentication. Configure an override only when that is
what the API requires.

Do not set multipart `Content-Type` in connection or request headers. Its
boundary must match the delimiters in the body; leave the complete header to
be generated for the multipart request.

## 5. Authentication and credential lifecycle

The fragments in this section are `connection.auth` objects. Keep real secrets
in a secret store and use placeholders when explaining wire messages. Base64 is
an encoding, not encryption; use HTTPS to protect credentials in transit.

### No structured authentication

```json
{"type": "none"}
```

Generated auth header: none. Extra token request: none. The endpoint may be
public, or credentials may be supplied manually in a header or signed URL.
`none` is not a guarantee that no credentials exist elsewhere in the request.

### Basic authentication

```json
{
  "type": "basic",
  "username": "{{ keyvault(scope='demo-secrets', key='api-user') }}",
  "password": "{{ keyvault(scope='demo-secrets', key='api-password') }}"
}
```

```http
Authorization: Basic <base64(username:password)>
```

Extra token request: none. Basic authentication encodes the username/password
pair using Base64. Keep these credentials current in the secret store. Base64
does not protect them from someone who can read the message; use HTTPS.

### Static bearer token

```json
{
  "type": "bearer",
  "token": "{{ keyvault(scope='demo-secrets', key='api-token') }}"
}
```

```http
Authorization: Bearer <configured-token>
```

Extra token request: none. DataBridge receives an already-created token and does
not inspect its expiry or renew it in this mode. The token provider must manage
its validity. Possession of a bearer token generally grants its associated
access; see [bearer usage](https://www.rfc-editor.org/rfc/rfc6750.html#section-2.1).

### API key

Header-key configuration:

```json
{
  "type": "api_key",
  "name": "X-API-Key",
  "value": "{{ keyvault(scope='demo-secrets', key='api-key') }}"
}
```

```http
X-API-Key: <configured-key>
```

Extra token request: none. Rotation and expiry are managed externally. HTTP also
accepts `location: "header"`, `"query"`, or `"cookie"`; omitted means `header`.

HTTP query-key fragment:

```json
{
  "type": "api_key",
  "location": "query",
  "name": "api_key",
  "value": "{{ keyvault(scope='demo-secrets', key='api-key') }}"
}
```

This produces `/reports?api_key=<encoded-key>` and no auth header. With
`location: "cookie"`, it produces `Cookie: api_key=<configured-key>` instead.
A query key overrides a matching key from the URL or `params`. Treat URLs
containing API keys as credentials and avoid sharing them.

### OAuth 2.0 client credentials

OAuth first obtains a token; the business request then uses bearer auth:

```text
POST token endpoint
    -> receive access_token
    -> send Authorization: Bearer <access_token>
    -> call the business API
```

Configuration using the default client authentication method:

```json
{
  "type": "oauth2_client_credentials",
  "token_url": "https://auth.vendor.example/token",
  "client_id": "{{ keyvault(scope='demo-secrets', key='client-id') }}",
  "client_secret": "{{ keyvault(scope='demo-secrets', key='client-secret') }}",
  "scope": "reports.read"
}
```

Default conceptual token exchange, using illustrative values:

```http
POST /token HTTP/1.1
Host: auth.vendor.example
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=example-client&client_secret=example-secret&scope=reports.read
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"access_token":"example-token","token_type":"Bearer","expires_in":3600}
```

| OAuth property | Meaning |
| --- | --- |
| `grant_type` | Which grant is requested; here `client_credentials` |
| `client_id` | Identifies the client application |
| `client_secret` | Authenticates that application |
| `scope` | Requested permissions, usually a space-separated string |
| `access_token` | Credential used on subsequent API calls |
| `token_type` | Token usage scheme, such as Bearer |
| `expires_in` | Token lifetime in seconds |

This grant authorizes an application without an interactive user login. The
OAuth token response identifies how the token is used through `token_type`.
These configurations require a token endpoint that issues bearer access tokens.
See [OAuth client credentials](https://www.rfc-editor.org/rfc/rfc6749.html#section-4.4)
and [token response fields](https://www.rfc-editor.org/rfc/rfc6749.html#section-5.1).

#### Client-secret Basic versus client-secret POST

`client_secret_basic` sends client credentials in the token request's Basic
header. `client_secret_post` sends them in its form body. These established names
are described in [client authentication](https://openid.net/specs/openid-connect-core-1_0.html#ClientAuthentication).
They describe authentication to the token endpoint, not the business API body.

| Token exchange option | HTTP behavior |
| --- | --- |
| Grant | Always `client_credentials` |
| Client-secret POST | `client_auth_method: "body"`, the default |
| Client-secret Basic | `client_auth_method: "basic"` |
| Scope | Optional form field |
| Extra token form fields/headers | `token_params` / `token_headers` |
| Access token field | `access_token_field`, default `access_token` |
| Lifetime field | `expires_in_field`, default `expires_in` |
| Token endpoint transport | Requires HTTPS |
| Token endpoint redirects | Disabled |

Field-name overrides select top-level properties in the token response object.

For HTTP Basic client auth, the client ID and secret are individually
form-encoded before the pair is Base64 encoded. Credentials are then omitted
from the token form body. HTTP reserves `grant_type`, `client_id`, `client_secret`,
and `scope` from `token_params` overrides. Its token headers cannot override
Authorization and must preserve the form media type. HTTP does not expose a
JSON token request or an arbitrary grant switch.

#### Token lifetime and credential responsibilities

`expires_in` describes how long an access token remains valid. A token with
`expires_in: 3600` has a lifetime of one hour. Client credentials authorize
obtaining another token when needed; this is separate from a refresh-token
grant.

For static bearer authentication, supply a token that will remain valid for the
operation. For client credentials, keep the client ID, secret, scope, and token
endpoint current. A 401 response indicates an authentication problem and should
prompt a check of token validity and the API's requirements.

### Choosing an authentication approach

Use the vendor's required mechanism. Select `bearer` for a token already issued
to you, or `oauth2_client_credentials` to obtain an application token from a
token endpoint. Use `api_key` for a static key and choose its required placement.
For a signed URL, select `none` when the URL itself supplies authorization.

The configuration fields shown here do not cover interactive authorization-code
login, refresh-token grants, client certificates, Digest authentication, or
request signing. A supplied Cookie header is a credential value, not a login
workflow. An externally supplied signed URL must already be valid for the
operation. See section 12.7 for that configuration pattern.

## 6. Request-body formats

Body format describes outbound bytes. Authentication supplies access credentials;
it does not choose JSON, form encoding, multipart, or a file body.

### No body

Omit `body` for an ordinary GET, HEAD, DELETE, or an API action that needs no
content. A configured upload body uses the same HTTP entry point; specify the
method required by the API because its default remains GET.

### JSON

HTTP request-body fragment:

```json
{
  "body": {
    "type": "json",
    "value": {"reportDate": "{{ runtime.rundate }}"}
  }
}
```

```http
Content-Type: application/json

{"reportDate": "2026-09-04"}
```

`body.value` is serialized as UTF-8 JSON. The default content type is
`application/json`; an explicit header takes precedence. Objects, arrays,
strings, numbers, booleans, and null are valid JSON values. Choose a content
type that agrees with the body and the API contract.

### URL-encoded form

The configuration calls this `form`. Its media type is
`application/x-www-form-urlencoded`, not `multipart/form-data`.

```json
{
  "body": {
    "type": "form",
    "value": {"reportDate": "{{ runtime.rundate }}", "label": "daily report"}
  }
}
```

```http
Content-Type: application/x-www-form-urlencoded

reportDate=2026-09-04&label=daily+report
```

Form fields accept strings, numbers, or booleans; use JSON for nested data.
Use strings when a vendor requires exact spelling or formatting, such as
`"true"` or `"2026-09-04"`. OAuth client-credentials token endpoints use form
encoding for grant parameters; the business request can use another format.

### Text: XML, plain text, or pre-serialized JSON

HTTP `text` bodies are UTF-8 encoded. Their default content type is
`text/plain; charset=utf-8`. Use `body.content_type` or a request header for a
different media type; an explicit header takes precedence.

The following are HTTP request fragments:

```json
{
  "url": "https://api.vendor.example/documents",
  "method": "POST",
  "body": {
    "type": "text",
    "value": "<report><date>2026-09-04</date></report>",
    "content_type": "application/xml"
  }
}
```

```http
Content-Type: application/xml

<report><date>2026-09-04</date></report>
```

```json
{
  "url": "https://api.vendor.example/messages",
  "method": "POST",
  "body": {"type": "text", "value": "Report ready"}
}
```

```http
Content-Type: text/plain; charset=utf-8

Report ready
```

```json
{
  "url": "https://api.vendor.example/events",
  "method": "POST",
  "body": {
    "type": "text",
    "value": "{\"ready\":true}",
    "content_type": "application/json"
  }
}
```

```http
Content-Type: application/json

{"ready":true}
```

The last example sends a pre-serialized JSON string. Prefer `type: "json"` when
starting from structured data so quoting and serialization are handled for you.

### Multipart: several named parts in one request

A multipart body contains sections separated by a generated boundary. Each part
has its own headers and content. The field `name` identifies the server's input;
`filename` describes a file within that input. They can differ.

HTTP multipart body fragment:

```json
{
  "body": {
    "type": "multipart",
    "fields": {"reportDate": "{{ runtime.rundate }}"},
    "files": [
      {
        "name": "documents",
        "path": "prepared/report.csv",
        "filename": "daily.csv",
        "content_type": "text/csv"
      },
      {
        "name": "documents",
        "path": "prepared/notes.txt",
        "content_type": "text/plain"
      }
    ]
  }
}
```

```http
Content-Type: multipart/form-data; boundary=example-boundary

--example-boundary
Content-Disposition: form-data; name="reportDate"

2026-09-04
--example-boundary
Content-Disposition: form-data; name="documents"; filename="daily.csv"
Content-Type: text/csv

[CSV bytes]
--example-boundary
Content-Disposition: form-data; name="documents"; filename="notes.txt"
Content-Type: text/plain

[notes bytes]
--example-boundary--
```

`files` must be non-empty. Repeated field names are supported. Omitted filenames
default to source basenames. Scalar `fields` are converted to strings. A per-file
content type is optional and describes only that part. The boundary shown here
is illustrative; the actual boundary is generated for the request.
**Do not manually set the overall multipart Content-Type.** The enclosing header
must contain the same boundary used inside the body. See
[multipart/form-data](https://www.rfc-editor.org/rfc/rfc7578.html#section-4).

### One file as the complete request body

Use `type: "file"` when one inbox file should become the entire request body:

```json
{
  "body": {
    "type": "file",
    "path": "prepared/report.zip",
    "content_type": "application/zip"
  }
}
```

```http
Content-Type: application/zip

[the complete contents of report.zip]
```

There are no multipart delimiters or part-level filename headers. The file can
contain text, JSON, a ZIP, a PDF, or arbitrary binary data. Complete-file
transfers are commonly used for PUT/object-storage endpoints, signed upload
URLs, archives, and document APIs when their contracts request that shape.
The file contents become the complete body. Set `body.content_type` to the
media type required by the endpoint unless it is already specified in headers.
A filename extension alone does not set the request Content-Type.

## 7. Upload configuration

Choose the body format required by the API:

| API expects | Body type | File configuration |
| --- | --- | --- |
| Named fields and one or more files | `multipart` | `body.files`, plus optional `body.fields` |
| One file as the complete body | `file` | `body.path`, plus optional `body.content_type` |

Upload files must exist in the task inbox. Use relative paths such as
`prepared/report.csv`. A leading `/` refers to the inbox root; do not use `..`,
external filesystem paths, or cloud URLs as file paths. An earlier task or
request may produce a file used by a later upload.

For multipart uploads, `name` is the form field expected by the API and
`filename` is the file name advertised in that part. `path` selects the local
file. For a complete-file upload, the target URL typically identifies the
remote object or document; the body contains only the file's bytes.

Authentication and body format can be combined independently:

| Upload | Body type | Authentication |
| --- | --- | --- |
| Multipart with OAuth | `multipart` | `oauth2_client_credentials` |
| Multipart with API key | `multipart` | `api_key` |
| Complete file with bearer | `file` | `bearer` |
| Complete file with API key | `file` | `api_key` |
| Complete file through a signed URL | `file` | `none`; URL supplied externally |

An upload can also return a useful response body. Set `response.save_to` to
retain an import receipt, document identifier, or other returned content.
The upload path and response destination serve different purposes.

### Signed and presigned URLs

A signed URL carries permission for a particular operation, usually with an
expiry time. A presigned URL or SAS URL is supplied by another system; no
signing fields are configured in these examples. Use the specified HTTP method,
required headers, and content type. Additional `params` or changes to query
encoding can invalidate the signature, so verify compatibility with the provider.

Treat the complete signed URL as a credential. Store it as a secret reference
and avoid pasting it into shared documents or logs. Obtain a new URL when its
permission expires. `auth.type: "none"` means no extra structured credentials
are configured; it does not make the endpoint public.

## 8. HTTP responses, status checks, and retries

An HTTP response contains a status code, headers, and an optional body:

```http
HTTP/1.1 200 OK
Content-Type: text/csv

date,value
2026-09-04,100
```

The status communicates the outcome. Headers describe the response, and the
body carries the returned data.

| Status class | General meaning | Examples |
| --- | --- | --- |
| 2xx | Successful request | 200 OK, 201 Created, 202 Accepted, 204 No Content |
| 3xx | Redirection | 301 Moved Permanently, 302 Found, 307 Temporary Redirect |
| 4xx | Client/request problem | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 429 Too Many Requests |
| 5xx | Server problem | 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable |

A 202 means the request was accepted, not that a remote job has completed.
A 204 has no response content. A successful status does not guarantee that the
body has the file format or business data you expected.

### Accepting a response

By default, status codes 200-299 are accepted. Set `response.expected_status`
to an integer or non-empty list to require specific statuses. For example,
`{"expected_status": [200, 201, 204]}` accepts those three codes only.

Redirects are not followed. Accepting a 3xx status does not fetch the destination
in its `Location` header. Configure the final API URL when it is known.

Use `response.save_to` to retain the response body as a file. Without a
save destination, the body is discarded. Response headers, such as
`Content-Disposition`, do not select a local file automatically.

### Timeout and retry configuration

| Setting | Meaning and default |
| --- | --- |
| `connection.timeout_sec` | Positive connection/read inactivity timeout; default 60 seconds |
| `retry.max_attempts` | Total attempts including the first; default 1 |
| `retry.interval_sec` | Seconds between attempts; default 0 |
| `retry.status_codes` | Unexpected statuses eligible for retry; default empty |

Set connection-level retry values as defaults and override individual fields
with a request's `retry`. Zero delays and empty status lists are valid overrides.
An accepted status takes precedence over the retry list. Connection failures,
timeouts, and interrupted response transfers may also be retried within the
configured attempt budget.

The timeout limits waiting for connection/read activity, not the total duration
of a transfer. A large response that keeps delivering data can take longer than
`timeout_sec`. Choose a value suitable for the vendor's response times.

A retry sends another request. For actions or uploads, a timeout may occur after
the server has accepted the first request. Use retries only when the API permits
safe repetition or provides an idempotency mechanism, such as a documented
request-key header. A fixed interval is used; do not assume automatic backoff
or handling of the response's `Retry-After` value.

## 9. Downloading files with GET or POST

`Accept: text/csv` asks for CSV. It neither validates the format nor instructs
DataBridge to save it. A `.csv` destination does not convert JSON/HTML into CSV.
HTTP saves response bytes only when `response.save_to` is configured. JSON, CSV,
XML, ZIP, PDF, and arbitrary binary content can all be saved this way.
Successful HTTP status alone does not prove the file is useful.

The following are HTTP `requests[]` fragments.

GET download:

```json
{
  "method": "GET",
  "url": "https://api.vendor.example/reports/daily",
  "headers": {"Accept": "text/csv"},
  "response": {"save_to": "raw/report_{{ runtime.rundate }}.csv"}
}
```

POST download:

```json
{
  "method": "POST",
  "url": "https://api.vendor.example/reports/export",
  "headers": {"Accept": "text/csv"},
  "body": {
    "type": "form",
    "value": {"date": "{{ runtime.rundate }}", "format": "csv"}
  },
  "response": {"save_to": "raw/report_{{ runtime.rundate }}.csv"}
}
```

The second request sends parameters, then receives the file. It is a download
workflow despite using POST and an outbound form body. A JSON request body can
also select a downloadable response when required by the API. A request can
upload a file and save its response in the same operation.

Without `response.save_to`, the response body is discarded. An `Accept` header
or a form field
such as `format: "csv"` does not change that behavior. Section 12.4 shows a
complete form-POST download; section 12.8 intentionally discards a response.

## 10. Choosing the response filename

Set `response.save_to` to an explicit inbox-relative path. For example,
`raw/report_{{ runtime.rundate }}.csv` produces a predictable name for each run
date. Choose distinct paths when several responses must be retained; using the
same path again replaces its contents.

| Possible filename source | Configuration guidance |
| --- | --- |
| Explicit destination | Set `response.save_to` |
| Server's Content-Disposition | Informational; does not replace the configured destination |
| URL basename | Does not select a destination automatically |
| Content-Type | Describes a media type; does not choose or validate a file extension |

For example, a server may send:

```http
Content-Disposition: attachment; filename="vendor-report.csv"
```

You can still save that response as `raw/daily.csv`. The header describes the
server's suggested download name, while `response.save_to` selects the local
artifact name. See
[Content-Disposition filenames](https://www.rfc-editor.org/rfc/rfc6266.html#section-4.3).

The inbox is a staging area. Arrange a later pipeline step to consume or persist
files that must be retained beyond the run.

## 11. Planning file transfers

Use the vendor's upload and download contract to choose the request shape and
configuration:

- For a complete-file endpoint, use `body.type: "file"`. For an endpoint requiring
  named parts or accompanying form fields, use `multipart`.
- Match the required media type, method, and accepted response statuses. A ZIP
  upload and a JSON receipt can have different content types.
- Check the provider's file-size and request-duration limits before selecting
  timeout and retry values. Split data only if the API supports separate files
  or parts.
- Give each saved response a suitable destination and ensure the task's staging
  area can accommodate it. A response body is saved only with `response.save_to`.
- Plan how to confirm completion. A 202 response may require a separate status
  request before a report or imported dataset is ready.

Timeouts, response filenames, and authentication do not change the vendor's
protocol. Use the file-transfer procedure described by that API.

## 12. Complete configuration-to-wire walkthroughs

Each example below is a complete HTTP task object. All wire values are synthetic.
The date is assumed to render as 2026-09-04; upload source files must already be
in the inbox. JSON whitespace and generated multipart boundaries may differ on
the wire without changing their meaning. Responses illustrate a vendor contract,
not an assertion that any placeholder endpoint was called.

### 12.1. GET JSON with a static bearer token and save it

```json
{
  "id": "get_json_report",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {
        "type": "bearer",
        "token": "{{ keyvault(scope='demo-secrets', key='api-token') }}"
      }
    },
    "requests": [
      {
        "method": "GET",
        "url": "https://api.vendor.example/reports/daily",
        "headers": {"Accept": "application/json"},
        "response": {
          "expected_status": 200,
          "save_to": "raw/report_{{ runtime.rundate }}.json"
        }
      }
    ]
  }
}
```

**Authentication preparation:** resolve the secret and generate the bearer
header. There is no token-endpoint request; DataBridge relies on the supplied
token remaining valid.

```http
GET /reports/daily HTTP/1.1
Host: api.vendor.example
Authorization: Bearer example-token
Accept: application/json
```

Conceptual response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"reportDate":"2026-09-04","rows":100}
```

**Result:** save the JSON response to `raw/report_2026-09-04.json` in the inbox.
The request has no body; the bearer header supplies authentication and `Accept`
asks for JSON. The configured destination retains the response content.

### 12.2. GET CSV with an API-key header and query parameters

```json
{
  "id": "get_csv_report",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {
        "type": "api_key",
        "location": "header",
        "name": "X-API-Key",
        "value": "{{ keyvault(scope='demo-secrets', key='api-key') }}"
      }
    },
    "requests": [
      {
        "method": "GET",
        "url": "https://api.vendor.example/reports",
        "params": {
          "date": "{{ runtime.rundate }}",
          "format": "csv"
        },
        "headers": {"Accept": "text/csv"},
        "response": {"save_to": "raw/daily_{{ runtime.rundate }}.csv"}
      }
    ]
  }
}
```

**Authentication preparation:** resolve the static key and put it in
`X-API-Key`. No extra request is made. The date and format are independent
query parameters; the key is not put in the URL in this example.

```http
GET /reports?date=2026-09-04&format=csv HTTP/1.1
Host: api.vendor.example
X-API-Key: example-key
Accept: text/csv
```

Conceptual response:

```http
HTTP/1.1 200 OK
Content-Type: text/csv
Content-Disposition: attachment; filename="vendor-daily.csv"

date,value
2026-09-04,100
```

**Result:** save the CSV response to `raw/daily_2026-09-04.csv` in the inbox.
The date and format query values select the report. The configured destination
is used even though the server suggests `vendor-daily.csv`.

### 12.3. POST JSON with OAuth client credentials

```json
{
  "id": "export_json_with_oauth",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {
        "type": "oauth2_client_credentials",
        "token_url": "https://auth.vendor.example/oauth/token",
        "client_id": "example-client",
        "client_secret": "{{ keyvault(scope='demo-secrets', key='client-secret') }}",
        "scope": "reports.read",
        "client_auth_method": "body"
      }
    },
    "requests": [
      {
        "method": "POST",
        "url": "https://api.vendor.example/reports/export",
        "headers": {"Accept": "application/json"},
        "body": {
          "type": "json",
          "value": {"reportDate": "{{ runtime.rundate }}"}
        },
        "response": {
          "expected_status": 200,
          "save_to": "raw/export_{{ runtime.rundate }}.json"
        }
      }
    ]
  }
}
```

**Authentication preparation:** resolve the client secret, then obtain a token
with the client-credentials grant. The illustrative form body below represents
`client_secret_post`; the business request does not send the client secret.

```http
POST /oauth/token HTTP/1.1
Host: auth.vendor.example
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&client_id=example-client&client_secret=example-secret&scope=reports.read
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"access_token":"example-access-token","token_type":"Bearer","expires_in":3600}
```

The bearer access token authorizes the business request:

```http
POST /reports/export HTTP/1.1
Host: api.vendor.example
Authorization: Bearer example-access-token
Accept: application/json
Content-Type: application/json

{"reportDate":"2026-09-04"}
```

Conceptual business response:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"reportDate":"2026-09-04","items":[{"id":1}]}
```

**Result:** save the business API's response to `raw/export_2026-09-04.json` in
the inbox. The OAuth exchange supplies authorization; the separate JSON request
body selects the report to export.

### 12.4. POST a URL-encoded form and download the CSV response

```json
{
  "id": "export_csv_with_form",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {"type": "none"}
    },
    "requests": [
      {
        "method": "POST",
        "url": "https://api.vendor.example/reports/export",
        "headers": {"Accept": "text/csv"},
        "body": {
          "type": "form",
          "value": {
            "date": "{{ runtime.rundate }}",
            "format": "csv"
          }
        },
        "response": {
          "expected_status": 200,
          "save_to": "raw/form_export_{{ runtime.rundate }}.csv"
        }
      }
    ]
  }
}
```

**Authentication preparation:** none for this hypothetical public endpoint.
Use the vendor's required authentication for a protected endpoint; form
encoding does not itself authenticate this request.

```http
POST /reports/export HTTP/1.1
Host: api.vendor.example
Accept: text/csv
Content-Type: application/x-www-form-urlencoded

date=2026-09-04&format=csv
```

Conceptual response:

```http
HTTP/1.1 200 OK
Content-Type: text/csv

date,value
2026-09-04,100
```

**Result:** save the CSV response to `raw/form_export_2026-09-04.csv` in the
inbox. This is a download initiated by POST. Omitting `response.save_to` would
discard the response body, even with `Accept: text/csv`.

### 12.5. POST multipart files with OAuth

```json
{
  "id": "upload_csv_with_oauth",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {
        "type": "oauth2_client_credentials",
        "token_url": "https://auth.vendor.example/oauth/token",
        "client_id": "example-client",
        "client_secret": "{{ keyvault(scope='demo-secrets', key='client-secret') }}",
        "scope": "reports.write",
        "client_auth_method": "basic"
      }
    },
    "requests": [
      {
        "method": "POST",
        "url": "https://api.vendor.example/reports/import",
        "headers": {"Accept": "application/json"},
        "body": {
          "type": "multipart",
          "fields": {"reportDate": "{{ runtime.rundate }}"},
          "files": [
            {
              "name": "file",
              "path": "prepared/report_{{ runtime.rundate }}.csv",
              "filename": "daily.csv",
              "content_type": "text/csv"
            }
          ]
        },
        "response": {
          "expected_status": 201,
          "save_to": "receipts/multipart_{{ runtime.rundate }}.json"
        }
      }
    ]
  }
}
```

**Authentication preparation:** this example uses `client_secret_basic`.
The synthetic Basic value below encodes `example-client:example-secret`.
Client credentials authenticate the token request; the returned bearer token
authenticates the multipart request.

```http
POST /oauth/token HTTP/1.1
Host: auth.vendor.example
Authorization: Basic ZXhhbXBsZS1jbGllbnQ6ZXhhbXBsZS1zZWNyZXQ=
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&scope=reports.write
```

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"access_token":"example-access-token","token_type":"Bearer","expires_in":3600}
```

Conceptual business request with an illustrative multipart boundary:

```http
POST /reports/import HTTP/1.1
Host: api.vendor.example
Authorization: Bearer example-access-token
Accept: application/json
Content-Type: multipart/form-data; boundary=example-boundary

--example-boundary
Content-Disposition: form-data; name="reportDate"

2026-09-04
--example-boundary
Content-Disposition: form-data; name="file"; filename="daily.csv"
Content-Type: text/csv

[bytes from prepared/report_2026-09-04.csv]
--example-boundary--
```

Conceptual response:

```http
HTTP/1.1 201 Created
Content-Type: application/json

{"importId":"example-import","accepted":true}
```

**Result:** upload `prepared/report_2026-09-04.csv` as the form field `file`,
with the advertised filename `daily.csv`. Save the JSON receipt to
`receipts/multipart_2026-09-04.json` in the inbox. The bearer token authorizes the
upload independently of the multipart format.

Do not copy the conceptual multipart `Content-Type` into configuration; its
boundary must be generated together with the request body.

### 12.6. PUT a complete file with an API-key header

```json
{
  "id": "upload_zip_with_api_key",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {
        "type": "api_key",
        "location": "header",
        "name": "X-API-Key",
        "value": "{{ keyvault(scope='demo-secrets', key='api-key') }}"
      }
    },
    "requests": [
      {
        "method": "PUT",
        "url": "https://api.vendor.example/archives/daily.zip",
        "body": {
          "type": "file",
          "path": "prepared/daily.zip",
          "content_type": "application/zip"
        },
        "response": {"expected_status": [200, 201, 204]}
      }
    ]
  }
}
```

**Authentication preparation:** resolve the API key and generate `X-API-Key`.
No token request is required. The file format and its content type are
independent of the authentication method.

```http
PUT /archives/daily.zip HTTP/1.1
Host: api.vendor.example
X-API-Key: example-key
Content-Type: application/zip

[complete bytes from prepared/daily.zip]
```

Conceptual response:

```http
HTTP/1.1 201 Created
Content-Type: application/json

{"stored":true}
```

**Result:** send the complete ZIP as the request body. The API-key header
authorizes the upload. The JSON receipt is intentionally discarded because no
`response.save_to` is configured. A permitted 204 response would have no body.

### 12.7. PUT a complete file through a supplied signed URL

```json
{
  "id": "upload_zip_with_signed_url",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {"type": "none"}
    },
    "requests": [
      {
        "method": "PUT",
        "url": "{{ keyvault(scope='demo-secrets', key='signed-upload-url') }}",
        "body": {
          "type": "file",
          "path": "prepared/daily.zip",
          "content_type": "application/zip"
        },
        "response": {"expected_status": [200, 201, 204]}
      }
    ]
  }
}
```

**Authentication preparation:** another system creates a URL authorizing this
operation before the task runs. The secret stores that URL. DataBridge neither
signs it nor refreshes it. The following query is schematic, not a complete
provider-specific SAS or presigning recipe. A real provider may require extra
signed headers or additional query fields.

```http
PUT /inbox/daily.zip?sp=w&sig=example-signature HTTP/1.1
Host: storage.vendor.example
Content-Type: application/zip

[complete bytes from prepared/daily.zip]
```

Conceptual response:

```http
HTTP/1.1 201 Created
Content-Length: 0
```

**Result:** send the complete ZIP to the location authorized by the signed URL.
The illustrated 201 response has no body, and no response file is saved.
`none` adds no structured authentication; the URL itself supplies permission.

Use the method and headers required by the signer. Do not add `params` to the
signed URL, and verify that its query encoding remains compatible with the
provider. Obtain a fresh signed URL if it expires.

### 12.8. POST an action and intentionally discard its response

```json
{
  "id": "trigger_report_build",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "timeout_sec": 60,
      "auth": {
        "type": "bearer",
        "token": "{{ keyvault(scope='demo-secrets', key='api-token') }}"
      }
    },
    "requests": [
      {
        "method": "POST",
        "url": "https://api.vendor.example/reports/build",
        "body": {
          "type": "json",
          "value": {"date": "{{ runtime.rundate }}"}
        },
        "retry": {"max_attempts": 1},
        "response": {"expected_status": 202}
      }
    ]
  }
}
```

**Authentication preparation:** read an existing bearer token from the secret
store. There is no OAuth exchange in this task.

```http
POST /reports/build HTTP/1.1
Host: api.vendor.example
Authorization: Bearer example-token
Content-Type: application/json

{"date":"2026-09-04"}
```

Conceptual response:

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
Location: /jobs/example-job

{"jobId":"example-job","state":"queued"}
```

**Result:** accept the 202 response and discard its body because no save
destination is configured. The remote job may still be queued. Configure a
response destination if a later step needs the job identifier, and use the
vendor's status endpoint to check completion separately.

One attempt avoids retrying this potentially non-idempotent action. A successful
HTTP request does not by itself guarantee that the remote job runs exactly once.

## 13. Configuration quick reference

A complete task uses `handler: "oedis.handler.http.request"` and places its
connection defaults and request list inside `params`.

| Configuration | Purpose |
| --- | --- |
| `connection.base_url` | Base URL for requests using `path` |
| `connection.headers` | Default headers for the task's requests |
| `connection.auth` | Authentication type and credentials |
| `connection.timeout_sec` | Positive connection/read inactivity timeout |
| `connection.retry` | Default attempt count, interval, and retryable statuses |
| `requests[].method` | HTTP method; defaults to GET |
| `requests[].url` | Absolute target URL; choose this or `path` |
| `requests[].path` | Target path relative to `connection.base_url` |
| `requests[].params` | Query parameters, including scalar arrays for repeated keys |
| `requests[].headers` | Headers overriding connection and generated auth headers |
| `requests[].body` | Optional `json`, `form`, `text`, `file`, or `multipart` content |
| `requests[].retry` | Overrides individual connection retry settings |
| `requests[].response.expected_status` | Accepted status or list of statuses; defaults to all 2xx |
| `requests[].response.save_to` | Inbox-relative path for saving the response body |

Choose the HTTP method and body format from the vendor's API contract, select
authentication independently, and configure a response destination whenever the
returned content must be retained.
