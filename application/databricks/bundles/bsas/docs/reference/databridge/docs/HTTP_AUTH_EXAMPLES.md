# HTTP authentication examples

These examples use `oedis.handler.http.request`. Each linked JSON file is a
complete task object that can be inserted into your pipeline's `tasks` array.
The inline snippets below are the corresponding `params.connection.auth`
objects, not complete tasks.

Replace the placeholder vendor endpoints and secret scope/key names with your
own values. `{{ runtime.rundate }}` is resolved by DataBridge. Upload examples assume
the listed source files have been prepared in the task inbox.

Authentication is independent of the HTTP method and body type. Any supported
authentication type can be combined with JSON, form, text, file, or multipart
bodies when the target API supports that combination.

| Authentication | Full task example |
| --- | --- |
| No authentication | [http_request_download_none_get.json](../examples/http_request_download_none_get.json) |
| Basic authentication | [http_request_download_basic_post_form.json](../examples/http_request_download_basic_post_form.json) |
| Bearer token | [http_request_upload_bearer_put_file.json](../examples/http_request_upload_bearer_put_file.json) |
| API key in a header | [http_request_upload_api_key_header_post_json.json](../examples/http_request_upload_api_key_header_post_json.json) |
| API key in the query string | [http_request_download_api_key_query_get_export.json](../examples/http_request_download_api_key_query_get_export.json) |
| API key in a cookie | [http_request_upload_api_key_cookie_post_multipart.json](../examples/http_request_upload_api_key_cookie_post_multipart.json) |
| OAuth client credentials in the token body | [http_request_upload_oauth_body_put_file.json](../examples/http_request_upload_oauth_body_put_file.json) |
| OAuth client credentials in a Basic header | [http_request_upload_oauth_basic_post_multipart.json](../examples/http_request_upload_oauth_basic_post_multipart.json) |
| OAuth with vendor token fields | [http_request_download_oauth_body_get_custom_fields.json](../examples/http_request_download_oauth_body_get_custom_fields.json) |

## No authentication

Read a public JSON catalogue and check an endpoint with HEAD. The HEAD request validates status without saving a response.

```json
{
  "type": "none"
}
```

Full task: [http_request_download_none_get.json](../examples/http_request_download_none_get.json).

## Basic authentication

Submit a URL-encoded report request with username/password authentication and save the CSV response.

```json
{
  "type": "basic",
  "username": "{{ keyvault(scope=\"dis-secrets\", key=\"http-user\") }}",
  "password": "{{ keyvault(scope=\"dis-secrets\", key=\"http-password\") }}"
}
```

Full task: [http_request_download_basic_post_form.json](../examples/http_request_download_basic_post_form.json).

## Bearer token

Upload a ZIP file using an existing bearer token and save the JSON receipt. The source file must already exist in the inbox.

```json
{
  "type": "bearer",
  "token": "{{ keyvault(scope=\"dis-secrets\", key=\"http-bearer-token\") }}"
}
```

Full task: [http_request_upload_bearer_put_file.json](../examples/http_request_upload_bearer_put_file.json).

## API key in a header

Submit a JSON notification using X-API-Key and accept HTTP 202 without writing a response file.

```json
{
  "type": "api_key",
  "location": "header",
  "name": "X-API-Key",
  "value": "{{ keyvault(scope=\"dis-secrets\", key=\"http-api-key\") }}"
}
```

Full task: [http_request_upload_api_key_header_post_json.json](../examples/http_request_upload_api_key_header_post_json.json).

## API key in the query string

Download CSV with a query API key, repeated field parameters, and retries for temporary failures. The configured key is injected into the query automatically.

```json
{
  "type": "api_key",
  "location": "query",
  "name": "api_key",
  "value": "{{ keyvault(scope=\"dis-secrets\", key=\"http-api-key\") }}"
}
```

Full task: [http_request_download_api_key_query_get_export.json](../examples/http_request_download_api_key_query_get_export.json).

## API key in a cookie

