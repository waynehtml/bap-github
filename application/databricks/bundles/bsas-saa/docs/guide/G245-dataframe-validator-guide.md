# DataFrame Validator Guide

This guide explains how to define and run business validation rules against PySpark DataFrames in the DataForge template. It focuses on the available validators, their null behavior, structured results, and task-level failure handling.

The implementation is split across:

- [DataKit DataFrame API reference](../reference/datakit/api/df_validator.md): complete validation rules, results, exact signatures, and source docstrings.
- [DataForge cluster requirements](../../cluster/requirements.txt): installs the compatible `oeds-common~=2.0` package used by the bundle.
- [task_30_raw_to_std.py](../../jobs/dataflow/task_30_raw_to_std.py): sample workflow integration that fails the task when business rules do not pass.

The validator is owned by DataKit. DataForge consumes its
public `oeds.core.df_validator` API and owns the pipeline decision to fail,
quarantine, or continue.

## Mental Model

Business validation has three parts:

1. Define immutable `Rule` objects with the `Rules` factory methods.
2. Call `validate_df(df, rules)` with a PySpark DataFrame and a sequence of rules.
3. Inspect the returned `DataFrameValidationResult` and decide whether to fail, quarantine, or continue.

For each rule, the validator:

1. Confirms that every path declared by the rule exists in the DataFrame schema.
2. Applies the optional `when` filter to the DataFrame used for that rule.
3. Translates the rule into a Great Expectations expectation.
4. Runs the equivalent Spark condition to identify invalid rows.
5. Confirms that Great Expectations and Spark agree on the result.
6. Returns a structured per-rule result with a compact failure message and up to five sample rows.

The validator does not modify or filter the input DataFrame. Invalid business data is represented by `result.success == False`; it is not raised automatically as an exception. The calling task owns that policy decision.

## Import The Validator

Import the validator directly from DataKit in notebooks and project modules:

```python
from oeds.core.df_validator import Rules, validate_df
```

`DataFrameValidationError` is available from the implementation module when code needs to catch validator execution failures specifically:

```python
from oeds.core.df_validator import DataFrameValidationError
```

## Quick Start

Define named rules, validate the standardized DataFrame, and fail the task when any expectation fails:

```python
from oeds.domain.exceptions import RawToStdTaskError
from oeds.core.df_validator import Rules, validate_df

business_rules = [
    Rules.not_null("number", name="number_required"),
    Rules.unique("number", name="number_unique"),
    Rules.not_null("country", name="country_required"),
    Rules.in_set("country", ["CA", "US"], name="country_supported"),
    Rules.gte_col("amount", "minimum_amount", name="amount_meets_minimum"),
]

try:
    validation_result = validate_df(standardized_df, business_rules)
except Exception as exc:
    logger.exception("Failed to execute business validation")
    raise RawToStdTaskError("Failed to execute business validation") from exc

if not validation_result.success:
    failed_expectations = [
        result.expectation
        for result in validation_result.results
        if not result.success
    ]
    logger.error(
        "Business validation failed for rules: %s",
        ", ".join(failed_expectations),
    )
    raise RawToStdTaskError(
        f"Business validation failed: {', '.join(failed_expectations)}"
    )
```

Use explicit rule names. Names make logs, failure messages, and support investigations easier to understand than generated names. Define rules before the `try` block only when rule-construction errors should be treated as programming or configuration failures rather than translated to a task exception.

## Available Validators

All rule factories accept an optional `name` and `when` unless their signatures require a name, as `Rules.sql` does.

### Presence And Membership

| Factory | Valid when | Null behavior | Example |
| --- | --- | --- | --- |
| `Rules.not_null(path)` | The value is not null. | Null fails. | `Rules.not_null("customer_id")` |
| `Rules.is_null(path)` | The value is null. | Null passes; non-null fails. | `Rules.is_null("closed_reason")` |
| `Rules.in_set(path, values)` | A non-null value belongs to the allowed set. | Null is ignored; combine with `not_null` when required. | `Rules.in_set("country", ["CA", "US"])` |
| `Rules.not_in_set(path, values)` | A non-null value is absent from the prohibited set. | Null is ignored; combine with `not_null` when required. | `Rules.not_in_set("status", ["deleted"])` |

Required controlled values normally use two rules:

```python
rules = [
    Rules.not_null("country", name="country_required"),
    Rules.in_set(
        "country",
        ["CA", "US"],
        name="country_supported",
    ),
]
```

### Ranges And Scalar Comparisons

