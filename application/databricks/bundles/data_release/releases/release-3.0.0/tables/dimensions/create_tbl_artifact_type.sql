create or replace table bsas_db.tbl_artifact_type (
    srce_sys_id string comment 'source system identifier',
    art_type_id string comment 'artifact type identifier',
    art_type_en_name string comment 'artifact type english name',
    art_type_fr_name string comment 'artifact type french name',
    art_type_en_desc string comment 'artifact type english description',
    art_type_fr_desc string comment 'artifact type french description',
    art_type_effect_start_date timestamp comment 'artifact type effective start date',
    art_type_effect_end_date timestamp comment 'artifact type effective end date',
    art_type_inp_file_name_prfx string comment 'artifact type input file name prefix',
    art_blob_extract binary comment 'artifact binary extract content',
    rule_capture_date_field_text string comment 'rule capture date field text',
    rule_title_field_text string comment 'rule title field text',
    rule_creator_field_text string comment 'rule creator field text',
    format_id string comment 'format identifier',
    scrty_lvl_type_id string comment 'security level type identifier',
    audit_creation_user string comment 'audit creation user',
    audit_creation_date timestamp comment 'audit creation timestamp',
    audit_last_update_user string comment 'audit last update user',
    audit_last_update_date timestamp comment 'audit last update timestamp',
    xsl_en_name string comment 'xsl english name',
    xsl_fr_name string comment 'xsl french name',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_artifact_type'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);



