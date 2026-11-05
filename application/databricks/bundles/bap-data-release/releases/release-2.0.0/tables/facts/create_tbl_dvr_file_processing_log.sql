CREATE TABLE IF NOT EXISTS derived_db.tbl_dvr_file_processing_log (
  log_skey BIGINT,
  filename STRING,
  file_type STRING COMMENT 'INBOUND or OUTBOUND',
  file_date DATE,
  file_path STRING,
  processing_status STRING COMMENT 'RECEIVED, VALIDATING, VALID, INVALID, LOADED, RECONCILED, ERROR',
  error_code STRING,
  error_description STRING,
  uploaded_by STRING,
  processing_start_ts TIMESTAMP,
  processing_end_ts TIMESTAMP,
  archive_path STRING,
  audit_create_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'DVR file lifecycle audit trail'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);
