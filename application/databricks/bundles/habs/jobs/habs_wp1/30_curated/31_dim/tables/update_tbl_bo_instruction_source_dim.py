catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_instruction_source_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_instruction_source_dim as tgt
using (
    select
        cast(a.code_pk as string)          as instruction_source_bid
        , a.attribute_en_name              as instruction_source_short_en_nm
        , a.attribute_fr_name              as instruction_source_short_fr_nm
        , a.attribute_en_desc              as instruction_source_long_en_nm
        , a.attribute_fr_desc              as instruction_source_long_fr_nm
        , a.attribute_en_desc              as instruction_source_en_desc
        , a.attribute_fr_desc              as instruction_source_fr_desc
    from raw_db.corporate_code_table a
    inner join raw_db.corporate_code_category_table b
        on a.code_category_fk = b.code_category_pk
    where b.attribute_en_desc = 'Instruction Source'
) as src
on tgt.instruction_source_bid = src.INSTRUCTION_SOURCE_BID

when matched and (
    not (tgt.instruction_source_short_en_nm <=> src.INSTRUCTION_SOURCE_SHORT_EN_NM)
    or not (tgt.instruction_source_short_fr_nm <=> src.INSTRUCTION_SOURCE_SHORT_FR_NM)
    or not (tgt.instruction_source_long_en_nm <=> src.INSTRUCTION_SOURCE_LONG_EN_NM)
    or not (tgt.instruction_source_long_fr_nm <=> src.INSTRUCTION_SOURCE_LONG_FR_NM)
    or not (tgt.instruction_source_en_desc <=> src.INSTRUCTION_SOURCE_EN_DESC)
    or not (tgt.instruction_source_fr_desc <=> src.INSTRUCTION_SOURCE_FR_DESC)
)
then update set
    instruction_source_short_en_nm = src.INSTRUCTION_SOURCE_SHORT_EN_NM
    , instruction_source_short_fr_nm = src.INSTRUCTION_SOURCE_SHORT_FR_NM
    , instruction_source_long_en_nm = src.INSTRUCTION_SOURCE_LONG_EN_NM
    , instruction_source_long_fr_nm = src.INSTRUCTION_SOURCE_LONG_FR_NM
    , instruction_source_en_desc = src.INSTRUCTION_SOURCE_EN_DESC
    , instruction_source_fr_desc = src.INSTRUCTION_SOURCE_FR_DESC
    , audit_load_id = {job_run_id}
    , audit_last_update_ts = current_timestamp()

when not matched then
insert (
    instruction_source_bid
    , instruction_source_short_en_nm
    , instruction_source_short_fr_nm
    , instruction_source_long_en_nm
    , instruction_source_long_fr_nm
    , instruction_source_en_desc
    , instruction_source_fr_desc
    , audit_load_id
    , audit_last_update_ts
)
values (
    src.INSTRUCTION_SOURCE_BID
    , src.INSTRUCTION_SOURCE_SHORT_EN_NM
    , src.INSTRUCTION_SOURCE_SHORT_FR_NM
    , src.INSTRUCTION_SOURCE_LONG_EN_NM
    , src.INSTRUCTION_SOURCE_LONG_FR_NM
    , src.INSTRUCTION_SOURCE_EN_DESC
    , src.INSTRUCTION_SOURCE_FR_DESC
    , {job_run_id}
    , current_timestamp()
)
"""

logger.info("Executing MERGE for curated_db.tbl_bo_instruction_source_dim")
logger.info(sql)
spark.sql(sql)

sql = """
update curated_db.tbl_bo_instruction_source_dim
set bo_instruction_source_dkey = bo_instruction_source_skey
where bo_instruction_source_dkey is null
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_instruction_source_dim build")
