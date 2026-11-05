CREATE TABLE IF NOT EXISTS derived_db.tbl_swift_message_fact (
  swift_message_fact_skey BIGINT,
  md_workflow_execution_skey BIGINT,
  trans_date_id DATE COMMENT 'Daily Period date from SWIFT DVR file',
  trans_utc_date_id DATE COMMENT 'Input Day UTC from SWIFT DVR file',
  swift_message_type_skey BIGINT,
  swift_gen_message_type STRING COMMENT 'MT103, MT202, MT202COV, MT205, MT205COV',
  currency_skey BIGINT,
  currency_code STRING,
  originating_country STRING,
  originating_fi_skey DECIMAL(12,0),
  originating_bic8 STRING,
  originating_bic_name STRING,
  counterparty_fi_skey DECIMAL(12,0),
  counterparty_bic8 STRING,
  counterparty_bic_name STRING,
  beneficiary_fi_skey DECIMAL(12,0),
  beneficiary_bic8 STRING,
  beneficiary_bic_name STRING,
  transaction_reference STRING,
  transactions_received_cnt INT,
  amount_received DECIMAL(20,2),
  amount_received_cad DECIMAL(20,2),
  inbound_outbound_ind STRING COMMENT 'INBOUND or OUTBOUND',
  source_filename STRING,
  source_file_date DATE,
  audit_create_ts TIMESTAMP DEFAULT current_timestamp(),
  audit_last_update_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'SWIFT DVR parsed message fact'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);
