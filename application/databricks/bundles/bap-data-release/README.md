# BAP Data Release Bundle

Centralised DB release management for `dev_banking_and_payments_cat`.

## Purpose

All DDL changes (tables, views, materialized views) across all BAP datasets
live in this bundle. ETL logic stays in each team's own bundle (habs, dvr, etc.).

This follows the 2-step deployment standard:
1. **DB release** — this bundle (schema/table DDL)
2. **ETL release** — team bundles (notebooks, jobs, apps)

## Structure

```
bap-data-release/
├── databricks.yml          # Bundle config (dev/stg/prd targets)
├── src/
│   ├── deploy.py           # Deploy notebook (runs SQL files)
│   └── rules.py            # Step resolution logic
└── releases/
    └── release-2.0.0/      # DVR Swift tables
        └── tables/
            ├── dimensions/
            │   └── create_tbl_swift_message_status_dim.sql
            └── facts/
                ├── create_tbl_swift_message_fact.sql
                ├── create_tbl_habs_message_fact.sql
                ├── create_tbl_swift_habs_recon_results_fact.sql
                └── create_tbl_dvr_file_processing_log.sql
```

## Adding a new release

1. Create `releases/release-X.Y.Z/` with subdirectories: `tables/dimensions/`, `tables/facts/`, `views/`
2. Add `.sql` files (one CREATE TABLE per file)
3. Run the `BAP Data Release` job with `release_version=release-X.Y.Z`
4. Stages run in order: Dimensions → Facts → Views → MViews

## Releases

| Version | Scope | Status |
|---------|-------|--------|
| release-2.0.0 | DVR Swift tables | Ready |

## Notes

- HABS release-1.0.0 tables remain in the habs bundle for now.
  Future releases should be added here.
- Each team adds their DDL files here; no separate release jobs needed.
