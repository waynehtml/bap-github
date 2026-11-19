"""Materialized summary of amounts by category in the sample table."""

SQL = """
SELECT category, SUM(amount) AS total_amount
FROM {tbl_sample}
GROUP BY category
"""

DEFINITION = {
    "catalog": "application_cat",
    "database": "oedisint_db",
    "name": "mv_sample",
    "kind": "mv",
    "sql": SQL,
}
