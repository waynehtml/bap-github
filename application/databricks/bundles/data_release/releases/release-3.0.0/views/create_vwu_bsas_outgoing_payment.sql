create or replace view bsas_db.vwu_bsas_outgoing_payment  
as  
select     
	artifact_type.art_type_en_name					as art_type_en_name,
	artifact_type.art_type_fr_name					as art_type_fr_name,
	archived_artifact.srce_sys_id					as srce_sys_id,
	archived_artifact.art_type_id					as art_type_id,
	archived_artifact.batch_id_process_file			as batch_id_process_file,
	archived_artifact.srce_sys_creation_date 		as created,
	archived_artifact.purge_forward_date			as purge_forward_date,
	archived_artifact.purge_hold_flag				as purge_hold_flag,
	archived_artifact.audit_creation_user			as audit_creation_user,
	archived_artifact.audit_creation_date			as audit_creation_date,
	archived_artifact.audit_last_update_user		as audit_last_update_user,
	archived_artifact.audit_last_update_date		as audit_last_update_date,
	archived_artifact.keyw4_boc_doc_title 			as title,   
	archived_artifact.keyw5_boc_doc_creator 		as creator,
	archived_artifact.keyw1_srce_tran_id 			as business_transaction_id,   
	archived_artifact.keyw2_srce_tran_effect_date 	as business_value_date,   
	archived_artifact.keyw3_srce_prime_party_id 	as client_id,
	archived_artifact.keyw6_srce_account_id 		as account_id,   
	archived_artifact.keyw7_value 					as src_reference_num,
	archived_artifact.keyw8_value 					as related_ref,   
	archived_artifact.keyw9_value 					as pcrn  
from         
	bsas_db.tbl_artifact_type artifact_type inner join bsas_db.tbl_archived_artifact archived_artifact 
		on artifact_type.art_type_id = archived_artifact.art_type_id
		and artifact_type.srce_sys_id = archived_artifact.srce_sys_id  
where     
	(
		upper(archived_artifact.art_type_id) = upper('habs302r')
	)