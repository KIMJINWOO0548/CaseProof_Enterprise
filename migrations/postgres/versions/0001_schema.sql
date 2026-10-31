-- Frozen PostgreSQL v1 DDL, generated once from G1.2 metadata, never at migration runtime.

CREATE TABLE v1_actor (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	enabled BOOLEAN NOT NULL,
	roles_payload BYTEA NOT NULL,
	CONSTRAINT pk_v1_actor PRIMARY KEY (tenant_id, id)
);

CREATE TABLE v1_adapter_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_adapter_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_adapter_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_adapter_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_adapter_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_approval_envelope (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	change_id VARCHAR NOT NULL,
	preapproval_revision BIGINT NOT NULL,
	approved_revision BIGINT NOT NULL,
	assessment_sha256 VARCHAR NOT NULL,
	release_decision_id VARCHAR NOT NULL,
	release_transition_id VARCHAR NOT NULL,
	release_event_id VARCHAR NOT NULL,
	approver_id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_approval_envelope PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_approval_envelope_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_approval_envelope_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_approval_envelope_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_approval_envelope_preapproval_revision_range CHECK (preapproval_revision BETWEEN 1 AND 9007199254740991),
	CONSTRAINT ck_v1_approval_envelope_approved_revision_range CHECK (approved_revision BETWEEN 1 AND 9007199254740991),
	CONSTRAINT ck_v1_approval_envelope_next_revision CHECK (approved_revision = preapproval_revision + 1),
	CONSTRAINT uq_v1_approval_envelope_tenant_id_change_id UNIQUE (tenant_id, change_id),
	CONSTRAINT uq_v1_approval_envelope_tenant_id_payload_sha256 UNIQUE (tenant_id, payload_sha256)
);

CREATE TABLE v1_assessment (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	change_id VARCHAR NOT NULL,
	preapproval_revision BIGINT NOT NULL,
	selected_run_id VARCHAR NOT NULL,
	source_eligibility_snapshot_id VARCHAR NOT NULL,
	model_id VARCHAR,
	prompt_id VARCHAR,
	candidate_snapshot_id VARCHAR NOT NULL,
	source_bundle_id VARCHAR NOT NULL,
	dataset_version_id VARCHAR NOT NULL,
	suite_version_id VARCHAR NOT NULL,
	evaluator_version_id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_assessment PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_assessment_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_assessment_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_assessment_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_assessment_preapproval_revision_range CHECK (preapproval_revision BETWEEN 1 AND 9007199254740991),
	CONSTRAINT uq_v1_assessment_tenant_id_change_id UNIQUE (tenant_id, change_id),
	CONSTRAINT uq_v1_assessment_tenant_id_payload_sha256 UNIQUE (tenant_id, payload_sha256)
);

CREATE TABLE v1_assessment_decision_ref (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	assessment_id VARCHAR NOT NULL,
	decision_id VARCHAR NOT NULL,
	CONSTRAINT pk_v1_assessment_decision_ref PRIMARY KEY (tenant_id, id),
	CONSTRAINT uq_v1_assessment_decision_ref_tenant_id_assessment_id_d_e9ac UNIQUE (tenant_id, assessment_id, decision_id)
);

CREATE TABLE v1_assessment_run_ref (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	assessment_id VARCHAR NOT NULL,
	run_id VARCHAR NOT NULL,
	CONSTRAINT pk_v1_assessment_run_ref PRIMARY KEY (tenant_id, id),
	CONSTRAINT uq_v1_assessment_run_ref_tenant_id_assessment_id_run_id UNIQUE (tenant_id, assessment_id, run_id)
);

CREATE TABLE v1_assessment_transition_ref (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	assessment_id VARCHAR NOT NULL,
	transition_id VARCHAR NOT NULL,
	event_id VARCHAR NOT NULL,
	CONSTRAINT pk_v1_assessment_transition_ref PRIMARY KEY (tenant_id, id),
	CONSTRAINT uq_v1_assessment_transition_ref_tenant_id_assessment_id_ef96 UNIQUE (tenant_id, assessment_id, transition_id)
);

