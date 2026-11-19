# Databricks Unity Catalog Standards

## Purpose

This standard defines consistent requirements for naming, documenting, and implementing tables, views, and materialized views in Databricks Unity Catalog.

The objectives are to:

- make objects consistent, predictable, and easy to understand;
- improve governance, maintainability, and data discoverability;
- support deterministic code generation by AI coding agents; and
- prevent environment-specific, temporary, or ambiguous implementations from becoming production standards.

## Scope

This standard applies to production:

- databases, also known as schemas, within Unity Catalogs;
- tables;
- views; and
- materialized views.

Catalog naming conventions are outside the scope of this document.

---

## 1. Database Organization

Databricks SQL uses database and schema interchangeably in Unity Catalog. This standard uses database for containers inside a catalog that are named with the `_db` suffix.

Each Unity catalog must include the core databases below. Core databases provide a consistent data lifecycle across catalogs.

### 1.1 Core Databases

| Database | Purpose |
|---|---|
| `standardized_db` | Structures, types, and formats raw source data for easier consumption. |
| `curated_db` | Supports enhancement of data from different sources, including conceptual adjustments, controlled cleansing, master-data enrichment, and source joins. |
| `derived_db` | Contains highly processed, aggregated, or summarized data for summary statistics, downstream model inputs, dashboards, and reusable analytical outputs. |
| `reference_db` | Supports fact data with metadata, master data models, and use-case enablement data. |

### 1.2 Catalog-Specific Databases

Catalog-specific databases are optional and should be created only when a catalog has a documented business use case or workflow that requires them.

| Database | Purpose |
|---|---|
| `view_db` | Contains presentation-layer snapshots of data intended for consumption. |
| `raw_db` | Contains original, unchanged table-formatted data from internal or external sources. File-based source data must remain in the storage account instead of being added to this database. |
| `intermediate_db` | Contains raw data staged before standardization. |
| `validation_db` | Supports domain-specific data-quality reporting, dashboards, and validation workflows for support teams. |

---

## 2. Object Naming Convention

### 2.1 General Naming Rules

All object names must:

1. Use lowercase letters.
2. Use `snake_case`.
3. Use clear and recognizable business terminology.
4. Use only organization-approved abbreviations.
5. Use only underscores (`_`) as word separators.
6. Avoid Databricks SQL reserved keywords.
7. Exclude environment names or indicators.
8. Exclude temporary, sequencing, backup, or version suffixes.

#### 2.1.1 Prohibited Environment Indicators

Environment indicators must not appear in object names, including:

```text
dev
test
qa
uat
stage
staging
prod
production
```

Environment separation must be managed through catalogs, schemas, workspaces, or deployment configuration.

#### 2.1.2 Prohibited Temporary and Version Suffixes

Do not use suffixes such as:

```text
_new
_old
_final
_temp
_tmp
_backup
_copy
_v2
_v3
_latest
```

Object changes must be managed through the approved deployment and migration process.

#### 2.1.3 Abbreviations

Use an abbreviation only when it is included in the organization-approved abbreviation list. Use the full business term when an abbreviation is not approved or could be ambiguous.

```text
# Preferred
sales_order
customer_address

# Avoid unless approved
sls_ord
cust_addr
```

### 2.2 Table Naming Standard

Table names must use the following pattern:

```text
tbl_<business_name>
```

Compliant examples:

```text
tbl_customer
tbl_sales_order
tbl_sales_order_line
tbl_customer_snapshot
```

| Noncompliant name | Reason |
|---|---|
| `customer` | Missing the `tbl_` prefix. |
| `Tbl_Customer` | Contains uppercase letters. |
| `tbl_sales order` | Contains a space. |
| `tbl_customer_prod` | Contains an environment indicator. |
| `tbl_customer_final` | Contains a prohibited temporary suffix. |
| `tbl_customer_v2` | Contains a prohibited version suffix. |

### 2.3 View Naming Standard

View names must use lowercase `snake_case`. The following prefixes are preferred
but are not required:

| View type | Preferred prefix | Preferred naming pattern |
|---|---|---|
| Standard view | `vw_` | `vw_<business_name>` |
| User-facing view | `vwu_` | `vwu_<business_name>` |

Prefer `vwu_` for views intended for direct user or consumer access. Prefer
`vw_` for views that support internal transformation, integration, or
controlled downstream use. Other prefixes and names without a prefix are
allowed. Do not reject or rename an otherwise compliant view only because it
does not use a preferred prefix.

