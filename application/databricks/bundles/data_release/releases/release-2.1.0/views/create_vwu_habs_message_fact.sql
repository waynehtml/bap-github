-- release-2.1.0: re-create so SELECT * picks up habs_sender_bic
-- (a view's column list is fixed when it is created).
CREATE OR REPLACE VIEW view_db.vwu_habs_message_fact
AS
SELECT *
FROM curated_db.tbl_habs_message_fact;
