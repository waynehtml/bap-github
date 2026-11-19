# mssql

Handler:

- `oedis.handler.mssql.download`

The MSSQL download handler connects directly to Microsoft SQL Server, Azure SQL
Database, Azure SQL Managed Instance, or a SQL database in Microsoft Fabric
with `mssql-python`. It runs read-only queries and writes exactly one local CSV
or Parquet file per request under `runtime.inbox` using pandas.

## Connection

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `connection.host` | Yes | - | SQL Server hostname or IP address. |
| `connection.port` | No | `1433` | SQL Server TCP port. |
| `connection.database` | Yes | - | Database used by every request in the task. |
| `connection.auth.type` | Yes | - | `sql_password` or `service_principal`. |

DataBridge resolves the complete configuration template before invoking the handler.
Supply credential fields through `keyvault(...)`; the handler receives the
resolved values and does not perform a second secret lookup.

### SQL password authentication

Use `sql_password` with a SQL Server login:

```json
{
  "connection": {
    "host": "sql.data.example.com",
    "port": 1433,
    "database": "Finance",
    "auth": {
      "type": "sql_password",
      "username": "{{ keyvault(scope='dis-secrets', key='mssql-username') }}",
      "password": "{{ keyvault(scope='dis-secrets', key='mssql-password') }}"
    }
  }
}
```

The resolved username and password are passed to `mssql_python.connect()` as
`uid` and `pwd` keyword arguments.

### Service-principal authentication

Use `service_principal` for a Microsoft Entra application identity:

```json
{
  "connection": {
    "host": "example.database.windows.net",
    "port": 1433,
    "database": "Operations",
    "auth": {
      "type": "service_principal",
      "client_id": "{{ keyvault(scope='dis-secrets', key='mssql-client-id') }}",
      "client_secret": "{{ keyvault(scope='dis-secrets', key='mssql-client-secret') }}"
    }
  }
}
```

The handler passes the client ID as `uid`, the client secret as `pwd`, and
`authentication="ActiveDirectoryServicePrincipal"` to `mssql_python.connect()`.
The service principal must already exist as a database user with permission to
execute the configured queries.

## Requests

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `id` | Yes | - | Unique request identifier and default file name. |
| `select_sql` or `table` | Yes | - | `table` generates `SELECT * FROM <table>` and takes precedence when both are supplied. |
| `parameters` | No | - | Named values for `%(name)s` placeholders in `select_sql`. |
| `format` | No | `parquet` | Supported values are `csv` and `parquet`. |
| `file` | No | `<id>.<format>` | Relative output path under `runtime.inbox`. |
| `write.options` | No | `{}` | Options forwarded to the selected pandas writer, except reserved path and layout controls. |

`select_sql` must start with `SELECT` or `WITH`. A single trailing semicolon is
removed. Parameters are not accepted when `table` is used. The handler passes
parameter values directly to `mssql-python`; it never interpolates them into
SQL.

For example:

```json
{
  "id": "daily_rates",
  "select_sql": "SELECT business_date, rate FROM dbo.daily_rates WHERE business_date = %(business_date)s",
  "parameters": {
    "business_date": "{{ runtime.rundate }}"
  },
  "format": "csv",
  "file": "exports/daily_rates.csv"
}
```

The handler rejects duplicate request IDs, duplicate destination files,
external or escaping paths, unsupported formats, and attempts to override
writer path, index, engine, filesystem, storage, or Parquet partition settings.
As with the Oracle download handler, a leading `/` in `file` is treated as
inbox-rooted shorthand.

## Output formats

CSV output uses:

```python
dataframe.to_csv(destination, index=False, **write_options)
```

Use pandas option names such as `sep`, `encoding`, `na_rep`, and `date_format`.

Parquet output uses:

```python
dataframe.to_parquet(
    destination,
    engine="pyarrow",
    index=False,
    **write_options,
)
```

Use pandas/PyArrow options such as `compression`, `row_group_size`, and
`use_dictionary`. Partitioned output is not supported because each request must
produce one regular file.

## Result shape

Each request adds one item to `TaskResult.outputs`:

```json
{
  "src": {
    "type": "table",
    "path": "dbo.customers",
    "size": 123
  },
  "dest": {
    "type": "file",
    "path": "/tmp/oedis/stage/run-id/exports/customers.parquet",
    "size": 123
  },
  "duration_sec": 0.456789
}
```

For `select_sql` requests, `src.path` is `select_sql:<id>`. Source and
destination sizes are row counts, matching the Oracle and database download
handlers.

## Runtime requirements and limits

- `ctx.inbox` must be set; `ctx.inbox_vol` is not used.
- The Python environment must install `mssql-python`, `pandas`, and `pyarrow`
  from `cluster/requirements.txt`.
- One connection is reused for every request in a task, and each request uses a
  separate cursor.
- The complete query result is materialized in driver memory before pandas
  writes the file. Size queries for the available driver memory.
- TLS and certificate validation use `mssql-python` defaults. This handler does
  not add certificate-bypass settings.
- The local inbox is removed after successful non-debug runs. A later task must
  persist output that needs to survive the pipeline.

See the Microsoft documentation for
[`mssql-python` connection strings](https://learn.microsoft.com/sql/connect/python/mssql-python/connection-strings)
and
[parameterized queries](https://learn.microsoft.com/sql/connect/python/mssql-python/parameterized-queries).