Preferred examples:

```text
vw_customer
vw_sales_summary
vw_restricted_customer
vwu_customer_profile
vwu_sales_dashboard
```

Allowed nonpreferred examples:

```text
customer_view
view_customer
reporting_customer
customer_summary
```

| Noncompliant name | Reason |
|---|---|
| `vw_Customer` | Contains an uppercase letter. |
| `CustomerSummary` | Contains uppercase letters. |
| `vw_customer_test` | Contains an environment indicator. |
| `customer_prod` | Contains an environment indicator. |
| `vwu_sales_summary_new` | Contains a prohibited temporary suffix. |
| `customer_v2` | Contains a prohibited version suffix. |

### 2.4 Materialized View Naming Standard

Materialized view names must use lowercase `snake_case`. The following prefixes
are preferred but are not required:

| Materialized view type | Preferred prefix | Preferred naming pattern |
|---|---|---|
| Standard materialized view | `mv_` | `mv_<business_name>` |
| User-facing materialized view | `mvu_` | `mvu_<business_name>` |

Prefer `mvu_` for materialized views intended for direct user or consumer
access. Prefer `mv_` for materialized views that support internal
transformation, integration, or controlled downstream use. Other prefixes and
names without a prefix are allowed. Do not reject or rename an otherwise
compliant materialized view only because it lacks a preferred prefix.

Preferred examples:

```text
mv_daily_sales
mv_customer_balance
mvu_daily_sales_dashboard
```

Allowed nonpreferred examples:

```text
daily_sales_materialized
materialized_daily_sales
aggregate_daily_sales
daily_sales
```

| Noncompliant name | Reason |
|---|---|
| `mv_DailySales` | Contains uppercase letters. |
| `DailySales` | Contains uppercase letters. |
| `daily_sales_prod` | Contains an environment indicator. |
| `materialized_daily_sales_test` | Contains an environment indicator. |
| `daily_sales_new` | Contains a prohibited temporary suffix. |
| `daily_sales_v2` | Contains a prohibited version suffix. |

### 2.5 Object Type Prefix Summary

| Object type | Prefix rule | Prefix |
|---|---|---|
| Table | Required | `tbl_` |
| View | Preferred | `vw_` |
| User-facing view | Preferred | `vwu_` |
| Materialized view | Preferred | `mv_` |
| User-facing materialized view | Preferred | `mvu_` |

---

## 3. Table Standards

### 3.1 Table-Level Standards

These standards apply to production tables managed in Databricks Unity Catalog.

#### 3.1.1 Table Tag Standard

Production tables must use applicable organization-approved governed tags.

Rules:

- Tag keys must use `snake_case`.
- Tag values must use approved controlled values.
- Required tags must be populated before production deployment.
- Conditional tags must be populated when applicable.
- Do not store secrets, personal data, or free-form documentation in tag values.
- Update tags when ownership, classification, source, lifecycle, or product association changes.

| Tag | Requirement | Example values |
|---|---|---|
| `domain` | Required | `finance`, `payments`, `markets` |
| `source` | Required | `oracle`, `sap`, `rtr` |
| `classification` | Required | `public`, `internal`, `confidential`, `restricted` |
| `lifecycle` | Required | `active`, `deprecated`, `retired` |
| `product` | Conditional | `corra`, `paycan` |

#### 3.1.2 Table Comment Standard

Every production table must include a human-readable comment.

The comment must describe, where applicable:

- business purpose;
- table grain;
- primary source;
- included or excluded records;
- important business rules; and
- refresh frequency.

Use one concise paragraph. Do not use generic or implementation-only descriptions.

```sql
COMMENT 'Contains one row per customer account, including active and inactive accounts received from the CRM source system.'
```

Avoid:

```text
Customer table
Sales data
Table created by pipeline
```

#### 3.1.3 Common Delta Table Properties

Recommended standard: rely on Databricks defaults unless a documented workload, compatibility, retention, or governance requirement justifies an override. Delta properties use the `delta.` prefix. Property changes should be made when no concurrent writes are running because metadata updates can conflict with writers.

Table properties should use Databricks defaults unless a documented exception is required. Explicit overrides must identify the business or technical reason, compatibility impact, owner, and review date. Protocol, checkpoint, and internal feature properties must not be configured manually.

