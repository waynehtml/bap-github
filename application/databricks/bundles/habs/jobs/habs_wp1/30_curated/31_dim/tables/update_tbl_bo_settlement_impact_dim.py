catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]
spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_settlement_impact_dim as tgt
using (
    select cast(a.code_pk as string) as settlement_impact_bid, a.attribute_en_name as settlement_impact_short_en_nm,
           a.attribute_fr_name as settlement_impact_short_fr_nm, a.attribute_en_desc as settlement_impact_long_en_nm,
           a.attribute_fr_desc as settlement_impact_long_fr_nm, a.attribute_en_desc as settlement_impact_en_desc,
           a.attribute_fr_desc as settlement_impact_fr_desc
    from raw_db.corporate_code_table a join raw_db.corporate_code_category_table b on a.code_category_fk = b.code_category_pk
    where b.attribute_en_desc = 'Settlement Impact'
) src on tgt.settlement_impact_bid = src.settlement_impact_bid
when matched and not (
    tgt.settlement_impact_short_en_nm <=> src.settlement_impact_short_en_nm and tgt.settlement_impact_short_fr_nm <=> src.settlement_impact_short_fr_nm
    and tgt.settlement_impact_long_en_nm <=> src.settlement_impact_long_en_nm and tgt.settlement_impact_long_fr_nm <=> src.settlement_impact_long_fr_nm
    and tgt.settlement_impact_en_desc <=> src.settlement_impact_en_desc and tgt.settlement_impact_fr_desc <=> src.settlement_impact_fr_desc
) then update set
    settlement_impact_short_en_nm = src.settlement_impact_short_en_nm, settlement_impact_short_fr_nm = src.settlement_impact_short_fr_nm,
    settlement_impact_long_en_nm = src.settlement_impact_long_en_nm, settlement_impact_long_fr_nm = src.settlement_impact_long_fr_nm,
    settlement_impact_en_desc = src.settlement_impact_en_desc, settlement_impact_fr_desc = src.settlement_impact_fr_desc,
    audit_load_id = {job_run_id}, audit_last_update_ts = current_timestamp()
when not matched then insert (
    settlement_impact_bid, settlement_impact_short_en_nm, settlement_impact_short_fr_nm, settlement_impact_long_en_nm,
    settlement_impact_long_fr_nm, settlement_impact_en_desc, settlement_impact_fr_desc, bo_settlement_impact_dkey,
    md_workflow_execution_skey, md_create_ts, md_last_update_ts, audit_load_id, audit_create_ts, audit_last_update_ts
) values (
    src.settlement_impact_bid, src.settlement_impact_short_en_nm, src.settlement_impact_short_fr_nm, src.settlement_impact_long_en_nm,
    src.settlement_impact_long_fr_nm, src.settlement_impact_en_desc, src.settlement_impact_fr_desc, 0, 0,
    current_timestamp(), current_timestamp(), {job_run_id}, current_timestamp(), current_timestamp()
)"""
spark.sql(sql)
spark.sql("""update curated_db.tbl_bo_settlement_impact_dim set bo_settlement_impact_dkey = bo_settlement_impact_skey
             where bo_settlement_impact_dkey = 0""")
