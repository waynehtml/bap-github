-- One row per validation error found in an uploaded SWIFT DVR file.
-- Written by 01_validate_swift_files. Replaces the error_logs CSV files in the raw volume.
CREATE TABLE IF NOT EXISTS standardized_db.tbl_dvr_validation_error_log (
  audit_run_id BIGINT COMMENT 'Databricks parent job run ID',
  filename STRING COMMENT 'Uploaded file name',
  file_type STRING COMMENT 'INBOUND or OUTBOUND',
  file_date DATE COMMENT 'Business date from the file name',
  error_code STRING COMMENT 'For example DVRFNERR001, DVRVALERR001',
  error_description STRING,
  excel_row STRING COMMENT 'Row in the file, or N/A',
  additional_details STRING,
  audit_create_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'DVR file validation errors'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);
