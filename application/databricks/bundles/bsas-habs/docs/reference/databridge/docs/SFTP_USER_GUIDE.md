# sftp

Handlers:

- `oedis.handler.sftp.download`
- `oedis.handler.sftp.upload`

Transfers files between an SFTP server and the task inbox using discovery plus
parallel workers.

## What this handler does

Use this handler when you need to:

- connect to an SFTP server with username/password or SSH private key authentication
- verify the remote host with `known_hosts` entries or SSH host key fingerprints
- download files from remote directories into `ctx.inbox`
- upload files from `ctx.inbox` into remote directories
- optionally recurse into subdirectories while preserving their hierarchy
- filter transfers by filename or relative-path patterns
- filter downloads by remote modified timestamps
- optionally delete source files after successful, validated transfers

Both directions reuse the same `connection` settings. Download and upload
requests reverse the local and remote meanings of `src_dir` and `dst_dir`.

## Configuration

### Task fields

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `connection.hostname` | Yes | none | SFTP host to connect to. |
| `connection.port` | No | `22` | SFTP port. |
| `connection.keepalive_sec` | No | `30` | SSH keepalive interval. |
| `connection.max_connections` | No | `1` | Max worker threads, capped by discovered file count. |
| `connection.root_dir` | No | `""` | Remote base directory for all requests. Empty or omitted means the connection's current/root remote directory. |
| `connection.disabled_algorithms` | No | none | Paramiko `disabled_algorithms` object. |
| `connection.auth.type` | No | `basic` | `basic` or `key`. |
| `connection.auth.username` | Yes | none | Username for the SFTP server. |
| `connection.auth.password` | Depends | none | Required for `basic`; optional for `key`. Some servers require both a private key and a login password. |
| `connection.auth.private_key` | Depends | none | Required for `key`; accepts raw PEM text or base64-encoded PEM text. Base64 is recommended for Key Vault and JSON/template delivery paths. |
| `connection.auth.private_key_passphrase` | No | none | Passphrase used to unlock the encrypted private key. This is not the same as the SFTP account password. |
| `connection.host_verification.mode` | No | auto-add | `allow_auto_add_host_key`, `known_hosts`, or `fingerprints`. |
| `connection.host_verification.known_hosts` | Depends | none | List of `known_hosts` lines when `mode = "known_hosts"`. |
| `connection.host_verification.fingerprints` | Depends | none | List of expected host fingerprints when `mode = "fingerprints"`. |
| `connection.fault_tolerant.retries` | No | `0` | Retry attempts per file transfer. |
| `connection.fault_tolerant.retry_interval_sec` | No | `0` | Delay between retries in seconds. |
| `requests` | Yes | none | One or more download or upload specs. |

### Download request fields

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `src_dir` | No | `""` | Remote source subdirectory under `connection.root_dir`. Empty or omitted means `connection.root_dir` itself. |
| `dst_dir` | No | `""` | Local destination subdirectory under `ctx.inbox`. Empty or omitted writes directly under `ctx.inbox`. |
| `include` | No | `["*"]` | Glob pattern or list of patterns to include. Matching is attempted against both the file name and the discovered path relative to the current listing root. |
| `exclude` | No | `[]` | Glob pattern or list of patterns to exclude after include matching. |
| `recursive` | No | `false` | When `true`, walk subdirectories under the effective remote source directory. |
| `updated_after` | No | none | Inclusive lower bound. Use an ISO 8601 datetime with timezone, for example `2026-04-01T00:00:00Z`. |
| `updated_before` | No | none | Exclusive upper bound. Use an ISO 8601 datetime with timezone, for example `2026-04-01T00:00:00Z`. |
| `delete_source_file` | No | `false` | Delete the remote file after successful download and validation. |

### Upload request fields

If an upload request's source directory is missing while the runtime inbox is
valid, the request is logged at INFO and skipped. Empty directories and filters
matching no files also succeed with zero uploads. Other requests continue normally.
Invalid source paths, permission errors, and subsequent listing or transfer errors
still fail. Connection setup is unchanged and may fail even when no files exist.

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `src_dir` | No | `""` | Local source subdirectory under `ctx.inbox`. Empty or omitted means `ctx.inbox` itself. |
| `dst_dir` | No | `""` | Remote destination subdirectory under `connection.root_dir`. Empty or omitted means `connection.root_dir` itself. |
| `include` | No | `["*"]` | Glob pattern or list of patterns applied to file names and paths relative to `src_dir`. |
| `exclude` | No | `[]` | Glob pattern or list of patterns excluded after include matching. |
| `recursive` | No | `false` | When `true`, discover nested local files and preserve their relative hierarchy remotely. |
| `delete_source_file` | No | `false` | Delete the local source only after all selected uploads succeed and pass remote size validation. |

