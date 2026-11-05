catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_settlement_mechanism_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_settlement_mechanism_dim as tgt
using (
	select
		cast(code.code_pk as string) as settlement_mech_bid
		, code.attribute_en_name as settlement_mech_short_en_nm
		, code.attribute_fr_name as settlement_mech_short_fr_nm
		, code.attribute_en_desc as settlement_mech_long_en_nm
		, code.attribute_fr_desc as settlement_mech_long_fr_nm
		, code.attribute_en_desc as settlement_mech_en_desc
		, code.attribute_fr_desc as settlement_mech_fr_desc
	from raw_db.corporate_code_table as code
	inner join raw_db.corporate_code_category_table as category
		on code.code_category_fk = category.code_category_pk
	where category.attribute_en_desc = 'Settlement Mechanism'
) as src
on tgt.settlement_mech_bid = src.SETTLEMENT_MECH_BID

when matched and (
	not (tgt.settlement_mech_short_en_nm <=> src.SETTLEMENT_MECH_SHORT_EN_NM)
	or not (tgt.settlement_mech_short_fr_nm <=> src.SETTLEMENT_MECH_SHORT_FR_NM)
	or not (tgt.settlement_mech_long_en_nm <=> src.SETTLEMENT_MECH_LONG_EN_NM)
	or not (tgt.settlement_mech_long_fr_nm <=> src.SETTLEMENT_MECH_LONG_FR_NM)
	or not (tgt.settlement_mech_en_desc <=> src.SETTLEMENT_MECH_EN_DESC)
	or not (tgt.settlement_mech_fr_desc <=> src.SETTLEMENT_MECH_FR_DESC)
)
then update set
	settlement_mech_short_en_nm = src.SETTLEMENT_MECH_SHORT_EN_NM
	, settlement_mech_short_fr_nm = src.SETTLEMENT_MECH_SHORT_FR_NM
	, settlement_mech_long_en_nm = src.SETTLEMENT_MECH_LONG_EN_NM
	, settlement_mech_long_fr_nm = src.SETTLEMENT_MECH_LONG_FR_NM
	, settlement_mech_en_desc = src.SETTLEMENT_MECH_EN_DESC
	, settlement_mech_fr_desc = src.SETTLEMENT_MECH_FR_DESC
	, audit_load_id = {job_run_id}
	, audit_last_update_ts = current_timestamp()

when not matched then
insert (
	settlement_mech_bid
	, settlement_mech_short_en_nm
	, settlement_mech_short_fr_nm
	, settlement_mech_long_en_nm
	, settlement_mech_long_fr_nm
	, settlement_mech_en_desc
	, settlement_mech_fr_desc
	, audit_load_id
	, audit_last_update_ts
)
values (
	src.SETTLEMENT_MECH_BID
	, src.SETTLEMENT_MECH_SHORT_EN_NM
	, src.SETTLEMENT_MECH_SHORT_FR_NM
	, src.SETTLEMENT_MECH_LONG_EN_NM
	, src.SETTLEMENT_MECH_LONG_FR_NM
	, src.SETTLEMENT_MECH_EN_DESC
	, src.SETTLEMENT_MECH_FR_DESC
	, {job_run_id}
	, current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_settlement_mechanism_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_settlement_mechanism_dim
set bo_settlement_mechanism_dkey = bo_settlement_mechanism_skey
where bo_settlement_mechanism_dkey is null
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_settlement_mechanism_dim build")