| Property | Function | Recommended setting |
|---|---|---|
| `delta.autoOptimize.optimizeWrite` | Reduces small files by optimizing file layout during writes. | Leave unset and use platform defaults. Set `true` only when testing shows a benefit for workloads not already covered by automatic optimized writes. |
| `delta.autoOptimize.autoCompact` | Combines small files after writes. | Leave unset. When explicitly configured, use `auto`; do not use `legacy`. |
| `delta.targetFileSize` | Specifies a preferred output-file size for optimization operations. | Leave unset so Databricks can autotune. Override only for a measured workload requirement. |
| `delta.dataSkippingStatsColumns` | Identifies columns for file-level statistics and data skipping. | Leave unset for Unity Catalog managed tables using predictive optimization. For external or unmanaged wide tables, list frequently filtered columns explicitly. Prefer this over `delta.dataSkippingNumIndexedCols`. |
| `delta.dataSkippingNumIndexedCols` | Collects statistics for the first specified number of columns. Default is 32. | Do not normally set. Use `delta.dataSkippingStatsColumns` when explicit control is required. |
| `delta.deletedFileRetentionDuration` | Controls how long logically deleted data files remain available before physical deletion. | Keep the default interval 1 week or longer. Increase for long-running jobs, extended time travel, or regulatory requirements. |
| `delta.logRetentionDuration` | Controls how long transaction-log history is retained. | Keep the default interval 30 days unless longer history is required. Extend file retention consistently when extending usable time travel. |
| `delta.enableDeletionVectors` | Accelerates `DELETE`, `UPDATE`, and `MERGE` by recording row changes without immediately rewriting entire files. | Enable or retain the workspace default for Databricks-native workloads. Disable only when older runtimes or external clients are incompatible. |
| `delta.appendOnly` | Prevents updates and deletes. | Keep `false` by default. Set `true` only for genuinely immutable event, audit, or landing tables. |
| `delta.enableChangeDataFeed` | Materializes row-level changes for incremental downstream processing. | Keep `false` unless a downstream CDC requirement exists. On supported Databricks Runtime 18 workloads, evaluate automatic change data feed instead of enabling legacy CDF. |
| `delta.enableRowTracking` | Adds stable hidden row IDs and row commit versions. | Keep `false` unless required for row lineage, automatic change data feed, or incremental materialized-view processing. Confirm client compatibility before enabling. |
| `delta.enableTypeWidening` | Allows supported column types to evolve to wider types. | Keep `false` unless controlled schema evolution explicitly permits type widening. |
| `delta.columnMapping.mode` | Allows logical column names to differ from physical Parquet column names, supporting metadata-only renames and drops. | Keep the default `none`. Enable only when column rename/drop requirements justify the protocol and client-compatibility impact. |
| `delta.isolationLevel` | Controls transaction isolation and conflict handling. | Keep the default `WriteSerializable`. Use `Serializable` only when strict transaction ordering is required and the additional conflicts are acceptable. |
| `delta.parquet.compression.codec` | Controls compression for newly written Parquet files. | Keep the current default `ZSTD` unless an integration requires another codec. Existing files are not automatically recompressed. |
| `delta.minReaderVersion` / `delta.minWriterVersion` | Control the minimum Delta protocol versions required by clients. | Never configure manually. Allow Databricks table features to manage protocol upgrades. |

#### 3.1.4 Clustering, Partitioning, and ZORDER Standard

This standard defines the approved use of liquid clustering, partitioning, and `ZORDER` for Databricks Delta tables.

##### 3.1.4.1 Differences

| Technique | How it organizes data | Best suited for | Main limitations |
|---|---|---|---|
| Liquid clustering | Incrementally groups related rows into files using clustering keys. Keys can change without redefining fixed partition boundaries. | New tables, changing access patterns, skewed data, and high- or low-cardinality filter columns. | Requires `OPTIMIZE` or predictive optimization. Cannot be combined with partitioning or `ZORDER`. |
| Partitioning | Stores rows in fixed physical partitions based on partition-column values. | Exceptional workloads with very large tables and stable, low-cardinality partition columns. | Static, vulnerable to skew and small files, and expensive to change. |
| `ZORDER` | Rewrites files to colocate values from selected columns for more effective data skipping. | Existing non-liquid-clustered Delta tables with frequent filters on high-cardinality columns. | Must be rerun as data arrives, depends on statistics, and cannot be used with liquid clustering. |

##### 3.1.4.2 Automatic Liquid Clustering

Use automatic liquid clustering for new Unity Catalog managed tables.

```sql
CREATE TABLE tbl_sales_order (
    sales_order_id BIGINT,
    customer_id BIGINT,
    business_date DATE,
    net_amount DECIMAL(18,2)
)
CLUSTER BY AUTO;
```

