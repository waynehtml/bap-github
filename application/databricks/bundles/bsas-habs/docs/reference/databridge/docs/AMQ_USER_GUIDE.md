# AMQ user guide

This guide documents the AMQP 1.0 handlers implemented with Apache Qpid Proton:

- `oedis.handler.amq.send`
- `oedis.handler.amq.receive`

The current implementation is intentionally narrow:

- AMQP 1.0 over TLS only
- `connection.uri` as a non-empty array of `amqps://` URIs only
- mutual TLS client certificate authentication only
- `requests` array processed sequentially
- configuration is validated by JSON schema and by handler runtime checks

## Runtime dependency

The Databricks cluster bootstrap installs `python-qpid-proton` from
`cluster/requirements.txt` through `cluster/init.sh`.

## Connection config

Both handlers use the same `connection` shape:

```json
{
  "connection": {
    "uri": [
      "amqps://broker-1.example.com:443",
      "amqps://broker-2.example.com:443"
    ],
    "timeout_sec": 60,
    "auth": {
      "type": "client_certificate",
      "certificate": "{{ keyvault(scope='dis-secrets', key='amq_client_certificate') }}",
      "private_key": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key') }}",
      "private_key_passphrase": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key_passphrase') }}",
      "ca_certificate": "{{ keyvault(scope='dis-secrets', key='amq_ca_certificate') }}"
    },
    "fault_tolerant": {
      "retries": 3,
      "retry_interval_sec": 30
    }
  }
}
```

Field notes:

- `uri`: ordered AMQP broker endpoint array. Each item must use `amqps://` and include a hostname. Port is part of each URI, for example `:443`.
- `timeout_sec`: connection and blocking operation timeout passed to Qpid Proton.
- `auth.certificate`, `auth.private_key`, `auth.ca_certificate`: raw PEM text and base64-encoded PEM text are accepted. Base64-encoded PEM is recommended for Key Vault and JSON/template configs because it avoids multiline newline and escaping issues.
- `auth.ca_certificate`: optional CA bundle used by the client to verify the broker/server certificate. When omitted, broker/server certificate verification is disabled.
- `fault_tolerant`: applies to opening each AMQP connection URI. The handler exhausts retries for the first URI before trying the next URI. It does not retry an already-started send or a partially-processed receive batch.

## TLS material secret format

AMQ client certificate fields support either raw PEM text or base64-encoded PEM text:

- `auth.certificate`
- `auth.private_key`
- `auth.ca_certificate`

Base64 is recommended for Key Vault secrets, portal copy/paste, and JSON/template configs. It keeps certificate and key material as single-line secret values, which avoids invalid JSON control characters and accidental newline stripping.

Raw PEM remains supported when multiline text is preserved cleanly end to end.

## Send handler

Handler path:

```json
"handler": "oedis.handler.amq.send"
```

Task params:

```json
{
  "connection": {
    "uri": [
      "amqps://broker-1.example.com:443",
      "amqps://broker-2.example.com:443"
    ],
    "timeout_sec": 60,
    "auth": {
      "type": "client_certificate",
      "certificate": "{{ keyvault(scope='dis-secrets', key='amq_client_certificate') }}",
      "private_key": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key') }}",
      "private_key_passphrase": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key_passphrase') }}",
      "ca_certificate": "{{ keyvault(scope='dis-secrets', key='amq_ca_certificate') }}"
    },
    "fault_tolerant": {
      "retries": 3,
      "retry_interval_sec": 30
    }
  },
  "requests": [
    {
      "queue": "ORDERS.OUT",
      "body": "business_date={{ runtime.rundate }}",
      "properties": {
        "message_type": "order",
        "business_date": "{{ runtime.rundate }}"
      }
    }
  ]
}
```

Send behavior:

- Requests are processed sequentially under the first successfully opened AMQP connection.
- `requests[*].queue` is used as the AMQP target address.
- A request uses exactly one source mode:
  - inline mode with `body`
  - file selector mode with `src_dir`, `include`, `exclude`, and `recursive`
- `requests[*].body`, when provided, must be a string and is sent as a UTF-8 message body.
- File selector mode reads files from `ctx.inbox` and sends one AMQP message per matched file.
- `src_dir` is relative to `ctx.inbox`. Empty or omitted `src_dir` reads directly from `ctx.inbox`.
- `include` defaults to `*`, `exclude` defaults to no exclusions, and `recursive` defaults to `false`.
- `requests[*].properties` is optional and must be an object when provided.
- `requests[*].properties` is sent as AMQP application properties on every message produced by the request.
- Successful output records one transfer in `TaskResult.outputs` for each sent message:
  - inline sends use `message -> queue`
  - file sends use `file -> queue`