CREATE TABLE v1_audit_event (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	sequence BIGINT NOT NULL,
	actor_id VARCHAR NOT NULL,
	subject_id VARCHAR NOT NULL,
	transition_id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_audit_event PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_audit_event_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_audit_event_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_audit_event_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_audit_event_sequence_range CHECK (sequence BETWEEN 1 AND 9007199254740991),
	CONSTRAINT uq_v1_audit_event_tenant_id_sequence UNIQUE (tenant_id, sequence),
	CONSTRAINT uq_v1_audit_event_tenant_id_transition_id UNIQUE (tenant_id, transition_id)
);

CREATE TABLE v1_candidate_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	model_id VARCHAR,
	prompt_id VARCHAR,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_candidate_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_candidate_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_candidate_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_candidate_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_change (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	revision BIGINT NOT NULL,
	status VARCHAR NOT NULL,
	approval_envelope_sha256 VARCHAR,
	requester_id VARCHAR NOT NULL,
	owner_id VARCHAR NOT NULL,
	domain_reviewer_id VARCHAR,
	release_approver_id VARCHAR,
	parent_change_id VARCHAR,
	active_run_id VARCHAR,
	assessment_sha256 VARCHAR,
	candidate_snapshot_id VARCHAR NOT NULL,
	source_bundle_id VARCHAR NOT NULL,
	dataset_version_id VARCHAR NOT NULL,
	suite_version_id VARCHAR NOT NULL,
	evaluator_version_id VARCHAR NOT NULL,
	CONSTRAINT pk_v1_change PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_change_revision_range CHECK (revision BETWEEN 0 AND 9007199254740991),
	CONSTRAINT ck_v1_change_projection_state CHECK ((revision = 0 AND status = 'INCOMPLETE') OR (revision > 0 AND status IN ('DRAFT','PENDING_DOMAIN_REVIEW','PENDING_RELEASE','REJECTED','APPROVED_FOR_DEMO')))
);

CREATE TABLE v1_change_revision (
	tenant_id VARCHAR NOT NULL,
	change_id VARCHAR NOT NULL,
	revision BIGINT NOT NULL,
	requester_id VARCHAR NOT NULL,
	owner_id VARCHAR NOT NULL,
	domain_reviewer_id VARCHAR,
	release_approver_id VARCHAR,
	parent_change_id VARCHAR,
	active_run_id VARCHAR,
	assessment_sha256 VARCHAR,
	candidate_snapshot_id VARCHAR NOT NULL,
	source_bundle_id VARCHAR NOT NULL,
	dataset_version_id VARCHAR NOT NULL,
	suite_version_id VARCHAR NOT NULL,
	evaluator_version_id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_change_revision PRIMARY KEY (tenant_id, change_id, revision),
	CONSTRAINT ck_v1_change_revision_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_change_revision_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_change_revision_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_change_revision_revision_range CHECK (revision BETWEEN 1 AND 9007199254740991)
);

CREATE TABLE v1_change_transition (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	change_id VARCHAR NOT NULL,
	revision_from BIGINT NOT NULL,
	revision_to BIGINT NOT NULL,
	actor_id VARCHAR NOT NULL,
	evaluation_run_id VARCHAR,
	decision_id VARCHAR,
	assessment_sha256 VARCHAR,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_change_transition PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_change_transition_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_change_transition_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_change_transition_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_change_transition_revision_from_range CHECK (revision_from BETWEEN 0 AND 9007199254740991),
	CONSTRAINT ck_v1_change_transition_revision_to_range CHECK (revision_to BETWEEN 1 AND 9007199254740991),
	CONSTRAINT ck_v1_change_transition_next_revision CHECK (revision_to = revision_from + 1),
	CONSTRAINT uq_v1_change_transition_tenant_id_change_id_revision_to UNIQUE (tenant_id, change_id, revision_to)
);

