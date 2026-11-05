catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]
spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_account_transfer_type_dim as tgt
using (
    select cast(a.code_pk as string) as account_transfer_type_bid,
           a.attribute_en_name as account_transfer_type_short_en_nm, a.attribute_fr_name as account_transfer_type_short_fr_nm,
           a.attribute_en_desc as account_transfer_type_long_en_nm, a.attribute_fr_desc as account_transfer_type_long_fr_nm,
           a.attribute_en_desc as account_transfer_type_en_desc, a.attribute_fr_desc as account_transfer_type_fr_desc
    from raw_db.corporate_code_table a join raw_db.corporate_code_category_table b
      on a.code_category_fk = b.code_category_pk
    where b.attribute_en_desc = 'Account Transfer Type'
) src on tgt.account_transfer_type_bid = src.account_transfer_type_bid
when matched and not (
    tgt.account_transfer_type_short_en_nm <=> src.account_transfer_type_short_en_nm and tgt.account_transfer_type_short_fr_nm <=> src.account_transfer_type_short_fr_nm
    and tgt.account_transfer_type_long_en_nm <=> src.account_transfer_type_long_en_nm and tgt.account_transfer_type_long_fr_nm <=> src.account_transfer_type_long_fr_nm
    and tgt.account_transfer_type_en_desc <=> src.account_transfer_type_en_desc and tgt.account_transfer_type_fr_desc <=> src.account_transfer_type_fr_desc
) then update set
    account_transfer_type_short_en_nm = src.account_transfer_type_short_en_nm, account_transfer_type_short_fr_nm = src.account_transfer_type_short_fr_nm,
    account_transfer_type_long_en_nm = src.account_transfer_type_long_en_nm, account_transfer_type_long_fr_nm = src.account_transfer_type_long_fr_nm,
    account_transfer_type_en_desc = src.account_transfer_type_en_desc, account_transfer_type_fr_desc = src.account_transfer_type_fr_desc,
    audit_load_id = {job_run_id}, audit_last_update_ts = current_timestamp()
when not matched then insert (
    account_transfer_type_bid, account_transfer_type_short_en_nm, account_transfer_type_short_fr_nm, account_transfer_type_long_en_nm,
    account_transfer_type_long_fr_nm, account_transfer_type_en_desc, account_transfer_type_fr_desc, audit_load_id, audit_create_ts, audit_last_update_ts
) values (
    src.account_transfer_type_bid, src.account_transfer_type_short_en_nm, src.account_transfer_type_short_fr_nm, src.account_transfer_type_long_en_nm,
    src.account_transfer_type_long_fr_nm, src.account_transfer_type_en_desc, src.account_transfer_type_fr_desc, {job_run_id}, current_timestamp(), current_timestamp()
)"""
spark.sql(sql)
spark.sql("""update curated_db.tbl_bo_account_transfer_type_dim set bo_account_transfer_type_dkey = bo_account_transfer_type_skey
             where bo_account_transfer_type_dkey is null""")