Upload a CSV file and a report date using an API-key cookie. This sends a configured key directly; it does not perform a cookie login exchange.

```json
{
  "type": "api_key",
  "location": "cookie",
  "name": "vendor_api_key",
  "value": "{{ keyvault(scope=\"dis-secrets\", key=\"http-api-key\") }}"
}
```

Full task: [http_request_upload_api_key_cookie_post_multipart.json](../examples/http_request_upload_api_key_cookie_post_multipart.json).

## OAuth client credentials in the token body

Fetch a bearer token with client credentials in the token form body, then upload a ZIP file. The API receives the access token; the client secret is sent to the token endpoint.

```json
{
  "type": "oauth2_client_credentials",
  "token_url": "https://auth.vendor.example.com/token",
  "client_id": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-id\") }}",
  "client_secret": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-secret\") }}",
  "client_auth_method": "body",
  "scope": "reports.write",
  "token_params": {
    "audience": "https://api.vendor.example.com"
  }
}
```

Full task: [http_request_upload_oauth_body_put_file.json](../examples/http_request_upload_oauth_body_put_file.json).

## OAuth client credentials in a Basic header

Authenticate to the token endpoint with Basic, upload multipart content, then read a known report URL. A valid token is reused across the two API requests. The second path uses the run date, not a value extracted from the upload response.

```json
{
  "type": "oauth2_client_credentials",
  "token_url": "https://auth.vendor.example.com/token",
  "client_id": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-id\") }}",
  "client_secret": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-secret\") }}",
  "client_auth_method": "basic",
  "scope": "reports.read reports.write",
  "token_headers": {
    "Accept": "application/json"
  }
}
```

Full task: [http_request_upload_oauth_basic_post_multipart.json](../examples/http_request_upload_oauth_basic_post_multipart.json).

## OAuth with vendor token fields

Configure an extra resource parameter, a vendor token header, and alternate response field names. This example assumes the token endpoint returns bearerToken and ttlSeconds at the top level.

```json
{
  "type": "oauth2_client_credentials",
  "token_url": "https://auth.vendor.example.com/token",
  "client_id": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-id\") }}",
  "client_secret": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-secret\") }}",
  "client_auth_method": "body",
  "scope": "reports.read",
  "token_params": {
    "resource": "https://api.vendor.example.com"
  },
  "token_headers": {
    "Accept": "application/json",
    "X-Vendor-Account": "example-account"
  },
  "access_token_field": "bearerToken",
  "expires_in_field": "ttlSeconds"
}
```

Full task: [http_request_download_oauth_body_get_custom_fields.json](../examples/http_request_download_oauth_body_get_custom_fields.json).

Example token endpoint response:

```json
{
  "bearerToken": "<access-token>",
  "ttlSeconds": 3600
}
```

## OAuth download recipes

See [HTTP downloads with OAuth 2.0](HTTP_DOWNLOAD_EXAMPLES.md) for CSV, ZIP, PDF,
JSON/form export requests, and multiple downloads using one connection.

## File upload recipes

See [HTTP file upload examples](HTTP_UPLOAD_EXAMPLES.md) for complete multipart
upload with OAuth 2.0 and binary upload with API-key configurations.

## Request behavior

- Bearer authentication uses an existing token. OAuth client credentials obtains
  a token from the configured HTTPS token endpoint.
- For OAuth, `client_auth_method` changes authentication to the token endpoint.
  The API requests use `Authorization: Bearer <access-token>` in both cases.
- `token_params` adds form fields; use the dedicated `scope`, `client_id`, and
  `client_secret` settings for those values.
- API keys use the configured name and location. A query API key is supplied
  by `auth`; it does not need to be repeated in request `params`.
- Request headers override connection and built-in authentication headers.
  Keep authentication headers out of request headers unless an override is intended.
- The write examples use the default single attempt. The query export example
  demonstrates explicit retries for a read request.

See the [HTTP user guide](HTTP_USER_GUIDE.md) for the complete contract,
response handling, retry behavior, and token caching rules.
