# DataFrames and validation

## When to use this capability

Use `df_utils` to shape or normalize a PySpark DataFrame. Use `df_validator` when a dataset must be evaluated against reusable business rules and the caller needs structured per-rule results and failing-row samples.

## Choose the public API

| Need | Choose |
| --- | --- |
| Align top-level fields to a target schema | `add_missing_cols` |
| Flatten struct fields | `flatten_all_col` or `flatten_selected_col` |
| Select literal top-level names safely | `select_columns` |
| Standardize field names or null-like strings recursively | `normalize_column_names` or `normalize_nulls` |
| Perform focused zero/null/NaN checks | `contains_zero_values`, `contains_null_or_nan`, or `check_not_null` |
| Express reusable value, range, regex, uniqueness, pair, or SQL rules | Factories on `Rules` |
| Execute rules and receive an aggregate result | `validate_df` |

## Restrictions and side effects

All functions in these modules require PySpark. Transformations return new DataFrames, but several checks perform Spark actions. `contains_*` uses `count`, `check_not_null` aggregates violation counts, and `validate_df` runs Great Expectations plus Spark invalid-row logic for every rule.

Flattening traverses structs, not arrays or maps. Name normalization rejects empty or colliding results. Null normalization changes string leaves only and leaves map keys unchanged. `check_not_null` has a historical return-shape inconsistency: it returns a list of violations when checks exist and an empty dictionary when none are built.

Most built-in validation rules ignore nulls; add `Rules.not_null` when presence is required. `Rules.sql` requires the caller to list every referenced path because the predicate is not parsed. `validate_df` raises for engine failures but returns `success=False` for ordinary rule failures. Failed rules collect up to five source-value dictionaries, which may contain sensitive data; handle and log them accordingly.

Great Expectations remains pinned to 1.23.1. DataKit creates its Spark datasource
with `persist=False`, so validation does not implicitly cache the input on
classic or serverless compute. It also does not unpersist caller-owned caches.
Repeated actions may reevaluate the source; keep the source and nondeterministic
expressions stable while validation runs. Engine disagreement is still an
error, and no rule silently falls back to Spark-only validation.

Uniqueness and compound uniqueness project their window-based Spark check
before filtering. This fixes the previous engine failure caused by a window
expression in `WHERE`, while retaining the GX comparison and existing null rules.

See [runtime coverage](../README.md#reader-and-validation-compute-compatibility)
for local verification and outstanding Databricks runtime checks.

## Short example

```python
from oeds.core.df_utils import normalize_column_names, normalize_nulls
from oeds.core.df_validator import Rules, validate_df

clean_df = normalize_column_names(raw_df)
clean_df = normalize_nulls(clean_df, columns=["customer_type"])

rules = [
    Rules.not_null("customer_id", name="customer_id_required"),
    Rules.in_set("customer_type", ["retail", "business"]),
]
result = validate_df(clean_df, rules)
if not result.success:
    raise RuntimeError("DataFrame validation failed")
```

## Related examples

- [DataFrame rule validation example](../../examples/df_validator/validate_dataframe.py)
- [String-leaf casting example](../../examples/file_reader/load_and_cast_files.py)
