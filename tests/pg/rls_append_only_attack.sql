-- PowerPath v30.8.2 — adversarial RLS + append-only acceptance test against a DISPOSABLE local PostgreSQL.
-- Prerequisites: pg_stage import + runtime_migration applied (see docs/AUDIT_2026-11-07.md). Run as the schema owner:
--   psql -v ON_ERROR_STOP=1 -f tests/pg/rls_append_only_attack.sql
-- Every attack runs as the non-owner, NOBYPASSRLS role powerpath_app. Each check RAISEs on failure, so the script
-- exits non-zero if any protection is missing. Fixture rows are created by the owner and removed by ROLLBACK.
\set ON_ERROR_STOP 1
BEGIN;
SET search_path = powerpath_runtime_v3090, public, extensions;

-- ---------- owner-side fixtures ----------
INSERT INTO v27_tenants VALUES ('tenant-a','Tenant A',now()::text),('tenant-b','Tenant B',now()::text);
INSERT INTO v27_users VALUES ('u-analyst-a','a@example.test','x',1,now()::text),('u-viewer-b','b@example.test','x',1,now()::text),
                             ('u-inactive-admin','c@example.test','x',0,now()::text);
INSERT INTO v27_memberships VALUES ('u-analyst-a','tenant-a','analyst'),('u-viewer-b','tenant-b','viewer'),('u-inactive-admin','tenant-a','admin');
INSERT INTO projects(id,name,location,target_mw,status,description,created_at,updated_at,created_by,owning_tenant)
  VALUES ('proj-b','Tenant B project','Synthetic',50,'Qualify','',now()::text,now()::text,'u-viewer-b','tenant-b');
UPDATE projects SET owning_tenant='tenant-a' WHERE id='demo-campus-001';
INSERT INTO v27_project_tenants VALUES ('demo-campus-001','tenant-a'),('proj-b','tenant-b');
INSERT INTO scenarios VALUES ('sc-b','proj-b','B base','underwrite','{}',1,now()::text,now()::text);
INSERT INTO runs VALUES ('run-a','demo-base-001',1,'underwrite','e','f','{}','{"npvM":1}','[]',now()::text,'SCREENING / UNVERIFIED'),
                        ('run-b','sc-b',1,'underwrite','e','f','{}','{"npvM":2}','[]',now()::text,'SCREENING / UNVERIFIED');
INSERT INTO evidence(id,project_id,title,category,created_at) VALUES ('ev-a','demo-campus-001','Utility letter','utility',now()::text);
INSERT INTO activity(project_id,action,object_id,created_at) VALUES ('demo-campus-001','run.created','run-a',now()::text);

CREATE TEMP TABLE results(check_name text, passed boolean, detail text);
GRANT INSERT, SELECT ON results TO powerpath_app;

-- Helper: run a statement as the app role and record whether it was BLOCKED (error or zero rows affected).
CREATE FUNCTION pg_temp.expect_blocked(name text, stmt text) RETURNS void LANGUAGE plpgsql AS $f$
DECLARE n bigint;
BEGIN
  BEGIN
    EXECUTE stmt; GET DIAGNOSTICS n = ROW_COUNT;
    INSERT INTO results VALUES (name, n = 0, 'affected '||n||' rows');
  EXCEPTION WHEN insufficient_privilege OR raise_exception OR check_violation OR others THEN
    INSERT INTO results VALUES (name, true, 'refused: '||SQLERRM);
  END;
END $f$;
CREATE FUNCTION pg_temp.expect_count(name text, q text, want bigint) RETURNS void LANGUAGE plpgsql AS $f$
DECLARE n bigint; BEGIN EXECUTE q INTO n; INSERT INTO results VALUES (name, n = want, 'got '||n||', want '||want); END $f$;
CREATE FUNCTION pg_temp.expect_ok(name text, stmt text) RETURNS void LANGUAGE plpgsql AS $f$
DECLARE n bigint; BEGIN EXECUTE stmt; GET DIAGNOSTICS n = ROW_COUNT; INSERT INTO results VALUES (name, n > 0, 'affected '||n||' rows');
EXCEPTION WHEN others THEN INSERT INTO results VALUES (name, false, 'error: '||SQLERRM); END $f$;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pg_temp TO powerpath_app;

