CREATE MATERIALIZED VIEW IF NOT EXISTS view_db.mv_mview1
SCHEDULE CRON '0 0 5 * * ?' AT TIME ZONE 'America/Toronto'
AS
SELECT * from curated_db.dim_table1;

REFRESH MATERIALIZED VIEW view_db.mv_mview1;