Rules:

- Use `CLUSTER BY AUTO` by default.
- Allow Databricks to select and evolve clustering keys.
- Do not require clustering keys when the table is too small or no benefit is expected.

##### 3.1.4.3 Explicit Liquid-Clustering Keys

Use explicit clustering keys only when a stable and validated access pattern is known.

```sql
CLUSTER BY (business_date, customer_id)
```

Rules:

- Select columns frequently used in selective filters, joins, or range predicates.
- Do not select a column only because it is a date or primary key.
- Keep the number of clustering columns small.
- Prefer automatic clustering when predictive optimization is available.

##### 3.1.4.4 Partitioning

Do not add `PARTITIONED BY` automatically.

Partitioning may be used only when:

- A demonstrated workload performs better with fixed partitions.
- The partition column has stable, low cardinality.
- Individual partitions are sufficiently large.
- A legacy or external integration requires partition paths.
- Testing demonstrates an advantage over liquid clustering.

```sql
PARTITIONED BY (business_date)
```

Do not partition by high-cardinality columns such as:

```text
customer_id
transaction_id
event_timestamp
```

##### 3.1.4.5 ZORDER

Use `ZORDER` only for existing Delta tables that do not use liquid clustering and cannot yet be migrated.

```sql
OPTIMIZE tbl_sales_order
ZORDER BY (customer_id);
```

Rules:

- Select columns frequently used in selective filters.
- Ensure file-level statistics are collected for the selected columns.
- Keep the number of Z-order columns small.
- Do not use a partition column as a Z-order column.

##### 3.1.4.6 Compatibility Rules

- Do not combine `CLUSTER BY` with `PARTITIONED BY`.
- Do not run `ZORDER` on a liquid-clustered table.
- Partitioning and `ZORDER` may coexist only on approved legacy tables.
- Do not use the same column for both partitioning and `ZORDER`.
- Prefer migrating existing partitioned or Z-ordered tables to liquid clustering when practical.

Use `CLUSTER BY AUTO` for new Unity Catalog managed tables. Use explicit liquid-clustering keys only for validated and stable access patterns. Partitioning and `ZORDER` are exception-based legacy techniques and must not be applied automatically. Any exception must include performance evidence, an owner, and a documented review date.

#### 3.1.5 Primary Key Constraint Standard

For RDBMS-ingested tables, declare a primary-key constraint in Databricks only when the corresponding primary key exists in the source database and remains valid in the target table.

Primary-key constraints document the source data model in Unity Catalog. They must not be created based only on column names, assumed uniqueness, or inferred relationships.

Declare a primary key when:

- The source table has a declared primary key.
- The target table preserves the same table grain.
- All source primary-key columns are included in the target.
- The key columns retain compatible data types and business meaning.
- The ingestion process does not intentionally introduce duplicates.

Constraint rules:

- Use the constraint name `pk_<logical_table_name>`.
- Omit the technical `tbl_` prefix from the constraint name.
- Use `NORELY` by default for imported source primary keys.
- Use `RELY` only when target-side validation continuously confirms that primary-key columns are not null, primary-key values are unique, and validation failures prevent publication or remove the `RELY` designation.

Do not declare a primary key when:

- No primary key exists in the source.
- The target combines, aggregates, explodes, or otherwise changes the source grain.
- Source key columns are omitted or transformed in a way that changes their meaning.
- The ingestion design intentionally preserves duplicate source versions.

Single-column example:

```sql
customer_id BIGINT NOT NULL,

CONSTRAINT pk_customer
PRIMARY KEY (customer_id)
NORELY
```

For a composite source primary key, preserve all columns in the same logical order:

```sql
sales_order_id BIGINT NOT NULL,
order_line_number INT NOT NULL,

CONSTRAINT pk_sales_order_line
PRIMARY KEY (sales_order_id, order_line_number)
NORELY
```

#### 3.1.6 Foreign Key Constraint Standard

For RDBMS-ingested tables, declare a foreign-key constraint in Databricks only when the corresponding foreign key exists in the source database and remains valid in the target model.

Foreign-key constraints document source-system relationships in Unity Catalog. They must not be created based only on matching column names, application logic, or inferred relationships.

Declare a foreign key when:

- The relationship is explicitly declared as a foreign key in the source database.
- Both the parent and child tables are ingested into the governed target model.
- The referenced parent key is also declared in Databricks.
- The source child and parent columns are preserved with compatible data types.
- The relationship remains valid after ingestion and transformation.

