"""Fail-closed PostgreSQL policy compiler for the inventoried legacy schema.

Generates reviewable DDL only. No credentials, implicit schema changes or grants
are executed by importing this module. All functions use SECURITY INVOKER.
"""

import re

GLOBAL_READ = {"geo29_sources", "geo29_versions", "geo29_parcels", "geo29_bounds", "geo30_latest", "schema_migrations"}
IDENTITY = {"v27_users", "v27_memberships", "v27_tenants", "v27_sessions", "v27_project_tenants", "v27_audit"}
# v30.8.2: financial outputs and the activity log are insert-only; evidence may only attach its file once.
APPEND_ONLY = {"runs", "feasibility_v82_runs", "activity"}
ATTACH_ONCE = {"evidence"}
INDIRECT = {
    "runs": ("scenarios", "scenario_id", "id"),
    "permit_steps": ("permit_items", "permit_id", "id"),
    "permit_notes": ("permit_items", "permit_id", "id"),
    "v27_transaction_facts": ("v27_transactions", "transaction_id", "id"),
    "v27_transaction_gaps": ("v27_transactions", "transaction_id", "id"),
    "intel_records": ("intel_snapshots", "snapshot_id", "id"),
    "intel_snapshot_raw": ("intel_snapshots", "snapshot_id", "id"),
    "agent_messages": ("agent_meetings", "meeting_id", "id"),
}


