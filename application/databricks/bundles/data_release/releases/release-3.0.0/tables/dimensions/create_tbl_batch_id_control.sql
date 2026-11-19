create or replace table bsas_db.tbl_batch_id_control(
    next_batch_id int comment 'next batch identifier',
    audit_creation_user string comment 'audit creation user',
    audit_creation_date timestamp comment 'audit creation timestamp',
    audit_last_update_user string comment 'audit last update user',
    audit_last_update_date timestamp comment 'audit last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_batch_id_control'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);