Constraint rules:

- Use the constraint name `fk_<child_logical_table>_<parent_logical_table>`.
- Add a business-role suffix when multiple relationships exist between the same tables.
- Omit technical prefixes such as `tbl_` from the constraint name.
- Use `NORELY` by default for imported source foreign keys.
- Use `RELY` only when target-side validation continuously confirms that foreign-key values resolve to valid parent rows and validation failures prevent publication or remove the `RELY` designation.

Do not declare a foreign key when:

- No foreign-key constraint exists in the source.
- The relationship is inferred from column names or application logic.
- The parent table is not available in the target.
- The target transformation changes or removes the relationship.
- Source-system relationships cannot be represented accurately in the target model.

```sql
CONSTRAINT fk_sales_order_customer
FOREIGN KEY (customer_id)
REFERENCES tbl_customer (customer_id)
NORELY
```

For tables ingested from internal relational databases, declare primary-key and foreign-key constraints only when the corresponding constraints exist in the source database and remain valid in the target table. Do not invent or infer constraints. Preserve source constraint columns and relationships where the target retains the same grain and semantics. Use `NORELY` by default and use `RELY` only when target-side validation continuously proves the constraint.

### 3.2 Column-Level Standards

#### 3.2.1 Column Naming Standard

Column names must:

- use lowercase `snake_case`;
- use clear and meaningful business terminology;
- use only approved abbreviations;
- preserve the source-system name when practical and compliant;
- avoid table-name prefixes unless required to resolve ambiguity; and
- document renamed source columns in the source-to-target mapping.

Examples:

```text
customer_id
customer_status_code
net_amount
order_date
```

#### 3.2.2 Column Data Type Standard

Column data types must be mapped to supported Databricks SQL data types using the most authoritative source information available.

##### 3.2.2.1 Source Type Precedence

Determine the target data type using the following precedence:

1. Approved source data contract or interface specification.
2. Source database metadata.
3. Schema embedded in the source format, such as Parquet or Avro.
4. Approved source-to-target mapping.
5. Representative sample-data inference.
6. `STRING` when the type cannot be determined safely.

Business meaning may override the physical source type. For example, account numbers, postal codes, and identifiers should normally remain `STRING`, even when all observed values are numeric.

The original source data type must be recorded in the source-to-target mapping.

##### 3.2.2.2 General Mapping Rules

- Preserve the source type when it maps directly to a supported target type.
- Safe widening is permitted when it reduces overflow or compatibility risk.
- Automatic narrowing is not permitted.
- Cross-family conversions require explicit transformation rules.
- Monetary and other exact numeric values must use `DECIMAL`.
- Monetary values must use `DECIMAL`, not `FLOAT` or `DOUBLE`.
- Character length declarations such as `VARCHAR(100)` map to `STRING`.
- Date-only values must use `DATE`.
- UTC instants and timezone-aware event times must use `TIMESTAMP`.
- Local date-time values without timezone semantics should use `TIMESTAMP_NTZ`.
- Ambiguous or inconsistent values must remain `STRING` in the ingestion layer.

##### 3.2.2.3 RDBMS-to-Delta Mapping

| Source type family | Target type | Mapping rule |
|---|---|---|
| `CHAR`, `VARCHAR`, `NCHAR`, `NVARCHAR` | `STRING` | Do not preserve source length restrictions. |
| `TEXT`, `CLOB`, `NCLOB` | `STRING` | Use for large textual values. |
| `TINYINT`, `SMALLINT` | `INT` | Approved safe widening. |
| `INTEGER`, `INT` | `INT` | Use `BIGINT` when the source range may exceed `INT`. |
| `BIGINT` | `BIGINT` | Preserve signed 64-bit integer values. |
| Unsigned 64-bit integer | `DECIMAL(20,0)` | Use when values may exceed signed `BIGINT`. |
| `DECIMAL(p,s)`, `NUMERIC(p,s)` | `DECIMAL(p,s)` | Preserve precision and scale. |
| Exact numeric without declared precision | `DECIMAL(p,s)` or `STRING` | Profile values before selecting precision and scale. |
| `REAL`, `FLOAT` | `DOUBLE` | Standardize approximate numeric values on `DOUBLE`. |
| `DOUBLE PRECISION` | `DOUBLE` | Preserve approximate numeric semantics. |
| `BOOLEAN` | `BOOLEAN` | Preserve Boolean values. |
| `BIT` | `BOOLEAN` | Only when the column represents a true/false flag. |
| Date without time | `DATE` | Preserve date-only semantics. |
| Date-time without timezone | `TIMESTAMP_NTZ` | Use for local or wall-clock date-time values. |
| Timestamp with timezone or UTC instant | `TIMESTAMP` | Normalize to the approved timezone standard. |
| `TIME` | `TIME` | Use when time-of-day has independent business meaning. |
| `BINARY`, `VARBINARY`, `BLOB` | `BINARY` | Preserve binary values. |
| `UUID`, `UNIQUEIDENTIFIER` | `STRING` | Store in canonical textual form. |
| Native JSON or XML | `STRING` | Preserve the original payload in the ingestion layer. |
| Stable arrays or objects | `ARRAY`, `MAP`, or `STRUCT` | Use only when the structure is defined and governed. |
| Unsupported source-specific type | `STRING` | Requires an approved transformation before use. |

