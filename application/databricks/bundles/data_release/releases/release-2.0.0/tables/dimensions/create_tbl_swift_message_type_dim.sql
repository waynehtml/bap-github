-- Mirrors FMBODW.SWIFT_MESSAGE_TYPE_DIM (SWIFT_MESSAGE_TYPE_SKEY, SWIFT_GEN_MESSAGE_TYPE).
-- Rows are loaded once from FMBODW so the keys match prod (no identity column).
CREATE TABLE IF NOT EXISTS curated_db.tbl_swift_message_type_dim (
  swift_message_type_skey BIGINT NOT NULL COMMENT 'Same value as FMBODW SWIFT_MESSAGE_TYPE_SKEY',
  swift_gen_message_type STRING NOT NULL COMMENT 'For example MT103, MT202',
  audit_create_ts TIMESTAMP DEFAULT current_timestamp(),
  audit_last_update_ts TIMESTAMP DEFAULT current_timestamp()
)
USING delta
COMMENT 'SWIFT message type dimension'
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.enableDeletionVectors' = 'true',
  'delta.feature.allowColumnDefaults' = 'supported'
);

-- One-time load: rows copied from PROD FMBODW.SWIFT_MESSAGE_TYPE_DIM (2026-11-09).
-- Keys must stay identical to FMBODW. Safe to re-run.
MERGE INTO curated_db.tbl_swift_message_type_dim AS target
USING (
  SELECT * FROM VALUES
    (-1, 'Un Known'),
    (1, 'MT103'),
    (2, 'MT202'),
    (3, 'MT202COV'),
    (4, 'MT205'),
    (5, 'MT205COV'),
    (21, 'pacs.008'),
    (22, 'pacs.009'),
    (23, 'pacs.009COV')
  AS source(swift_message_type_skey, swift_gen_message_type)
) AS source
ON target.swift_message_type_skey = source.swift_message_type_skey
WHEN MATCHED AND target.swift_gen_message_type <> source.swift_gen_message_type THEN UPDATE SET
  target.swift_gen_message_type = source.swift_gen_message_type,
  target.audit_last_update_ts = current_timestamp()
WHEN NOT MATCHED THEN INSERT (swift_message_type_skey, swift_gen_message_type)
  VALUES (source.swift_message_type_skey, source.swift_gen_message_type);
