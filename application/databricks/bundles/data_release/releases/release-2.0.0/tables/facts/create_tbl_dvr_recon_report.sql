-- One row per reconciled transaction for each DVR job run.
-- Written by 07_generate_reports. Replaces the .xlsx/.html report files in the raw volume.
CREATE TABLE IF NOT EXISTS curated_db.tbl_dvr_recon_report (
  report_date DATE COMMENT 'SWIFT business date',
  inbound_outbound_ind STRING COMMENT 'INBOUND or OUTBOUND',
  transaction_reference STRING,
  swift_gen_message_type STRING,
  swift_transaction_cnt INT,
  swift_amount DECIMAL(30,2),
  clob_transaction_cnt INT,
  clob_amount DECIMAL(30,2),
  db_transaction_cnt INT,
  db_amount DECIMAL(30,2),
  recon_result STRING COMMENT 'Success or Warning',
  warning_reason STRING,
  source_filename STRING COMMENT 'Uploaded SWIFT DVR file, NULL for HABS-only rows',
  report_run_date DATE COMMENT 'Date the report was generated',
  audit_run_id BIGINT COMMENT 'Databricks parent job run ID',
  audit_create_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'DVR reconciliation report rows (per job run)'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);