Source-specific exceptions must be documented. For example, an Oracle `DATE` containing time components must map to a timestamp type rather than `DATE`.

##### 3.2.2.4 Sample-Data-to-Delta Mapping

Sample-based inference may be used only when no reliable source schema is available.

The sample must:

- Include multiple source files where applicable.
- Include data from representative processing periods.
- Include null, minimum, maximum, and exceptional values where available.
- Be reviewed for leading zeros, identifier fields, date formats, and decimal scale.
- Produce a stored and version-controlled schema after approval.

Use the following inference rules:

| Observed values | Target type | Conditions |
|---|---|---|
| Empty or entirely null | `STRING` | Keep as `STRING` until evidence is available. |
| Numeric-looking identifier | `STRING` | Includes IDs, account numbers, postal codes, and values with leading zeros. |
| `true` and `false` | `BOOLEAN` | Values must be consistent. |
| `0` and `1` | `BOOLEAN` or numeric type | Use `BOOLEAN` only when business meaning confirms a flag. |
| Whole numbers | `INT` or `BIGINT` | Use `BIGINT` when the domain or future range is unknown. |
| Fixed-point numbers | `DECIMAL(p,s)` | Derive sufficient precision and scale from the sample and expected range. |
| Scientific or approximate measurements | `DOUBLE` | Must not represent monetary values. |
| Date-only values | `DATE` | All non-null values must match the approved date format. |
| Date-time values with timezone | `TIMESTAMP` | Normalize according to the timezone standard. |
| Date-time values without timezone | `TIMESTAMP_NTZ` | Timezone interpretation must not be implied. |
| Stable JSON array or object | `ARRAY`, `MAP`, or `STRUCT` | Structure must be consistent and approved. |
| Mixed or conflicting values | `STRING` | Invalid values must not be silently converted to null. |

##### 3.2.2.5 Safe Widening Rules

The following widening operations are permitted:

```text
TINYINT -> SMALLINT -> INT -> BIGINT
FLOAT -> DOUBLE
DECIMAL(p,s) -> DECIMAL(p2,s2)
DATE -> TIMESTAMP_NTZ
```

For decimal widening:

- The target must preserve all existing integer digits.
- The target scale must not be less than the source scale.
- The target precision must not exceed the supported maximum.
- Values exceeding supported decimal precision must remain `STRING` in the ingestion layer until an approved transformation is defined.

The following changes require explicit approval:

```text
STRING -> numeric
STRING -> date or timestamp
numeric -> STRING
BOOLEAN -> numeric
timestamp -> date
DECIMAL -> FLOAT or DOUBLE
```

##### 3.2.2.6 Ingestion and Validation Rules

When the source type is uncertain:

1. Ingest ambiguous values as `STRING`.
2. Preserve the original source value.
3. Apply explicit parsing and casting in a subsequent transformation.
4. Capture invalid or incompatible values in a rescued-data or quarantine column.
5. Record parsing failures as data-quality metrics.

After a sample-inferred schema is approved, it must be declared explicitly and reused for subsequent loads. Production pipelines must not repeatedly infer a new schema independently for every batch.

#### 3.2.3 Column Comment Standard

Every production column must include a human-readable comment describing its business definition.

Where applicable, the comment must also describe:

- approved values or code meanings;
- unit of measure or currency;
- calculation logic; and
- the meaning of null.

Dimension example:

```sql
customer_status_code STRING
COMMENT 'Lifecycle status of the customer account. Approved values are ACTIVE, INACTIVE, and CLOSED.'
```

