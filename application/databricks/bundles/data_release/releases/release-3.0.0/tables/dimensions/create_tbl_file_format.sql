create or replace table bsas_db.tbl_file_format(
    format_id string comment 'file format identifier',
    format_en_desc string comment 'file format english description',
    format_fr_desc string comment 'file format french description',
    mime_type_name string comment 'mime type name',
    audit_creation_user string comment 'audit creation user',
    audit_creation_date timestamp comment 'audit creation timestamp',
    audit_last_update_user string comment 'audit last update user',
    audit_last_update_date timestamp comment 'audit last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_file_format'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);