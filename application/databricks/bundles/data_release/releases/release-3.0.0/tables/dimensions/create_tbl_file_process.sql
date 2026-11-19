create or replace table bsas_db.tbl_file_process(
    file_name string comment 'processed file name',
    process_error_msg string comment 'process error message',
    file_art_written_count int comment 'number of artifacts written to file',
    batch_id int comment 'batch identifier',
    process_status_id string comment 'process status identifier',
    srce_sys_id string comment 'source system identifier',
    art_type_id string comment 'artifact type identifier',
    audit_creation_user string comment 'audit creation user',
    audit_creation_date timestamp comment 'audit creation timestamp',
    audit_last_update_user string comment 'audit last update user',
    audit_last_update_date timestamp comment 'audit last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_file_process'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);