create or replace table bsas_db.tbl_artifact_keyword (
    srce_sys_id string comment 'source system identifier',
    art_type_id string comment 'artifact type identifier',
    keyw_ordinal_nr smallint comment 'keyword ordinal number',
    keyw_query_name string comment 'keyword query name',
    keyw_datatype string comment 'keyword data type',
    keyw_tag_str string comment 'keyword tag string',
	keyw_srce_data_column_name string comment 'source data column name',
    keyw_srce_data_table_name string comment 'source data table name',
    keyw_en_name string comment 'keyword english name',
    keyw_fr_name string comment 'keyword french name',
    audit_creation_user string comment 'audit creation user',
    audit_creation_date timestamp comment 'audit creation timestamp',
    audit_last_update_user string comment 'audit last update user',
    audit_last_update_date timestamp comment 'audit last update timestamp',
	audit_load_id bigint default 0 comment 'Databricks job run identifier'  
)
using delta
comment 'tbl_artifact_keyword'
tblproperties (
  'delta.columnMapping.mode' = 'name',
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);