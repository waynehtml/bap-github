# Datafile Module Developer Guide

This guide explains how developers register source file locations and read schemas in Dataforge, retrieve those definitions through `DatafileManager`, compose caller-owned paths, and read the files with the shared strict reader.

The Datafile module supports source files used by two common scenarios:

1. Read a raw-zone file for standardized processing in the dataflow workflow.
2. Read an external landing-zone file used for system initialization or reference data.

The module owns the source-file contract. Target-table definitions and downstream processing belong to separate project components.

## Module Responsibilities

The Datafile module owns:

| Concern | Registry field or API |
| --- | --- |
| Logical source identity | Datafile module filename and `DatafileRegistry.ref` |
| Relative source location | `DEFINITION["path"]` |
| Spark source format | `DEFINITION["format"]` |
| Spark reader settings | `DEFINITION["options"]` |
| Source columns and data types | `DEFINITION["schema"]` |
| File path composition | Calling task or utility |

It does not define the standardized table, table creation SQL, business rules, audit policy, or Delta write behavior.

## Key Locations

- [datafile_utils.py](../../src/oeds/domain/utils/datafile/datafile_utils.py): `DatafileRegistry` and `DatafileManager` APIs.
- [file_sample.py](../../conf/oeds/config/datafile/file_sample.py): sample source-file registry entry.
- [datafile_manager.py](../../examples/datafile/datafile_manager.py): executable registry discovery and lookup example.
- [task_30_raw_to_std.py](../../jobs/dataflow/task_30_raw_to_std.py): raw-zone usage example.
- [DataKit file API reference](../reference/datakit/api/file_reader.md): shared strict reader used with resolved registry values.

## Datafile Registry Contract

Create one Python module per logical source-file contract under `conf/oeds/config/datafile`. The module filename becomes the registry reference. For example, `file_sample.py` is discovered as `file_sample`.

Each module exposes a top-level `DEFINITION` dictionary:

```python
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

SOURCE_SCHEMA = StructType(
    [
        StructField("number", IntegerType(), True),
        StructField("category", StringType(), True),
        StructField("country", StringType(), True),
        StructField("amount", IntegerType(), True),
        StructField("minimum_amount", IntegerType(), True),
    ]
)

DEFINITION = {
    "path": "tbl_sample.csv",
    "format": "csv",
    "options": {
        "encoding": "windows-1252",
        "header": "true",
    },
    "schema": SOURCE_SCHEMA,
}
```

| Field | Type | Purpose |
| --- | --- | --- |
| `path` | `str` | Source path or path fragment interpreted and composed by the caller. |
| `format` | `str` | Spark source format, such as `csv`, `json`, `xml`, `parquet`, or `delta`. |
| `options` | `dict` | Format-specific Spark reader options. |
| `schema` | `StructType` | Expected source column names, Spark data types, and declared nullability. |

`DatafileRegistry` permits missing values, but production definitions should explicitly provide all four fields. Explicit contracts make path composition and file reading consistent across workflow tasks and operational notebooks.

### Registry Discovery

After `ConfigManager` is initialized, `DatafileManager.initialize(env)`
discovers the effective module names from `oeds.config.datafile`:

- Shared and active-environment modules are discovered in sorted ref order.
- Active-environment modules override shared modules with the same basename.
- Environment-only and shared-only modules are both retained.
- Filenames beginning with `_` are ignored by `ConfigManager`.
- The module filename is used as the registry ref.
- A missing `DEFINITION` is treated as an empty dictionary.
- A non-dictionary `DEFINITION` raises `ValueError`.
- Duplicate refs cannot occur because each ref is a Python module filename.

Environment overrides replace complete modules; `DEFINITION` dictionaries are
not merged. Definition modules are imported only when `find(ref)` requests them.

Use stable, descriptive filenames because the ref is consumed by task code and may be used in logs or configuration.

## Source Schema

`DatafileRegistry.schema` describes the source file as Spark should read it. It is passed to `load_file_failfast` before the DataFrame is materialized.

The source schema should define:

- The source column names expected in the file.
- The Spark data type used to parse each column.
- The declared nullability of each source field.
- Nested structures when the source format supports them.

Declared nullability does not replace explicit validation of required values. The schema establishes the read contract; project validation still decides whether a null or source value is acceptable for the business process.

Keep the source schema faithful to the external file. For example, if an external CSV contract provides a date as text, the Datafile schema can preserve that agreed source representation. Downstream standardized-table handling is outside the Datafile registry.

### Source Schema Versus Table Schema

The Datafile schema and standardized table schema are separate contracts:

| Datafile source schema | Standardized table schema |
| --- | --- |
| Describes the external file. | Describes a Unity Catalog table. |
| Used by the Spark file reader. | Used to create and govern the table. |
| Stored under `config/datafile`. | Stored under `config/schema`. |
| Can include source-only fields. | Can include table-only audit or generated fields. |

Do not copy a table schema into a Datafile registry unless it genuinely matches the external file contract. See the [Schema Guide](G211-schema-guide.md) for standardized table definitions.

### Schema Change Guidance

Treat a Datafile schema change as a source-contract change:

1. Confirm the external producer changed the file contract.
2. Update the registry schema and reader options together when necessary.
3. Review every caller of the affected Datafile ref.
4. Test representative valid and malformed files.
5. Coordinate downstream changes separately.

Avoid silently broadening types or making fields nullable only to accept an unexpected file. Surface incompatible input at the read boundary unless the source-contract change is intentional.

## `DatafileManager` API

Create a caller-owned `DatafileManager` after `common.py` has configured it for
the active environment:

