# HTTP downloads with OAuth 2.0

These are complete `oedis.handler.http.request` task objects for a pipeline's
`tasks` array. They obtain a bearer token using OAuth 2.0 client credentials
and save each successful response beneath the task inbox.

Replace the placeholder URLs, secret scope/key names, scopes, endpoint paths,
and request fields with those expected by your API. `{{ runtime.rundate }}` is
resolved by DataBridge. The examples assume synchronous endpoints that return
the requested file directly with HTTP 200.

| Download scenario | Token client authentication | Complete task |
| --- | --- | --- |
| GET CSV | Form body | [oauth_body](../examples/http_request_download_oauth_body_get.json) |
| GET CSV | Basic header | [oauth_basic](../examples/http_request_download_oauth_basic_get.json) |
| GET ZIP with retries | Basic header | [oauth_zip](../examples/http_request_download_oauth_basic_get_zip.json) |
| POST JSON, receive CSV | Form body | [oauth_json_post](../examples/http_request_download_oauth_body_post_json.json) |
| POST form, receive PDF | Basic header | [oauth_form_post](../examples/http_request_download_oauth_basic_post_form.json) |
| Sequential JSON and CSV downloads | Form body | [oauth_multiple_reports](../examples/http_request_download_oauth_body_get_multiple_reports.json) |
| Custom token response fields | Form body | [oauth_custom_fields](../examples/http_request_download_oauth_body_get_custom_fields.json) |

## POST JSON and save the CSV response

The API request sends report criteria as JSON. Its response is saved as a CSV
file; the handler saves the returned bytes without converting the format.

```json
{
  "id": "http_request_download_oauth_json_post",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "base_url": "https://api.vendor.example.com/v1",
      "timeout_sec": 120,
      "auth": {
        "type": "oauth2_client_credentials",
        "token_url": "https://auth.vendor.example.com/token",
        "client_id": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-id\") }}",
        "client_secret": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-secret\") }}",
        "client_auth_method": "body",
        "scope": "reports.read",
        "token_headers": {
          "Accept": "application/json"
        }
      }
    },
    "requests": [
      {
        "id": "export_csv",
        "method": "POST",
        "path": "reports/export",
        "headers": {
          "Accept": "text/csv"
        },
        "body": {
          "type": "json",
          "value": {
            "reportDate": "{{ runtime.rundate }}",
            "format": "csv",
            "columns": [
              "id",
              "amount",
              "currency"
            ]
          }
        },
        "response": {
          "expected_status": 200,
          "save_to": "raw/oauth-export_{{ runtime.rundate }}.csv"
        }
      }
    ]
  }
}
```

## Download variations

- **ZIP:** `http_request_download_oauth_basic_get_zip.json` sends a GET with
  `Accept: application/zip`, saves the archive, and retries selected temporary
  failures. It does not extract the archive.
- **Form export:** `http_request_download_oauth_basic_post_form.json` sends
  URL-encoded form fields and saves the PDF response. The request body type
  controls the export request; `Accept` describes the expected response.
- **Multiple reports:** `http_request_download_oauth_body_get_multiple_reports.json`
  downloads metadata and data from two configured endpoints in order. The
  handler reuses a token while its reported lifetime remains valid and
  refreshes before expiry. The second request does not extract its URL from
  the first response.

## Authentication and response settings

- `client_auth_method: "body"` puts credentials in the token request form.
  `"basic"` puts them in the token request Authorization header. Both produce
  bearer authentication for the subsequent download requests.
- The token endpoint must use HTTPS. Configure `scope` and any vendor-required
  `token_params`, such as `audience` or `resource`, for your service.
- `response.save_to` is relative to `ctx.inbox`. Parent directories are created
  as needed, and an existing destination is replaced after a complete transfer.
- The POST examples use the default single attempt. Enable replay only when
  the export endpoint supports it safely.
- APIs that return a download link or HTTP 202 for asynchronous processing
  need additional workflow logic. These examples expect the file response
  directly and do not implement polling or redirect following.

See the [HTTP user guide](HTTP_USER_GUIDE.md) and
[authentication examples](HTTP_AUTH_EXAMPLES.md) for the complete contract.
