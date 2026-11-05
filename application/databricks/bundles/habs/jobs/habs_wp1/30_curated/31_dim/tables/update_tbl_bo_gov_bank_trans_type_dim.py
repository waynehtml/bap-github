catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]
spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_gov_bank_trans_type_dim as tgt
using (
    select a.code_constant_id as gov_bank_trans_typ_bid, a.attribute_en_name as gov_bank_trans_typ_short_en_nm,
           a.attribute_fr_name as gov_bank_trans_typ_short_fr_nm, a.attribute_en_desc as gov_bank_trans_typ_long_en_nm,
           a.attribute_fr_desc as gov_bank_trans_typ_long_fr_nm, a.attribute_en_desc as gov_bank_trans_typ_en_desc,
           a.attribute_fr_desc as gov_bank_trans_typ_fr_desc
    from raw_db.corporate_code_table a join raw_db.corporate_code_category_table b on a.code_category_fk = b.code_category_pk
    where b.attribute_en_name = 'GOVBANKTRANSTYPE'
) src on tgt.gov_bank_trans_typ_bid = src.gov_bank_trans_typ_bid
when matched and not (
    tgt.gov_bank_trans_typ_short_en_nm <=> src.gov_bank_trans_typ_short_en_nm and tgt.gov_bank_trans_typ_short_fr_nm <=> src.gov_bank_trans_typ_short_fr_nm
    and tgt.gov_bank_trans_typ_long_en_nm <=> src.gov_bank_trans_typ_long_en_nm and tgt.gov_bank_trans_typ_long_fr_nm <=> src.gov_bank_trans_typ_long_fr_nm
    and tgt.gov_bank_trans_typ_en_desc <=> src.gov_bank_trans_typ_en_desc and tgt.gov_bank_trans_typ_fr_desc <=> src.gov_bank_trans_typ_fr_desc
) then update set
    gov_bank_trans_typ_short_en_nm = src.gov_bank_trans_typ_short_en_nm, gov_bank_trans_typ_short_fr_nm = src.gov_bank_trans_typ_short_fr_nm,
    gov_bank_trans_typ_long_en_nm = src.gov_bank_trans_typ_long_en_nm, gov_bank_trans_typ_long_fr_nm = src.gov_bank_trans_typ_long_fr_nm,
    gov_bank_trans_typ_en_desc = src.gov_bank_trans_typ_en_desc, gov_bank_trans_typ_fr_desc = src.gov_bank_trans_typ_fr_desc,
    audit_load_id = {job_run_id}, audit_last_update_ts = current_timestamp()
when not matched then insert (
    gov_bank_trans_typ_bid, gov_bank_trans_typ_short_en_nm, gov_bank_trans_typ_short_fr_nm, gov_bank_trans_typ_long_en_nm,
    gov_bank_trans_typ_long_fr_nm, gov_bank_trans_typ_en_desc, gov_bank_trans_typ_fr_desc, md_current_ind, md_eff_ts, md_exp_ts,
    md_workflow_execution_skey, md_exp_workflow_execution_skey, md_create_ts, md_last_update_ts, audit_load_id, audit_create_ts, audit_last_update_ts
) values (
    src.gov_bank_trans_typ_bid, src.gov_bank_trans_typ_short_en_nm, src.gov_bank_trans_typ_short_fr_nm, src.gov_bank_trans_typ_long_en_nm,
    src.gov_bank_trans_typ_long_fr_nm, src.gov_bank_trans_typ_en_desc, src.gov_bank_trans_typ_fr_desc, 1, current_timestamp(),
    timestamp('9999-12-31 00:00:00'), 0, 0, current_timestamp(), current_timestamp(), {job_run_id}, current_timestamp(), current_timestamp()
)"""
spark.sql(sql)
spark.sql("""update curated_db.tbl_bo_gov_bank_trans_type_dim set bo_gov_bank_trans_type_dkey = bo_gov_bank_trans_type_skey
             where bo_gov_bank_trans_type_dkey is null""")