```python
from oeds.domain.utils.datafile import DatafileManager

datafile_manager = DatafileManager.get_instance()
print(datafile_manager.get_module_map())
```

`common.py` calls `DatafileManager.initialize(env)` after `ConfigManager` and
`SchemaManager`. Initialization discovers the effective module names and stores
one immutable `(environment, ModuleMap)` snapshot without importing definition
modules. Every `get_instance()` call returns a new manager using that snapshot.
`find(name)` imports and validates only the requested definition.

| API | Result | Notes |
| --- | --- | --- |
| `initialize(env)` | `type[DatafileManager]` | Rebuilds the module-map snapshot and supports chaining to `get_instance()`. |
| `get_instance()` | `DatafileManager` | Creates a caller-owned manager; raises before initialization. |
| `get_module_map()` | `dict[str, str]` | Returns a printable copy of discovered refs and full module names. |
| `find(name)` | `DatafileRegistry` | Returns `ref`, `path`, `format`, `options`, and `schema`. |

`find` raises `ValueError` for a blank or unknown ref. The caller must validate
and compose the returned path before reading the file.

### Path Ownership And Parameters

The registry supplies a configured path. The caller owns parameter substitution,
the zone and batch boundary, and construction of the path passed to the reader:

```python
datafile_registry = datafile_manager.find("daily_orders")
configured_path = str(datafile_registry.path).format(file_date=file_date)
source_path = (
    f"{str(raw_root).strip().rstrip('/')}/"
    f"{configured_path.strip().lstrip('/')}"
)
```

For a registry path of `orders/{file_date}/orders.csv`, this produces
`<raw_root>/orders/<file_date>/orders.csv`.

`DatafileManager` does not validate, substitute, or join paths. Callers may use
parameterized or literal registry paths, but must validate every required value.
Do not apply the same date scope in both the caller-owned base URI and registry
path; one layer should own each path segment. Compose a URI compatible with the
Spark reader, such as a Unity Catalog volume path or supported cloud URI.

## Use Case A: Read A Raw-Zone Source

Use `DatafileManager` in the raw-to-standardized task to resolve the source contract for the selected raw batch:

```python
from oeds.core.file_reader import load_file_failfast
from oeds.domain.utils.datafile import DatafileManager

datafile_manager = DatafileManager.get_instance()
datafile_registry = datafile_manager.find("file_sample")
if not datafile_registry.path or not str(datafile_registry.path).strip():
    raise ValueError("Datafile registry 'file_sample' must provide 'path'")
source_path = (
    f"{str(raw_dir).strip().rstrip('/')}/"
    f"{str(datafile_registry.path).strip().lstrip('/')}"
)

source_df = load_file_failfast(
    source_path,
    datafile_registry.format,
    schema=datafile_registry.schema,
    options=datafile_registry.options,
)
```

The registry supplies the relative path and read contract. The task supplies the exact raw batch directory and owns everything after the source DataFrame is returned. See the [Raw To Standardized Flow Guide](G240-raw-to-standardized-flow-guide.md) for the complete workflow.

## Use Case B: Read An External Landing Source

The same Datafile APIs can describe an initialization or reference file retained in the landing zone:

```python
from oeds.core.file_reader import load_file_failfast
from oeds.domain.utils.datafile import DatafileManager

datafile_manager = DatafileManager.get_instance()
datafile_registry = datafile_manager.find("reference_countries")
if not datafile_registry.path or not str(datafile_registry.path).strip():
    raise ValueError("Datafile registry 'reference_countries' must provide 'path'")
source_path = (
    f"{str(landing_dir).strip().rstrip('/')}/"
    f"{str(datafile_registry.path).strip().lstrip('/')}"
)

source_df = load_file_failfast(
    source_path,
    datafile_registry.format,
    schema=datafile_registry.schema,
    options=datafile_registry.options,
)
```

For this scenario, define a stable landing path in the registry and let the
caller decide whether to prepend a landing directory. The Datafile module
provides the source contract, and the shared reader reads the caller-composed
path without moving or deleting the file. Follow the [Landing Zone Best
Practices](../standards-and-practices/landing_zone_best_practices.md) for source
ownership, immutability, and retention.

## Error And Logging Guidance

Let registry discovery, lookup, caller path composition, and strict reader errors fail the calling task. Do not replace a missing registry or incompatible file with partial success.

Log the Datafile ref, resolved source path, and relevant batch identifier around the read boundary. Never log source contents, credentials, access tokens, or sensitive reader options.

## Developer Checklist

- The module filename is a stable, descriptive Datafile ref.
- `path` is relative to the intended caller-owned base URI.
- Path dates or batch folders are owned by exactly one layer.
- `format` matches the actual source format.
- Reader `options` match the external file contract.
- The source `schema` matches the file's columns and data types.
- Source and standardized table schemas remain separate.
- Required source values are validated outside schema declaration.
- Registry and strict reader errors propagate to the calling task.
- Landing and raw source files remain unchanged after reading.

## Related Guides

- [Raw To Standardized Flow Guide](G240-raw-to-standardized-flow-guide.md): consume a registered raw source in the dataflow workflow.
- [Fileloader Developer Guide](G226-fileloader-developer-guide.md): connect a registered source to a target table with normalization, transformation, validation, and write policy.
- [Land To Raw Flow Guide](G230-land-to-raw-flow-guide.md): validate and copy recurring landing batches into raw.
- [Schema Guide](G211-schema-guide.md): define standardized Unity Catalog tables separately from source files.
- [Landing Zone Best Practices](../standards-and-practices/landing_zone_best_practices.md): retain and govern landing sources.