## Path and matching behavior

- Download remote source = `connection.root_dir / requests[].src_dir`.
- Download local destination = `ctx.inbox / requests[].dst_dir`.
- Upload local source = `ctx.inbox / requests[].src_dir`.
- Upload remote destination = `connection.root_dir / requests[].dst_dir`.
- Request paths must remain under their configured inbox or remote root and
  cannot be absolute or contain `..` path segments.
- If the relevant root and request directory are both empty, the handler uses
  `ctx.inbox` locally or the connection's current remote directory.
- Relative paths under the selected source root are preserved at the destination.
- `include` and `exclude` are matched against both the file name and the discovered path relative to the current listing root.
- Prefer `recursive: true` with `include: ["*.csv"]` instead of `include: ["**/*.csv"]`.
- Download time filtering uses a half-open interval: `updated_after <= mtime < updated_before`.
- Use ISO 8601 datetime strings with an explicit timezone offset or `Z`.
- Upload creates missing remote directories, overwrites existing destination
  files, and verifies the remote size after each transfer.
- Multiple local files cannot resolve to the same remote destination.

### Upload example

```json
{
  "handler": "oedis.handler.sftp.upload",
  "params": {
    "connection": {
      "hostname": "sftp.example.com",
      "root_dir": "/drop",
      "auth": {
        "type": "basic",
        "username": "partner_user",
        "password": "{{ keyvault(scope='oedis-kv', key='partner-sftp-password') }}"
      },
      "host_verification": {
        "mode": "fingerprints",
        "fingerprints": ["sha256:EXAMPLEFINGERPRINTBASE64"]
      }
    },
    "requests": [
      {
        "src_dir": "outbound",
        "dst_dir": "partner/inbound",
        "include": ["*.csv"],
        "recursive": true
      }
    ]
  }
}
```

## Authentication

### Basic authentication

Use `basic` when the server authenticates with a username and password.

Required fields:

- `connection.auth.type = "basic"`
- `connection.auth.username`
- `connection.auth.password`

Example:

```json
{
  "connection": {
    "hostname": "sftp.example.com",
    "port": 22,
    "auth": {
      "type": "basic",
      "username": "partner_user",
      "password": "{{ keyvault(scope='oedis-kv', key='partner-sftp-password') }}"
    }
  },
  "requests": [
    {
      "src_dir": "outbound",
      "dst_dir": "partner/outbound",
      "include": ["*.csv"]
    }
  ]
}
```

### Key authentication

Use `key` when the server authenticates with an SSH private key.

Required fields:

- `connection.auth.type = "key"`
- `connection.auth.username`
- `connection.auth.private_key`

Optional fields:

- `connection.auth.private_key_passphrase`
- `connection.auth.password`

`connection.auth.password` is still allowed in key mode because some partner-managed SFTP servers require both:

- an SSH private key for primary authentication
- a user password as an additional login factor

Example with an encrypted private key:

```json
{
  "connection": {
    "hostname": "files.partner.com",
    "port": 22,
    "auth": {
      "type": "key",
      "username": "svc_partner",
      "private_key": "{{ keyvault(scope='oedis-kv', key='partner-sftp-private-key') }}",
      "private_key_passphrase": "{{ keyvault(scope='oedis-kv', key='partner-sftp-private-key-passphrase') }}"
    }
  },
  "requests": [
    {
      "src_dir": "export",
      "dst_dir": "partner/export",
      "include": ["*.txt", "*.csv"],
      "recursive": true
    }
  ]
}
```

Example where the server requires both private key and account password:

```json
{
  "connection": {
    "hostname": "secure.partner.com",
    "port": 22,
    "auth": {
      "type": "key",
      "username": "svc_partner",
      "private_key": "{{ keyvault(scope='oedis-kv', key='partner-sftp-private-key') }}",
      "private_key_passphrase": "{{ keyvault(scope='oedis-kv', key='partner-sftp-private-key-passphrase') }}",
      "password": "{{ keyvault(scope='oedis-kv', key='partner-sftp-password') }}"
    }
  },
  "requests": [
    {
      "src_dir": "drop",
      "include": ["*.dat"]
    }
  ]
}
```

## Private key handling

`connection.auth.private_key` supports either of these secret formats:

- raw PEM text
- base64-encoded PEM text

