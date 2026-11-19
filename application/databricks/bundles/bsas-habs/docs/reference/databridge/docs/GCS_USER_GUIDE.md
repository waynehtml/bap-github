# gcs

Handler:

- `oedis.handler.gcs.download`

Downloads files from Google Cloud Storage into the task inbox using GCS HMAC interoperability mode.

This is intentionally implemented as S3-compatible object storage access:

- endpoint URL: `https://storage.googleapis.com`
- client: `boto3` S3 client
- credentials: GCS HMAC `access_id` and `secret`

It does not use Google service-account JSON authentication.

## Configuration

### Task parameters (`params`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `connection.uri` | Yes | string | none | GCS source base URI, for example `gs://bucket-name` or `gs://bucket-name/base-prefix`. |
| `connection.endpoint_url` | Yes | string | none | S3-compatible endpoint URL, expected to be `https://storage.googleapis.com` for GCS HMAC interoperability. |
| `connection.auth.access_id` | Yes | string | none | GCS HMAC access key ID. |
| `connection.auth.secret` | Yes | string | none | GCS HMAC secret access key. Use a secret reference or template; do not hard-code it. |
| `requests` | Yes | list | none | One or more download specs. |

### Download spec (`requests[]`)

| Field | Required | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `src_dir` | No | string | `""` | GCS source prefix relative to `connection.uri`. |
| `dst_dir` | No | string | `""` | Local destination directory relative to `ctx.inbox`. |
| `include` | No | string or list[string] | `["*"]` | Glob pattern or list of patterns to include. |
| `exclude` | No | string or list[string] | `[]` | Glob pattern or list of patterns to exclude before include matching. |
| `recursive` | No | bool | `false` | When true, recursively lists objects under the resolved source prefix. |

## Behavior

- Remote source prefix = `connection.uri + src_dir`.
- Local destination root = `ctx.inbox + dst_dir`.
- GCS folders are object key prefixes. The handler uses paginated `list_objects_v2` calls through the S3-compatible API.
- `recursive=false` lists only direct child objects under `src_dir`; nested objects are skipped.
- `recursive=true` recursively lists objects under `src_dir`.
- When `recursive=false`, `include` and `exclude` match file names only.
- When `recursive=true`, `include` and `exclude` match both file names and paths relative to `src_dir`.
- Downloads preserve each object's path relative to `src_dir` under `dst_dir`.
- The handler verifies the downloaded local file size against the object size returned by GCS.
- Secrets are passed into boto3 but are not logged.

## Example

```json
{
  "pipeline": "gcs_hmac_download",
  "tasks": [
    {
      "id": "download_gcs",
      "handler": "oedis.handler.gcs.download",
      "params": {
        "connection": {
          "uri": "gs://paycan-bucket/dropzone",
          "endpoint_url": "https://storage.googleapis.com",
          "auth": {
            "access_id": "{{ runtime.job_params.gcs_access_id }}",
            "secret": "{{ keyvault(scope='my-secret-scope', key='st-paycangcs-accesskeysecret') }}"
          }
        },
        "requests": [
          {
            "src_dir": "incoming",
            "dst_dir": "raw/paycan",
            "recursive": true,
            "include": ["*.csv"],
            "exclude": ["*.tmp"]
          }
        ]
      }
    }
  ]
}
```

The bucket and object prefix belong in `connection.uri` and `requests[].src_dir`.
