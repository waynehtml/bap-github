CREATE TABLE IF NOT EXISTS curated_db.tbl_swift_message_status_dim (
  swift_message_status_skey BIGINT,
  swift_message_status_code INT,
  swift_message_status_edesc STRING COMMENT 'English description',
  swift_message_status_fdesc STRING COMMENT 'French description',
  audit_create_ts TIMESTAMP DEFAULT current_timestamp(),
  audit_last_update_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'SWIFT message status dimension'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);
