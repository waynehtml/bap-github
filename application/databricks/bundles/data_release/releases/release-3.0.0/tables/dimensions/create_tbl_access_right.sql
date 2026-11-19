create or replace table bsas_db.tbl_access_right (
  srce_sys_id string comment 'Source System ID',
  art_type_id string comment 'Art Type ID',
  application_id string comment 'Application ID',
  active_flag string comment 'Active indicator flag',
  audit_creation_user string comment 'User record creation',
  audit_creation_date timestamp comment 'Date/Time record created',
  audit_last_update_user string comment 'Last user update name',
  audit_last_update_date timestamp comment 'Date/Time record update',
  audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_access_right'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);