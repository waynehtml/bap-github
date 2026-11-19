-- release-2.2.0: re-create so SELECT * picks up the findur_* columns
-- (a view's column list is fixed when it is created).
CREATE OR REPLACE VIEW view_db.vwu_swift_habs_recon_results_fact
AS
SELECT *
FROM curated_db.tbl_swift_habs_recon_results_fact;
