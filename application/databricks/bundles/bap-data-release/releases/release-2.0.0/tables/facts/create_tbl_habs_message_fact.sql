CREATE TABLE IF NOT EXISTS curated_db.tbl_habs_message_fact (
  habs_message_fact_skey BIGINT,
  md_workflow_execution_skey BIGINT,
  trans_date_id DATE,
  trans_utc_date_id DATE,
  application_update_ts TIMESTAMP,
  swift_message_type_skey BIGINT,
  habs_swift_message_code STRING,
  swift_gen_message_type STRING,
  swift_message_status_skey BIGINT,
  currency_skey BIGINT,
  originating_fi_skey BIGINT,
  counterparty_fi_skey BIGINT,
  beneficiary_fi_skey BIGINT,
  transaction_reference STRING,
  amount DECIMAL(20,2),
  amount_cad DECIMAL(20,2),
  habs_outgoing_message_ind INT COMMENT '0=Inbound, 1=Outbound',
  relational_table_ind INT COMMENT '0=CLOB source, 1=Relational source',
  source_message_pk BIGINT,
  audit_create_ts TIMESTAMP DEFAULT current_timestamp(),
  audit_last_update_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'HABS message fact for DVR reconciliation'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);