Measure example:

```sql
net_amount DECIMAL(18,2)
COMMENT 'Order amount after discounts and before tax, expressed in the currency identified by currency_code.'
```

Avoid comments that only repeat the column name:

```text
Customer status
Net amount
Order date
```

#### 3.2.4 Column Nullability Standard

Rules:

- Define a column as `NOT NULL` unless null has a valid business meaning.
- Document the meaning of null in the comment for every nullable column.
- Do not use empty strings as substitutes for null.
- Handle unknown, not applicable, and not yet available values consistently.
- Obtain approval for default or placeholder values and document their meaning.

```sql
customer_id STRING NOT NULL
```

Example nullable-column description:

```text
Null when the customer has not yet been assigned to a sales region.
```

#### 3.2.5 Audit Columns Standard

##### 3.2.5.1 Purpose

Standardized tables should include a minimal set of technical audit columns to support:

- Record-level traceability
- Operational troubleshooting
- Data lineage
- Identification of the source batch associated with each record
- Identification of the Databricks job run that created or last changed a record

This standard applies primarily to current-state standardized Delta tables maintained through `MERGE`, upsert, or equivalent processing.

##### 3.2.5.2 Required and Recommended Audit Columns

Audit columns should appear in the following order:

| Column | Requirement | Data type | Nullable | Definition |
|---|---|---|---:|---|
| `audit_batch_id` | Recommended | `STRING` | No | Source-derived batch identifier used to group records that belong to the same logical source batch. It is typically a date extracted from the source filename, but it may also contain a timestamp or another source-defined batch value. |
| `audit_load_id` | Recommended | `STRING` | No | Identifier of the Databricks job run that inserted or most recently changed the record. The Databricks Job run ID should be used. |
| `audit_created_ts` | Required | `TIMESTAMP` | No | Timestamp when the record was first inserted into the standardized table. This value must remain unchanged during subsequent updates. |
| `audit_last_update_ts` | Required | `TIMESTAMP` | No | Timestamp when the business data in the record was most recently inserted or changed in the standardized table. |
| `audit_source_file_path` | Recommended | `STRING` | Yes | Full path of the original source file that produced the current version of the record. This value should be captured during file ingestion and propagated to the standardized table. |

##### 3.2.5.3 Audit Batch ID Standard

The `audit_batch_id` identifies the logical batch represented by the source data. It is different from `audit_load_id`:

- `audit_batch_id` identifies the source batch.
- `audit_load_id` identifies the Databricks job execution that processed the batch.
- The same `audit_batch_id` may be processed more than once because of retries or reprocessing.
- Each processing attempt should have a different `audit_load_id`.

The `STRING` data type should be used because the batch value may have different levels of granularity depending on the source.

Preferred normalized formats are:

| Batch granularity | Recommended format | Example |
|---|---|---|
| Date | `yyyy-MM-dd` | `2026-07-16` |
| Date and time | ISO 8601 | `2026-07-16T14:30:00Z` |
| Source-defined identifier | Documented source format | `BATCH-2026-0716-A` |

Where practical, pipelines should normalize date-based batch values into the recommended formats instead of retaining source-specific filename formats such as `20260716`.

##### 3.2.5.4 Column Behavior

###### Record Insertion

When a new record is inserted:

```text
audit_batch_id             = source-derived batch identifier
audit_load_id              = current Databricks job run ID
audit_created_ts           = current_timestamp()
audit_last_update_ts       = current_timestamp()
audit_source_file_path     = source record file path
```

###### Record Update

When one or more business values change:

```text
audit_batch_id             = batch identifier associated with the updated record
audit_load_id              = current Databricks job run ID
audit_created_ts           = preserve the existing value
audit_last_update_ts       = current_timestamp()
audit_source_file_path     = source file containing the updated record
```

###### Record Reprocessing Without Changes

When a record is reprocessed but its business values have not changed:

- Do not update `audit_batch_id`.
- Do not update `audit_load_id`.
- Do not update `audit_created_ts`.
- Do not update `audit_last_update_ts`.
- Do not update `audit_source_file_path`.

This ensures that the audit columns describe the source batch and load that last produced a meaningful change to the standardized record.

##### 3.2.5.5 Source File Path

The original source file path should be captured when reading the source file:

```python
from pyspark.sql import functions as F

df = (
    spark.read
        .format("json")
        .load(source_path)
        .select(
            "*",
            F.col("_metadata.file_path")
                .alias("audit_source_file_path")
        )
)
```

