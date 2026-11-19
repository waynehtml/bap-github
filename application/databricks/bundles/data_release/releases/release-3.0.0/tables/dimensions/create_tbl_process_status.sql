create or replace table bsas_db.tbl_process_status(
    process_status_id string comment 'process status identifier',
    process_status_en_desc string comment 'process status english description',
    process_status_fr_desc string comment 'process status french description',
    creation_user string comment 'record creation user',
    creation_date timestamp comment 'record creation timestamp',
    last_update_user string comment 'record last update user',
    last_update_date timestamp comment 'record last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_process_status'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);