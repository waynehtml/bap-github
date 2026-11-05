catalog = job_ctx["catalog"]
job_run_id = job_ctx["job_run_id"]

logger.info("Starting tbl_bo_account_dim build")
logger.info(f"Catalog    : {catalog}")
logger.info(f"Job Run ID : {job_run_id}")

spark.sql(f"USE CATALOG {catalog}")

sql = f"""
merge into curated_db.tbl_bo_account_dim as tgt
using(
    select
        a.account_id                        as account_id,
        accttype.code_constant_id           as account_type_bid,
        accttype.attribute_en_name          as account_type_short_en_nm,
        accttype.attribute_fr_name          as account_type_short_fr_nm,
        accttype.attribute_en_desc          as account_type_long_en_nm,
        accttype.attribute_fr_desc          as account_type_long_fr_nm,
        accttype.attribute_en_desc          as account_type_en_desc,
        accttype.attribute_fr_desc          as account_type_fr_desc,
        a.account_en_name                   as account_en_nm,
        a.account_fr_name                   as account_fr_nm,
        a.account_en_desc                   as account_en_desc,
        a.account_fr_desc                   as account_fr_desc,
        acctformat.code_constant_id         as account_format_bid,
        acctformat.attribute_en_name        as account_format_short_en_nm,
        acctformat.attribute_fr_name        as account_format_short_fr_nm,
        acctformat.attribute_en_desc        as account_format_long_en_nm,
        acctformat.attribute_fr_desc        as account_format_long_fr_nm,
        acctformat.attribute_en_desc        as account_format_en_desc,
        acctformat.attribute_fr_desc        as account_format_fr_desc,
        acctstatus.code_constant_id         as account_status_bid,
        acctstatus.attribute_en_name        as account_status_short_en_nm,
        acctstatus.attribute_fr_name        as account_status_short_fr_nm,
        acctstatus.attribute_en_desc        as account_status_long_en_nm,
        acctstatus.attribute_fr_desc        as account_status_long_fr_nm,
        acctstatus.attribute_en_desc        as account_status_en_desc,
        acctstatus.attribute_fr_desc        as account_status_fr_desc,
        glcategory.code_constant_id         as gl_category_bid,
        glcategory.attribute_en_name        as gl_category_short_en_nm,
        glcategory.attribute_fr_name        as gl_category_short_fr_nm,
        glcategory.attribute_en_desc        as gl_category_long_en_nm,
        glcategory.attribute_fr_desc        as gl_category_long_fr_nm,
        glcategory.attribute_en_desc        as gl_category_en_desc,
        glcategory.attribute_fr_desc        as gl_category_fr_desc,
        a.account_pk                        as rk_account_pk,
        g.gl_account_num                    as gl_account_nb,
        a.creation_date                     as creation_date,
        a.effective_date                    as effective_date,
        a.inactive_date                     as inactive_date,
        comp.comp_account_fk                as rk_comp_account_fk		
    from raw_db.habs_account a
        join raw_db.corporate_code_table accttype
            on accttype.code_pk = a.account_type_fk
        left join raw_db.corporate_code_table acctformat
            on acctformat.code_pk = a.account_format_fk
        left join raw_db.corporate_code_table acctstatus
            on acctstatus.code_pk = a.account_status_fk
        left join raw_db.corporate_code_table glcategory
            on glcategory.code_pk = a.gl_category_fk
        left join raw_db.habs_gl_category g
            on a.gl_category_fk = g.gl_category_pk
        left join raw_db.habs_account_service comp
            on comp.account_fk = a.account_pk
    where 
        comp.service_type_fk = 840
) as src
on (tgt.rk_account_pk = src.rk_account_pk and tgt.bo_account_skey > 0)

when matched then update set   
     account_id                     =   src.account_id,
     account_type_bid               =   src.account_type_bid,
     account_type_short_en_nm       =   src.account_type_short_en_nm,
     account_type_short_fr_nm       =   src.account_type_short_fr_nm,
     account_type_long_fr_nm        =   src.account_type_long_fr_nm,
     account_type_long_en_nm        =   src.account_type_long_en_nm,
     account_type_en_desc           =   src.account_type_en_desc,
     account_type_fr_desc           =   src.account_type_fr_desc,
     account_en_nm                  =   src.account_en_nm,
     account_fr_nm                  =   src.account_fr_nm, 
     account_en_desc                =   src.account_en_desc,
     account_fr_desc                =   src.account_fr_desc,
     account_format_bid             =   src.account_format_bid,
     account_format_short_en_nm     =   src.account_format_short_en_nm,
     account_format_short_fr_nm     =   src.account_format_short_fr_nm,
     account_format_long_en_nm      =   src.account_format_long_en_nm,
     account_format_long_fr_nm      =   src.account_format_long_fr_nm,
     account_format_en_desc         =   src.account_format_en_desc,
     account_format_fr_desc         =   src.account_format_fr_desc,
     account_status_bid             =   src.account_status_bid,
     account_status_short_en_nm     =   src.account_status_short_en_nm,
     account_status_short_fr_nm     =   src.account_status_short_fr_nm,
     account_status_long_en_nm      =   src.account_status_long_en_nm,
     account_status_long_fr_nm      =   src.account_status_long_fr_nm,
     account_status_en_desc         =   src.account_status_en_desc,
     account_status_fr_desc         =   src.account_status_fr_desc,
     gl_category_bid                =   src.gl_category_bid,
     gl_category_short_en_nm        =   src.gl_category_short_en_nm,
     gl_category_short_fr_nm        =   src.gl_category_short_fr_nm,
     gl_category_long_en_nm         =   src.gl_category_long_en_nm,
     gl_category_long_fr_nm         =   src.gl_category_long_fr_nm,
     gl_category_en_desc            =   src.gl_category_en_desc,
     gl_category_fr_desc            =   src.gl_category_fr_desc,
     rk_account_pk                  =   src.rk_account_pk,
     gl_account_nb                  =   src.gl_account_nb,
     creation_date                  =   src.creation_date,
     effective_date                 =   src.effective_date,
     inactive_date                  =   src.inactive_date,
     rk_comp_account_fk				=	src.rk_comp_account_fk,
     audit_load_id                  =   {job_run_id},
     audit_last_update_ts           =   current_timestamp()	 

when not matched then insert (
        account_id,                     account_type_bid,               account_type_short_en_nm,   	account_type_short_fr_nm,
        account_type_long_en_nm,		account_type_long_fr_nm,        account_type_en_desc,       	account_type_fr_desc,
        account_en_nm,                  account_fr_nm,                  account_en_desc,            	account_fr_desc,
        account_format_bid,             account_format_short_en_nm,     account_format_short_fr_nm, 	account_format_long_en_nm,
        account_format_long_fr_nm,      account_format_en_desc,         account_format_fr_desc,     	account_status_bid,
        account_status_short_en_nm,     account_status_short_fr_nm,     account_status_long_en_nm,  	account_status_long_fr_nm,
        account_status_en_desc,         account_status_fr_desc,         gl_category_bid,            	gl_category_short_en_nm,
        gl_category_short_fr_nm,        gl_category_long_en_nm,         gl_category_long_fr_nm,     	gl_category_en_desc,
        gl_category_fr_desc,            rk_account_pk,                  creation_date,              	effective_date,
        inactive_date,                  gl_account_nb,					rk_comp_account_fk,				audit_load_id,					
        audit_create_ts,	            audit_last_update_ts
    ) values
    (
        src.account_id,                 src.account_type_bid,               src.account_type_short_en_nm,   src.account_type_short_fr_nm,
        src.account_type_long_en_nm,    src.account_type_long_fr_nm,	    src.account_type_en_desc,       src.account_type_fr_desc,
        src.account_en_nm,              src.account_fr_nm,                  src.account_en_desc,            src.account_fr_desc,
        src.account_format_bid,         src.account_format_short_en_nm,     src.account_format_short_fr_nm, src.account_format_long_en_nm,
        src.account_format_long_fr_nm,  src.account_format_en_desc,         src.account_format_fr_desc,     src.account_status_bid,
        src.account_status_short_en_nm, src.account_status_short_fr_nm,     src.account_status_long_en_nm,  src.account_status_long_fr_nm,
        src.account_status_en_desc,     src.account_status_fr_desc,         src.gl_category_bid,            src.gl_category_short_en_nm,
        src.gl_category_short_fr_nm,    src.gl_category_long_en_nm,         src.gl_category_long_fr_nm,     src.gl_category_en_desc,
        src.gl_category_fr_desc,        src.rk_account_pk,                  src.creation_date,              src.effective_date,
        src.inactive_date,				src.gl_account_nb,					src.rk_comp_account_fk,			{job_run_id},					
        current_timestamp(),			current_timestamp()					
)
"""


logger.info("Executing MERGE for curated_db.tbl_bo_account_dim")
logger.info(sql)
spark.sql(sql)

sql = """
UPDATE curated_db.tbl_bo_account_dim
SET bo_account_dkey = bo_account_skey
WHERE bo_account_dkey IS NULL
"""
logger.info(sql)
spark.sql(sql)

logger.info("Completed tbl_bo_account_dim build")