The source file path should be captured at the initial file-ingestion stage and propagated to the standardized table.

##### 3.2.5.6 Audit Batch ID Extraction

The `audit_batch_id` should be extracted from the source filename, file path, or source data according to the source-specific ingestion rules.

For example, given a filename containing a date:

```text
customer_20260716.json
```

the pipeline may extract and normalize the batch identifier as:

```text
2026-07-16
```

Example PySpark logic:

```python
from pyspark.sql import functions as F

df = (
    df
        .withColumn(
            "batch_date_raw",
            F.regexp_extract(
                F.col("audit_source_file_path"),
                r"(\d{8})",
                1
            )
        )
        .withColumn(
            "audit_batch_id",
            F.date_format(
                F.to_date("batch_date_raw", "yyyyMMdd"),
                "yyyy-MM-dd"
            )
        )
        .drop("batch_date_raw")
)
```

##### 3.2.5.7 Recommended Table Definition

```sql
CREATE TABLE IF NOT EXISTS <catalog>.<schema>.<table_name> (
    -- Business columns
    <business_columns>,

    -- Audit columns
    audit_batch_id           STRING NOT NULL,
    audit_load_id            STRING NOT NULL,
    audit_created_ts         TIMESTAMP NOT NULL,
    audit_last_update_ts     TIMESTAMP NOT NULL,
    audit_source_file_path   STRING
)
USING DELTA;
```

---

## 4. View Standards

These standards apply to production standard views and materialized views unless a requirement explicitly states otherwise.

### 4.1 View Tag Standard

Production views must use applicable organization-approved governed tags consistent with the table tag standard in Section 3.1.1.

Rules:

- Use the same approved tag keys and controlled values as tables.
- Populate only tags that apply to the view.
- Do not store secrets, personal data, or free-form documentation in tag values.
- Update tags when ownership, classification, source, lifecycle, or product association changes.

```sql
ALTER VIEW catalog_name.schema_name.vw_customer_order
SET TAGS (
    'owner' = 'customer_data_team',
    'data_domain' = 'customer',
    'source_system' = 'crm',
    'classification' = 'internal',
    'lifecycle' = 'active'
);
```

### 4.2 View Definition Standard

Production views must:

- use an explicit `SELECT` column list and never use `SELECT *`;
- define and document a clear row-level grain;
- expose only columns required by the intended use case;
- use explicit join conditions;
- use short, meaningful table aliases;
- use clear aliases for calculated, aggregated, or renamed columns;
- apply filters and transformations explicitly; and
- avoid unnecessary view-on-view dependency chains.

Example:

```sql
SELECT
    o.order_id,
    o.customer_id,
    c.customer_name,
    o.created_timestamp AS order_created_timestamp,
    c.created_timestamp AS customer_created_timestamp
FROM catalog_name.schema_name.tbl_sales_order AS o
JOIN catalog_name.schema_name.tbl_customer AS c
    ON o.customer_id = c.customer_id;
```

### 4.3 View Column Naming Standard

Rules:

- Preserve the source column name when its meaning is unchanged and the name is compliant.
- Use lowercase `snake_case`.
- Rename a column when:
  - the source name does not comply with the standard;
  - the business meaning changes;
  - the column is calculated or aggregated; or
  - duplicate output names must be resolved.
- Do not routinely prefix output columns with physical table names.
- Use business-role qualifiers such as `billing_`, `shipping_`, `source_`, or `target_` when required for clarity.
- Expose one copy of a shared business key unless multiple copies have a documented purpose.
- Ensure every output column name is unique and understandable without inspecting the view definition.

### 4.4 View Comment Standard

Every production view must include a human-readable comment describing:

- business purpose;
- row-level grain; and
- important filters, exclusions, aggregations, or transformations.

Every output column must include a comment. Comments for calculated, aggregated, renamed, or business-specific columns must explain the applicable logic or interpretation.

```sql
CREATE OR REPLACE VIEW catalog_name.schema_name.vw_active_customer (
    customer_id COMMENT 'Unique identifier of the customer.',
    customer_name COMMENT 'Current customer display name.',
    customer_created_date COMMENT 'Date on which the customer account was created.'
)
COMMENT 'Provides one row per active customer for operational reporting. Excludes closed and merged customer accounts.'
AS
SELECT
    customer_id,
    customer_name,
    CAST(created_timestamp AS DATE) AS customer_created_date
FROM catalog_name.schema_name.tbl_customer
WHERE account_status = 'active';
```
