-- release-2.2.0: Findur match details on the DVR report (shown in the Excel
-- next to the SWIFT, HABS CLOB and HABS DB columns).
-- Run ONCE per environment: the data_release deploy does not skip
-- FIELD_ALREADY_EXISTS, so a re-run fails if the columns already exist.
-- Requires release-2.0.0 (creates the table) to have run first.
ALTER TABLE curated_db.tbl_dvr_recon_report ADD COLUMNS (
  findur_deal_num STRING COMMENT 'Findur deal (transaction) number matched to the SWIFT row',
  findur_document_num STRING COMMENT 'Findur settlement document number (STLDOC, Released and sent) matched to an outbound SWIFT row',
  findur_transaction_cnt INT COMMENT 'Number of Findur cash settlement rows netted into the match (document rows for DOCUMENT, cash events otherwise)',
  findur_amount DECIMAL(30,2) COMMENT 'Netted Findur amount (whole document for DOCUMENT, signed: negative = payment, positive = receipt)',
  findur_currency_skey BIGINT COMMENT 'Findur settlement currency (same keys as swift_currency_skey)',
  findur_value_date DATE COMMENT 'Findur cash settlement (value) date',
  findur_match_type STRING COMMENT 'DOCUMENT (outbound: deal + Released and sent document number in the SWIFT reference), REFERENCE (outbound fallback: deal number only, documents unavailable) or AMOUNT_DATE (inbound: single currency + date + amount match)'
);
