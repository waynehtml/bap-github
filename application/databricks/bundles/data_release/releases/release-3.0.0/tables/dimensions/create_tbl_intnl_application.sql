create or replace table bsas_db.tbl_intnl_application(
    application_id string comment 'application identifier',
    application_login string comment 'application login name',
    application_en_name string comment 'application english name',
    application_fr_name string comment 'application french name',
    application_en_desc string comment 'application english description',
    application_fr_desc string comment 'application french description',
    audit_creation_user string comment 'audit creation user',
    audit_creation_date timestamp comment 'audit creation timestamp',
    audit_last_update_user string comment 'audit last update user',
    audit_last_update_date timestamp comment 'audit last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'Internal application reference table'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);