-- ---------- Tenant A analyst ----------
SET ROLE powerpath_app;
SELECT set_config('powerpath.actor_id','u-analyst-a',true), set_config('powerpath.tenant_id','tenant-a',true);
SELECT pg_temp.expect_count('A sees own run',            'SELECT count(*) FROM runs', 1);
SELECT pg_temp.expect_count('A cannot see tenant B project','SELECT count(*) FROM projects WHERE id=''proj-b''', 0);
SELECT pg_temp.expect_blocked('A cannot DELETE own run (append-only)',  'DELETE FROM runs WHERE id=''run-a''');
SELECT pg_temp.expect_blocked('A cannot UPDATE own run (append-only)',  'UPDATE runs SET summary_json=''{"npvM":999}'' WHERE id=''run-a''');
SELECT pg_temp.expect_blocked('A cannot DELETE activity log',           'DELETE FROM activity');
SELECT pg_temp.expect_blocked('A cannot UPDATE activity log',           'UPDATE activity SET action=''x''');
SELECT pg_temp.expect_blocked('A cannot DELETE evidence',               'DELETE FROM evidence WHERE id=''ev-a''');
SELECT pg_temp.expect_blocked('A cannot rewrite evidence metadata before attach', 'UPDATE evidence SET title=''Edited'' WHERE id=''ev-a''');
SELECT pg_temp.expect_blocked('A cannot change title while attaching (OLD/NEW guard)', 'UPDATE evidence SET stored_filename=''ev-a.pdf'',title=''Swapped'' WHERE id=''ev-a''');
SELECT pg_temp.expect_ok     ('A CAN attach evidence file once',        'UPDATE evidence SET stored_filename=''ev-a.pdf'',filename=''l.pdf'' WHERE id=''ev-a''');
SELECT pg_temp.expect_blocked('A cannot re-attach / edit attached evidence','UPDATE evidence SET stored_filename=''other.pdf'' WHERE id=''ev-a''');
SELECT pg_temp.expect_ok     ('A CAN append a new run',                 'INSERT INTO runs VALUES (''run-a2'',''demo-base-001'',1,''underwrite'',''e'',''f'',''{}'',''{}'',''[]'',now()::text,''SCREENING / UNVERIFIED'')');
SELECT pg_temp.expect_ok     ('A CAN still edit scenarios (normal table)','UPDATE scenarios SET name=name WHERE id=''demo-base-001''');
SELECT pg_temp.expect_blocked('A cannot append a run into tenant B',     'INSERT INTO runs VALUES (''run-x'',''sc-b'',1,''underwrite'',''e'',''f'',''{}'',''{}'',''[]'',now()::text,''x'')');
SELECT pg_temp.expect_blocked('A cannot self-grant admin',               'INSERT INTO v27_memberships VALUES (''u-analyst-a'',''tenant-b'',''admin'')');
SELECT pg_temp.expect_blocked('A cannot move project to tenant B',       'UPDATE projects SET owning_tenant=''tenant-b'' WHERE id=''demo-campus-001''');

-- ---------- Tenant B viewer ----------
SELECT set_config('powerpath.actor_id','u-viewer-b',true), set_config('powerpath.tenant_id','tenant-b',true);
SELECT pg_temp.expect_count('B sees only own run',      'SELECT count(*) FROM runs', 1);
SELECT pg_temp.expect_blocked('B viewer cannot append a run', 'INSERT INTO runs VALUES (''run-y'',''sc-b'',1,''underwrite'',''e'',''f'',''{}'',''{}'',''[]'',now()::text,''x'')');
SELECT pg_temp.expect_blocked('B viewer cannot edit scenario','UPDATE scenarios SET name=''hacked'' WHERE id=''sc-b''');

-- ---------- no actor / forged / inactive ----------
SELECT set_config('powerpath.actor_id','',true), set_config('powerpath.tenant_id','',true);
SELECT pg_temp.expect_count('No actor sees 0 projects', 'SELECT count(*) FROM projects', 0);
SELECT set_config('powerpath.actor_id','forged-user',true);
SELECT pg_temp.expect_count('Forged actor sees 0 runs', 'SELECT count(*) FROM runs', 0);
SELECT set_config('powerpath.actor_id','u-inactive-admin',true), set_config('powerpath.tenant_id','tenant-a',true);
SELECT pg_temp.expect_count('Inactive admin sees 0 runs','SELECT count(*) FROM runs', 0);
RESET ROLE;

-- Owner confirms the protected rows are untouched.
SELECT pg_temp.expect_blocked('Even the schema owner cannot UPDATE a run', 'UPDATE runs SET label=''x'' WHERE id=''run-a''');
SELECT pg_temp.expect_count('run-a summary unchanged', 'SELECT count(*) FROM runs WHERE id=''run-a'' AND summary_json=''{"npvM":1}''', 1);

\echo
SELECT CASE WHEN passed THEN 'PASS' ELSE 'FAIL' END AS result, check_name, detail FROM results;
DO $$ DECLARE f int; BEGIN SELECT count(*) INTO f FROM results WHERE NOT passed;
  IF f > 0 THEN RAISE EXCEPTION '% RLS/append-only check(s) FAILED', f; END IF;
  RAISE NOTICE 'ALL % CHECKS PASSED', (SELECT count(*) FROM results); END $$;
ROLLBACK;
