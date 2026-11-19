create or replace table bsas_db.tbl_file_source(
    srce_sys_id string comment 'source system identifier',
    srce_sys_en_name string comment 'source system english name',
    srce_sys_fr_name string comment 'source system french name',
    audit_creation_user string comment 'audit creation user',
    audit_creation_date timestamp comment 'audit creation timestamp',
    audit_last_update_user string comment 'audit last update user',
    audit_last_update_date timestamp comment 'audit last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_file_source'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);


    
