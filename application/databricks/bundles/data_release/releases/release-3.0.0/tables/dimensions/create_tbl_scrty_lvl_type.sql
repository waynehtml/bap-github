create or replace table bsas_db.tbl_scrty_lvl_type (
    scrty_lvl_type_id string not null comment 'Security level type identifier',
    scrty_lvl_type_en_name string comment 'Security level type English name',
    scrty_lvl_type_fr_name string comment 'Security level type French name',
    audit_creation_user string comment 'Audit creation user',
    audit_creation_date timestamp comment 'Audit creation timestamp',
    audit_last_update_user string comment 'Audit last update user',
    audit_last_update_date timestamp comment 'Audit last update timestamp',
    audit_load_id bigint default 0 comment 'Databricks job run identifier'
)
using delta
comment 'Security level type reference table'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);