create or replace table bsas_db.tbl_archived_artifact(
  srce_sys_id string comment 'Source System ID',
  art_type_id string comment 'Art Type ID',
  batch_id_process_file int comment 'Batch file process ID',
  keyw1_srce_tran_id string comment ' Key source transaction ID',
  keyw2_srce_tran_effect_date timestamp comment 'Source transaction effect date',
  keyw3_srce_prime_party_id string comment 'Source prime party ID',
  keyw4_boc_doc_title string comment 'BOC document title',
  keyw5_boc_doc_creator string comment 'BOC document creator',
  keyw6_srce_account_id string comment 'Source account ID',
  keyw7_value string comment 'Key W7 value',
  keyw8_value string comment 'Key W8 value',
  keyw9_value string comment 'Key W9 value',
  keyw10_value string comment 'Key W10 value',
  art_archive_bytes binary comment 'Art archive',
  srce_sys_creation_date timestamp comment 'Source system creation date',
  purge_forward_date timestamp comment 'Purge forward date',
  purge_hold_flag string comment 'Purge hold flag',
  audit_creation_user string comment 'Audit creation user name',
  audit_creation_date timestamp comment 'Audit creation date',
  audit_last_update_user string comment 'Audit last update user',
  audit_last_update_date timestamp comment 'Audit last update date/time',
  audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_archived_artifact'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);