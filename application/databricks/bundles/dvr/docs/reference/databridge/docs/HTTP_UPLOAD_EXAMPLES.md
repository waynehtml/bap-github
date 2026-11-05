# HTTP file upload examples

Both examples are complete task objects for `oedis.handler.http.request`.
Insert one into the pipeline `tasks` array. Replace the placeholder URLs,
secret scope/key names, endpoint paths, and expected statuses with the values
required by your API. Files must already exist beneath `ctx.inbox`.

## Multipart upload with OAuth 2.0 client credentials

This example obtains a bearer token, then sends a CSV file and report-date
field as `multipart/form-data`.

[Task JSON](../examples/http_request_upload_oauth_body_post_multipart.json)

```json
{
  "id": "upload_multipart_oauth2",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "base_url": "https://api.vendor.example.com/v1",
      "timeout_sec": 60,
      "headers": {
        "Accept": "application/json"
      },
      "auth": {
        "type": "oauth2_client_credentials",
        "token_url": "https://auth.vendor.example.com/token",
        "client_id": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-id\") }}",
        "client_secret": "{{ keyvault(scope=\"dis-secrets\", key=\"http-client-secret\") }}",
        "client_auth_method": "body",
        "scope": "reports.write"
      }
    },
    "requests": [
      {
        "id": "upload_report",
        "method": "POST",
        "path": "uploads",
        "body": {
          "type": "multipart",
          "fields": {
            "reportDate": "{{ runtime.rundate }}"
          },
          "files": [
            {
              "name": "file",
              "path": "prepared/report.csv",
              "filename": "report.csv",
              "content_type": "text/csv"
            }
          ]
        },
        "response": {
          "expected_status": [
            200,
            201
          ],
          "save_to": "receipts/multipart-oauth2.json"
        }
      }
    ]
  }
}
```

- `client_auth_method: "body"` sends the client credentials in the token
  request form. Set it to `"basic"` if the token endpoint expects HTTP Basic.
  In both cases the upload uses the returned bearer token.
- `files[].name` is the form field expected by the API; `filename` is the
  filename included in the multipart part.
- `files[].path` resolves to `ctx.inbox/prepared/report.csv`.
- Requests generates the multipart boundary. Leave `Content-Type` out of the
  connection and request headers; each file may specify its own MIME type.
- `response.save_to` saves the API response under the inbox. Omit it when
  only status validation is needed.

## Binary upload with an API key

This example sends a ZIP file as the entire PUT request body and places the
API key in `X-API-Key`. Binary upload uses `body.type: "file"` in the HTTP
handler.

[Task JSON](../examples/http_request_upload_api_key_header_put_file.json)

```json
{
  "id": "upload_binary_api_key",
  "handler": "oedis.handler.http.request",
  "params": {
    "connection": {
      "base_url": "https://api.vendor.example.com/v1",
      "timeout_sec": 60,
      "headers": {
        "Accept": "application/json"
      },
      "auth": {
        "type": "api_key",
        "location": "header",
        "name": "X-API-Key",
        "value": "{{ keyvault(scope=\"dis-secrets\", key=\"http-api-key\") }}"
      }
    },
    "requests": [
      {
        "id": "upload_archive",
        "method": "PUT",
        "path": "archives/daily",
        "body": {
          "type": "file",
          "path": "prepared/report.zip",
          "content_type": "application/zip"
        },
        "response": {
          "expected_status": [
            200,
            201
          ],
          "save_to": "receipts/binary-api-key.json"
        }
      }
    ]
  }
}
```

- `body.path` resolves to `ctx.inbox/prepared/report.zip`.
- `body.content_type` sets the request MIME type. Use the type expected by
  the endpoint, such as `application/octet-stream` for generic binary data.
- Set the method to `POST` if your API expects POST instead of PUT.
- If the API expects a query key, change `auth.location` to `"query"` and
  `auth.name` to its query parameter name. Cookie placement is also supported.

Both examples use the default single attempt. Enable retries only when the
API supports safe replay of uploads. These examples do not call live endpoints.

See the [HTTP user guide](HTTP_USER_GUIDE.md) and
[authentication examples](HTTP_AUTH_EXAMPLES.md) for the complete contract.