def compile_policies(schema, tables, role="powerpath_app"):
    for identifier in (schema, role, *tables):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", identifier):
            raise ValueError("unsafe identifier")
    prefix = schema + "."
    actor = "nullif(current_setting('powerpath.actor_id',true),'')"
    tenant = "nullif(current_setting('powerpath.tenant_id',true),'')"
    sql = [
        f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC,anon,authenticated,service_role;",
        f"GRANT USAGE ON SCHEMA {schema} TO {role};",
        f"""CREATE FUNCTION {prefix}pp_tenant_access(t text, minimum integer) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path={schema},pg_catalog AS $policy$
 SELECT EXISTS(SELECT 1 FROM v27_memberships m JOIN v27_users u ON u.id=m.user_id
 WHERE u.id={actor} AND u.active=1 AND m.tenant_id=t AND
 CASE m.role WHEN 'admin' THEN 4 WHEN 'approver' THEN 3 WHEN 'analyst' THEN 2 WHEN 'viewer' THEN 1 ELSE 0 END>=minimum)
$policy$;""",
        f"""CREATE FUNCTION {prefix}pp_project_access(p text, minimum integer) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path={schema},pg_catalog AS $policy$
 SELECT EXISTS(SELECT 1 FROM v27_project_tenants pt WHERE pt.project_id=p AND pp_tenant_access(pt.tenant_id,minimum))
$policy$;""",
    ]
    for table, columns in tables.items():
        qualified = prefix + table
        sql += [
            f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY;",
            f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY;",
            f"REVOKE ALL ON {qualified} FROM PUBLIC,anon,authenticated,service_role;",
        ]
        read = write = None
        if table in GLOBAL_READ:
            read = "true"
        elif table in {"v27_users", "v27_memberships"}:
            read = ("id" if table == "v27_users" else "user_id") + "=" + actor
        elif table == "v27_tenants":
            read = f"{prefix}pp_tenant_access(id,1)"
        elif table == "v27_sessions":
            read = f"user_id={actor}"
            check = f"user_id={actor} AND revoked=1"
            sql += [
                f"GRANT INSERT,UPDATE ON {qualified} TO {role};",
                f"CREATE POLICY revoke_session ON {qualified} FOR INSERT TO {role} WITH CHECK ({check});",
                f"CREATE POLICY keep_revoked ON {qualified} FOR UPDATE TO {role} USING ({check}) WITH CHECK ({check});",
            ]
        elif table == "v27_project_tenants":
            read = f"{prefix}pp_tenant_access(tenant_id,1)"
            check = f"tenant_id={tenant} AND {prefix}pp_tenant_access(tenant_id,2) AND EXISTS(SELECT 1 FROM {prefix}projects p WHERE p.id=project_id AND p.created_by={actor} AND p.owning_tenant=tenant_id)"
            sql += [
                f"GRANT INSERT ON {qualified} TO {role};",
                f"CREATE POLICY map_new_project ON {qualified} FOR INSERT TO {role} WITH CHECK ({check});",
            ]
        elif table == "v27_audit":
            read = f"{prefix}pp_tenant_access(tenant_id,1)"
            check = f"{prefix}pp_tenant_access(tenant_id,2) AND actor_id={actor}"
            sql += [
                f"GRANT INSERT ON {qualified} TO {role};",
                f"CREATE POLICY append_audit ON {qualified} FOR INSERT TO {role} WITH CHECK ({check});",
            ]
        elif table == "projects":
            read = f"{prefix}pp_tenant_access(owning_tenant,1)"
            write = f"{prefix}pp_tenant_access(owning_tenant,2)"
            sql += [
                f"GRANT INSERT ON {qualified} TO {role};",
                f"CREATE POLICY new_project ON {qualified} FOR INSERT TO {role} WITH CHECK (created_by={actor} AND owning_tenant={tenant} AND {prefix}pp_tenant_access({tenant},2));",
            ]
        elif "project_id" in columns:
            read = f"{prefix}pp_project_access(project_id,1)"
            write = f"{prefix}pp_project_access(project_id,2)"
        elif table in INDIRECT:
            parent, child, key = INDIRECT[table]
            read = f"EXISTS(SELECT 1 FROM {prefix}{parent} p WHERE p.{key}={table}.{child} AND {prefix}pp_project_access(p.project_id,1))"
            write = read.replace("project_id,1)", "project_id,2)")
        else:
            raise ValueError("unclassified table: " + table)
        if read:
            sql += [
                f"GRANT SELECT ON {qualified} TO {role};",
                f"CREATE POLICY read_allowed ON {qualified} FOR SELECT TO {role} USING ({read});",
            ]
        if write and table in APPEND_ONLY | ATTACH_ONCE:
            sql += [
                f"GRANT INSERT ON {qualified} TO {role};",
                f"CREATE POLICY insert_allowed ON {qualified} FOR INSERT TO {role} WITH CHECK ({write});",
            ]
            if table in ATTACH_ONCE:
                sql += [
                    f"GRANT UPDATE ON {qualified} TO {role};",
                    f"CREATE POLICY attach_file_once ON {qualified} FOR UPDATE TO {role} USING ({write} AND stored_filename='') WITH CHECK ({write} AND stored_filename<>'');",
                ]
        elif write:
            sql += [
                f"GRANT UPDATE,DELETE ON {qualified} TO {role};",
                f"CREATE POLICY update_allowed ON {qualified} FOR UPDATE TO {role} USING ({write}) WITH CHECK ({write});",
                f"CREATE POLICY delete_allowed ON {qualified} FOR DELETE TO {role} USING ({write});",
            ]
            if table != "projects":
                sql += [
                    f"GRANT INSERT ON {qualified} TO {role};",
                    f"CREATE POLICY insert_allowed ON {qualified} FOR INSERT TO {role} WITH CHECK ({write});",
                ]
    # v30.8.2 defence in depth: triggers apply to every role (including the owner) and can compare OLD/NEW, which RLS
    # policies cannot. Mirrors server/append_only.py so SQLite and PostgreSQL enforce identical rules.
    present = set(tables)
    guarded = sorted(APPEND_ONLY & present)
    if guarded or "evidence" in present:
        sql += [
            f"""CREATE FUNCTION {prefix}pp_refuse_mutation() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path={schema},pg_catalog AS $guard$
BEGIN RAISE EXCEPTION '% is append-only: create a new record instead', TG_TABLE_NAME USING ERRCODE='insufficient_privilege'; END
$guard$;"""
        ]
        for table in guarded:
            sql.append(
                f"CREATE TRIGGER pp_append_only BEFORE UPDATE OR DELETE ON {prefix}{table} FOR EACH ROW EXECUTE FUNCTION {prefix}pp_refuse_mutation();"
            )
    if "evidence" in present:
        sql += [
            f"""CREATE FUNCTION {prefix}pp_evidence_attach_once() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path={schema},pg_catalog AS $guard$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'evidence is append-only: records cannot be deleted' USING ERRCODE='insufficient_privilege'; END IF;
 IF OLD.stored_filename<>'' OR NEW.stored_filename='' OR NEW.id IS DISTINCT FROM OLD.id OR NEW.project_id IS DISTINCT FROM OLD.project_id
    OR NEW.title IS DISTINCT FROM OLD.title OR NEW.category IS DISTINCT FROM OLD.category OR NEW.evidence_status IS DISTINCT FROM OLD.evidence_status
    OR NEW.citation IS DISTINCT FROM OLD.citation OR NEW.notes IS DISTINCT FROM OLD.notes OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
  RAISE EXCEPTION 'evidence is immutable once its file is attached: create a new record' USING ERRCODE='insufficient_privilege';
 END IF;
 RETURN NEW;
END
$guard$;""",
            f"CREATE TRIGGER pp_evidence_attach_once BEFORE UPDATE OR DELETE ON {prefix}evidence FOR EACH ROW EXECUTE FUNCTION {prefix}pp_evidence_attach_once();",
        ]
    sql += [
        f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {schema} FROM PUBLIC,anon,authenticated,service_role;",
        f"GRANT EXECUTE ON FUNCTION {prefix}pp_tenant_access(text,integer),{prefix}pp_project_access(text,integer) TO {role};",
        f"GRANT USAGE ON ALL SEQUENCES IN SCHEMA {schema} TO {role};",
    ]
    return "\n".join(sql) + "\n"
