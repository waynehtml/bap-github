# oracle

Handler:

- `oedis.handler.oracle.download`

The Oracle download handler connects directly to Oracle Database with
`python-oracledb` in Thin mode. It runs read-only queries and writes exactly
one local CSV or Parquet file per request under `runtime.inbox` using pandas.

It does not use Spark, JDBC, ODBC, Oracle Instant Client, Oracle Client
libraries, native Linux packages, or Oracle-specific init scripts.

## Connection

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `connection.host` | Yes | - | Oracle listener hostname or IP address. |
| `connection.port` | No | `1521` | Oracle listener TCP port. |
| `connection.service_name` | Yes | - | Oracle database service name. |
| `connection.auth.username` | Yes | - | Oracle database username. |
| `connection.auth.password` | Yes | - | Oracle password; use a secret template instead of literal text. |

The handler explicitly enables Thin mode before creating one connection for
all requests in the task. If the Python process was already switched to Thick
mode, the task fails instead of loading Oracle Client libraries.

## Requests

| Field | Required | Default | Notes |
| --- | --- | --- | --- |
| `id` | Yes | - | Unique request identifier and default file name. |
| `select_sql` or `table` | Yes | - | `table` generates `SELECT * FROM <table>` and takes precedence when both are supplied. |
| `parameters` | No | - | Named bind values for `select_sql`; values are never interpolated into SQL. |
| `format` | No | `parquet` | Supported values are `csv` and `parquet`. |
| `file` | No | `<id>.<format>` | Relative output path under `runtime.inbox`. |
| `write.options` | No | `{}` | Options forwarded to the selected pandas writer, except reserved path and layout controls. |

`select_sql` must start with `SELECT` or `WITH`. A single trailing semicolon is
removed. Parameters are not accepted when `table` is used.

The handler rejects duplicate request IDs, duplicate destination files,
external or escaping paths, and attempts to override writer path, index,
engine, filesystem, storage, or Parquet partition settings. As with the other
download handlers, a leading `/` is treated as inbox-rooted shorthand.

## CSV output

CSV files are written with:

```python
dataframe.to_csv(destination, index=False, **write_options)
```

`write.options` uses pandas option names and native JSON value types. These are
case-sensitive and differ from the Spark options used by
`oedis.handler.database.download`; for example, use `sep` instead of
`delimiter` and `na_rep` instead of `nullValue`. Use JSON booleans such as
`true`, not quoted strings such as `"true"`.

Common CSV options:

| Option | Value type | Default | Purpose |
| --- | --- | --- | --- |
| `sep` | string | `","` | Field delimiter, normally one character such as `","` or `"\t"`. |
| `header` | boolean or array of strings | `true` | Writes column names, suppresses them with `false`, or replaces them with the supplied names. |
| `encoding` | string or `null` | `null` | Output text encoding, commonly `"utf-8"`. |
| `na_rep` | string | `""` | Text written for missing values. |
| `float_format` | string or `null` | `null` | Formatting pattern for floating-point values, such as `"%.4f"`. |
| `date_format` | string or `null` | `null` | `strftime` pattern for date values, such as `"%Y-%m-%d"`. |
| `quotechar` | one-character string | `"\""` | Character used to quote fields. |
| `lineterminator` | string or `null` | platform default | Row terminator, commonly `"\n"`. |

See the [pandas `DataFrame.to_csv` documentation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html)
for the complete option list.

## Parquet output

Parquet files are written with:

```python
dataframe.to_parquet(
    destination,
    engine="pyarrow",
    index=False,
    **write_options,
)
```

Common Parquet options:

| Option | Value type | Default | Purpose |
| --- | --- | --- | --- |
| `compression` | string or `null` | `"snappy"` | Compression codec. Common values are `"snappy"`, `"gzip"`, `"brotli"`, `"lz4"`, and `"zstd"`; use `null` for no compression. |
| `compression_level` | integer or `null` | codec default | Compression level passed to PyArrow when the selected codec supports it. |
| `row_group_size` | integer or `null` | PyArrow default | Maximum number of rows written in each row group. |
| `use_dictionary` | boolean or array of strings | `true` | Enables dictionary encoding globally or for selected columns. |
| `write_statistics` | boolean or array of strings | `true` | Writes Parquet column statistics globally or for selected columns. |
| `coerce_timestamps` | string or `null` | `null` | Coerces timestamps to a resolution such as `"ms"` or `"us"`. |
| `allow_truncated_timestamps` | boolean | `false` | Allows precision loss caused by timestamp coercion. |

Additional Parquet options are forwarded by pandas to PyArrow and can depend on
the installed PyArrow version. See the
[pandas `DataFrame.to_parquet` documentation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_parquet.html)
and [PyArrow `parquet.write_table` documentation](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.write_table.html).

Partitioned output is intentionally unsupported so each request always
produces one regular file. The handler also reserves `path`, `engine`,
`filesystem`, `index`, `partition_cols`, and `storage_options`.

## Example

```json
{
  "connection": {
    "host": "oracle.data.example.com",
    "port": 1521,
    "service_name": "FINPDB",
    "auth": {
      "username": "svc_reader",
      "password": "{{keyvault(scope=dis-secrets, key=oracle-password)}}"
    }
  },
  "requests": [
    {
      "id": "daily_rates",
      "select_sql": "SELECT business_date, rate FROM daily_rates WHERE business_date = :business_date",
      "parameters": {
        "business_date": "{{ runtime.rundate }}"
      },
      "format": "csv",
      "file": "exports/daily_rates.csv"
    },
    {
      "id": "customers",
      "table": "CUSTOMER_OWNER.CUSTOMERS",
      "format": "parquet",
      "file": "exports/customers.parquet"
    }
  ]
}
```

## Result shape

Each request adds one item to `TaskResult.outputs`:

```json
{
  "src": {
    "type": "table",
    "path": "CUSTOMER_OWNER.CUSTOMERS",
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

For `select_sql` requests, `src.path` is `select_sql:<id>`. Sizes represent row
counts, matching the database download handler.

## Runtime requirements and limits

- `ctx.inbox` must be set; `ctx.inbox_vol` is not used.
- The Python environment must install `oracledb>=3.4.0`, `pandas`, and
  `pyarrow` from `cluster/requirements.txt`.
- Thin mode supports Oracle Database 12.1 or later.
- The complete query result is materialized in driver memory before pandas
  writes the file. Queries must be sized for available driver memory.
- The local inbox is removed after successful non-debug runs. A later task must
  persist any output that needs to survive the pipeline.
- This version supports direct TCP username/password authentication. TCPS,
  wallets, Native Network Encryption, and external authentication are not
  configured by this handler.
