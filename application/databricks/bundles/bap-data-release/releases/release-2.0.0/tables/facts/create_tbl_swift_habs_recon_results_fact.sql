CREATE TABLE IF NOT EXISTS derived_db.tbl_swift_habs_recon_results_fact (
  recon_result_skey BIGINT,
  md_workflow_execution_skey BIGINT,
  report_date DATE,
  source_filename STRING COMMENT 'Source SWIFT DVR file for file-level notifications',
  inbound_outbound_ind STRING,
  transaction_reference STRING,
  swift_gen_message_type STRING,
  swift_message_type_skey BIGINT,
  swift_transaction_cnt INT,
  swift_amount DECIMAL(30,2),
  swift_currency_skey BIGINT,
  clob_message_type STRING,
  clob_transaction_cnt INT,
  clob_amount DECIMAL(30,2),
  clob_currency_skey BIGINT,
  clob_application_update_ts TIMESTAMP,
  db_message_type STRING,
  db_transaction_cnt INT,
  db_amount DECIMAL(30,2),
  db_currency_skey BIGINT,
  db_application_update_ts TIMESTAMP,
  recon_result STRING COMMENT 'Success or Warning reconciliation status',
  warning_reason STRING,
  recon_result_code STRING COMMENT 'MATCH, SWIFT_ONLY, HABS_ONLY, AMOUNT_DIFF',
  recon_result_detail STRING,
  audit_create_ts TIMESTAMP DEFAULT current_timestamp(),
  audit_last_update_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'SWIFT vs HABS three-way reconciliation results'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);
