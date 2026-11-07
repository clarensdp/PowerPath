CREATE SCHEMA powerpath_runtime_v3090;
CREATE ROLE powerpath_app NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT;

CREATE TABLE powerpath_runtime_v3090.activity (
	id SERIAL, 
	project_id TEXT, 
	action TEXT NOT NULL, 
	object_id TEXT NOT NULL, 
	details_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE powerpath_runtime_v3090.agent_call_log (
	id TEXT, 
	project_id TEXT NOT NULL, 
	meeting_id TEXT NOT NULL, 
	role TEXT NOT NULL, 
	outcome TEXT DEFAULT 'reserved' NOT NULL, 
	usage_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE powerpath_runtime_v3090.geo29_sources (
	id TEXT, 
	name TEXT NOT NULL, 
	state_fips TEXT NOT NULL, 
	county_fips TEXT NOT NULL, 
	source_url TEXT NOT NULL, 
	license_note TEXT NOT NULL, 
	coverage_scope TEXT NOT NULL, 
	provenance TEXT NOT NULL, 
	active_version TEXT, 
	PRIMARY KEY (id)
)

;

CREATE TABLE powerpath_runtime_v3090.projects (
	id TEXT, 
	name TEXT NOT NULL, 
	location TEXT DEFAULT '' NOT NULL, 
	target_mw FLOAT(53) DEFAULT 0 NOT NULL, 
	status TEXT DEFAULT 'Qualify' NOT NULL, 
	description TEXT DEFAULT '' NOT NULL, 
	created_at TEXT NOT NULL, 
	updated_at TEXT NOT NULL, 
	created_by TEXT DEFAULT nullif(current_setting('powerpath.actor_id',true),''), 
	owning_tenant TEXT DEFAULT nullif(current_setting('powerpath.tenant_id',true),''), 
	PRIMARY KEY (id)
)

;

CREATE TABLE powerpath_runtime_v3090.schema_migrations (
	version TEXT, 
	checksum TEXT NOT NULL, 
	applied_at TEXT NOT NULL, 
	PRIMARY KEY (version)
)

;

CREATE TABLE powerpath_runtime_v3090.v27_audit (
	id SERIAL, 
	tenant_id TEXT, 
	actor_id TEXT, 
	action TEXT NOT NULL, 
	object_id TEXT NOT NULL, 
	details TEXT NOT NULL, 
	prev_hash TEXT NOT NULL, 
	entry_hash TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE powerpath_runtime_v3090.v27_tenants (
	id TEXT, 
	name TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE TABLE powerpath_runtime_v3090.v27_users (
	id TEXT, 
	email TEXT NOT NULL, 
	password_hash TEXT NOT NULL, 
	active INTEGER DEFAULT 1 NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)

;

CREATE TABLE powerpath_runtime_v3090.agent_meetings (
	id TEXT, 
	project_id TEXT NOT NULL, 
	mode TEXT NOT NULL, 
	status TEXT NOT NULL, 
	mission TEXT NOT NULL, 
	source_digest TEXT NOT NULL, 
	model TEXT DEFAULT '' NOT NULL, 
	result_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TEXT NOT NULL, 
	completed_at TEXT DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;

CREATE TABLE powerpath_runtime_v3090.agent_ops_config (
	project_id TEXT, 
	enabled INTEGER DEFAULT 0 NOT NULL, 
	mode TEXT DEFAULT 'rules' NOT NULL, 
	updated_at TEXT NOT NULL, 
	PRIMARY KEY (project_id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	CHECK (enabled IN (0,1)), 
	CHECK (mode IN ('rules','live'))
)

;

CREATE TABLE powerpath_runtime_v3090.agent_ops_events (
	id SERIAL, 
	project_id TEXT NOT NULL, 
	object_id TEXT NOT NULL, 
	event_type TEXT NOT NULL, 
	payload_json TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	previous_hash TEXT NOT NULL, 
	event_hash TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX agent_ops_events_project ON powerpath_runtime_v3090.agent_ops_events (project_id, id);

CREATE TABLE powerpath_runtime_v3090.agent_ops_jobs (
	id TEXT, 
	project_id TEXT NOT NULL, 
	role TEXT NOT NULL, 
	task_type TEXT NOT NULL, 
	schedule_key TEXT NOT NULL, 
	mode TEXT NOT NULL, 
	status TEXT DEFAULT 'queued' NOT NULL, 
	attempts INTEGER DEFAULT 0 NOT NULL, 
	max_attempts INTEGER DEFAULT 2 NOT NULL, 
	created_at TEXT NOT NULL, 
	started_at TEXT DEFAULT '' NOT NULL, 
	completed_at TEXT DEFAULT '' NOT NULL, 
	worker_id TEXT DEFAULT '' NOT NULL, 
	lease_until TEXT DEFAULT '' NOT NULL, 
	source_hash TEXT DEFAULT '' NOT NULL, 
	result_json TEXT DEFAULT '{}' NOT NULL, 
	error_code TEXT DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (project_id, schedule_key), 
	CHECK (mode IN ('rules','live')), 
	CHECK (status IN ('queued','running','complete','failed','abandoned'))
)

;
CREATE INDEX agent_ops_jobs_project ON powerpath_runtime_v3090.agent_ops_jobs (project_id, created_at);
CREATE INDEX agent_ops_jobs_queue ON powerpath_runtime_v3090.agent_ops_jobs (status, created_at);

CREATE TABLE powerpath_runtime_v3090.evidence (
	id TEXT, 
	project_id TEXT NOT NULL, 
	title TEXT NOT NULL, 
	category TEXT NOT NULL, 
	evidence_status TEXT DEFAULT 'unverified' NOT NULL, 
	citation TEXT DEFAULT '' NOT NULL, 
	filename TEXT DEFAULT '' NOT NULL, 
	stored_filename TEXT DEFAULT '' NOT NULL, 
	content_hash TEXT DEFAULT '' NOT NULL, 
	bytes INTEGER DEFAULT 0 NOT NULL, 
	notes TEXT DEFAULT '' NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX evidence_project ON powerpath_runtime_v3090.evidence (project_id);

CREATE TABLE powerpath_runtime_v3090.feasibility_v82_runs (
	id TEXT, 
	project_id TEXT NOT NULL, 
	model_version TEXT NOT NULL, 
	mode TEXT NOT NULL, 
	config_sha256 TEXT NOT NULL, 
	input_sha256 TEXT NOT NULL, 
	input_snapshot_json TEXT NOT NULL, 
	output_json TEXT NOT NULL, 
	evidence_json TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX feasibility_v82_project ON powerpath_runtime_v3090.feasibility_v82_runs (project_id, created_at);

CREATE TABLE powerpath_runtime_v3090.geo29_versions (
	id TEXT, 
	source_id TEXT NOT NULL, 
	retrieved_at TEXT NOT NULL, 
	content_hash TEXT NOT NULL, 
	feature_count INTEGER NOT NULL, 
	metadata_json TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(source_id) REFERENCES powerpath_runtime_v3090.geo29_sources (id)
)

;

CREATE TABLE powerpath_runtime_v3090.geographic_assets (
	id TEXT, 
	project_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	asset_type TEXT NOT NULL, 
	latitude FLOAT(53) NOT NULL, 
	longitude FLOAT(53) NOT NULL, 
	source_provider TEXT NOT NULL, 
	source_url TEXT NOT NULL, 
	source_record_id TEXT NOT NULL, 
	vintage TEXT NOT NULL, 
	evidence_level TEXT NOT NULL, 
	attributes_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (project_id, source_provider, source_record_id)
)

;
CREATE INDEX geographic_assets_project ON powerpath_runtime_v3090.geographic_assets (project_id);

CREATE TABLE powerpath_runtime_v3090.intel_snapshots (
	id TEXT, 
	project_id TEXT NOT NULL, 
	source_key TEXT NOT NULL, 
	source_url TEXT NOT NULL, 
	observed_at TEXT NOT NULL, 
	source_published_date TEXT DEFAULT '' NOT NULL, 
	data_sha256 TEXT NOT NULL, 
	record_count INTEGER NOT NULL, 
	import_label TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX intel_snapshots_project ON powerpath_runtime_v3090.intel_snapshots (project_id, source_key, created_at);

CREATE TABLE powerpath_runtime_v3090.parcel_assessments28 (
	project_id TEXT NOT NULL, 
	parcel_id TEXT NOT NULL, 
	factor TEXT NOT NULL, 
	body TEXT NOT NULL, 
	updated_at TEXT NOT NULL, 
	PRIMARY KEY (project_id, parcel_id, factor), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;

CREATE TABLE powerpath_runtime_v3090.parcel_shortlist28 (
	project_id TEXT NOT NULL, 
	parcel_id TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (project_id, parcel_id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;

CREATE TABLE powerpath_runtime_v3090.parcel_tasks28 (
	id SERIAL, 
	project_id TEXT NOT NULL, 
	parcel_id TEXT NOT NULL, 
	title TEXT NOT NULL, 
	owner TEXT NOT NULL, 
	due TEXT, 
	done INTEGER DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;

CREATE TABLE powerpath_runtime_v3090.scenarios (
	id TEXT, 
	project_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	mode TEXT DEFAULT 'underwrite' NOT NULL, 
	config_json TEXT NOT NULL, 
	version INTEGER DEFAULT 1 NOT NULL, 
	created_at TEXT NOT NULL, 
	updated_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (project_id, name)
)

;
CREATE INDEX scenarios_project ON powerpath_runtime_v3090.scenarios (project_id);

CREATE TABLE powerpath_runtime_v3090.v271_inputs (
	id TEXT, 
	project_id TEXT NOT NULL, 
	instrument TEXT NOT NULL, 
	name TEXT NOT NULL, 
	version INTEGER NOT NULL, 
	value_json TEXT NOT NULL, 
	units TEXT NOT NULL, 
	classification TEXT NOT NULL, 
	source_document TEXT, 
	source_locator TEXT, 
	source_date TEXT, 
	document_sha256 TEXT, 
	reviewer TEXT, 
	analyst TEXT, 
	rationale TEXT NOT NULL, 
	dependents_json TEXT NOT NULL, 
	modified_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (project_id, instrument, name, version)
)

;

CREATE TABLE powerpath_runtime_v3090.v27_approvals (
	id TEXT, 
	project_id TEXT NOT NULL, 
	object_type TEXT NOT NULL, 
	object_id TEXT NOT NULL, 
	version TEXT NOT NULL, 
	decision TEXT NOT NULL, 
	actor_id TEXT NOT NULL, 
	reason TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES powerpath_runtime_v3090.v27_users (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (project_id, object_type, object_id, version), 
	CHECK (decision IN ('approved','rejected'))
)

;

CREATE TABLE powerpath_runtime_v3090.v27_memberships (
	user_id TEXT NOT NULL, 
	tenant_id TEXT NOT NULL, 
	role TEXT NOT NULL, 
	PRIMARY KEY (user_id, tenant_id), 
	FOREIGN KEY(tenant_id) REFERENCES powerpath_runtime_v3090.v27_tenants (id), 
	FOREIGN KEY(user_id) REFERENCES powerpath_runtime_v3090.v27_users (id), 
	CHECK (role IN ('viewer','analyst','approver','admin'))
)

;

CREATE TABLE powerpath_runtime_v3090.v27_project_tenants (
	project_id TEXT, 
	tenant_id TEXT NOT NULL, 
	PRIMARY KEY (project_id), 
	FOREIGN KEY(tenant_id) REFERENCES powerpath_runtime_v3090.v27_tenants (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;

CREATE TABLE powerpath_runtime_v3090.v27_sessions (
	token_hash TEXT, 
	user_id TEXT NOT NULL, 
	expires_at TEXT NOT NULL, 
	revoked INTEGER DEFAULT 0 NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES powerpath_runtime_v3090.v27_users (id)
)

;

CREATE TABLE powerpath_runtime_v3090.v27_transactions (
	id TEXT, 
	project_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	issuer TEXT NOT NULL, 
	status TEXT DEFAULT 'PUBLIC_DISCLOSURE_ONLY' NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (project_id, issuer)
)

;

CREATE TABLE powerpath_runtime_v3090.agent_messages (
	id TEXT, 
	meeting_id TEXT NOT NULL, 
	role TEXT NOT NULL, 
	content TEXT NOT NULL, 
	mode TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(meeting_id) REFERENCES powerpath_runtime_v3090.agent_meetings (id)
)

;

CREATE TABLE powerpath_runtime_v3090.agent_ops_calls (
	id TEXT, 
	project_id TEXT NOT NULL, 
	job_id TEXT NOT NULL, 
	attempt INTEGER NOT NULL, 
	state TEXT NOT NULL, 
	usage_json TEXT DEFAULT '{}' NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES powerpath_runtime_v3090.agent_ops_jobs (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (job_id, attempt), 
	CHECK (attempt>=1), 
	CHECK (state IN ('reserved','sent','ok','failed'))
)

;

CREATE TABLE powerpath_runtime_v3090.agent_ops_reviews (
	id TEXT, 
	project_id TEXT NOT NULL, 
	job_id TEXT NOT NULL, 
	artifact_hash TEXT NOT NULL, 
	status TEXT DEFAULT 'pending' NOT NULL, 
	reviewed_by TEXT DEFAULT '' NOT NULL, 
	reason TEXT DEFAULT '' NOT NULL, 
	created_at TEXT NOT NULL, 
	decided_at TEXT DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES powerpath_runtime_v3090.agent_ops_jobs (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id), 
	UNIQUE (job_id), 
	CHECK (status IN ('pending','acknowledged','rejected'))
)

;
CREATE INDEX agent_ops_reviews_pending ON powerpath_runtime_v3090.agent_ops_reviews (project_id, status, created_at);

CREATE TABLE powerpath_runtime_v3090.geo29_parcels (
	rid SERIAL, 
	parcel_key TEXT NOT NULL, 
	workspace_id TEXT NOT NULL, 
	source_id TEXT NOT NULL, 
	version_id TEXT NOT NULL, 
	local_pin TEXT NOT NULL, 
	area_acres FLOAT(53), 
	feature_json TEXT NOT NULL, 
	PRIMARY KEY (rid), 
	FOREIGN KEY(version_id) REFERENCES powerpath_runtime_v3090.geo29_versions (id), 
	FOREIGN KEY(source_id) REFERENCES powerpath_runtime_v3090.geo29_sources (id), 
	UNIQUE (parcel_key, version_id)
)

;
CREATE INDEX geo29_key ON powerpath_runtime_v3090.geo29_parcels (parcel_key);
CREATE INDEX geo29_workspace ON powerpath_runtime_v3090.geo29_parcels (workspace_id);

CREATE TABLE powerpath_runtime_v3090.intel_changes (
	id TEXT, 
	project_id TEXT NOT NULL, 
	snapshot_id TEXT NOT NULL, 
	source_key TEXT NOT NULL, 
	record_id TEXT NOT NULL, 
	change_type TEXT NOT NULL, 
	old_json TEXT, 
	new_json TEXT, 
	delta_json TEXT NOT NULL, 
	review_state TEXT DEFAULT 'open' NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(snapshot_id) REFERENCES powerpath_runtime_v3090.intel_snapshots (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX intel_changes_project ON powerpath_runtime_v3090.intel_changes (project_id, created_at);

CREATE TABLE powerpath_runtime_v3090.intel_records (
	snapshot_id TEXT NOT NULL, 
	record_id TEXT NOT NULL, 
	record_json TEXT NOT NULL, 
	PRIMARY KEY (snapshot_id, record_id), 
	FOREIGN KEY(snapshot_id) REFERENCES powerpath_runtime_v3090.intel_snapshots (id)
)

;

CREATE TABLE powerpath_runtime_v3090.intel_snapshot_raw (
	snapshot_id TEXT, 
	csv_text TEXT NOT NULL, 
	text_sha256 TEXT NOT NULL, 
	PRIMARY KEY (snapshot_id), 
	FOREIGN KEY(snapshot_id) REFERENCES powerpath_runtime_v3090.intel_snapshots (id)
)

;

CREATE TABLE powerpath_runtime_v3090.power_paths (
	id TEXT, 
	project_id TEXT NOT NULL, 
	name TEXT NOT NULL, 
	strategy TEXT NOT NULL, 
	status TEXT DEFAULT 'hypothesis' NOT NULL, 
	capacity_mw FLOAT(53) DEFAULT 0 NOT NULL, 
	power_month INTEGER, 
	latitude FLOAT(53), 
	longitude FLOAT(53), 
	delay_months INTEGER DEFAULT 0 NOT NULL, 
	capex_uplift_pct FLOAT(53) DEFAULT 0 NOT NULL, 
	energy_uplift_pct FLOAT(53) DEFAULT 0 NOT NULL, 
	source_note TEXT DEFAULT '' NOT NULL, 
	evidence_id TEXT, 
	created_at TEXT NOT NULL, 
	updated_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(evidence_id) REFERENCES powerpath_runtime_v3090.evidence (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX power_paths_project ON powerpath_runtime_v3090.power_paths (project_id);

CREATE TABLE powerpath_runtime_v3090.runs (
	id TEXT, 
	scenario_id TEXT NOT NULL, 
	scenario_version INTEGER NOT NULL, 
	mode TEXT NOT NULL, 
	engine_sha256 TEXT NOT NULL, 
	finance_sha256 TEXT NOT NULL, 
	input_json TEXT NOT NULL, 
	summary_json TEXT NOT NULL, 
	rows_json TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	label TEXT DEFAULT 'SCREENING / UNVERIFIED' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(scenario_id) REFERENCES powerpath_runtime_v3090.scenarios (id)
)

;
CREATE INDEX runs_scenario ON powerpath_runtime_v3090.runs (scenario_id, created_at);

CREATE TABLE powerpath_runtime_v3090.v27_transaction_facts (
	id TEXT, 
	transaction_id TEXT NOT NULL, 
	field TEXT NOT NULL, 
	value_json TEXT NOT NULL, 
	unit TEXT NOT NULL, 
	source_url TEXT NOT NULL, 
	source_locator TEXT NOT NULL, 
	verification TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(transaction_id) REFERENCES powerpath_runtime_v3090.v27_transactions (id), 
	UNIQUE (transaction_id, field)
)

;

CREATE TABLE powerpath_runtime_v3090.v27_transaction_gaps (
	id TEXT, 
	transaction_id TEXT NOT NULL, 
	code TEXT NOT NULL, 
	description TEXT NOT NULL, 
	status TEXT DEFAULT 'OPEN' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(transaction_id) REFERENCES powerpath_runtime_v3090.v27_transactions (id), 
	UNIQUE (transaction_id, code)
)

;

CREATE TABLE powerpath_runtime_v3090.geo29_saved_versions (
	project_id TEXT NOT NULL, 
	parcel_id TEXT NOT NULL, 
	record_id INTEGER NOT NULL, 
	PRIMARY KEY (project_id, parcel_id), 
	FOREIGN KEY(record_id) REFERENCES powerpath_runtime_v3090.geo29_parcels (rid), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;

CREATE TABLE powerpath_runtime_v3090.geo30_latest (
	parcel_key TEXT, 
	record_id INTEGER NOT NULL, 
	PRIMARY KEY (parcel_key), 
	FOREIGN KEY(record_id) REFERENCES powerpath_runtime_v3090.geo29_parcels (rid)
)

;

CREATE TABLE powerpath_runtime_v3090.permit_items (
	id TEXT, 
	project_id TEXT NOT NULL, 
	path_id TEXT, 
	title TEXT NOT NULL, 
	kind TEXT NOT NULL, 
	status TEXT DEFAULT 'not_started' NOT NULL, 
	owner TEXT DEFAULT '' NOT NULL, 
	due_month INTEGER, 
	delay_months INTEGER DEFAULT 0 NOT NULL, 
	evidence_id TEXT, 
	detail TEXT DEFAULT '' NOT NULL, 
	created_at TEXT NOT NULL, 
	updated_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(evidence_id) REFERENCES powerpath_runtime_v3090.evidence (id), 
	FOREIGN KEY(path_id) REFERENCES powerpath_runtime_v3090.power_paths (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX permits_project ON powerpath_runtime_v3090.permit_items (project_id);

CREATE TABLE powerpath_runtime_v3090.delivery_milestones (
	id TEXT, 
	project_id TEXT NOT NULL, 
	path_id TEXT NOT NULL, 
	permit_id TEXT, 
	title TEXT NOT NULL, 
	category TEXT NOT NULL, 
	status TEXT NOT NULL, 
	planned_month INTEGER, 
	delay_months INTEGER DEFAULT 0 NOT NULL, 
	predecessor_id TEXT, 
	source_url TEXT DEFAULT '' NOT NULL, 
	source_note TEXT DEFAULT '' NOT NULL, 
	evidence_id TEXT, 
	created_at TEXT NOT NULL, 
	updated_at TEXT NOT NULL, 
	float_months INTEGER DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(evidence_id) REFERENCES powerpath_runtime_v3090.evidence (id), 
	FOREIGN KEY(predecessor_id) REFERENCES powerpath_runtime_v3090.delivery_milestones (id), 
	FOREIGN KEY(permit_id) REFERENCES powerpath_runtime_v3090.permit_items (id), 
	FOREIGN KEY(path_id) REFERENCES powerpath_runtime_v3090.power_paths (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
CREATE INDEX delivery_milestones_path ON powerpath_runtime_v3090.delivery_milestones (path_id);

CREATE TABLE powerpath_runtime_v3090.permit_notes (
	id TEXT, 
	permit_id TEXT NOT NULL, 
	body TEXT NOT NULL, 
	created_at TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(permit_id) REFERENCES powerpath_runtime_v3090.permit_items (id)
)

;

CREATE TABLE powerpath_runtime_v3090.permit_steps (
	id TEXT, 
	permit_id TEXT NOT NULL, 
	title TEXT NOT NULL, 
	is_done INTEGER DEFAULT 0 NOT NULL, 
	sort_index INTEGER DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(permit_id) REFERENCES powerpath_runtime_v3090.permit_items (id)
)

;

CREATE TABLE powerpath_runtime_v3090.intel_proposals (
	id TEXT, 
	project_id TEXT NOT NULL, 
	change_id TEXT NOT NULL, 
	milestone_id TEXT NOT NULL, 
	proposed_delay_months INTEGER NOT NULL, 
	reason TEXT NOT NULL, 
	status TEXT DEFAULT 'pending' NOT NULL, 
	created_at TEXT NOT NULL, 
	decided_at TEXT DEFAULT '' NOT NULL, 
	base_delay_months INTEGER, 
	base_status TEXT DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(milestone_id) REFERENCES powerpath_runtime_v3090.delivery_milestones (id), 
	FOREIGN KEY(change_id) REFERENCES powerpath_runtime_v3090.intel_changes (id), 
	FOREIGN KEY(project_id) REFERENCES powerpath_runtime_v3090.projects (id)
)

;
INSERT INTO powerpath_runtime_v3090."activity" ("id","project_id","action","object_id","details_json","created_at") SELECT "id","project_id","action","object_id","details_json","created_at" FROM powerpath_stage_v3081."activity";
SELECT setval(pg_get_serial_sequence('powerpath_runtime_v3090.activity','id'),COALESCE(MAX("id"),1),MAX("id") IS NOT NULL) FROM powerpath_runtime_v3090."activity";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","action","object_id","details_json","created_at" FROM powerpath_runtime_v3090."activity" EXCEPT ALL SELECT "id","project_id","action","object_id","details_json","created_at" FROM powerpath_stage_v3081."activity") UNION ALL
 (SELECT "id","project_id","action","object_id","details_json","created_at" FROM powerpath_stage_v3081."activity" EXCEPT ALL SELECT "id","project_id","action","object_id","details_json","created_at" FROM powerpath_runtime_v3090."activity")) THEN
 RAISE EXCEPTION 'Source parity failed: activity'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_call_log" ("id","project_id","meeting_id","role","outcome","usage_json","created_at") SELECT "id","project_id","meeting_id","role","outcome","usage_json","created_at" FROM powerpath_stage_v3081."agent_call_log";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","meeting_id","role","outcome","usage_json","created_at" FROM powerpath_runtime_v3090."agent_call_log" EXCEPT ALL SELECT "id","project_id","meeting_id","role","outcome","usage_json","created_at" FROM powerpath_stage_v3081."agent_call_log") UNION ALL
 (SELECT "id","project_id","meeting_id","role","outcome","usage_json","created_at" FROM powerpath_stage_v3081."agent_call_log" EXCEPT ALL SELECT "id","project_id","meeting_id","role","outcome","usage_json","created_at" FROM powerpath_runtime_v3090."agent_call_log")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_call_log'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."geo29_sources" ("id","name","state_fips","county_fips","source_url","license_note","coverage_scope","provenance","active_version") SELECT "id","name","state_fips","county_fips","source_url","license_note","coverage_scope","provenance","active_version" FROM powerpath_stage_v3081."geo29_sources";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","name","state_fips","county_fips","source_url","license_note","coverage_scope","provenance","active_version" FROM powerpath_runtime_v3090."geo29_sources" EXCEPT ALL SELECT "id","name","state_fips","county_fips","source_url","license_note","coverage_scope","provenance","active_version" FROM powerpath_stage_v3081."geo29_sources") UNION ALL
 (SELECT "id","name","state_fips","county_fips","source_url","license_note","coverage_scope","provenance","active_version" FROM powerpath_stage_v3081."geo29_sources" EXCEPT ALL SELECT "id","name","state_fips","county_fips","source_url","license_note","coverage_scope","provenance","active_version" FROM powerpath_runtime_v3090."geo29_sources")) THEN
 RAISE EXCEPTION 'Source parity failed: geo29_sources'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."projects" ("id","name","location","target_mw","status","description","created_at","updated_at") SELECT "id","name","location","target_mw","status","description","created_at","updated_at" FROM powerpath_stage_v3081."projects";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","name","location","target_mw","status","description","created_at","updated_at" FROM powerpath_runtime_v3090."projects" EXCEPT ALL SELECT "id","name","location","target_mw","status","description","created_at","updated_at" FROM powerpath_stage_v3081."projects") UNION ALL
 (SELECT "id","name","location","target_mw","status","description","created_at","updated_at" FROM powerpath_stage_v3081."projects" EXCEPT ALL SELECT "id","name","location","target_mw","status","description","created_at","updated_at" FROM powerpath_runtime_v3090."projects")) THEN
 RAISE EXCEPTION 'Source parity failed: projects'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."schema_migrations" ("version","checksum","applied_at") SELECT "version","checksum","applied_at" FROM powerpath_stage_v3081."schema_migrations";
DO $verify$ BEGIN
 IF EXISTS((SELECT "version","checksum","applied_at" FROM powerpath_runtime_v3090."schema_migrations" EXCEPT ALL SELECT "version","checksum","applied_at" FROM powerpath_stage_v3081."schema_migrations") UNION ALL
 (SELECT "version","checksum","applied_at" FROM powerpath_stage_v3081."schema_migrations" EXCEPT ALL SELECT "version","checksum","applied_at" FROM powerpath_runtime_v3090."schema_migrations")) THEN
 RAISE EXCEPTION 'Source parity failed: schema_migrations'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_audit" ("id","tenant_id","actor_id","action","object_id","details","prev_hash","entry_hash","created_at") SELECT "id","tenant_id","actor_id","action","object_id","details","prev_hash","entry_hash","created_at" FROM powerpath_stage_v3081."v27_audit";
SELECT setval(pg_get_serial_sequence('powerpath_runtime_v3090.v27_audit','id'),COALESCE(MAX("id"),1),MAX("id") IS NOT NULL) FROM powerpath_runtime_v3090."v27_audit";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","tenant_id","actor_id","action","object_id","details","prev_hash","entry_hash","created_at" FROM powerpath_runtime_v3090."v27_audit" EXCEPT ALL SELECT "id","tenant_id","actor_id","action","object_id","details","prev_hash","entry_hash","created_at" FROM powerpath_stage_v3081."v27_audit") UNION ALL
 (SELECT "id","tenant_id","actor_id","action","object_id","details","prev_hash","entry_hash","created_at" FROM powerpath_stage_v3081."v27_audit" EXCEPT ALL SELECT "id","tenant_id","actor_id","action","object_id","details","prev_hash","entry_hash","created_at" FROM powerpath_runtime_v3090."v27_audit")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_audit'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_tenants" ("id","name","created_at") SELECT "id","name","created_at" FROM powerpath_stage_v3081."v27_tenants";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","name","created_at" FROM powerpath_runtime_v3090."v27_tenants" EXCEPT ALL SELECT "id","name","created_at" FROM powerpath_stage_v3081."v27_tenants") UNION ALL
 (SELECT "id","name","created_at" FROM powerpath_stage_v3081."v27_tenants" EXCEPT ALL SELECT "id","name","created_at" FROM powerpath_runtime_v3090."v27_tenants")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_tenants'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_users" ("id","email","password_hash","active","created_at") SELECT "id","email","password_hash","active","created_at" FROM powerpath_stage_v3081."v27_users";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","email","password_hash","active","created_at" FROM powerpath_runtime_v3090."v27_users" EXCEPT ALL SELECT "id","email","password_hash","active","created_at" FROM powerpath_stage_v3081."v27_users") UNION ALL
 (SELECT "id","email","password_hash","active","created_at" FROM powerpath_stage_v3081."v27_users" EXCEPT ALL SELECT "id","email","password_hash","active","created_at" FROM powerpath_runtime_v3090."v27_users")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_users'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_meetings" ("id","project_id","mode","status","mission","source_digest","model","result_json","created_at","completed_at") SELECT "id","project_id","mode","status","mission","source_digest","model","result_json","created_at","completed_at" FROM powerpath_stage_v3081."agent_meetings";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","mode","status","mission","source_digest","model","result_json","created_at","completed_at" FROM powerpath_runtime_v3090."agent_meetings" EXCEPT ALL SELECT "id","project_id","mode","status","mission","source_digest","model","result_json","created_at","completed_at" FROM powerpath_stage_v3081."agent_meetings") UNION ALL
 (SELECT "id","project_id","mode","status","mission","source_digest","model","result_json","created_at","completed_at" FROM powerpath_stage_v3081."agent_meetings" EXCEPT ALL SELECT "id","project_id","mode","status","mission","source_digest","model","result_json","created_at","completed_at" FROM powerpath_runtime_v3090."agent_meetings")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_meetings'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_ops_config" ("project_id","enabled","mode","updated_at") SELECT "project_id","enabled","mode","updated_at" FROM powerpath_stage_v3081."agent_ops_config";
DO $verify$ BEGIN
 IF EXISTS((SELECT "project_id","enabled","mode","updated_at" FROM powerpath_runtime_v3090."agent_ops_config" EXCEPT ALL SELECT "project_id","enabled","mode","updated_at" FROM powerpath_stage_v3081."agent_ops_config") UNION ALL
 (SELECT "project_id","enabled","mode","updated_at" FROM powerpath_stage_v3081."agent_ops_config" EXCEPT ALL SELECT "project_id","enabled","mode","updated_at" FROM powerpath_runtime_v3090."agent_ops_config")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_ops_config'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_ops_events" ("id","project_id","object_id","event_type","payload_json","created_at","previous_hash","event_hash") SELECT "id","project_id","object_id","event_type","payload_json","created_at","previous_hash","event_hash" FROM powerpath_stage_v3081."agent_ops_events";
SELECT setval(pg_get_serial_sequence('powerpath_runtime_v3090.agent_ops_events','id'),COALESCE(MAX("id"),1),MAX("id") IS NOT NULL) FROM powerpath_runtime_v3090."agent_ops_events";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","object_id","event_type","payload_json","created_at","previous_hash","event_hash" FROM powerpath_runtime_v3090."agent_ops_events" EXCEPT ALL SELECT "id","project_id","object_id","event_type","payload_json","created_at","previous_hash","event_hash" FROM powerpath_stage_v3081."agent_ops_events") UNION ALL
 (SELECT "id","project_id","object_id","event_type","payload_json","created_at","previous_hash","event_hash" FROM powerpath_stage_v3081."agent_ops_events" EXCEPT ALL SELECT "id","project_id","object_id","event_type","payload_json","created_at","previous_hash","event_hash" FROM powerpath_runtime_v3090."agent_ops_events")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_ops_events'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_ops_jobs" ("id","project_id","role","task_type","schedule_key","mode","status","attempts","max_attempts","created_at","started_at","completed_at","worker_id","lease_until","source_hash","result_json","error_code") SELECT "id","project_id","role","task_type","schedule_key","mode","status","attempts","max_attempts","created_at","started_at","completed_at","worker_id","lease_until","source_hash","result_json","error_code" FROM powerpath_stage_v3081."agent_ops_jobs";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","role","task_type","schedule_key","mode","status","attempts","max_attempts","created_at","started_at","completed_at","worker_id","lease_until","source_hash","result_json","error_code" FROM powerpath_runtime_v3090."agent_ops_jobs" EXCEPT ALL SELECT "id","project_id","role","task_type","schedule_key","mode","status","attempts","max_attempts","created_at","started_at","completed_at","worker_id","lease_until","source_hash","result_json","error_code" FROM powerpath_stage_v3081."agent_ops_jobs") UNION ALL
 (SELECT "id","project_id","role","task_type","schedule_key","mode","status","attempts","max_attempts","created_at","started_at","completed_at","worker_id","lease_until","source_hash","result_json","error_code" FROM powerpath_stage_v3081."agent_ops_jobs" EXCEPT ALL SELECT "id","project_id","role","task_type","schedule_key","mode","status","attempts","max_attempts","created_at","started_at","completed_at","worker_id","lease_until","source_hash","result_json","error_code" FROM powerpath_runtime_v3090."agent_ops_jobs")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_ops_jobs'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."evidence" ("id","project_id","title","category","evidence_status","citation","filename","stored_filename","content_hash","bytes","notes","created_at") SELECT "id","project_id","title","category","evidence_status","citation","filename","stored_filename","content_hash","bytes","notes","created_at" FROM powerpath_stage_v3081."evidence";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","title","category","evidence_status","citation","filename","stored_filename","content_hash","bytes","notes","created_at" FROM powerpath_runtime_v3090."evidence" EXCEPT ALL SELECT "id","project_id","title","category","evidence_status","citation","filename","stored_filename","content_hash","bytes","notes","created_at" FROM powerpath_stage_v3081."evidence") UNION ALL
 (SELECT "id","project_id","title","category","evidence_status","citation","filename","stored_filename","content_hash","bytes","notes","created_at" FROM powerpath_stage_v3081."evidence" EXCEPT ALL SELECT "id","project_id","title","category","evidence_status","citation","filename","stored_filename","content_hash","bytes","notes","created_at" FROM powerpath_runtime_v3090."evidence")) THEN
 RAISE EXCEPTION 'Source parity failed: evidence'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."feasibility_v82_runs" ("id","project_id","model_version","mode","config_sha256","input_sha256","input_snapshot_json","output_json","evidence_json","created_at") SELECT "id","project_id","model_version","mode","config_sha256","input_sha256","input_snapshot_json","output_json","evidence_json","created_at" FROM powerpath_stage_v3081."feasibility_v82_runs";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","model_version","mode","config_sha256","input_sha256","input_snapshot_json","output_json","evidence_json","created_at" FROM powerpath_runtime_v3090."feasibility_v82_runs" EXCEPT ALL SELECT "id","project_id","model_version","mode","config_sha256","input_sha256","input_snapshot_json","output_json","evidence_json","created_at" FROM powerpath_stage_v3081."feasibility_v82_runs") UNION ALL
 (SELECT "id","project_id","model_version","mode","config_sha256","input_sha256","input_snapshot_json","output_json","evidence_json","created_at" FROM powerpath_stage_v3081."feasibility_v82_runs" EXCEPT ALL SELECT "id","project_id","model_version","mode","config_sha256","input_sha256","input_snapshot_json","output_json","evidence_json","created_at" FROM powerpath_runtime_v3090."feasibility_v82_runs")) THEN
 RAISE EXCEPTION 'Source parity failed: feasibility_v82_runs'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."geo29_versions" ("id","source_id","retrieved_at","content_hash","feature_count","metadata_json") SELECT "id","source_id","retrieved_at","content_hash","feature_count","metadata_json" FROM powerpath_stage_v3081."geo29_versions";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","source_id","retrieved_at","content_hash","feature_count","metadata_json" FROM powerpath_runtime_v3090."geo29_versions" EXCEPT ALL SELECT "id","source_id","retrieved_at","content_hash","feature_count","metadata_json" FROM powerpath_stage_v3081."geo29_versions") UNION ALL
 (SELECT "id","source_id","retrieved_at","content_hash","feature_count","metadata_json" FROM powerpath_stage_v3081."geo29_versions" EXCEPT ALL SELECT "id","source_id","retrieved_at","content_hash","feature_count","metadata_json" FROM powerpath_runtime_v3090."geo29_versions")) THEN
 RAISE EXCEPTION 'Source parity failed: geo29_versions'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."geographic_assets" ("id","project_id","name","asset_type","latitude","longitude","source_provider","source_url","source_record_id","vintage","evidence_level","attributes_json","created_at") SELECT "id","project_id","name","asset_type","latitude","longitude","source_provider","source_url","source_record_id","vintage","evidence_level","attributes_json","created_at" FROM powerpath_stage_v3081."geographic_assets";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","name","asset_type","latitude","longitude","source_provider","source_url","source_record_id","vintage","evidence_level","attributes_json","created_at" FROM powerpath_runtime_v3090."geographic_assets" EXCEPT ALL SELECT "id","project_id","name","asset_type","latitude","longitude","source_provider","source_url","source_record_id","vintage","evidence_level","attributes_json","created_at" FROM powerpath_stage_v3081."geographic_assets") UNION ALL
 (SELECT "id","project_id","name","asset_type","latitude","longitude","source_provider","source_url","source_record_id","vintage","evidence_level","attributes_json","created_at" FROM powerpath_stage_v3081."geographic_assets" EXCEPT ALL SELECT "id","project_id","name","asset_type","latitude","longitude","source_provider","source_url","source_record_id","vintage","evidence_level","attributes_json","created_at" FROM powerpath_runtime_v3090."geographic_assets")) THEN
 RAISE EXCEPTION 'Source parity failed: geographic_assets'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."intel_snapshots" ("id","project_id","source_key","source_url","observed_at","source_published_date","data_sha256","record_count","import_label","created_at") SELECT "id","project_id","source_key","source_url","observed_at","source_published_date","data_sha256","record_count","import_label","created_at" FROM powerpath_stage_v3081."intel_snapshots";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","source_key","source_url","observed_at","source_published_date","data_sha256","record_count","import_label","created_at" FROM powerpath_runtime_v3090."intel_snapshots" EXCEPT ALL SELECT "id","project_id","source_key","source_url","observed_at","source_published_date","data_sha256","record_count","import_label","created_at" FROM powerpath_stage_v3081."intel_snapshots") UNION ALL
 (SELECT "id","project_id","source_key","source_url","observed_at","source_published_date","data_sha256","record_count","import_label","created_at" FROM powerpath_stage_v3081."intel_snapshots" EXCEPT ALL SELECT "id","project_id","source_key","source_url","observed_at","source_published_date","data_sha256","record_count","import_label","created_at" FROM powerpath_runtime_v3090."intel_snapshots")) THEN
 RAISE EXCEPTION 'Source parity failed: intel_snapshots'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."parcel_assessments28" ("project_id","parcel_id","factor","body","updated_at") SELECT "project_id","parcel_id","factor","body","updated_at" FROM powerpath_stage_v3081."parcel_assessments28";
DO $verify$ BEGIN
 IF EXISTS((SELECT "project_id","parcel_id","factor","body","updated_at" FROM powerpath_runtime_v3090."parcel_assessments28" EXCEPT ALL SELECT "project_id","parcel_id","factor","body","updated_at" FROM powerpath_stage_v3081."parcel_assessments28") UNION ALL
 (SELECT "project_id","parcel_id","factor","body","updated_at" FROM powerpath_stage_v3081."parcel_assessments28" EXCEPT ALL SELECT "project_id","parcel_id","factor","body","updated_at" FROM powerpath_runtime_v3090."parcel_assessments28")) THEN
 RAISE EXCEPTION 'Source parity failed: parcel_assessments28'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."parcel_shortlist28" ("project_id","parcel_id","created_at") SELECT "project_id","parcel_id","created_at" FROM powerpath_stage_v3081."parcel_shortlist28";
DO $verify$ BEGIN
 IF EXISTS((SELECT "project_id","parcel_id","created_at" FROM powerpath_runtime_v3090."parcel_shortlist28" EXCEPT ALL SELECT "project_id","parcel_id","created_at" FROM powerpath_stage_v3081."parcel_shortlist28") UNION ALL
 (SELECT "project_id","parcel_id","created_at" FROM powerpath_stage_v3081."parcel_shortlist28" EXCEPT ALL SELECT "project_id","parcel_id","created_at" FROM powerpath_runtime_v3090."parcel_shortlist28")) THEN
 RAISE EXCEPTION 'Source parity failed: parcel_shortlist28'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."parcel_tasks28" ("id","project_id","parcel_id","title","owner","due","done") SELECT "id","project_id","parcel_id","title","owner","due","done" FROM powerpath_stage_v3081."parcel_tasks28";
SELECT setval(pg_get_serial_sequence('powerpath_runtime_v3090.parcel_tasks28','id'),COALESCE(MAX("id"),1),MAX("id") IS NOT NULL) FROM powerpath_runtime_v3090."parcel_tasks28";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","parcel_id","title","owner","due","done" FROM powerpath_runtime_v3090."parcel_tasks28" EXCEPT ALL SELECT "id","project_id","parcel_id","title","owner","due","done" FROM powerpath_stage_v3081."parcel_tasks28") UNION ALL
 (SELECT "id","project_id","parcel_id","title","owner","due","done" FROM powerpath_stage_v3081."parcel_tasks28" EXCEPT ALL SELECT "id","project_id","parcel_id","title","owner","due","done" FROM powerpath_runtime_v3090."parcel_tasks28")) THEN
 RAISE EXCEPTION 'Source parity failed: parcel_tasks28'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."scenarios" ("id","project_id","name","mode","config_json","version","created_at","updated_at") SELECT "id","project_id","name","mode","config_json","version","created_at","updated_at" FROM powerpath_stage_v3081."scenarios";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","name","mode","config_json","version","created_at","updated_at" FROM powerpath_runtime_v3090."scenarios" EXCEPT ALL SELECT "id","project_id","name","mode","config_json","version","created_at","updated_at" FROM powerpath_stage_v3081."scenarios") UNION ALL
 (SELECT "id","project_id","name","mode","config_json","version","created_at","updated_at" FROM powerpath_stage_v3081."scenarios" EXCEPT ALL SELECT "id","project_id","name","mode","config_json","version","created_at","updated_at" FROM powerpath_runtime_v3090."scenarios")) THEN
 RAISE EXCEPTION 'Source parity failed: scenarios'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v271_inputs" ("id","project_id","instrument","name","version","value_json","units","classification","source_document","source_locator","source_date","document_sha256","reviewer","analyst","rationale","dependents_json","modified_at") SELECT "id","project_id","instrument","name","version","value_json","units","classification","source_document","source_locator","source_date","document_sha256","reviewer","analyst","rationale","dependents_json","modified_at" FROM powerpath_stage_v3081."v271_inputs";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","instrument","name","version","value_json","units","classification","source_document","source_locator","source_date","document_sha256","reviewer","analyst","rationale","dependents_json","modified_at" FROM powerpath_runtime_v3090."v271_inputs" EXCEPT ALL SELECT "id","project_id","instrument","name","version","value_json","units","classification","source_document","source_locator","source_date","document_sha256","reviewer","analyst","rationale","dependents_json","modified_at" FROM powerpath_stage_v3081."v271_inputs") UNION ALL
 (SELECT "id","project_id","instrument","name","version","value_json","units","classification","source_document","source_locator","source_date","document_sha256","reviewer","analyst","rationale","dependents_json","modified_at" FROM powerpath_stage_v3081."v271_inputs" EXCEPT ALL SELECT "id","project_id","instrument","name","version","value_json","units","classification","source_document","source_locator","source_date","document_sha256","reviewer","analyst","rationale","dependents_json","modified_at" FROM powerpath_runtime_v3090."v271_inputs")) THEN
 RAISE EXCEPTION 'Source parity failed: v271_inputs'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_approvals" ("id","project_id","object_type","object_id","version","decision","actor_id","reason","created_at") SELECT "id","project_id","object_type","object_id","version","decision","actor_id","reason","created_at" FROM powerpath_stage_v3081."v27_approvals";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","object_type","object_id","version","decision","actor_id","reason","created_at" FROM powerpath_runtime_v3090."v27_approvals" EXCEPT ALL SELECT "id","project_id","object_type","object_id","version","decision","actor_id","reason","created_at" FROM powerpath_stage_v3081."v27_approvals") UNION ALL
 (SELECT "id","project_id","object_type","object_id","version","decision","actor_id","reason","created_at" FROM powerpath_stage_v3081."v27_approvals" EXCEPT ALL SELECT "id","project_id","object_type","object_id","version","decision","actor_id","reason","created_at" FROM powerpath_runtime_v3090."v27_approvals")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_approvals'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_memberships" ("user_id","tenant_id","role") SELECT "user_id","tenant_id","role" FROM powerpath_stage_v3081."v27_memberships";
DO $verify$ BEGIN
 IF EXISTS((SELECT "user_id","tenant_id","role" FROM powerpath_runtime_v3090."v27_memberships" EXCEPT ALL SELECT "user_id","tenant_id","role" FROM powerpath_stage_v3081."v27_memberships") UNION ALL
 (SELECT "user_id","tenant_id","role" FROM powerpath_stage_v3081."v27_memberships" EXCEPT ALL SELECT "user_id","tenant_id","role" FROM powerpath_runtime_v3090."v27_memberships")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_memberships'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_project_tenants" ("project_id","tenant_id") SELECT "project_id","tenant_id" FROM powerpath_stage_v3081."v27_project_tenants";
DO $verify$ BEGIN
 IF EXISTS((SELECT "project_id","tenant_id" FROM powerpath_runtime_v3090."v27_project_tenants" EXCEPT ALL SELECT "project_id","tenant_id" FROM powerpath_stage_v3081."v27_project_tenants") UNION ALL
 (SELECT "project_id","tenant_id" FROM powerpath_stage_v3081."v27_project_tenants" EXCEPT ALL SELECT "project_id","tenant_id" FROM powerpath_runtime_v3090."v27_project_tenants")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_project_tenants'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_sessions" ("token_hash","user_id","expires_at","revoked") SELECT "token_hash","user_id","expires_at","revoked" FROM powerpath_stage_v3081."v27_sessions";
DO $verify$ BEGIN
 IF EXISTS((SELECT "token_hash","user_id","expires_at","revoked" FROM powerpath_runtime_v3090."v27_sessions" EXCEPT ALL SELECT "token_hash","user_id","expires_at","revoked" FROM powerpath_stage_v3081."v27_sessions") UNION ALL
 (SELECT "token_hash","user_id","expires_at","revoked" FROM powerpath_stage_v3081."v27_sessions" EXCEPT ALL SELECT "token_hash","user_id","expires_at","revoked" FROM powerpath_runtime_v3090."v27_sessions")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_sessions'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_transactions" ("id","project_id","name","issuer","status","created_at") SELECT "id","project_id","name","issuer","status","created_at" FROM powerpath_stage_v3081."v27_transactions";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","name","issuer","status","created_at" FROM powerpath_runtime_v3090."v27_transactions" EXCEPT ALL SELECT "id","project_id","name","issuer","status","created_at" FROM powerpath_stage_v3081."v27_transactions") UNION ALL
 (SELECT "id","project_id","name","issuer","status","created_at" FROM powerpath_stage_v3081."v27_transactions" EXCEPT ALL SELECT "id","project_id","name","issuer","status","created_at" FROM powerpath_runtime_v3090."v27_transactions")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_transactions'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_messages" ("id","meeting_id","role","content","mode","created_at") SELECT "id","meeting_id","role","content","mode","created_at" FROM powerpath_stage_v3081."agent_messages";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","meeting_id","role","content","mode","created_at" FROM powerpath_runtime_v3090."agent_messages" EXCEPT ALL SELECT "id","meeting_id","role","content","mode","created_at" FROM powerpath_stage_v3081."agent_messages") UNION ALL
 (SELECT "id","meeting_id","role","content","mode","created_at" FROM powerpath_stage_v3081."agent_messages" EXCEPT ALL SELECT "id","meeting_id","role","content","mode","created_at" FROM powerpath_runtime_v3090."agent_messages")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_messages'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_ops_calls" ("id","project_id","job_id","attempt","state","usage_json","created_at") SELECT "id","project_id","job_id","attempt","state","usage_json","created_at" FROM powerpath_stage_v3081."agent_ops_calls";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","job_id","attempt","state","usage_json","created_at" FROM powerpath_runtime_v3090."agent_ops_calls" EXCEPT ALL SELECT "id","project_id","job_id","attempt","state","usage_json","created_at" FROM powerpath_stage_v3081."agent_ops_calls") UNION ALL
 (SELECT "id","project_id","job_id","attempt","state","usage_json","created_at" FROM powerpath_stage_v3081."agent_ops_calls" EXCEPT ALL SELECT "id","project_id","job_id","attempt","state","usage_json","created_at" FROM powerpath_runtime_v3090."agent_ops_calls")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_ops_calls'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."agent_ops_reviews" ("id","project_id","job_id","artifact_hash","status","reviewed_by","reason","created_at","decided_at") SELECT "id","project_id","job_id","artifact_hash","status","reviewed_by","reason","created_at","decided_at" FROM powerpath_stage_v3081."agent_ops_reviews";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","job_id","artifact_hash","status","reviewed_by","reason","created_at","decided_at" FROM powerpath_runtime_v3090."agent_ops_reviews" EXCEPT ALL SELECT "id","project_id","job_id","artifact_hash","status","reviewed_by","reason","created_at","decided_at" FROM powerpath_stage_v3081."agent_ops_reviews") UNION ALL
 (SELECT "id","project_id","job_id","artifact_hash","status","reviewed_by","reason","created_at","decided_at" FROM powerpath_stage_v3081."agent_ops_reviews" EXCEPT ALL SELECT "id","project_id","job_id","artifact_hash","status","reviewed_by","reason","created_at","decided_at" FROM powerpath_runtime_v3090."agent_ops_reviews")) THEN
 RAISE EXCEPTION 'Source parity failed: agent_ops_reviews'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."geo29_parcels" ("rid","parcel_key","workspace_id","source_id","version_id","local_pin","area_acres","feature_json") SELECT "rid","parcel_key","workspace_id","source_id","version_id","local_pin","area_acres","feature_json" FROM powerpath_stage_v3081."geo29_parcels";
SELECT setval(pg_get_serial_sequence('powerpath_runtime_v3090.geo29_parcels','rid'),COALESCE(MAX("rid"),1),MAX("rid") IS NOT NULL) FROM powerpath_runtime_v3090."geo29_parcels";
DO $verify$ BEGIN
 IF EXISTS((SELECT "rid","parcel_key","workspace_id","source_id","version_id","local_pin","area_acres","feature_json" FROM powerpath_runtime_v3090."geo29_parcels" EXCEPT ALL SELECT "rid","parcel_key","workspace_id","source_id","version_id","local_pin","area_acres","feature_json" FROM powerpath_stage_v3081."geo29_parcels") UNION ALL
 (SELECT "rid","parcel_key","workspace_id","source_id","version_id","local_pin","area_acres","feature_json" FROM powerpath_stage_v3081."geo29_parcels" EXCEPT ALL SELECT "rid","parcel_key","workspace_id","source_id","version_id","local_pin","area_acres","feature_json" FROM powerpath_runtime_v3090."geo29_parcels")) THEN
 RAISE EXCEPTION 'Source parity failed: geo29_parcels'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."intel_changes" ("id","project_id","snapshot_id","source_key","record_id","change_type","old_json","new_json","delta_json","review_state","created_at") SELECT "id","project_id","snapshot_id","source_key","record_id","change_type","old_json","new_json","delta_json","review_state","created_at" FROM powerpath_stage_v3081."intel_changes";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","snapshot_id","source_key","record_id","change_type","old_json","new_json","delta_json","review_state","created_at" FROM powerpath_runtime_v3090."intel_changes" EXCEPT ALL SELECT "id","project_id","snapshot_id","source_key","record_id","change_type","old_json","new_json","delta_json","review_state","created_at" FROM powerpath_stage_v3081."intel_changes") UNION ALL
 (SELECT "id","project_id","snapshot_id","source_key","record_id","change_type","old_json","new_json","delta_json","review_state","created_at" FROM powerpath_stage_v3081."intel_changes" EXCEPT ALL SELECT "id","project_id","snapshot_id","source_key","record_id","change_type","old_json","new_json","delta_json","review_state","created_at" FROM powerpath_runtime_v3090."intel_changes")) THEN
 RAISE EXCEPTION 'Source parity failed: intel_changes'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."intel_records" ("snapshot_id","record_id","record_json") SELECT "snapshot_id","record_id","record_json" FROM powerpath_stage_v3081."intel_records";
DO $verify$ BEGIN
 IF EXISTS((SELECT "snapshot_id","record_id","record_json" FROM powerpath_runtime_v3090."intel_records" EXCEPT ALL SELECT "snapshot_id","record_id","record_json" FROM powerpath_stage_v3081."intel_records") UNION ALL
 (SELECT "snapshot_id","record_id","record_json" FROM powerpath_stage_v3081."intel_records" EXCEPT ALL SELECT "snapshot_id","record_id","record_json" FROM powerpath_runtime_v3090."intel_records")) THEN
 RAISE EXCEPTION 'Source parity failed: intel_records'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."intel_snapshot_raw" ("snapshot_id","csv_text","text_sha256") SELECT "snapshot_id","csv_text","text_sha256" FROM powerpath_stage_v3081."intel_snapshot_raw";
DO $verify$ BEGIN
 IF EXISTS((SELECT "snapshot_id","csv_text","text_sha256" FROM powerpath_runtime_v3090."intel_snapshot_raw" EXCEPT ALL SELECT "snapshot_id","csv_text","text_sha256" FROM powerpath_stage_v3081."intel_snapshot_raw") UNION ALL
 (SELECT "snapshot_id","csv_text","text_sha256" FROM powerpath_stage_v3081."intel_snapshot_raw" EXCEPT ALL SELECT "snapshot_id","csv_text","text_sha256" FROM powerpath_runtime_v3090."intel_snapshot_raw")) THEN
 RAISE EXCEPTION 'Source parity failed: intel_snapshot_raw'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."power_paths" ("id","project_id","name","strategy","status","capacity_mw","power_month","latitude","longitude","delay_months","capex_uplift_pct","energy_uplift_pct","source_note","evidence_id","created_at","updated_at") SELECT "id","project_id","name","strategy","status","capacity_mw","power_month","latitude","longitude","delay_months","capex_uplift_pct","energy_uplift_pct","source_note","evidence_id","created_at","updated_at" FROM powerpath_stage_v3081."power_paths";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","name","strategy","status","capacity_mw","power_month","latitude","longitude","delay_months","capex_uplift_pct","energy_uplift_pct","source_note","evidence_id","created_at","updated_at" FROM powerpath_runtime_v3090."power_paths" EXCEPT ALL SELECT "id","project_id","name","strategy","status","capacity_mw","power_month","latitude","longitude","delay_months","capex_uplift_pct","energy_uplift_pct","source_note","evidence_id","created_at","updated_at" FROM powerpath_stage_v3081."power_paths") UNION ALL
 (SELECT "id","project_id","name","strategy","status","capacity_mw","power_month","latitude","longitude","delay_months","capex_uplift_pct","energy_uplift_pct","source_note","evidence_id","created_at","updated_at" FROM powerpath_stage_v3081."power_paths" EXCEPT ALL SELECT "id","project_id","name","strategy","status","capacity_mw","power_month","latitude","longitude","delay_months","capex_uplift_pct","energy_uplift_pct","source_note","evidence_id","created_at","updated_at" FROM powerpath_runtime_v3090."power_paths")) THEN
 RAISE EXCEPTION 'Source parity failed: power_paths'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."runs" ("id","scenario_id","scenario_version","mode","engine_sha256","finance_sha256","input_json","summary_json","rows_json","created_at","label") SELECT "id","scenario_id","scenario_version","mode","engine_sha256","finance_sha256","input_json","summary_json","rows_json","created_at","label" FROM powerpath_stage_v3081."runs";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","scenario_id","scenario_version","mode","engine_sha256","finance_sha256","input_json","summary_json","rows_json","created_at","label" FROM powerpath_runtime_v3090."runs" EXCEPT ALL SELECT "id","scenario_id","scenario_version","mode","engine_sha256","finance_sha256","input_json","summary_json","rows_json","created_at","label" FROM powerpath_stage_v3081."runs") UNION ALL
 (SELECT "id","scenario_id","scenario_version","mode","engine_sha256","finance_sha256","input_json","summary_json","rows_json","created_at","label" FROM powerpath_stage_v3081."runs" EXCEPT ALL SELECT "id","scenario_id","scenario_version","mode","engine_sha256","finance_sha256","input_json","summary_json","rows_json","created_at","label" FROM powerpath_runtime_v3090."runs")) THEN
 RAISE EXCEPTION 'Source parity failed: runs'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_transaction_facts" ("id","transaction_id","field","value_json","unit","source_url","source_locator","verification","created_at") SELECT "id","transaction_id","field","value_json","unit","source_url","source_locator","verification","created_at" FROM powerpath_stage_v3081."v27_transaction_facts";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","transaction_id","field","value_json","unit","source_url","source_locator","verification","created_at" FROM powerpath_runtime_v3090."v27_transaction_facts" EXCEPT ALL SELECT "id","transaction_id","field","value_json","unit","source_url","source_locator","verification","created_at" FROM powerpath_stage_v3081."v27_transaction_facts") UNION ALL
 (SELECT "id","transaction_id","field","value_json","unit","source_url","source_locator","verification","created_at" FROM powerpath_stage_v3081."v27_transaction_facts" EXCEPT ALL SELECT "id","transaction_id","field","value_json","unit","source_url","source_locator","verification","created_at" FROM powerpath_runtime_v3090."v27_transaction_facts")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_transaction_facts'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."v27_transaction_gaps" ("id","transaction_id","code","description","status") SELECT "id","transaction_id","code","description","status" FROM powerpath_stage_v3081."v27_transaction_gaps";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","transaction_id","code","description","status" FROM powerpath_runtime_v3090."v27_transaction_gaps" EXCEPT ALL SELECT "id","transaction_id","code","description","status" FROM powerpath_stage_v3081."v27_transaction_gaps") UNION ALL
 (SELECT "id","transaction_id","code","description","status" FROM powerpath_stage_v3081."v27_transaction_gaps" EXCEPT ALL SELECT "id","transaction_id","code","description","status" FROM powerpath_runtime_v3090."v27_transaction_gaps")) THEN
 RAISE EXCEPTION 'Source parity failed: v27_transaction_gaps'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."geo29_saved_versions" ("project_id","parcel_id","record_id") SELECT "project_id","parcel_id","record_id" FROM powerpath_stage_v3081."geo29_saved_versions";
DO $verify$ BEGIN
 IF EXISTS((SELECT "project_id","parcel_id","record_id" FROM powerpath_runtime_v3090."geo29_saved_versions" EXCEPT ALL SELECT "project_id","parcel_id","record_id" FROM powerpath_stage_v3081."geo29_saved_versions") UNION ALL
 (SELECT "project_id","parcel_id","record_id" FROM powerpath_stage_v3081."geo29_saved_versions" EXCEPT ALL SELECT "project_id","parcel_id","record_id" FROM powerpath_runtime_v3090."geo29_saved_versions")) THEN
 RAISE EXCEPTION 'Source parity failed: geo29_saved_versions'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."geo30_latest" ("parcel_key","record_id") SELECT "parcel_key","record_id" FROM powerpath_stage_v3081."geo30_latest";
DO $verify$ BEGIN
 IF EXISTS((SELECT "parcel_key","record_id" FROM powerpath_runtime_v3090."geo30_latest" EXCEPT ALL SELECT "parcel_key","record_id" FROM powerpath_stage_v3081."geo30_latest") UNION ALL
 (SELECT "parcel_key","record_id" FROM powerpath_stage_v3081."geo30_latest" EXCEPT ALL SELECT "parcel_key","record_id" FROM powerpath_runtime_v3090."geo30_latest")) THEN
 RAISE EXCEPTION 'Source parity failed: geo30_latest'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."permit_items" ("id","project_id","path_id","title","kind","status","owner","due_month","delay_months","evidence_id","detail","created_at","updated_at") SELECT "id","project_id","path_id","title","kind","status","owner","due_month","delay_months","evidence_id","detail","created_at","updated_at" FROM powerpath_stage_v3081."permit_items";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","path_id","title","kind","status","owner","due_month","delay_months","evidence_id","detail","created_at","updated_at" FROM powerpath_runtime_v3090."permit_items" EXCEPT ALL SELECT "id","project_id","path_id","title","kind","status","owner","due_month","delay_months","evidence_id","detail","created_at","updated_at" FROM powerpath_stage_v3081."permit_items") UNION ALL
 (SELECT "id","project_id","path_id","title","kind","status","owner","due_month","delay_months","evidence_id","detail","created_at","updated_at" FROM powerpath_stage_v3081."permit_items" EXCEPT ALL SELECT "id","project_id","path_id","title","kind","status","owner","due_month","delay_months","evidence_id","detail","created_at","updated_at" FROM powerpath_runtime_v3090."permit_items")) THEN
 RAISE EXCEPTION 'Source parity failed: permit_items'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."delivery_milestones" ("id","project_id","path_id","permit_id","title","category","status","planned_month","delay_months","predecessor_id","source_url","source_note","evidence_id","created_at","updated_at","float_months") SELECT "id","project_id","path_id","permit_id","title","category","status","planned_month","delay_months","predecessor_id","source_url","source_note","evidence_id","created_at","updated_at","float_months" FROM powerpath_stage_v3081."delivery_milestones";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","path_id","permit_id","title","category","status","planned_month","delay_months","predecessor_id","source_url","source_note","evidence_id","created_at","updated_at","float_months" FROM powerpath_runtime_v3090."delivery_milestones" EXCEPT ALL SELECT "id","project_id","path_id","permit_id","title","category","status","planned_month","delay_months","predecessor_id","source_url","source_note","evidence_id","created_at","updated_at","float_months" FROM powerpath_stage_v3081."delivery_milestones") UNION ALL
 (SELECT "id","project_id","path_id","permit_id","title","category","status","planned_month","delay_months","predecessor_id","source_url","source_note","evidence_id","created_at","updated_at","float_months" FROM powerpath_stage_v3081."delivery_milestones" EXCEPT ALL SELECT "id","project_id","path_id","permit_id","title","category","status","planned_month","delay_months","predecessor_id","source_url","source_note","evidence_id","created_at","updated_at","float_months" FROM powerpath_runtime_v3090."delivery_milestones")) THEN
 RAISE EXCEPTION 'Source parity failed: delivery_milestones'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."permit_notes" ("id","permit_id","body","created_at") SELECT "id","permit_id","body","created_at" FROM powerpath_stage_v3081."permit_notes";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","permit_id","body","created_at" FROM powerpath_runtime_v3090."permit_notes" EXCEPT ALL SELECT "id","permit_id","body","created_at" FROM powerpath_stage_v3081."permit_notes") UNION ALL
 (SELECT "id","permit_id","body","created_at" FROM powerpath_stage_v3081."permit_notes" EXCEPT ALL SELECT "id","permit_id","body","created_at" FROM powerpath_runtime_v3090."permit_notes")) THEN
 RAISE EXCEPTION 'Source parity failed: permit_notes'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."permit_steps" ("id","permit_id","title","is_done","sort_index") SELECT "id","permit_id","title","is_done","sort_index" FROM powerpath_stage_v3081."permit_steps";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","permit_id","title","is_done","sort_index" FROM powerpath_runtime_v3090."permit_steps" EXCEPT ALL SELECT "id","permit_id","title","is_done","sort_index" FROM powerpath_stage_v3081."permit_steps") UNION ALL
 (SELECT "id","permit_id","title","is_done","sort_index" FROM powerpath_stage_v3081."permit_steps" EXCEPT ALL SELECT "id","permit_id","title","is_done","sort_index" FROM powerpath_runtime_v3090."permit_steps")) THEN
 RAISE EXCEPTION 'Source parity failed: permit_steps'; END IF; END $verify$;
INSERT INTO powerpath_runtime_v3090."intel_proposals" ("id","project_id","change_id","milestone_id","proposed_delay_months","reason","status","created_at","decided_at","base_delay_months","base_status") SELECT "id","project_id","change_id","milestone_id","proposed_delay_months","reason","status","created_at","decided_at","base_delay_months","base_status" FROM powerpath_stage_v3081."intel_proposals";
DO $verify$ BEGIN
 IF EXISTS((SELECT "id","project_id","change_id","milestone_id","proposed_delay_months","reason","status","created_at","decided_at","base_delay_months","base_status" FROM powerpath_runtime_v3090."intel_proposals" EXCEPT ALL SELECT "id","project_id","change_id","milestone_id","proposed_delay_months","reason","status","created_at","decided_at","base_delay_months","base_status" FROM powerpath_stage_v3081."intel_proposals") UNION ALL
 (SELECT "id","project_id","change_id","milestone_id","proposed_delay_months","reason","status","created_at","decided_at","base_delay_months","base_status" FROM powerpath_stage_v3081."intel_proposals" EXCEPT ALL SELECT "id","project_id","change_id","milestone_id","proposed_delay_months","reason","status","created_at","decided_at","base_delay_months","base_status" FROM powerpath_runtime_v3090."intel_proposals")) THEN
 RAISE EXCEPTION 'Source parity failed: intel_proposals'; END IF; END $verify$;
UPDATE powerpath_runtime_v3090.projects p SET owning_tenant=t.tenant_id FROM powerpath_runtime_v3090.v27_project_tenants t WHERE t.project_id=p.id;
CREATE TABLE powerpath_runtime_v3090.geo29_bounds(rid integer PRIMARY KEY REFERENCES powerpath_runtime_v3090.geo29_parcels(rid),minx double precision NOT NULL,maxx double precision NOT NULL,miny double precision NOT NULL,maxy double precision NOT NULL);
INSERT INTO powerpath_runtime_v3090.geo29_bounds SELECT record_id,extensions.ST_XMin(geom::extensions.box3d),extensions.ST_XMax(geom::extensions.box3d),extensions.ST_YMin(geom::extensions.box3d),extensions.ST_YMax(geom::extensions.box3d) FROM powerpath_stage_v3081.pp_parcel_geometry_v1;
CREATE INDEX geo29_bounds_x ON powerpath_runtime_v3090.geo29_bounds(minx,maxx);
CREATE INDEX geo29_bounds_y ON powerpath_runtime_v3090.geo29_bounds(miny,maxy);
REVOKE ALL ON SCHEMA powerpath_runtime_v3090 FROM PUBLIC,anon,authenticated,service_role;
GRANT USAGE ON SCHEMA powerpath_runtime_v3090 TO powerpath_app;
CREATE FUNCTION powerpath_runtime_v3090.pp_tenant_access(t text, minimum integer) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=powerpath_runtime_v3090,pg_catalog AS $policy$
 SELECT EXISTS(SELECT 1 FROM v27_memberships m JOIN v27_users u ON u.id=m.user_id
 WHERE u.id=nullif(current_setting('powerpath.actor_id',true),'') AND u.active=1 AND m.tenant_id=t AND
 CASE m.role WHEN 'admin' THEN 4 WHEN 'approver' THEN 3 WHEN 'analyst' THEN 2 WHEN 'viewer' THEN 1 ELSE 0 END>=minimum)
$policy$;
CREATE FUNCTION powerpath_runtime_v3090.pp_project_access(p text, minimum integer) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=powerpath_runtime_v3090,pg_catalog AS $policy$
 SELECT EXISTS(SELECT 1 FROM v27_project_tenants pt WHERE pt.project_id=p AND pp_tenant_access(pt.tenant_id,minimum))
$policy$;
ALTER TABLE powerpath_runtime_v3090.activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.activity FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.activity FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.activity TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.activity FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.activity TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.activity FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.activity FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.activity TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.activity FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.agent_call_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_call_log FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_call_log FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_call_log TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_call_log FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_call_log TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_call_log FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_call_log FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.agent_call_log TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_call_log FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.geo29_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.geo29_sources FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.geo29_sources FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.geo29_sources TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.geo29_sources FOR SELECT TO powerpath_app USING (true);
ALTER TABLE powerpath_runtime_v3090.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.projects FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.projects FROM PUBLIC,anon,authenticated,service_role;
GRANT INSERT ON powerpath_runtime_v3090.projects TO powerpath_app;
CREATE POLICY new_project ON powerpath_runtime_v3090.projects FOR INSERT TO powerpath_app WITH CHECK (created_by=nullif(current_setting('powerpath.actor_id',true),'') AND owning_tenant=nullif(current_setting('powerpath.tenant_id',true),'') AND powerpath_runtime_v3090.pp_tenant_access(nullif(current_setting('powerpath.tenant_id',true),''),2));
GRANT SELECT ON powerpath_runtime_v3090.projects TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.projects FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_tenant_access(owning_tenant,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.projects TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.projects FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_tenant_access(owning_tenant,2)) WITH CHECK (powerpath_runtime_v3090.pp_tenant_access(owning_tenant,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.projects FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_tenant_access(owning_tenant,2));
ALTER TABLE powerpath_runtime_v3090.schema_migrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.schema_migrations FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.schema_migrations FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.schema_migrations TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.schema_migrations FOR SELECT TO powerpath_app USING (true);
ALTER TABLE powerpath_runtime_v3090.v27_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_audit FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_audit FROM PUBLIC,anon,authenticated,service_role;
GRANT INSERT ON powerpath_runtime_v3090.v27_audit TO powerpath_app;
CREATE POLICY append_audit ON powerpath_runtime_v3090.v27_audit FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_tenant_access(tenant_id,2) AND actor_id=nullif(current_setting('powerpath.actor_id',true),''));
GRANT SELECT ON powerpath_runtime_v3090.v27_audit TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_audit FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_tenant_access(tenant_id,1));
ALTER TABLE powerpath_runtime_v3090.v27_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_tenants FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_tenants FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v27_tenants TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_tenants FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_tenant_access(id,1));
ALTER TABLE powerpath_runtime_v3090.v27_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_users FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_users FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v27_users TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_users FOR SELECT TO powerpath_app USING (id=nullif(current_setting('powerpath.actor_id',true),''));
ALTER TABLE powerpath_runtime_v3090.agent_meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_meetings FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_meetings FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_meetings TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_meetings FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_meetings TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_meetings FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_meetings FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.agent_meetings TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_meetings FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.agent_ops_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_ops_config FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_ops_config FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_ops_config TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_ops_config FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_ops_config TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_ops_config FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_ops_config FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.agent_ops_config TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_ops_config FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.agent_ops_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_ops_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_ops_events FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_ops_events TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_ops_events FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_ops_events TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_ops_events FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_ops_events FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.agent_ops_events TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_ops_events FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.agent_ops_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_ops_jobs FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_ops_jobs FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_ops_jobs TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_ops_jobs FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_ops_jobs TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_ops_jobs FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_ops_jobs FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.agent_ops_jobs TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_ops_jobs FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.evidence FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.evidence FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.evidence TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.evidence FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.evidence TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.evidence FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.evidence FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.evidence TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.evidence FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.feasibility_v82_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.feasibility_v82_runs FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.feasibility_v82_runs FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.feasibility_v82_runs TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.feasibility_v82_runs FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.feasibility_v82_runs TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.feasibility_v82_runs FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.feasibility_v82_runs FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.feasibility_v82_runs TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.feasibility_v82_runs FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.geo29_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.geo29_versions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.geo29_versions FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.geo29_versions TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.geo29_versions FOR SELECT TO powerpath_app USING (true);
ALTER TABLE powerpath_runtime_v3090.geographic_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.geographic_assets FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.geographic_assets FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.geographic_assets TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.geographic_assets FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.geographic_assets TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.geographic_assets FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.geographic_assets FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.geographic_assets TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.geographic_assets FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.intel_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.intel_snapshots FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.intel_snapshots FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.intel_snapshots TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.intel_snapshots FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.intel_snapshots TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.intel_snapshots FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.intel_snapshots FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.intel_snapshots TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.intel_snapshots FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.parcel_assessments28 ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.parcel_assessments28 FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.parcel_assessments28 FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.parcel_assessments28 TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.parcel_assessments28 FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.parcel_assessments28 TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.parcel_assessments28 FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.parcel_assessments28 FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.parcel_assessments28 TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.parcel_assessments28 FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.parcel_shortlist28 ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.parcel_shortlist28 FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.parcel_shortlist28 FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.parcel_shortlist28 TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.parcel_shortlist28 FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.parcel_shortlist28 TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.parcel_shortlist28 FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.parcel_shortlist28 FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.parcel_shortlist28 TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.parcel_shortlist28 FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.parcel_tasks28 ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.parcel_tasks28 FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.parcel_tasks28 FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.parcel_tasks28 TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.parcel_tasks28 FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.parcel_tasks28 TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.parcel_tasks28 FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.parcel_tasks28 FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.parcel_tasks28 TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.parcel_tasks28 FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.scenarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.scenarios FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.scenarios FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.scenarios TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.scenarios FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.scenarios TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.scenarios FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.scenarios FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.scenarios TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.scenarios FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.v271_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v271_inputs FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v271_inputs FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v271_inputs TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v271_inputs FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.v271_inputs TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.v271_inputs FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.v271_inputs FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.v271_inputs TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.v271_inputs FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.v27_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_approvals FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_approvals FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v27_approvals TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_approvals FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.v27_approvals TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.v27_approvals FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.v27_approvals FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.v27_approvals TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.v27_approvals FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.v27_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_memberships FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_memberships FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v27_memberships TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_memberships FOR SELECT TO powerpath_app USING (user_id=nullif(current_setting('powerpath.actor_id',true),''));
ALTER TABLE powerpath_runtime_v3090.v27_project_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_project_tenants FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_project_tenants FROM PUBLIC,anon,authenticated,service_role;
GRANT INSERT ON powerpath_runtime_v3090.v27_project_tenants TO powerpath_app;
CREATE POLICY map_new_project ON powerpath_runtime_v3090.v27_project_tenants FOR INSERT TO powerpath_app WITH CHECK (tenant_id=nullif(current_setting('powerpath.tenant_id',true),'') AND powerpath_runtime_v3090.pp_tenant_access(tenant_id,2) AND EXISTS(SELECT 1 FROM powerpath_runtime_v3090.projects p WHERE p.id=project_id AND p.created_by=nullif(current_setting('powerpath.actor_id',true),'') AND p.owning_tenant=tenant_id));
GRANT SELECT ON powerpath_runtime_v3090.v27_project_tenants TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_project_tenants FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_tenant_access(tenant_id,1));
ALTER TABLE powerpath_runtime_v3090.v27_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_sessions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_sessions FROM PUBLIC,anon,authenticated,service_role;
GRANT INSERT,UPDATE ON powerpath_runtime_v3090.v27_sessions TO powerpath_app;
CREATE POLICY revoke_session ON powerpath_runtime_v3090.v27_sessions FOR INSERT TO powerpath_app WITH CHECK (user_id=nullif(current_setting('powerpath.actor_id',true),'') AND revoked=1);
CREATE POLICY keep_revoked ON powerpath_runtime_v3090.v27_sessions FOR UPDATE TO powerpath_app USING (user_id=nullif(current_setting('powerpath.actor_id',true),'') AND revoked=1) WITH CHECK (user_id=nullif(current_setting('powerpath.actor_id',true),'') AND revoked=1);
GRANT SELECT ON powerpath_runtime_v3090.v27_sessions TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_sessions FOR SELECT TO powerpath_app USING (user_id=nullif(current_setting('powerpath.actor_id',true),''));
ALTER TABLE powerpath_runtime_v3090.v27_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_transactions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_transactions FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v27_transactions TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_transactions FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.v27_transactions TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.v27_transactions FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.v27_transactions FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.v27_transactions TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.v27_transactions FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.agent_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_messages FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_messages FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_messages TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_messages FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.agent_meetings p WHERE p.id=agent_messages.meeting_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_messages TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_messages FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.agent_meetings p WHERE p.id=agent_messages.meeting_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.agent_meetings p WHERE p.id=agent_messages.meeting_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_messages FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.agent_meetings p WHERE p.id=agent_messages.meeting_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.agent_messages TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_messages FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.agent_meetings p WHERE p.id=agent_messages.meeting_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.agent_ops_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_ops_calls FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_ops_calls FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_ops_calls TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_ops_calls FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_ops_calls TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_ops_calls FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_ops_calls FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.agent_ops_calls TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_ops_calls FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.agent_ops_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.agent_ops_reviews FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.agent_ops_reviews FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.agent_ops_reviews TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.agent_ops_reviews FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.agent_ops_reviews TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.agent_ops_reviews FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.agent_ops_reviews FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.agent_ops_reviews TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.agent_ops_reviews FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.geo29_parcels ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.geo29_parcels FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.geo29_parcels FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.geo29_parcels TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.geo29_parcels FOR SELECT TO powerpath_app USING (true);
ALTER TABLE powerpath_runtime_v3090.intel_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.intel_changes FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.intel_changes FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.intel_changes TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.intel_changes FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.intel_changes TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.intel_changes FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.intel_changes FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.intel_changes TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.intel_changes FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.intel_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.intel_records FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.intel_records FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.intel_records TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.intel_records FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_records.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.intel_records TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.intel_records FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_records.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_records.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.intel_records FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_records.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.intel_records TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.intel_records FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_records.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.intel_snapshot_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.intel_snapshot_raw FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.intel_snapshot_raw FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.intel_snapshot_raw TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.intel_snapshot_raw FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_snapshot_raw.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.intel_snapshot_raw TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.intel_snapshot_raw FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_snapshot_raw.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_snapshot_raw.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.intel_snapshot_raw FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_snapshot_raw.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.intel_snapshot_raw TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.intel_snapshot_raw FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.intel_snapshots p WHERE p.id=intel_snapshot_raw.snapshot_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.power_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.power_paths FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.power_paths FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.power_paths TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.power_paths FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.power_paths TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.power_paths FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.power_paths FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.power_paths TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.power_paths FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.runs FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.runs FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.runs TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.runs FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.scenarios p WHERE p.id=runs.scenario_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.runs TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.runs FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.scenarios p WHERE p.id=runs.scenario_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.scenarios p WHERE p.id=runs.scenario_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.runs FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.scenarios p WHERE p.id=runs.scenario_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.runs TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.runs FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.scenarios p WHERE p.id=runs.scenario_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.v27_transaction_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_transaction_facts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_transaction_facts FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v27_transaction_facts TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_transaction_facts FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_facts.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.v27_transaction_facts TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.v27_transaction_facts FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_facts.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_facts.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.v27_transaction_facts FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_facts.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.v27_transaction_facts TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.v27_transaction_facts FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_facts.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.v27_transaction_gaps ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.v27_transaction_gaps FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.v27_transaction_gaps FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.v27_transaction_gaps TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.v27_transaction_gaps FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_gaps.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.v27_transaction_gaps TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.v27_transaction_gaps FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_gaps.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_gaps.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.v27_transaction_gaps FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_gaps.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.v27_transaction_gaps TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.v27_transaction_gaps FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.v27_transactions p WHERE p.id=v27_transaction_gaps.transaction_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.geo29_saved_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.geo29_saved_versions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.geo29_saved_versions FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.geo29_saved_versions TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.geo29_saved_versions FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.geo29_saved_versions TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.geo29_saved_versions FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.geo29_saved_versions FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.geo29_saved_versions TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.geo29_saved_versions FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.geo30_latest ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.geo30_latest FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.geo30_latest FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.geo30_latest TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.geo30_latest FOR SELECT TO powerpath_app USING (true);
ALTER TABLE powerpath_runtime_v3090.permit_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.permit_items FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.permit_items FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.permit_items TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.permit_items FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.permit_items TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.permit_items FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.permit_items FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.permit_items TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.permit_items FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.delivery_milestones ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.delivery_milestones FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.delivery_milestones FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.delivery_milestones TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.delivery_milestones FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.delivery_milestones TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.delivery_milestones FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.delivery_milestones FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.delivery_milestones TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.delivery_milestones FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.permit_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.permit_notes FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.permit_notes FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.permit_notes TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.permit_notes FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_notes.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.permit_notes TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.permit_notes FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_notes.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_notes.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.permit_notes FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_notes.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.permit_notes TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.permit_notes FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_notes.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.permit_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.permit_steps FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.permit_steps FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.permit_steps TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.permit_steps FOR SELECT TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_steps.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,1)));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.permit_steps TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.permit_steps FOR UPDATE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_steps.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2))) WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_steps.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.permit_steps FOR DELETE TO powerpath_app USING (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_steps.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
GRANT INSERT ON powerpath_runtime_v3090.permit_steps TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.permit_steps FOR INSERT TO powerpath_app WITH CHECK (EXISTS(SELECT 1 FROM powerpath_runtime_v3090.permit_items p WHERE p.id=permit_steps.permit_id AND powerpath_runtime_v3090.pp_project_access(p.project_id,2)));
ALTER TABLE powerpath_runtime_v3090.intel_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.intel_proposals FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.intel_proposals FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.intel_proposals TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.intel_proposals FOR SELECT TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,1));
GRANT UPDATE,DELETE ON powerpath_runtime_v3090.intel_proposals TO powerpath_app;
CREATE POLICY update_allowed ON powerpath_runtime_v3090.intel_proposals FOR UPDATE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2)) WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
CREATE POLICY delete_allowed ON powerpath_runtime_v3090.intel_proposals FOR DELETE TO powerpath_app USING (powerpath_runtime_v3090.pp_project_access(project_id,2));
GRANT INSERT ON powerpath_runtime_v3090.intel_proposals TO powerpath_app;
CREATE POLICY insert_allowed ON powerpath_runtime_v3090.intel_proposals FOR INSERT TO powerpath_app WITH CHECK (powerpath_runtime_v3090.pp_project_access(project_id,2));
ALTER TABLE powerpath_runtime_v3090.geo29_bounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE powerpath_runtime_v3090.geo29_bounds FORCE ROW LEVEL SECURITY;
REVOKE ALL ON powerpath_runtime_v3090.geo29_bounds FROM PUBLIC,anon,authenticated,service_role;
GRANT SELECT ON powerpath_runtime_v3090.geo29_bounds TO powerpath_app;
CREATE POLICY read_allowed ON powerpath_runtime_v3090.geo29_bounds FOR SELECT TO powerpath_app USING (true);
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA powerpath_runtime_v3090 FROM PUBLIC,anon,authenticated,service_role;
GRANT EXECUTE ON FUNCTION powerpath_runtime_v3090.pp_tenant_access(text,integer),powerpath_runtime_v3090.pp_project_access(text,integer) TO powerpath_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA powerpath_runtime_v3090 TO powerpath_app;