| Factory | Valid when | Null behavior | Example |
| --- | --- | --- | --- |
| `Rules.between(path, min_value=..., max_value=...)` | The value is within the configured bounds. Bounds are inclusive by default. | Null is ignored. | `Rules.between("score", min_value=0, max_value=100)` |
| `Rules.gt(path, value)` | The value is greater than the constant. | Null is ignored. | `Rules.gt("amount", 0)` |
| `Rules.gte(path, value)` | The value is greater than or equal to the constant. | Null is ignored. | `Rules.gte("quantity", 1)` |
| `Rules.lt(path, value)` | The value is less than the constant. | Null is ignored. | `Rules.lt("discount", 1)` |
| `Rules.lte(path, value)` | The value is less than or equal to the constant. | Null is ignored. | `Rules.lte("attempt_count", 5)` |

`between` requires at least one bound. Use `strict_min=True` or `strict_max=True` to exclude a configured boundary:

```python
rules = [
    Rules.between(
        "ratio",
        min_value=0,
        max_value=1,
        strict_min=True,
        name="ratio_in_open_closed_interval",
    ),
    Rules.gte("quantity", 1, name="quantity_positive"),
]
```

`gt`, `gte`, `lt`, and `lte` are convenience factories over `between`. They
therefore generate a default name such as `between[quantity]` when `name` is
omitted.

Use values compatible with the Spark column type. For example, compare numeric columns with numeric values and date columns with values Spark and Great Expectations can interpret consistently.

### String Rules

| Factory | Valid when | Null behavior | Example |
| --- | --- | --- | --- |
| `Rules.regex(path, pattern)` | A non-null string matches the regular expression. | Null is ignored. | `Rules.regex("postal_code", r"^[A-Z]\d[A-Z] ?\d[A-Z]\d$")` |
| `Rules.length_between(path, min_value=..., max_value=...)` | String length is within the inclusive bounds. | Null is ignored. | `Rules.length_between("account_id", min_value=8, max_value=20)` |

The regular expression is compiled when the rule is created, so an invalid pattern raises immediately. `length_between` requires at least one bound.

```python
rules = [
    Rules.not_null("account_id", name="account_id_required"),
    Rules.length_between(
        "account_id",
        min_value=8,
        max_value=20,
        name="account_id_length",
    ),
    Rules.regex(
        "account_id",
        r"^[A-Z0-9]+$",
        name="account_id_format",
    ),
]
```

### Uniqueness Rules

| Factory | Valid when | Null behavior | Example |
| --- | --- | --- | --- |
| `Rules.unique(path)` | Every non-null value occurs once. | Null values are ignored. | `Rules.unique("record_id")` |
| `Rules.compound_unique(paths)` | Every non-fully-null column tuple occurs once. | A tuple where every component is null is ignored. | `Rules.compound_unique(["account_id", "effective_date"])` |

`compound_unique` requires at least two paths. A partially null tuple still participates in duplicate detection.

```python
rules = [
    Rules.not_null("record_id", name="record_id_required"),
    Rules.unique("record_id", name="record_id_unique"),
    Rules.compound_unique(
        ["account_id", "effective_date"],
        name="account_effective_date_unique",
    ),
]
```

Uniqueness is evaluated against the DataFrame passed to `validate_df`. Apply the rule before writing the batch, and separately enforce any cross-batch uniqueness required by the target table.

For a conditional uniqueness rule, duplicate detection is limited to rows that
match the `when` condition.

### Column-Pair Comparisons

| Factory | Valid when | Null behavior | Example |
| --- | --- | --- | --- |
| `Rules.eq_col(left, right)` | Both values are equal. | Both null passes; exactly one null fails. | `Rules.eq_col("reported_total", "calculated_total")` |
| `Rules.gt_col(left, right)` | Left is greater than right. | Compared only when both values are non-null. | `Rules.gt_col("end_sequence", "start_sequence")` |
| `Rules.gte_col(left, right)` | Left is greater than or equal to right. | Compared only when both values are non-null. | `Rules.gte_col("amount", "minimum_amount")` |
| `Rules.lt_col(left, right)` | Left is less than right. | Compared only when both values are non-null. | `Rules.lt_col("start_date", "end_date")` |
| `Rules.lte_col(left, right)` | Left is less than or equal to right. | Compared only when both values are non-null. | `Rules.lte_col("used_limit", "approved_limit")` |

Add `not_null` rules when either side is mandatory:

```python
rules = [
    Rules.not_null("amount", name="amount_required"),
    Rules.not_null("minimum_amount", name="minimum_amount_required"),
    Rules.gte_col(
        "amount",
        "minimum_amount",
        name="amount_meets_minimum",
    ),
]
```

### Custom SQL Predicate

Use `Rules.sql` when a business rule cannot be expressed clearly with a built-in factory:

```python
rules = [
    Rules.sql(
        name="active_record_has_owner",
        predicate="status <> 'active' OR owner_id IS NOT NULL",
        columns=["status", "owner_id"],
    ),
]
```

