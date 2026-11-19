create or replace view bsas_db.vw_bsas_swift  
as  
select     
	artifact_type.art_type_en_name,
	artifact_type.art_type_fr_name,
	archived_artifact.srce_sys_id,   
	archived_artifact.art_type_id,
	archived_artifact.batch_id_process_file,
	archived_artifact.srce_sys_creation_date as created,   
	archived_artifact.purge_forward_date,
	archived_artifact.purge_hold_flag,
	archived_artifact.audit_creation_user,   
	archived_artifact.audit_creation_date,
	archived_artifact.audit_last_update_user,
	archived_artifact.audit_last_update_date,   
	archived_artifact.keyw4_boc_doc_title as title,
	archived_artifact.keyw5_boc_doc_creator as creator,   
	archived_artifact.keyw1_srce_tran_id as uumid,
	archived_artifact.keyw2_srce_tran_effect_date as date_created,   
	archived_artifact.keyw3_srce_prime_party_id as bic,
	archived_artifact.keyw7_value as record_type  
from 
	bsas_db.tbl_artifact_type artifact_type inner join bsas_db.tbl_archived_artifact archived_artifact 
		on artifact_type.art_type_id = archived_artifact.art_type_id
		and artifact_type.srce_sys_id = archived_artifact.srce_sys_id  
where
	(
		upper(archived_artifact.art_type_id) in 
		(
			upper('swiftin'), 
			upper('swiftout'), 
			upper('swift')
		)
	)