Base64 is recommended for Key Vault secrets, portal copy/paste, and any config delivery path where multiline text may be normalized or escaped. Raw PEM is still supported when multiline secrets are preserved cleanly end to end.

### Raw PEM secret value

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

### Base64-encoded PEM secret value

```text
LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K...
```

### Password vs passphrase

These two fields are different and should usually be stored as separate Key Vault secrets:

- `connection.auth.password`: the SFTP account password
- `connection.auth.private_key_passphrase`: the passphrase that decrypts the private key file

Example secret naming:

- `partner-sftp-password`
- `partner-sftp-private-key`
- `partner-sftp-private-key-passphrase`

Recommendation:

- prefer base64-encoded PEM for Key Vault and JSON/template configs
- use base64-encoded PEM when your config delivery path does not handle multiline secrets reliably
- use raw PEM when multiline secrets are supported cleanly end to end
- never combine password and passphrase into one secret

## Host verification

### `allow_auto_add_host_key`

This mode automatically trusts and adds the presented host key.

Example:

```json
{
  "connection": {
    "host_verification": {
      "mode": "allow_auto_add_host_key"
    }
  }
}
```

Use this only for local development, short-lived testing, or controlled non-production troubleshooting. Do not use it for production partner integrations.

### `known_hosts`

This mode verifies the remote server against one or more full `known_hosts` lines.

Required fields:

- `connection.host_verification.mode = "known_hosts"`
- `connection.host_verification.known_hosts`

Example:

```json
{
  "connection": {
    "host_verification": {
      "mode": "known_hosts",
      "known_hosts": [
        "sftp.example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB7...",
        "sftp.example.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC..."
      ]
    }
  }
}
```

This is the preferred production option when the partner can provide canonical `known_hosts` entries.

### `fingerprints`

This mode verifies the remote server against one or more expected fingerprints.

Required fields:

- `connection.host_verification.mode = "fingerprints"`
- `connection.host_verification.fingerprints`

Example:

```json
{
  "connection": {
    "host_verification": {
      "mode": "fingerprints",
      "fingerprints": [
        "SHA256:r5WkAnExampleFingerprintBase64",
        "aa:bb:cc:dd:ee:ff:11:22:33:44:55:66:77:88:99:00"
      ]
    }
  }
}
```

Accepted fingerprint styles include:

- `SHA256:...`
- SHA256 base64 without the `SHA256:` prefix
- MD5 with colons
- MD5 without colons
- `md5:...`

Use this mode when the partner provides fingerprints but not complete `known_hosts` lines.

## Azure Key Vault guidance

Store authentication and trust material in Azure Key Vault and inject it with the template helper:

```jinja
{{ keyvault(scope='oedis-kv', key='partner-sftp-private-key') }}
```

### Example Key Vault secret values

Username secret value:

```text
svc_partner
```

Password secret value:

```text
ProdSftpLogin#2026
```

Private key secret value as raw PEM:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

Private key secret value as base64 PEM:

```text
LS0tLS1CRUdJTiBPUEVOU1NIIFBSSVZBVEUgS0VZLS0tLS0K...
```

Private key passphrase secret value:

```text
MyEncryptedKeyPassphrase#2026
```

Known hosts secret value:

```text
sftp.partner.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOjV...
sftp.partner.com ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC7...
```

Fingerprint secret value as newline-delimited text:

```text
SHA256:r5WkAnExampleFingerprintBase64
aa:bb:cc:dd:ee:ff:11:22:33:44:55:66:77:88:99:00
```

## Key Vault-backed task examples

### Example 1: basic auth with fingerprints

```json
{
  "handler": "oedis.handler.sftp.download",
  "connection": {
    "hostname": "{{ keyvault(scope='oedis-kv', key='acme-sftp-hostname') }}",
    "port": 22,
    "auth": {
      "type": "basic",
      "username": "{{ keyvault(scope='oedis-kv', key='acme-sftp-username') }}",
      "password": "{{ keyvault(scope='oedis-kv', key='acme-sftp-password') }}"
    },
    "host_verification": {
      "mode": "fingerprints",
      "fingerprints": [
        "{{ keyvault(scope='oedis-kv', key='acme-sftp-host-fingerprint-sha256') }}"
      ]
    }
  },
  "requests": [
    {
      "src_dir": "outbound",
      "dst_dir": "acme",
      "include": ["*.csv"],
      "recursive": true
    }
  ]
}
```

Use this pattern when the partner gives you a username/password login and one or more SSH host fingerprints.

### Example 2: key auth with encrypted private key and known hosts

