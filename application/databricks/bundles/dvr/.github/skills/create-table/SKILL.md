---
name: create-table
description: >-
  Create one DataForge Unity Catalog table reference under
  conf/oeds/config/schema from an optional reference, full name, and schema.
  Use when a developer wants a best-effort table definition with the standard
  audit columns; do not use for views, deployment, permissions, loaders, or
  runtime pipeline changes.
---

# Create Table

Create exactly one table reference under `conf/oeds/config/schema`. Ask at most
three quick questions, generate the reference with best effort, and show the
developer exactly where the file was created.

## Required References

Before asking questions, read:

- `docs/guide/G211-schema-guide.md` for the schema registry contract.
- `docs/standards-and-practices/databricks_uc_standards.md` for table names,
  data types, nullability, comments, and constraints.
- `conf/oeds/config/schema/tbl_sample.py`, when present, for the current
  reference-file and audit-column pattern.
- `src/oeds/domain/utils/schema/schema_utils.py` for supported fields and
  metadata.

Inspect other table definitions only to preserve the local file format. Do not
scan consumers to infer answers that the developer declines to provide.

## Three Questions

If the current request already supplies one of these answers, use it without
asking again. Otherwise ask each missing question in order and wait for its
answer before continuing. Never ask a follow-up, confirmation, or replacement
question.

### Question 1: Reference Name

Ask:

> What is the table reference name? This is the name used in code to refer to
> the actual table, and its full table name can be resolved from this reference.
> Use `tbl_<reference_name>`. If it is not available, reply `no`.

Help prompt:

> Example: `tbl_customer`. The skill uses it for `tbl_customer.py` and the
> schema reference. If you reply `no`, it uses `tbl_table_name`.

Parse a supplied value as follows:

- Trim whitespace, surrounding SQL identifier quotes, paths, and a trailing
  `.py` extension.
- Normalize the value to lowercase `snake_case`.
- Add the `tbl_` prefix when it is missing.
- Use the normalized value for the file and module reference.
- Use `tbl_table_name` when no usable reference name is supplied. Do not ask
  the developer to correct the value.

### Question 2: Full Table Name

Ask:

> Do you have the table's full name? If yes, paste
> `catalog.database.table`. A leading `{env}_` prefix in the catalog is
> stripped if provided. If no, reply `no`.

Help prompt:

> Example: `dev_application_cat.sales_db.tbl_customer`. The skill removes the
> environment prefix from the stored catalog. If you reply `no`, it uses
> visible placeholders for catalog, database, and physical table name.

Parse a supplied value as follows:

- Trim whitespace and surrounding SQL identifier quotes.
- Split it into catalog, database, and physical table components.
- Strip one leading literal `{env}_` or recognized DataForge environment
  prefix such as `dev_`, `stg_`, or `prd_` from the catalog.
- Normalize the physical table name to lowercase `snake_case` and add `tbl_`
  when it is missing.
- Preserve usable components from imperfect input and use placeholders for
  unresolved components. Do not ask the developer to correct the value.

When no usable full name is supplied, use:

- catalog: `catalog_name`
- database: `database_name`
- physical table name: `tbl_table_name`

A bare `yes` without a full name follows the same fallback as `no`.

### Question 3: Schema

Ask:

> Do you have the table schema now? If yes, paste it. If no, reply `no`.

Help prompt:

> You can paste SQL DDL, a Spark `StructType`, JSON or Avro schema, a column
> list, or another structured schema. The skill infers names, types,
> nullability, comments, identity metadata, defaults, and declared constraints
> with best effort. If you reply `no`, it creates no business columns.

Parse supplied schema content with maximum effort:

- Prefer explicit declared types, nullability, comments, defaults, identity
  metadata, and constraints.
- Normalize business column names to lowercase `snake_case`.
- Follow the Unity Catalog type mappings. Keep identifier-like values as
  strings and use exact decimal types for monetary values.
- Use `StringType` when a type is unknown.
- Make a column nullable when nullability is not provided.
- Preserve useful source comments. Use a visible `TODO` comment when a
  business-column description or nullable meaning is unavailable.
- Preserve identity metadata, defaults, and constraints only when the supplied
  schema declares them. Never infer them from column names.
- Normalize supplied audit columns to the standard definitions below and do
  not duplicate them.

A bare `yes` without schema content follows the same fallback as `no`. Do not
invent business columns when no schema is available.

## Definition Rules

After the third answer, create the file immediately without another prompt.

- Export `SCHEMA`, `SQL`, and `DEFINITION`.
- Use explicit imports from `pyspark.sql.types`. Do not use wildcard imports.
- Populate catalog, database, and physical name from Question 2 or its
  placeholders.
- Set `DEFINITION["kind"]` to `"table"` and bind `schema` and `sql` to
  `SCHEMA` and `SQL`.
- Use `{schema}` inside the column list and `USING DELTA` after it.
- Use `COMMENT 'TODO: Describe the table purpose and grain.'` because the
  three-question flow does not collect business documentation.
- Never add a clustering clause, partitioning, table properties, governance
  tag statements, or other performance options.
- Add at most one explicitly supplied identity column. It must use `LongType`,
  be non-nullable, and use supported `identity` metadata.

## Audit Columns

Place parsed business and generated columns before these fields. Always add the
five audit columns in this exact order without default expressions:

- `audit_batch_id` uses non-nullable `StringType`.
- `audit_load_id` uses non-nullable `StringType`.
- `audit_created_ts` uses non-nullable `TimestampType`.
- `audit_last_update_ts` uses non-nullable `TimestampType`.
- `audit_source_file_path` uses nullable `StringType`.

Give every audit field the established comment from `tbl_sample.py`. Apply this
audit shape to standardized, curated, reference, and operational tables.

## Existing Files

The three questions do not authorize overwriting an existing reference. If the
resolved target already exists, do not change it and do not ask a fourth
question. Report its path and state that creation stopped to protect the
existing file.

## Output Boundary

Create only the resolved `conf/oeds/config/schema/tbl_*.py` file. Do not change
`__init__.py`, catalogs, documentation, views, permissions, loaders, jobs,
release notebooks, tests, or consumers. Do not provide unsolicited follow-up
recommendations for those areas.

## Validation and Handoff

After writing the file:

1. Confirm that it parses as Python and exports `SCHEMA`, `SQL`, and
   `DEFINITION`.
2. Confirm the file and module reference match Question 1.
3. Confirm catalog, database, and physical table name match Question 2 or
   its placeholders.
4. Confirm parsed business fields match the supplied schema as closely as the
   supported renderer allows.
5. Confirm the audit fields have the required order, types, and nullability.
6. When PySpark is available, import and render the definition through
   `SchemaManager`. Otherwise complete the static checks and report that the
   runtime check was unavailable.
7. Confirm that this workflow changed no other project file.

Lead the completion message with:

> Created table reference: `<absolute-path-to-created-file>`

Render the absolute path as a clickable local-file link when the client
supports it. Then report the parsing fallback used and validation performed.
For an existing-file collision, lead with the protected existing path instead.
Stop without deploying the table.