The predicate describes a valid row. The validator marks a row invalid when the predicate is false or null. The `columns` argument is mandatory and must list every DataFrame path referenced by the predicate. It is used for schema validation and compact failing-row samples; the validator does not parse the SQL expression to infer these paths.

Prefer the built-in factories when they express the rule. Use SQL predicates for real multi-column domain logic, not as a shortcut for simple presence, range, or membership checks.

## Conditional Rules

A conditional rule validates only rows matching a Spark SQL condition. Use the fluent `Rules.when(...)` form:

```python
rules = [
    Rules.when("country = 'CA'").not_null(
        "payload.source",
        name="canadian_source_required",
    ),
]
```

Every factory also accepts `when=` directly:

```python
rule = Rules.not_null(
    "payload.source",
    name="canadian_source_required",
    when="country = 'CA'",
)
```

The condition is evaluated with `pyspark.sql.functions.expr`. Rows where the condition is false or null are excluded from that rule before both Great Expectations and Spark tagging run. Keep conditions deterministic and reference columns available in the DataFrame.

Paths used only in `when` are not prevalidated as declared rule paths. A missing
column or invalid Spark SQL condition fails during rule execution with a
`DataFrameValidationError` whose cause contains the Spark error.

Do not pass `when=` again after starting with `Rules.when(...)`; the conditional builder rejects the duplicate condition.

## Nested Struct Paths

Rules support dotted paths through nested `StructType` fields:

```python
rules = [
    Rules.not_null("payload.source", name="payload_source_required"),
    Rules.in_set(
        "payload.channel",
        ["api", "batch", "portal"],
        name="payload_channel_supported",
    ),
]
```

Every path is resolved against the DataFrame schema before Great Expectations runs. A missing path raises `ValueError` immediately.

Dotted traversal is supported for nested structs. Traversing through an array, map, or scalar as though it were a struct is rejected. Normalize or explode those values into a supported shape before validation.

## Null Behavior

Most validators intentionally treat null as outside their domain. This lets a pipeline separate two questions:

1. Is the field required?
2. If present, is its value valid?

Use `Rules.not_null` for the first question and another rule for the second.

| Rule group | Null behavior |
| --- | --- |
| `not_null` | Null fails. |
| `is_null` | Null passes; non-null fails. |
| Membership, range, regex, and length rules | Null is ignored. |
| `unique` | Null is ignored. |
| `compound_unique` | A fully null tuple is ignored; partially null tuples participate. |
| `eq_col` | Both null passes; one null and one non-null fails. |
| Other pair comparisons | Evaluated only when both values are non-null. |
| `sql` | A false or null predicate fails. |

Normalize source null markers such as empty strings, `N/A`, or `NULL` into Spark nulls before running business validation. Otherwise those markers remain ordinary strings and may pass or fail a different rule than intended.

## Rule Names

Give production rules stable names:

```python
Rules.not_null("customer_id", name="customer_id_required")
```

When `name` is omitted, the validator creates a readable name such as:

```text
not_null[customer_id]
between[amount]
gte[amount,minimum_amount]
```

The pair-comparison form includes its operator and both paths. If multiple rules resolve to the same name, later occurrences receive suffixes such as `_2` and `_3`.

Because scalar `gt`, `gte`, `lt`, and `lte` factories produce `between` rules,
their generated name is `between[path]`. Use an explicit name when the exact
operator should appear in diagnostics.

Stable explicit names are recommended because the names appear in logs, result objects, and raised task errors.

## Result Contract

`validate_df` returns a frozen `DataFrameValidationResult`:

```python
DataFrameValidationResult(
    success=False,
    results=(...),
)
```

Fields:

| Field | Meaning |
| --- | --- |
| `success` | `True` only when every rule passes. |
| `results` | One `DataFrameRuleResult` per prepared rule, in input order. |

Each per-rule result contains:

| Field | Meaning |
| --- | --- |
| `expectation` | Explicit or generated rule name. |
| `success` | Whether that rule passed. |
| `error_message` | Compact failure message, or `None` for a passing rule. |
| `sample_rows` | Up to five dictionaries containing values for the rule's referenced paths. |

Both result models are frozen dataclasses, and `results` and `sample_rows` are
tuples. A passing rule has `error_message=None` and `sample_rows=()`. A failed
rule's message may include the Great Expectations unexpected count and a preview
of up to three unexpected values; `sample_rows` comes from the equivalent Spark
invalid-row selection.

Inspect results programmatically:

```python
validation_result = validate_df(df, rules)

for rule_result in validation_result.results:
    logger.info(
        "Validation rule '%s': success=%s",
        rule_result.expectation,
        rule_result.success,
    )
```

Failure messages and `sample_rows` may contain source values. Do not log them when the data may be sensitive. Log rule names and counts at normal operational levels, and expose row-level diagnostics only through an approved secure workflow.

