---
name: create-view
description: >-
  Create one DataForge Unity Catalog view reference under
  conf/oeds/config/schema from an optional reference, full name, and SELECT
  query. Use for standard or user-facing views; do not use for tables,
  materialized views, deployment, permissions, or runtime pipeline changes.
---

# Create View

Create exactly one view reference under `conf/oeds/config/schema`. Ask at most
three quick questions, generate the reference with best effort, and show the
developer exactly where the file was created.

## Required References

Before asking questions, read:

- `docs/guide/G211-schema-guide.md` for the schema registry contract.
- `docs/standards-and-practices/databricks_uc_standards.md` for view naming
  and SQL standards.
- `conf/oeds/config/schema/vw_sample.py`, when present, for the current
  reference-file pattern.
- `src/oeds/domain/utils/schema/schema_utils.py` for view rendering and
  placeholder behavior.

Inspect existing modules under `conf/oeds/config/schema` before asking the
questions. Use their module names to validate query placeholders and their
content to preserve the local file format. Do not scan consumers to invent
view logic that the developer declines to provide.

## Three Questions

If the current request already supplies an answer, use it without asking again.
Otherwise ask each missing question in order and wait for its answer before
continuing. Never ask a follow-up, confirmation, or replacement question.

### Question 1: Reference Name

Ask:

> What is the view reference name? This is the name used in code to refer to
> the actual view, and its full view name can be resolved from this reference.
> The preferred prefixes are `vw_` and `vwu_`, but any lowercase `snake_case`
> name is allowed. If it is unavailable, reply `no`.

Help prompt:

> Prefer `vw_customer` for a standard view or `vwu_customer` for a view meant
> for direct consumer access. Names such as `reporting_customer` and
> `customer_summary` are also allowed. If you reply `no`, the skill uses
> `vw_view_name`.

Parse a supplied value as follows:

- Trim whitespace, surrounding SQL identifier quotes, paths, and a trailing
  `.py` extension.
- Normalize the value to lowercase `snake_case`.
- Preserve the normalized supplied name, including any prefix or no prefix.
  Never add, replace, or reject a prefix.
- Use the normalized value for the file and module reference.
- Use `vw_view_name` when no usable reference is supplied. Do not ask the
  developer to correct the value.

### Question 2: Full View Name

Ask:

> Do you have the view's full name? If yes, paste `catalog.database.view`. A
> leading `{env}_` prefix in the catalog is stripped if provided. If no, reply
> `no`.

Help prompt:

> Example: `dev_application_cat.view_db.vw_customer`. The stored catalog is
> `application_cat`. If you reply `no`, the skill uses visible placeholders
> for the catalog, database, and physical view name.

Parse a supplied value as follows:

- Trim whitespace and surrounding SQL identifier quotes.
- Split it into catalog, database, and physical view components.
- Strip one leading literal `{env}_` or recognized DataForge environment
  prefix such as `dev_`, `stg_`, or `prd_` from the catalog.
- Normalize the physical view name to lowercase `snake_case`.
- Preserve the normalized physical name, including any prefix or no prefix.
  Never add, replace, or reject a prefix.
- Preserve usable components from imperfect input and use placeholders for
  unresolved components. Do not ask the developer to correct the value.

When no usable full name is supplied, use:

- catalog: `catalog_name`
- database: `database_name`
- physical view name: `vw_view_name`, or `vwu_view_name` when Question 1 uses
  the `vwu_` prefix

A bare `yes` without a full name follows the same fallback as `no`.

### Question 3: SELECT Query

Ask:

> Do you have the view's SELECT query? Paste one `SELECT` query or a `WITH`
> query whose final statement is `SELECT`. If no, reply `no`.

Help prompt:

> Paste only the query body, not `CREATE VIEW` DDL. Registered table and view
> dependencies can use references such as `{tbl_customer}` or `{vw_customer}`.
> If the query is missing or unusable, the skill creates a safe empty-result
> query with a visible TODO.

Parse a supplied query as follows:

- Trim whitespace, one surrounding Markdown fence, and one trailing semicolon.
- Accept exactly one query whose first effective keyword is `SELECT` or `WITH`.
  A `WITH` query must have a final `SELECT` statement.
- Reject `CREATE VIEW`, other DDL, DML, and multiple SQL statements.
- Reject wildcard projections such as `SELECT *` or `alias.*`. Do not reject
  an aggregate such as `COUNT(*)`.
- Preserve the submitted projections, joins, filters, aliases, expressions,
  comments, and formatting. Do not rewrite or invent business logic.
- Preserve a schema placeholder only when its name exactly matches an existing
  module under `conf/oeds/config/schema` whose `DEFINITION["kind"]` is
  `"table"` or `"view"`. Do not require a filename prefix.
- Treat an unregistered schema placeholder as unusable because the renderer
  cannot resolve it. Do not modify registry modules or ask another question.

Use this query when the answer is missing or unusable:

```sql
-- TODO: Replace this placeholder query.
SELECT
    CAST(NULL AS STRING) AS todo
WHERE FALSE
```

A bare `yes` without query content uses the same placeholder.

## Definition Rules

After the third answer, create the file immediately without another prompt.

- Add a concise module docstring matching the local reference-file pattern.
- Export only `SQL` and `DEFINITION`.
- Store only the `SELECT` or `WITH` query body in `SQL`. Do not add
  `CREATE VIEW`, `AS`, tags, permissions, or deployment statements.
- Populate catalog, database, and physical name from Question 2 or its
  placeholders.
- Set `DEFINITION["kind"]` to `"view"` and bind `sql` to `SQL`.
- Do not define `SCHEMA`, table audit columns, table properties, clustering,
  partitioning, or materialized-view configuration.

The deployment layer constructs `CREATE OR REPLACE VIEW` and resolves registered
schema placeholders. Do not change the renderer or deployment utilities.

## Existing Files

The three questions do not authorize overwriting an existing reference. If the
resolved target already exists, do not change it and do not ask a fourth
question. Report its path and state that creation stopped to protect it.

## Output Boundary

Create only the resolved
`conf/oeds/config/schema/<normalized_reference>.py` file. Do not change
`__init__.py`, schema registry dependencies, catalogs, documentation,
permissions, jobs, release notebooks, tests, runtime utilities, or consumers.
Do not deploy the view or provide unsolicited follow-up recommendations.

## Validation and Handoff

After writing the file:

1. Confirm that it parses as Python and exports `SQL` and `DEFINITION`.
2. Confirm the file and module reference match Question 1.
3. Confirm catalog, database, and physical view name match Question 2 or its
   placeholders.
4. Confirm `SQL` contains one accepted query body or the exact fallback query,
   without generated view DDL or a wildcard projection.
5. Confirm every schema placeholder resolves to an existing registry module.
6. When PySpark is available, import and render the view through
   `SchemaManager`. Otherwise complete the static checks and report that the
   runtime check was unavailable.
7. Confirm that this workflow changed no other project file.

Lead the completion message with:

> Created view reference: `<absolute-path-to-created-file>`

Render the absolute path as a clickable local-file link when the client
supports it. Then report whether supplied or fallback SQL was used and what
validation was performed. For an existing-file collision, lead with the
protected existing path instead. Stop without deploying the view.