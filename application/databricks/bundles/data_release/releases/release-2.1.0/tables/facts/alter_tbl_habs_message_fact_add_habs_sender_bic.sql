-- release-2.1.0: sender BIC on the HABS message fact.
-- Lets 04_reconcile mark HABS rows from internal senders (Receiver General
-- instructions via Viagate, BIC8 PWGSXXW2) as "Out of scope": they are
-- formatted like SWIFT messages but never go over the SWIFT network, so they
-- are never in the SWIFT DVR file (ARM decision, option B).
-- Run ONCE per environment: the data_release deploy does not skip
-- FIELD_ALREADY_EXISTS, so a re-run fails if the columns already exist.
-- Requires release-2.0.0 (creates the table) to have run first.
ALTER TABLE curated_db.tbl_habs_message_fact ADD COLUMNS (
  habs_sender_bic STRING COMMENT 'Sender BIC8 of the HABS message (AppHdr From for pacs, Block 1/2 for MT)'
);
