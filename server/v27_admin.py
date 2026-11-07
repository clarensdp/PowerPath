"""Bootstrap local tenancy. Example: python -m server.v27_admin bootstrap --email ... --tenant ...
Pass password securely through POWERPATH_BOOTSTRAP_PASSWORD environment variable.
"""
import argparse, os, secrets
from server.app import db
from server.institutional import init,utc,password_hash,append_audit

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['bootstrap','grant','assign-project','verify-audit'])
    parser.add_argument('--email');parser.add_argument('--tenant');parser.add_argument('--name');parser.add_argument('--role',default='viewer');parser.add_argument('--project')
    args=parser.parse_args()
    with db() as con:
        init(con)
        if args.command=='bootstrap':
            password=os.environ.get('POWERPATH_BOOTSTRAP_PASSWORD','')
            if not args.email or not args.tenant or not args.name:parser.error('--email --tenant --name required')
            if con.execute('SELECT 1 FROM v27_users').fetchone():parser.error('Bootstrap refuses to run after first user; use grant')
            uid=secrets.token_hex(12)
            con.execute('INSERT INTO v27_tenants VALUES(?,?,?)',(args.tenant,args.name,utc()))
            con.execute('INSERT INTO v27_users VALUES(?,?,?,?,?)',(uid,args.email.lower(),password_hash(password),1,utc()))
            con.execute('INSERT INTO v27_memberships VALUES(?,?,?)',(uid,args.tenant,'admin'))
            append_audit(con,args.tenant,uid,'tenant.bootstrapped',args.tenant)
            print('Created tenant and administrator:',args.tenant,args.email)
        elif args.command=='grant':
            if not args.email or not args.tenant or args.role not in ('viewer','analyst','approver','admin'):parser.error('email, tenant and valid role required')
            user=con.execute('SELECT id FROM v27_users WHERE email=?',(args.email.lower(),)).fetchone()
            if not user:parser.error('User must already exist; no unaudited user creation with this command')
            con.execute('INSERT INTO v27_memberships VALUES(?,?,?) ON CONFLICT(user_id,tenant_id) DO UPDATE SET role=excluded.role',(user['id'],args.tenant,args.role))
            append_audit(con,args.tenant,'OPERATOR_CLI','membership.granted',user['id'],{'role':args.role})
            print('Granted',args.role)
        elif args.command=='assign-project':
            if not args.project or not args.tenant:parser.error('--project and --tenant required')
            if not con.execute('SELECT 1 FROM projects WHERE id=?',(args.project,)).fetchone():parser.error('Unknown project')
            if not con.execute('SELECT 1 FROM v27_tenants WHERE id=?',(args.tenant,)).fetchone():parser.error('Unknown tenant')
            if con.execute('SELECT 1 FROM v27_project_tenants WHERE project_id=?',(args.project,)).fetchone():parser.error('Already assigned. Tenant transfer requires separate reviewed migration.')
            con.execute('INSERT INTO v27_project_tenants VALUES(?,?)',(args.project,args.tenant))
            append_audit(con,args.tenant,'OPERATOR_CLI','project.assigned',args.project)
            print('Assigned',args.project,args.tenant)
        else:
            from server.institutional import verify_audit
            print(verify_audit(con))
if __name__=='__main__':main()