CREATE TABLE v1_dataset_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_dataset_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_dataset_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_dataset_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_dataset_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_decision_note (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	change_id VARCHAR NOT NULL,
	stage VARCHAR NOT NULL,
	actor_id VARCHAR NOT NULL,
	input_revision BIGINT NOT NULL,
	output_revision BIGINT NOT NULL,
	assessment_sha256 VARCHAR,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_decision_note PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_decision_note_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_decision_note_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_decision_note_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_decision_note_input_revision_range CHECK (input_revision BETWEEN 1 AND 9007199254740991),
	CONSTRAINT ck_v1_decision_note_output_revision_range CHECK (output_revision BETWEEN 1 AND 9007199254740991),
	CONSTRAINT ck_v1_decision_note_next_revision CHECK (output_revision = input_revision + 1),
	CONSTRAINT ck_v1_decision_note_stage CHECK (stage IN ('DOMAIN','RELEASE')),
	CONSTRAINT uq_v1_decision_note_tenant_id_change_id_stage UNIQUE (tenant_id, change_id, stage)
);

CREATE TABLE v1_evaluation_run (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	change_id VARCHAR NOT NULL,
	recorded_revision BIGINT NOT NULL,
	actor_id VARCHAR NOT NULL,
	adapter_version_id VARCHAR NOT NULL,
	candidate_snapshot_id VARCHAR NOT NULL,
	source_bundle_id VARCHAR NOT NULL,
	dataset_version_id VARCHAR NOT NULL,
	suite_version_id VARCHAR NOT NULL,
	evaluator_version_id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_evaluation_run PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_evaluation_run_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_evaluation_run_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_evaluation_run_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_evaluation_run_recorded_revision_range CHECK (recorded_revision BETWEEN 1 AND 9007199254740991),
	CONSTRAINT uq_v1_evaluation_run_tenant_id_change_id_recorded_revision UNIQUE (tenant_id, change_id, recorded_revision)
);

CREATE TABLE v1_evaluator_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_evaluator_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_evaluator_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_evaluator_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_evaluator_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_idempotency_record (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	actor_id VARCHAR NOT NULL,
	key VARCHAR NOT NULL,
	change_id VARCHAR NOT NULL,
	result_revision BIGINT NOT NULL,
	original_status BIGINT NOT NULL,
	fingerprint_sha256 VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_idempotency_record PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_idempotency_record_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_idempotency_record_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_idempotency_record_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
	CONSTRAINT ck_v1_idempotency_record_result_revision_range CHECK (result_revision BETWEEN 1 AND 9007199254740991),
	CONSTRAINT ck_v1_idempotency_record_success_status CHECK (original_status BETWEEN 200 AND 299),
	CONSTRAINT uq_v1_idempotency_record_tenant_id_actor_id_key UNIQUE (tenant_id, actor_id, key)
);

CREATE TABLE v1_model_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_model_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_model_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_model_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_model_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_policy_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_policy_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_policy_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_policy_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_policy_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_prompt_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_prompt_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_prompt_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_prompt_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_prompt_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_run_source_ref (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	run_id VARCHAR NOT NULL,
	source_id VARCHAR NOT NULL,
	case_id VARCHAR NOT NULL,
	CONSTRAINT pk_v1_run_source_ref PRIMARY KEY (tenant_id, id),
	CONSTRAINT uq_v1_run_source_ref_tenant_id_run_id_case_id_source_id UNIQUE (tenant_id, run_id, case_id, source_id)
);