## Failure Behavior

The validator distinguishes invalid business data from validator failures.

### Invalid Business Data

A rule mismatch returns normally:

```python
result = validate_df(df, rules)

if not result.success:
    # The caller decides whether to fail, quarantine, or continue.
    ...
```

Pipeline tasks should normally raise their task-specific exception when required business rules fail.

### Configuration And Execution Failures

Invalid configuration raises during rule construction or before validation work
begins. Execution failures are separated from these caller-input errors.

`ValueError` is used for invalid API inputs such as:

- a non-DataFrame input;
- a non-sequence rule collection (use a list or tuple, not a generator or set);
- a non-`Rule` item in the collection;
- an empty or missing column path;
- a path absent from the DataFrame schema;
- a `between` or `length_between` rule without any bounds;
- a `compound_unique` rule with fewer than two paths;
- a SQL rule without referenced columns.

An invalid regular expression is compiled by `Rules.regex(...)` immediately and
raises Python's `re.error` (`re.PatternError` on newer Python versions).

`DataFrameValidationError` is used once the validation engine cannot complete,
including:

- a missing or incompatible Great Expectations installation;
- invalid SQL in `when` or a custom predicate;
- Great Expectations or Spark execution failures;
- an unexpected Great Expectations result shape;
- disagreement between Great Expectations and Spark invalid-row tagging.

The validator preserves the underlying exception as the cause when it wraps an
execution failure. Catch narrowly when the workflow needs to distinguish invalid
rule/dataframe inputs from engine failures:

```python
from oeds.core.df_validator import DataFrameValidationError

try:
    result = validate_df(df, rules)
except ValueError as exc:
    raise RawToStdTaskError("Invalid business validation configuration") from exc
except DataFrameValidationError as exc:
    raise RawToStdTaskError("Failed to execute business validation") from exc
```

Rule factory calls may raise before `validate_df(...)`, so include rule creation
inside the protected block when the task should translate those failures too.

An empty rule list is valid, does not initialize Great Expectations, and returns
`success=True` with no per-rule results:

```python
result = validate_df(df, [])
assert result.success
assert result.results == ()
```

Engine failures are raised rather than converted into unsuccessful rule results.
They are not evidence that business rows violated a rule, so do not quarantine
data based only on an engine exception.

## Complete Example

This example combines presence, membership, range, string, uniqueness, pair, conditional nested, and SQL rules:

```python
rules = [
    Rules.not_null("record_id", name="record_id_required"),
    Rules.unique("record_id", name="record_id_unique"),
    Rules.not_null("category", name="category_required"),
    Rules.in_set(
        "category",
        ["retail", "enterprise", "public"],
        name="category_supported",
    ),
    Rules.not_in_set(
        "status",
        ["deleted", "invalid"],
        name="status_not_prohibited",
    ),
    Rules.between(
        "score",
        min_value=0,
        max_value=100,
        name="score_in_range",
    ),
    Rules.regex(
        "account_id",
        r"^[A-Z0-9]{8,20}$",
        name="account_id_format",
    ),
    Rules.compound_unique(
        ["account_id", "effective_date"],
        name="account_effective_date_unique",
    ),
    Rules.gte_col(
        "amount",
        "minimum_amount",
        name="amount_meets_minimum",
    ),
    Rules.when("country = 'CA'").not_null(
        "payload.source",
        name="canadian_source_required",
    ),
    Rules.sql(
        name="closed_record_has_reason",
        predicate="status <> 'closed' OR closed_reason IS NOT NULL",
        columns=["status", "closed_reason"],
    ),
]

result = validate_df(standardized_df, rules)
```

The bundled [DataKit DataFrame API reference](../reference/datakit/api/df_validator.md) provides exact signatures and source docstrings for the complete validator API.

## Performance And Operational Guidance

- Run validation after technical standardization and null normalization so rules see stable column names, data types, and Spark nulls.
- Validate only columns needed by business rules. Avoid duplicate rules that enforce the same condition.
- Each rule creates a Great Expectations batch, runs a validation, and triggers a
  Spark action to detect at least one invalid row. A failed rule triggers another
  action to collect up to five samples. Large rule sets and large uncached
  DataFrames can therefore cause repeated work.
- A conditional rule evaluates uniqueness and all other checks only within its
  filtered subset.
- Reuse one rule list for the dataset instead of constructing different rule semantics across notebooks.
- Use rule names in normal logs. Avoid logging `sample_rows` or unexpected values from sensitive datasets.
- Keep invalid-data policy in the workflow task: fail, quarantine, or explicitly allow continuation.
- Use table constraints for simple invariants that Unity Catalog can enforce, while keeping richer cross-column and conditional validation in the pipeline.