```json
{
  "handler": "oedis.handler.sftp.download",
  "connection": {
    "hostname": "{{ keyvault(scope='oedis-kv', key='beta-sftp-hostname') }}",
    "port": 22,
    "auth": {
      "type": "key",
      "username": "{{ keyvault(scope='oedis-kv', key='beta-sftp-username') }}",
      "private_key": "{{ keyvault(scope='oedis-kv', key='beta-sftp-private-key') }}",
      "private_key_passphrase": "{{ keyvault(scope='oedis-kv', key='beta-sftp-private-key-passphrase') }}"
    },
    "host_verification": {
      "mode": "known_hosts",
      "known_hosts": [
        "{{ keyvault(scope='oedis-kv', key='beta-sftp-known-host-ed25519') }}",
        "{{ keyvault(scope='oedis-kv', key='beta-sftp-known-host-rsa') }}"
      ]
    }
  },
  "requests": [
    {
      "src_dir": "export",
      "dst_dir": "beta/export",
      "include": ["*.txt", "*.csv"],
      "recursive": true,
      "updated_after": "2026-04-01T00:00:00Z"
    }
  ]
}
```

Use this pattern when the partner gives you a private key and full host key lines. This is the preferred production configuration.

### Example 3: key auth with both private key and password

```json
{
  "handler": "oedis.handler.sftp.download",
  "connection": {
    "hostname": "{{ keyvault(scope='oedis-kv', key='gamma-sftp-hostname') }}",
    "port": 22,
    "auth": {
      "type": "key",
      "username": "{{ keyvault(scope='oedis-kv', key='gamma-sftp-username') }}",
      "private_key": "{{ keyvault(scope='oedis-kv', key='gamma-sftp-private-key') }}",
      "private_key_passphrase": "{{ keyvault(scope='oedis-kv', key='gamma-sftp-private-key-passphrase') }}",
      "password": "{{ keyvault(scope='oedis-kv', key='gamma-sftp-password') }}"
    },
    "host_verification": {
      "mode": "fingerprints",
      "fingerprints": [
        "{{ keyvault(scope='oedis-kv', key='gamma-sftp-host-fingerprint-sha256') }}"
      ]
    },
    "fault_tolerant": {
      "retries": 2,
      "retry_interval_sec": 10
    }
  },
  "requests": [
    {
      "src_dir": "drop",
      "dst_dir": "gamma/drop",
      "include": ["*.dat"],
      "delete_source_file": false
    }
  ]
}
```

Use this pattern only when the partner explicitly requires both credentials.

### Example 4: non-production auto-add host key

```json
{
  "handler": "oedis.handler.sftp.download",
  "connection": {
    "hostname": "dev-sftp.partner.local",
    "port": 22,
    "auth": {
      "type": "basic",
      "username": "{{ keyvault(scope='oedis-kv', key='dev-sftp-username') }}",
      "password": "{{ keyvault(scope='oedis-kv', key='dev-sftp-password') }}"
    },
    "host_verification": {
      "mode": "allow_auto_add_host_key"
    }
  },
  "requests": [
    {
      "src_dir": "sample",
      "include": ["*.csv"]
    }
  ]
}
```

Use this only in development or controlled short-term validation.

## Production recommendations

For production SFTP integrations:

- do not use `allow_auto_add_host_key`
- prefer `known_hosts`
- use `fingerprints` when full `known_hosts` entries are not available
- store hostname, username, password, private key, private key passphrase, and host verification material in Azure Key Vault
- keep `password` and `private_key_passphrase` as separate secrets
- prefer SHA256 fingerprints over MD5 when both are available
- avoid logging rendered configuration values that contain secrets
- use partner-specific secret names rather than shared generic secret names

Preferred host verification order:

1. `known_hosts`
2. `fingerprints`
3. `allow_auto_add_host_key`

## Outputs

Both handlers return the standardized file-to-file `TaskResult` shape documented
in [`TASK_RESULTS.md`](TASK_RESULTS.md). For upload, `src.path` is the local
inbox file and `dest.path` is the remote SFTP path. A transfer failure raises an
exception instead of returning a partial-success result.

## Related examples

See the shipped examples in:

- `application/databricks/bundles/databridge/examples/sftp_download_basic.json`
- `application/databricks/bundles/databridge/examples/sftp_download_auto_add_host_key.json`
- `application/databricks/bundles/databridge/examples/sftp_download_known_hosts.json`
- `application/databricks/bundles/databridge/examples/sftp_download_fingerprints.json`
- `application/databricks/bundles/databridge/examples/sftp_upload_basic.json`