CREATE TABLE v1_source_bundle (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_source_bundle PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_source_bundle_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_source_bundle_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_source_bundle_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_source_bundle_member (
	tenant_id VARCHAR NOT NULL,
	source_bundle_id VARCHAR NOT NULL,
	source_id VARCHAR NOT NULL,
	policy_id VARCHAR NOT NULL,
	CONSTRAINT pk_v1_source_bundle_member PRIMARY KEY (tenant_id, source_bundle_id, source_id, policy_id)
);

CREATE TABLE v1_source_eligibility_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	source_bundle_id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_source_eligibility_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_source_eligibility_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_source_eligibility_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_source_eligibility_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_source_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_source_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_source_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_source_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_source_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_suite_snapshot (
	tenant_id VARCHAR NOT NULL,
	id VARCHAR NOT NULL,
	schema_version VARCHAR NOT NULL,
	canonical_payload BYTEA NOT NULL,
	payload_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_suite_snapshot PRIMARY KEY (tenant_id, id),
	CONSTRAINT ck_v1_suite_snapshot_schema_nonempty CHECK (length(schema_version) > 0),
	CONSTRAINT ck_v1_suite_snapshot_payload_nonempty CHECK (length(canonical_payload) > 0),
	CONSTRAINT ck_v1_suite_snapshot_hash_hex CHECK (payload_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE v1_tenant (
	id VARCHAR NOT NULL,
	CONSTRAINT pk_v1_tenant PRIMARY KEY (id)
);

CREATE TABLE v1_tenant_audit_head (
	tenant_id VARCHAR NOT NULL,
	sequence BIGINT NOT NULL,
	head_sha256 VARCHAR NOT NULL,
	CONSTRAINT pk_v1_tenant_audit_head PRIMARY KEY (tenant_id),
	CONSTRAINT uq_v1_tenant_audit_head_tenant_id UNIQUE (tenant_id),
	CONSTRAINT ck_v1_tenant_audit_head_sequence_range CHECK (sequence BETWEEN 0 AND 9007199254740991),
	CONSTRAINT ck_v1_tenant_audit_head_head_hex CHECK (head_sha256 ~ '^[0-9a-f]{64}$')
);

ALTER TABLE v1_actor ADD CONSTRAINT fk_v1_actor_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_adapter_snapshot ADD CONSTRAINT fk_v1_adapter_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_approver_id_v1_actor FOREIGN KEY(tenant_id, approver_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_assessment_sha256_v1__9f53 FOREIGN KEY(tenant_id, assessment_sha256) REFERENCES v1_assessment (tenant_id, payload_sha256) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_change_id_approved_re_547d FOREIGN KEY(tenant_id, change_id, approved_revision) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_change_id_preapproval_c258 FOREIGN KEY(tenant_id, change_id, preapproval_revision) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_change_id_v1_change FOREIGN KEY(tenant_id, change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_release_decision_id_v_a381 FOREIGN KEY(tenant_id, release_decision_id) REFERENCES v1_decision_note (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_release_event_id_v1_a_0447 FOREIGN KEY(tenant_id, release_event_id) REFERENCES v1_audit_event (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_release_transition_id_22cb FOREIGN KEY(tenant_id, release_transition_id) REFERENCES v1_change_transition (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_approval_envelope ADD CONSTRAINT fk_v1_approval_envelope_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_candidate_snapshot_id_v1_can_4f61 FOREIGN KEY(tenant_id, candidate_snapshot_id) REFERENCES v1_candidate_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_change_id_preapproval_revisi_c6c4 FOREIGN KEY(tenant_id, change_id, preapproval_revision) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_change_id_v1_change FOREIGN KEY(tenant_id, change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_dataset_version_id_v1_datase_8340 FOREIGN KEY(tenant_id, dataset_version_id) REFERENCES v1_dataset_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_evaluator_version_id_v1_eval_7894 FOREIGN KEY(tenant_id, evaluator_version_id) REFERENCES v1_evaluator_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_model_id_v1_model_snapshot FOREIGN KEY(tenant_id, model_id) REFERENCES v1_model_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_prompt_id_v1_prompt_snapshot FOREIGN KEY(tenant_id, prompt_id) REFERENCES v1_prompt_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_selected_run_id_v1_evaluation_run FOREIGN KEY(tenant_id, selected_run_id) REFERENCES v1_evaluation_run (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_source_bundle_id_v1_source_bundle FOREIGN KEY(tenant_id, source_bundle_id) REFERENCES v1_source_bundle (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_source_eligibility_snapshot__355f FOREIGN KEY(tenant_id, source_eligibility_snapshot_id) REFERENCES v1_source_eligibility_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_suite_version_id_v1_suite_snapshot FOREIGN KEY(tenant_id, suite_version_id) REFERENCES v1_suite_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment ADD CONSTRAINT fk_v1_assessment_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_assessment_decision_ref ADD CONSTRAINT fk_v1_assessment_decision_ref_tenant_id_assessment_id_v_6c98 FOREIGN KEY(tenant_id, assessment_id) REFERENCES v1_assessment (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment_decision_ref ADD CONSTRAINT fk_v1_assessment_decision_ref_tenant_id_decision_id_v1__45a1 FOREIGN KEY(tenant_id, decision_id) REFERENCES v1_decision_note (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment_decision_ref ADD CONSTRAINT fk_v1_assessment_decision_ref_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_assessment_run_ref ADD CONSTRAINT fk_v1_assessment_run_ref_tenant_id_assessment_id_v1_assessment FOREIGN KEY(tenant_id, assessment_id) REFERENCES v1_assessment (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment_run_ref ADD CONSTRAINT fk_v1_assessment_run_ref_tenant_id_run_id_v1_evaluation_run FOREIGN KEY(tenant_id, run_id) REFERENCES v1_evaluation_run (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment_run_ref ADD CONSTRAINT fk_v1_assessment_run_ref_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_assessment_transition_ref ADD CONSTRAINT fk_v1_assessment_transition_ref_tenant_id_assessment_id_8861 FOREIGN KEY(tenant_id, assessment_id) REFERENCES v1_assessment (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment_transition_ref ADD CONSTRAINT fk_v1_assessment_transition_ref_tenant_id_event_id_v1_a_08b3 FOREIGN KEY(tenant_id, event_id) REFERENCES v1_audit_event (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment_transition_ref ADD CONSTRAINT fk_v1_assessment_transition_ref_tenant_id_transition_id_d253 FOREIGN KEY(tenant_id, transition_id) REFERENCES v1_change_transition (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_assessment_transition_ref ADD CONSTRAINT fk_v1_assessment_transition_ref_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_audit_event ADD CONSTRAINT fk_v1_audit_event_tenant_id_actor_id_v1_actor FOREIGN KEY(tenant_id, actor_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_audit_event ADD CONSTRAINT fk_v1_audit_event_tenant_id_subject_id_v1_change FOREIGN KEY(tenant_id, subject_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_audit_event ADD CONSTRAINT fk_v1_audit_event_tenant_id_transition_id_v1_change_transition FOREIGN KEY(tenant_id, transition_id) REFERENCES v1_change_transition (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_audit_event ADD CONSTRAINT fk_v1_audit_event_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_candidate_snapshot ADD CONSTRAINT fk_v1_candidate_snapshot_tenant_id_model_id_v1_model_snapshot FOREIGN KEY(tenant_id, model_id) REFERENCES v1_model_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_candidate_snapshot ADD CONSTRAINT fk_v1_candidate_snapshot_tenant_id_prompt_id_v1_prompt_snapshot FOREIGN KEY(tenant_id, prompt_id) REFERENCES v1_prompt_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_candidate_snapshot ADD CONSTRAINT fk_v1_candidate_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_active_run_id_v1_evaluation_run FOREIGN KEY(tenant_id, active_run_id) REFERENCES v1_evaluation_run (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_approval_envelope_sha256_v1_appr_46a7 FOREIGN KEY(tenant_id, approval_envelope_sha256) REFERENCES v1_approval_envelope (tenant_id, payload_sha256) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_assessment_sha256_v1_assessment FOREIGN KEY(tenant_id, assessment_sha256) REFERENCES v1_assessment (tenant_id, payload_sha256) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_candidate_snapshot_id_v1_candida_cf98 FOREIGN KEY(tenant_id, candidate_snapshot_id) REFERENCES v1_candidate_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_dataset_version_id_v1_dataset_snapshot FOREIGN KEY(tenant_id, dataset_version_id) REFERENCES v1_dataset_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_domain_reviewer_id_v1_actor FOREIGN KEY(tenant_id, domain_reviewer_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_evaluator_version_id_v1_evaluato_85e1 FOREIGN KEY(tenant_id, evaluator_version_id) REFERENCES v1_evaluator_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_owner_id_v1_actor FOREIGN KEY(tenant_id, owner_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_parent_change_id_v1_change FOREIGN KEY(tenant_id, parent_change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_release_approver_id_v1_actor FOREIGN KEY(tenant_id, release_approver_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_requester_id_v1_actor FOREIGN KEY(tenant_id, requester_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_source_bundle_id_v1_source_bundle FOREIGN KEY(tenant_id, source_bundle_id) REFERENCES v1_source_bundle (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_suite_version_id_v1_suite_snapshot FOREIGN KEY(tenant_id, suite_version_id) REFERENCES v1_suite_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change ADD CONSTRAINT fk_v1_change_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_active_run_id_v1_evaluation_run FOREIGN KEY(tenant_id, active_run_id) REFERENCES v1_evaluation_run (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_assessment_sha256_v1_assessment FOREIGN KEY(tenant_id, assessment_sha256) REFERENCES v1_assessment (tenant_id, payload_sha256) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_candidate_snapshot_id_v_87b6 FOREIGN KEY(tenant_id, candidate_snapshot_id) REFERENCES v1_candidate_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_change_id_v1_change FOREIGN KEY(tenant_id, change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_dataset_version_id_v1_d_5b94 FOREIGN KEY(tenant_id, dataset_version_id) REFERENCES v1_dataset_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_domain_reviewer_id_v1_actor FOREIGN KEY(tenant_id, domain_reviewer_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_evaluator_version_id_v1_979f FOREIGN KEY(tenant_id, evaluator_version_id) REFERENCES v1_evaluator_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_owner_id_v1_actor FOREIGN KEY(tenant_id, owner_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_parent_change_id_v1_change FOREIGN KEY(tenant_id, parent_change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_release_approver_id_v1_actor FOREIGN KEY(tenant_id, release_approver_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_requester_id_v1_actor FOREIGN KEY(tenant_id, requester_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_source_bundle_id_v1_sou_137d FOREIGN KEY(tenant_id, source_bundle_id) REFERENCES v1_source_bundle (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_suite_version_id_v1_sui_af9e FOREIGN KEY(tenant_id, suite_version_id) REFERENCES v1_suite_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_revision ADD CONSTRAINT fk_v1_change_revision_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_change_transition ADD CONSTRAINT fk_v1_change_transition_tenant_id_actor_id_v1_actor FOREIGN KEY(tenant_id, actor_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_transition ADD CONSTRAINT fk_v1_change_transition_tenant_id_assessment_sha256_v1__3cfc FOREIGN KEY(tenant_id, assessment_sha256) REFERENCES v1_assessment (tenant_id, payload_sha256) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_transition ADD CONSTRAINT fk_v1_change_transition_tenant_id_change_id_revision_to_102f FOREIGN KEY(tenant_id, change_id, revision_to) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_transition ADD CONSTRAINT fk_v1_change_transition_tenant_id_change_id_v1_change FOREIGN KEY(tenant_id, change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_transition ADD CONSTRAINT fk_v1_change_transition_tenant_id_decision_id_v1_decision_note FOREIGN KEY(tenant_id, decision_id) REFERENCES v1_decision_note (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_transition ADD CONSTRAINT fk_v1_change_transition_tenant_id_evaluation_run_id_v1__9914 FOREIGN KEY(tenant_id, evaluation_run_id) REFERENCES v1_evaluation_run (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_change_transition ADD CONSTRAINT fk_v1_change_transition_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_dataset_snapshot ADD CONSTRAINT fk_v1_dataset_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_decision_note ADD CONSTRAINT fk_v1_decision_note_tenant_id_actor_id_v1_actor FOREIGN KEY(tenant_id, actor_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_decision_note ADD CONSTRAINT fk_v1_decision_note_tenant_id_assessment_sha256_v1_assessment FOREIGN KEY(tenant_id, assessment_sha256) REFERENCES v1_assessment (tenant_id, payload_sha256) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_decision_note ADD CONSTRAINT fk_v1_decision_note_tenant_id_change_id_input_revision__83f0 FOREIGN KEY(tenant_id, change_id, input_revision) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_decision_note ADD CONSTRAINT fk_v1_decision_note_tenant_id_change_id_output_revision_7b47 FOREIGN KEY(tenant_id, change_id, output_revision) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_decision_note ADD CONSTRAINT fk_v1_decision_note_tenant_id_change_id_v1_change FOREIGN KEY(tenant_id, change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_decision_note ADD CONSTRAINT fk_v1_decision_note_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_actor_id_v1_actor FOREIGN KEY(tenant_id, actor_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_adapter_version_id_v1_ad_5c4d FOREIGN KEY(tenant_id, adapter_version_id) REFERENCES v1_adapter_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_candidate_snapshot_id_v1_2fc7 FOREIGN KEY(tenant_id, candidate_snapshot_id) REFERENCES v1_candidate_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_change_id_recorded_revis_3f1d FOREIGN KEY(tenant_id, change_id, recorded_revision) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_change_id_v1_change FOREIGN KEY(tenant_id, change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_dataset_version_id_v1_da_4727 FOREIGN KEY(tenant_id, dataset_version_id) REFERENCES v1_dataset_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_evaluator_version_id_v1__c477 FOREIGN KEY(tenant_id, evaluator_version_id) REFERENCES v1_evaluator_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_source_bundle_id_v1_sour_068d FOREIGN KEY(tenant_id, source_bundle_id) REFERENCES v1_source_bundle (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_suite_version_id_v1_suit_be75 FOREIGN KEY(tenant_id, suite_version_id) REFERENCES v1_suite_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_evaluation_run ADD CONSTRAINT fk_v1_evaluation_run_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_evaluator_snapshot ADD CONSTRAINT fk_v1_evaluator_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_idempotency_record ADD CONSTRAINT fk_v1_idempotency_record_tenant_id_actor_id_v1_actor FOREIGN KEY(tenant_id, actor_id) REFERENCES v1_actor (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_idempotency_record ADD CONSTRAINT fk_v1_idempotency_record_tenant_id_change_id_result_rev_fc89 FOREIGN KEY(tenant_id, change_id, result_revision) REFERENCES v1_change_revision (tenant_id, change_id, revision) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_idempotency_record ADD CONSTRAINT fk_v1_idempotency_record_tenant_id_change_id_v1_change FOREIGN KEY(tenant_id, change_id) REFERENCES v1_change (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_idempotency_record ADD CONSTRAINT fk_v1_idempotency_record_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_model_snapshot ADD CONSTRAINT fk_v1_model_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_policy_snapshot ADD CONSTRAINT fk_v1_policy_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_prompt_snapshot ADD CONSTRAINT fk_v1_prompt_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_run_source_ref ADD CONSTRAINT fk_v1_run_source_ref_tenant_id_run_id_v1_evaluation_run FOREIGN KEY(tenant_id, run_id) REFERENCES v1_evaluation_run (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_run_source_ref ADD CONSTRAINT fk_v1_run_source_ref_tenant_id_source_id_v1_source_snapshot FOREIGN KEY(tenant_id, source_id) REFERENCES v1_source_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_run_source_ref ADD CONSTRAINT fk_v1_run_source_ref_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_source_bundle ADD CONSTRAINT fk_v1_source_bundle_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_source_bundle_member ADD CONSTRAINT fk_v1_source_bundle_member_tenant_id_policy_id_v1_polic_4a84 FOREIGN KEY(tenant_id, policy_id) REFERENCES v1_policy_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_source_bundle_member ADD CONSTRAINT fk_v1_source_bundle_member_tenant_id_source_bundle_id_v_ea25 FOREIGN KEY(tenant_id, source_bundle_id) REFERENCES v1_source_bundle (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_source_bundle_member ADD CONSTRAINT fk_v1_source_bundle_member_tenant_id_source_id_v1_sourc_fb48 FOREIGN KEY(tenant_id, source_id) REFERENCES v1_source_snapshot (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_source_bundle_member ADD CONSTRAINT fk_v1_source_bundle_member_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_source_eligibility_snapshot ADD CONSTRAINT fk_v1_source_eligibility_snapshot_tenant_id_source_bund_f775 FOREIGN KEY(tenant_id, source_bundle_id) REFERENCES v1_source_bundle (tenant_id, id) DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE v1_source_eligibility_snapshot ADD CONSTRAINT fk_v1_source_eligibility_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_source_snapshot ADD CONSTRAINT fk_v1_source_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_suite_snapshot ADD CONSTRAINT fk_v1_suite_snapshot_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_tenant_audit_head ADD CONSTRAINT fk_v1_tenant_audit_head_tenant_id_v1_tenant FOREIGN KEY(tenant_id) REFERENCES v1_tenant (id);

ALTER TABLE v1_actor ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_actor FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_actor USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_adapter_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_adapter_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_adapter_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_approval_envelope ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_approval_envelope FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_approval_envelope USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_assessment ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_assessment FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_assessment USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_assessment_decision_ref ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_assessment_decision_ref FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_assessment_decision_ref USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_assessment_run_ref ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_assessment_run_ref FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_assessment_run_ref USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_assessment_transition_ref ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_assessment_transition_ref FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_assessment_transition_ref USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_audit_event ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_audit_event FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_audit_event USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_candidate_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_candidate_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_candidate_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_change ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_change FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_change USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_change_revision ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_change_revision FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_change_revision USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_change_transition ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_change_transition FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_change_transition USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_dataset_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_dataset_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_dataset_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_decision_note ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_decision_note FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_decision_note USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_evaluation_run ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_evaluation_run FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_evaluation_run USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_evaluator_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_evaluator_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_evaluator_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_idempotency_record ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_idempotency_record FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_idempotency_record USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_model_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_model_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_model_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_policy_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_policy_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_policy_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_prompt_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_prompt_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_prompt_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_run_source_ref ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_run_source_ref FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_run_source_ref USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_source_bundle ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_source_bundle FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_source_bundle USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_source_bundle_member ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_source_bundle_member FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_source_bundle_member USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_source_eligibility_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_source_eligibility_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_source_eligibility_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_source_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_source_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_source_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_suite_snapshot ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_suite_snapshot FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_suite_snapshot USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE v1_tenant ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_tenant FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_tenant USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND id = current_setting('app.tenant_id', true));

ALTER TABLE v1_tenant_audit_head ENABLE ROW LEVEL SECURITY;

ALTER TABLE v1_tenant_audit_head FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON v1_tenant_audit_head USING (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true)) WITH CHECK (current_setting('app.tenant_id', true) ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$' AND tenant_id = current_setting('app.tenant_id', true));