File selector example:

```json
{
  "connection": {
    "uri": [
      "amqps://broker-1.example.com:443",
      "amqps://broker-2.example.com:443"
    ],
    "timeout_sec": 60,
    "auth": {
      "type": "client_certificate",
      "certificate": "{{ keyvault(scope='dis-secrets', key='amq_client_certificate') }}",
      "private_key": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key') }}",
      "private_key_passphrase": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key_passphrase') }}",
      "ca_certificate": "{{ keyvault(scope='dis-secrets', key='amq_ca_certificate') }}"
    }
  },
  "requests": [
    {
      "queue": "ORDERS.OUT",
      "src_dir": "outbound/orders",
      "include": "*.json",
      "exclude": "*.tmp",
      "recursive": false,
      "properties": {
        "message_type": "order",
        "business_date": "{{ runtime.rundate }}"
      }
    }
  ]
}
```

## Receive handler

Handler path:

```json
"handler": "oedis.handler.amq.receive"
```

Task params:

```json
{
  "connection": {
    "uri": [
      "amqps://broker-1.example.com:443",
      "amqps://broker-2.example.com:443"
    ],
    "timeout_sec": 60,
    "auth": {
      "type": "client_certificate",
      "certificate": "{{ keyvault(scope='dis-secrets', key='amq_client_certificate') }}",
      "private_key": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key') }}",
      "private_key_passphrase": "{{ keyvault(scope='dis-secrets', key='amq_client_private_key_passphrase') }}",
      "ca_certificate": "{{ keyvault(scope='dis-secrets', key='amq_ca_certificate') }}"
    },
    "fault_tolerant": {
      "retries": 3,
      "retry_interval_sec": 30
    }
  },
  "requests": [
    {
      "queue": "ORDERS.IN",
      "max_messages": 10,
      "wait_timeout_sec": 30,
      "dst_dir": "raw",
      "file_name": "orders_in_{{ runtime.job_run_id }}.dat"
    }
  ]
}
```

Receive behavior:

- Requests are processed sequentially under the first successfully opened AMQP connection.
- `requests[*].queue` is used as the AMQP source address.
- `requests[*].max_messages` controls the maximum number of messages read for that request item.
- `requests[*].wait_timeout_sec` is treated as a total wait budget for that request item, not a per-message wait budget.
- When no messages arrive before the timeout expires, the request item finishes successfully with zero outputs.
- A received message is accepted only after its payload has been written successfully.
- If processing the current message fails, the handler attempts to release that message before raising the error.

## Receive file output

The receive handler writes payloads under `ctx.inbox`.

- `requests[*].dst_dir` is resolved relative to `ctx.inbox`. Empty or omitted `dst_dir` writes directly into `ctx.inbox`.
- `requests[*].file_name` is required and must be a file name only, not a path.
- `requests[*].file_name` supports task-level `<< ... >>` templates resolved for each received message. The context contains `runtime`, prior `task_results`, and `metadata`.
- `metadata` contains the standard AMQP message attributes plus all application properties from `message.properties`. For example, a custom `payload_type` property is available as `<< metadata.payload_type >>`. A custom property takes precedence when it has the same name as a standard attribute.
- When `max_messages` is `1`, `requests[*].file_name` is used exactly as provided under `dst_dir`.
- When `max_messages` is greater than `1`, the handler appends a 4-digit sequence before the file extension.
- Numbering restarts for each request item.

Examples:

- `dst_dir=raw`, `file_name=orders_in_{{ runtime.job_run_id }}.dat` -> `raw/orders_in_<job_run_id>_0001.dat`
- `dst_dir=raw`, `file_name=orders_in_{{ runtime.job_run_id }}.dat` -> `raw/orders_in_<job_run_id>_0002.dat`
- `dst_dir=raw`, `file_name=orders_{{ runtime.job_run_id }}.json` -> `raw/orders_<job_run_id>_0001.json`

## Receive payload serialization

The handler preserves binary payloads when Proton returns `bytes`, `bytearray`, or `memoryview`.

For non-binary AMQP bodies:

- `str` values are written as UTF-8 bytes
- `dict`, `list`, `tuple`, `int`, `float`, and `bool` values are JSON-serialized to UTF-8 bytes
- `null`/`None` is written as an empty file

This keeps the receive side usable for both text-like and binary payloads without adding an `encoding` option yet.

## Sample configs

See the example task configs:

- `examples/amq_send_basic.json`
- `examples/amq_send_files.json`
- `examples/amq_receive_basic.json`
