create or replace table bsas_db.tbl_purge_rule (
    srce_sys_id string not null comment 'Source system identifier',
    art_type_id string not null comment 'Artifact type identifier',
    purge_rule_seq_nr int not null comment 'Purge rule sequence number',
    purge_rule_field_name string comment 'Purge rule field name',
    purge_rule_value string comment 'Purge rule value',
    purge_rule_en_desc string comment 'Purge rule English description',
    purge_rule_fr_desc string comment 'Purge rule French description',
    audit_creation_user string comment 'Audit creation user',
    audit_creation_date timestamp comment 'Audit creation timestamp',
    audit_last_update_user string comment 'Audit last update user',
    audit_last_update_date timestamp comment 'Audit last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'
)
using delta
comment 'Purge rule reference table'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);