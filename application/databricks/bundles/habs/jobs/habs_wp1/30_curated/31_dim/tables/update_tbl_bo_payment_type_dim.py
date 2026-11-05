catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_payment_type_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

# COMMAND ----------

sql = f"""
merge into curated_db.tbl_bo_payment_type_dim as tgt
using (
    select
        a.code_constant_id  as payment_type_bid,
        a.attribute_en_name as payment_type_short_en_nm,
        a.attribute_fr_name as payment_type_short_fr_nm,
        a.attribute_en_desc as payment_type_long_en_nm,
        a.attribute_fr_desc as payment_type_long_fr_nm,
        a.attribute_en_desc as payment_type_en_desc,
        a.attribute_fr_desc as payment_type_fr_desc
    from
	    raw_db.corporate_code_table a join raw_db.corporate_code_category_table b
		    on a.code_category_fk  = b.code_category_pk
    where
        b.attribute_en_name = 'PAYMENTTYPE'
) as src
on tgt.payment_type_bid = src.PAYMENT_TYPE_BID

when matched then update
set
    tgt.payment_type_short_en_nm    = src.PAYMENT_TYPE_SHORT_EN_NM,
    tgt.payment_type_short_fr_nm    = src.PAYMENT_TYPE_SHORT_FR_NM,
    tgt.payment_type_long_en_nm     = src.PAYMENT_TYPE_LONG_EN_NM,
    tgt.payment_type_long_fr_nm     = src.PAYMENT_TYPE_LONG_FR_NM,
    tgt.payment_type_en_desc        = src.PAYMENT_TYPE_EN_DESC,
    tgt.payment_type_fr_desc        = src.PAYMENT_TYPE_FR_DESC,
    tgt.audit_load_id                  = {job_run_id},
    tgt.audit_last_update_ts               = current_timestamp()

when not matched then
insert (
    payment_type_bid,
    payment_type_short_en_nm,
    payment_type_short_fr_nm,
    payment_type_long_en_nm,
    payment_type_long_fr_nm,
    payment_type_en_desc,
    payment_type_fr_desc,
    audit_load_id,
    audit_last_update_ts
)
values (
    src.PAYMENT_TYPE_BID,
    src.PAYMENT_TYPE_SHORT_EN_NM,
    src.PAYMENT_TYPE_SHORT_FR_NM,
    src.PAYMENT_TYPE_LONG_EN_NM,
    src.PAYMENT_TYPE_LONG_FR_NM,
    src.PAYMENT_TYPE_EN_DESC,
    src.PAYMENT_TYPE_FR_DESC,
    {job_run_id},
    current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_payment_type_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_payment_type_dim
set bo_payment_type_dkey = bo_payment_type_skey where bo_payment_type_dkey is null
"""
logger.info(sql)
spark.sql(sql)
logger.info("Completed tbl_bo_payment_type_dim build")