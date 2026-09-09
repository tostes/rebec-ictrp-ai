SELECT 
    -- Campos do ensaio clínico
    ct.date_registration,
    ct.scientific_title,
    ct.scientific_acronym,
    ct.scientific_acronym_expansion,
    ct.primary_sponsor_id,
    ct.public_title,
    ct.acronym,
    ct.acronym_expansion,
    ct.hc_freetext,
    ct.i_freetext,
    ct.inclusion_criteria,
    ct.gender,
    ct.agemin_value,
    ct.agemin_unit,
    ct.agemax_value,
    ct.agemax_unit,
    ct.exclusion_criteria,
    ct.study_design,
    ct.expanded_access_program,
    ct.number_of_arms,
    ct.masking_id,
    ct.phase_id,
    ct.enrollment_start_planned,
    ct.enrollment_start_actual,
    ct.enrollment_end_planned,
    ct.enrollment_end_actual,
    ct.target_sample_size,
    ct.recruitment_status_id,
    ct.utrn_number,
    ct.is_observational,
    ct.outdated,
    ct.enrollment_actual_results,
    ct.results_date_completed,
    ct.results_date_posted,
    ct.results_date_first_publication,
    ct.results_url_link,
    ct.results_baseline_char,
    ct.results_participant_flow,
    ct.results_adverse_events,
    ct.results_outcome_measure,
    ct.results_url_protocol,
    ct.results_summary,
    ct.results_IPD_description,
    ct.url,

    -- Campos do patrocinador primário
    inst.name AS sponsor_name,
    inst.address AS sponsor_address,
    inst.country_id AS sponsor_country_id,
    inst.i_type_id AS sponsor_type_id,
    inst.city AS sponsor_city,
    inst.state AS sponsor_state,
    inst.institution_origin_id AS sponsor_origin_id,

    -- Campos do contato público
    pub_contact.id AS public_contact_id,
    pub_contact.firstname AS public_contact_firstname,
    pub_contact.lastname AS public_contact_lastname,
    pub_contact.email AS public_contact_email,
    pub_contact.telephone AS public_contact_phone,

    -- Campos do contato científico
    sci_contact.id AS scientific_contact_id,
    sci_contact.firstname AS scientific_contact_firstname,
    sci_contact.lastname AS scientific_contact_lastname,
    sci_contact.email AS scientific_contact_email,
    sci_contact.telephone AS scientific_contact_phone,

    -- Campos do contato do site
    site_contact.id AS site_contact_id,
    site_contact.firstname AS site_contact_firstname,
    site_contact.lastname AS site_contact_lastname,
    site_contact.email AS site_contact_email,
    site_contact.telephone AS site_contact_phone,

    -- Campos do contato de revisão ética
    ethics_contact.id AS ethics_contact_id,
    ethics_contact.firstname AS ethics_contact_firstname,
    ethics_contact.lastname AS ethics_contact_lastname,
    ethics_contact.email AS ethics_contact_email,
    ethics_contact.telephone AS ethics_contact_phone,

    -- Campos relacionados a vocabulary
    vst.label AS study_type,
    vsp.label AS study_purpose,
    via.label AS intervention_assignment,
    vms.label AS study_masking,
    val.label AS study_allocation,
    vph.label AS study_phase_label,
    vph.description AS study_phase_description,
    vrs.label AS recruitment_status,
    vtp.label AS time_perspective,
    vos.label AS observational_study_design,
    vipd.label AS ipd_plan,

    -- Campos dos anexos
    att.file AS attach_file,
    att.description AS attach_description,
    att.public AS attach_public,
    att.attach_url AS attach_url,

    -- Contagem de anexos
    (SELECT COUNT(*) 
     FROM reviewapp_attachment att_count
     JOIN reviewapp_submission sub_count ON att_count.submission_id = sub_count.id
     WHERE sub_count.trial_id = ct.id) AS attach_qty

FROM repository_clinicaltrial ct
LEFT JOIN repository_institution inst ON ct.primary_sponsor_id = inst.id
LEFT JOIN vocabulary_studytype vst ON ct.study_type_id = vst.id
LEFT JOIN vocabulary_studypurpose vsp ON ct.purpose_id = vsp.id
LEFT JOIN vocabulary_interventionassigment via ON ct.intervention_assignment_id = via.id
LEFT JOIN vocabulary_studymasking vms ON ct.masking_id = vms.id
LEFT JOIN vocabulary_studyallocation val ON ct.allocation_id = val.id
LEFT JOIN vocabulary_studyphase vph ON ct.phase_id = vph.id
LEFT JOIN vocabulary_recruitmentstatus vrs ON ct.recruitment_status_id = vrs.id
LEFT JOIN vocabulary_timeperspective vtp ON ct.time_perspective_id = vtp.id
LEFT JOIN vocabulary_observationalstudydesign vos ON ct.observational_study_design_id = vos.id
LEFT JOIN vocabulary_ipd_plan vipd ON ct.results_IPD_plan_id = vipd.id

-- Relacionamento com contatos públicos
LEFT JOIN repository_publiccontact rpc ON ct.id = rpc.trial_id
LEFT JOIN repository_contact pub_contact ON rpc.contact_id = pub_contact.id

-- Relacionamento com contatos científicos
LEFT JOIN repository_scientificcontact rsc ON ct.id = rsc.trial_id
LEFT JOIN repository_contact sci_contact ON rsc.contact_id = sci_contact.id

-- Relacionamento com contatos do site
LEFT JOIN repository_sitecontact rsite ON ct.id = rsite.trial_id
LEFT JOIN repository_contact site_contact ON rsite.contact_id = site_contact.id

-- Relacionamento com contatos de revisão ética
LEFT JOIN repository_ethicsreviewcontact reth ON ct.id = reth.trial_id
LEFT JOIN repository_contact ethics_contact ON reth.contact_id = ethics_contact.id

-- Relacionamento com anexos
LEFT JOIN reviewapp_submission sub ON ct.id = sub.trial_id
LEFT JOIN reviewapp_attachment att ON sub.id = att.submission_id

WHERE ct.id = 14843;

