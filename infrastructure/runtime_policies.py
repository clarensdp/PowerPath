"""Fail-closed PostgreSQL policy compiler for the inventoried legacy schema.

Generates reviewable DDL only. No credentials, implicit schema changes or grants
are executed by importing this module. All functions use SECURITY INVOKER.
"""
import re

GLOBAL_READ = {'geo29_sources','geo29_versions','geo29_parcels','geo29_bounds','geo30_latest','schema_migrations'}
IDENTITY = {'v27_users','v27_memberships','v27_tenants','v27_sessions','v27_project_tenants','v27_audit'}
INDIRECT = {
 'runs': ('scenarios','scenario_id','id'),
 'permit_steps': ('permit_items','permit_id','id'),
 'permit_notes': ('permit_items','permit_id','id'),
 'v27_transaction_facts': ('v27_transactions','transaction_id','id'),
 'v27_transaction_gaps': ('v27_transactions','transaction_id','id'),
 'intel_records': ('intel_snapshots','snapshot_id','id'),
 'intel_snapshot_raw': ('intel_snapshots','snapshot_id','id'),
 'agent_messages': ('agent_meetings','meeting_id','id'),
}


def compile_policies(schema, tables, role='powerpath_app'):
    for identifier in (schema,role,*tables):
        if not re.fullmatch(r'[a-z][a-z0-9_]*',identifier): raise ValueError('unsafe identifier')
    prefix = schema + '.'
    actor = "nullif(current_setting('powerpath.actor_id',true),'')"
    tenant = "nullif(current_setting('powerpath.tenant_id',true),'')"
    sql = [f'REVOKE ALL ON SCHEMA {schema} FROM PUBLIC,anon,authenticated,service_role;',
           f'GRANT USAGE ON SCHEMA {schema} TO {role};',
           f'''CREATE FUNCTION {prefix}pp_tenant_access(t text, minimum integer) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path={schema},pg_catalog AS $policy$
 SELECT EXISTS(SELECT 1 FROM v27_memberships m JOIN v27_users u ON u.id=m.user_id
 WHERE u.id={actor} AND u.active=1 AND m.tenant_id=t AND
 CASE m.role WHEN 'admin' THEN 4 WHEN 'approver' THEN 3 WHEN 'analyst' THEN 2 WHEN 'viewer' THEN 1 ELSE 0 END>=minimum)
$policy$;''',
           f'''CREATE FUNCTION {prefix}pp_project_access(p text, minimum integer) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path={schema},pg_catalog AS $policy$
 SELECT EXISTS(SELECT 1 FROM v27_project_tenants pt WHERE pt.project_id=p AND pp_tenant_access(pt.tenant_id,minimum))
$policy$;''']
    for table, columns in tables.items():
        qualified=prefix+table
        sql += [f'ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY;',f'ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY;',f'REVOKE ALL ON {qualified} FROM PUBLIC,anon,authenticated,service_role;']
        read=write=None
        if table in GLOBAL_READ: read='true'
        elif table in {'v27_users','v27_memberships'}: read=('id' if table=='v27_users' else 'user_id')+'='+actor
        elif table=='v27_tenants': read=f'{prefix}pp_tenant_access(id,1)'
        elif table=='v27_sessions':
            read=f'user_id={actor}'
            check=f'user_id={actor} AND revoked=1'
            sql += [f'GRANT INSERT,UPDATE ON {qualified} TO {role};',f'CREATE POLICY revoke_session ON {qualified} FOR INSERT TO {role} WITH CHECK ({check});',f'CREATE POLICY keep_revoked ON {qualified} FOR UPDATE TO {role} USING ({check}) WITH CHECK ({check});']
        elif table=='v27_project_tenants':
            read=f'{prefix}pp_tenant_access(tenant_id,1)'
            check=f"tenant_id={tenant} AND {prefix}pp_tenant_access(tenant_id,2) AND EXISTS(SELECT 1 FROM {prefix}projects p WHERE p.id=project_id AND p.created_by={actor} AND p.owning_tenant=tenant_id)"
            sql += [f'GRANT INSERT ON {qualified} TO {role};',f'CREATE POLICY map_new_project ON {qualified} FOR INSERT TO {role} WITH CHECK ({check});']
        elif table=='v27_audit':
            read=f'{prefix}pp_tenant_access(tenant_id,1)'
            check=f'{prefix}pp_tenant_access(tenant_id,2) AND actor_id={actor}'
            sql += [f'GRANT INSERT ON {qualified} TO {role};',f'CREATE POLICY append_audit ON {qualified} FOR INSERT TO {role} WITH CHECK ({check});']
        elif table=='projects':
            read=f'{prefix}pp_tenant_access(owning_tenant,1)'
            write=f'{prefix}pp_tenant_access(owning_tenant,2)'
            sql += [f'GRANT INSERT ON {qualified} TO {role};',f'CREATE POLICY new_project ON {qualified} FOR INSERT TO {role} WITH CHECK (created_by={actor} AND owning_tenant={tenant} AND {prefix}pp_tenant_access({tenant},2));']
        elif 'project_id' in columns:
            read=f'{prefix}pp_project_access(project_id,1)';write=f'{prefix}pp_project_access(project_id,2)'
        elif table in INDIRECT:
            parent,child,key=INDIRECT[table]
            read=f'EXISTS(SELECT 1 FROM {prefix}{parent} p WHERE p.{key}={table}.{child} AND {prefix}pp_project_access(p.project_id,1))'
            write=read.replace('project_id,1)','project_id,2)')
        else: raise ValueError('unclassified table: '+table)
        if read:
            sql += [f'GRANT SELECT ON {qualified} TO {role};',f'CREATE POLICY read_allowed ON {qualified} FOR SELECT TO {role} USING ({read});']
        if write:
            sql += [f'GRANT UPDATE,DELETE ON {qualified} TO {role};',f'CREATE POLICY update_allowed ON {qualified} FOR UPDATE TO {role} USING ({write}) WITH CHECK ({write});',f'CREATE POLICY delete_allowed ON {qualified} FOR DELETE TO {role} USING ({write});']
            if table!='projects':
                sql += [f'GRANT INSERT ON {qualified} TO {role};',f'CREATE POLICY insert_allowed ON {qualified} FOR INSERT TO {role} WITH CHECK ({write});']
    sql += [f'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA {schema} FROM PUBLIC,anon,authenticated,service_role;',f'GRANT EXECUTE ON FUNCTION {prefix}pp_tenant_access(text,integer),{prefix}pp_project_access(text,integer) TO {role};',f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA {schema} TO {role};']
    return '\n'.join(sql)+'\n'
