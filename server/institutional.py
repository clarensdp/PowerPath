"""v27 local institutional security preview. Fail-closed in required mode.
Production hosting still requires external security assessment, TLS, managed identity,
tenant-level DB policies, key management and operational controls.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, os, re, secrets, sqlite3
from contextvars import ContextVar
from datetime import datetime, timezone, timedelta
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROLE_RANK={'viewer':1,'analyst':2,'approver':3,'admin':4}
MUTATE={'POST','PUT','PATCH','DELETE'}
ACTOR=ContextVar('v27_actor',default=None)
TENANT=ContextVar('v27_tenant',default=None)
AUTH_MODE=os.environ.get('POWERPATH_V27_AUTH_MODE','local_only')
SEC_SCHEMA='''
CREATE TABLE IF NOT EXISTS v27_tenants (id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v27_users (id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v27_memberships (user_id TEXT NOT NULL REFERENCES v27_users(id),tenant_id TEXT NOT NULL REFERENCES v27_tenants(id),role TEXT NOT NULL CHECK(role IN ('viewer','analyst','approver','admin')),PRIMARY KEY(user_id,tenant_id));
CREATE TABLE IF NOT EXISTS v27_sessions (token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES v27_users(id),expires_at TEXT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS v27_project_tenants (project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE, tenant_id TEXT NOT NULL REFERENCES v27_tenants(id));
CREATE TABLE IF NOT EXISTS v27_audit (id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT,actor_id TEXT,action TEXT NOT NULL,object_id TEXT NOT NULL,details TEXT NOT NULL,prev_hash TEXT NOT NULL,entry_hash TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS v27_approvals (id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),object_type TEXT NOT NULL,object_id TEXT NOT NULL,version TEXT NOT NULL,decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),actor_id TEXT NOT NULL REFERENCES v27_users(id),reason TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(project_id,object_type,object_id,version));
'''
def utc():return datetime.now(timezone.utc).isoformat()
def password_hash(password:str):
    if len(password)<14: raise ValueError('Password must contain at least 14 characters')
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,390000)
    return 'pbkdf2_sha256$390000$'+salt.hex()+'$'+digest.hex()
def password_ok(password,stored):
    try:
        algorithm,iterations,salt,digest=stored.split('$')
        if algorithm!='pbkdf2_sha256':return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(iterations))
        return hmac.compare_digest(actual,bytes.fromhex(digest))
    except (ValueError,TypeError):return False

def init(con):
    con.executescript(SEC_SCHEMA)

def append_audit(con,tenant,actor,action,obj,details=None):
    prev=con.execute('SELECT entry_hash FROM v27_audit ORDER BY id DESC LIMIT 1').fetchone()
    prev_hash=prev['entry_hash'] if prev else 'GENESIS'
    ts=utc();details=json.dumps(details or {},sort_keys=True,separators=(',',':'))
    content=json.dumps([prev_hash,tenant,actor,action,obj,details,ts],separators=(',',':'))
    digest=hashlib.sha256(content.encode()).hexdigest()
    con.execute('INSERT INTO v27_audit(tenant_id,actor_id,action,object_id,details,prev_hash,entry_hash,created_at) VALUES(?,?,?,?,?,?,?,?)',
                (tenant,actor,action,obj,details,prev_hash,digest,ts))

def verify_audit(con):
    prev='GENESIS';count=0
    for row in con.execute('SELECT * FROM v27_audit ORDER BY id'):
        content=json.dumps([prev,row['tenant_id'],row['actor_id'],row['action'],row['object_id'],row['details'],row['created_at']],separators=(',',':'))
        if row['prev_hash']!=prev or hashlib.sha256(content.encode()).hexdigest()!=row['entry_hash']:
            return {'valid':False,'first_invalid_id':row['id'],'entries_checked':count}
        prev=row['entry_hash'];count+=1
    return {'valid':True,'entries_checked':count,'head':prev}

class LoginIn(BaseModel):
    email:str
    password:str
class ApprovalIn(BaseModel):
    object_type:str=Field(pattern='^(scenario|milestone|intelligence_proposal)$')
    object_id:str=Field(min_length=1,max_length=100)
    version:str=Field(min_length=1,max_length=120)
    decision:str=Field(pattern='^(approved|rejected)$')
    reason:str=Field(min_length=8,max_length=2000)

def install(app,db):
    with db() as con:init(con)
    @app.middleware('http')
    async def auth_gate(request:Request,call_next):
        from server import supabase_identity
        if supabase_identity.enabled():
            return await supabase_identity.gate(request,call_next,db)
        if AUTH_MODE!='required':return await call_next(request)
        path=request.url.path
        if path in ('/api/health','/api/v27/auth/login') or not path.startswith('/api/'):
            return await call_next(request)
        token=request.headers.get('authorization','')
        if not token.startswith('Bearer '):return JSONResponse({'detail':'Bearer token required'},status_code=401)
        token_hash=hashlib.sha256(token[7:].encode()).hexdigest()
        with db() as con:
            sess=con.execute('SELECT u.id,u.email,s.expires_at FROM v27_sessions s JOIN v27_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.revoked=0 AND u.active=1',(token_hash,)).fetchone()
            if not sess or sess['expires_at']<=utc():return JSONResponse({'detail':'Invalid or expired session'},status_code=401)
            request.state.user_id=sess['id'];request.state.email=sess['email']
            members=[dict(r) for r in con.execute('SELECT tenant_id,role FROM v27_memberships WHERE user_id=?',(sess['id'],))]
            request.state.members=members
            m=re.match(r'^/api/projects/([^/]+)(?:/|$)',path)
            if m:
                tenant=con.execute('SELECT tenant_id FROM v27_project_tenants WHERE project_id=?',(m.group(1),)).fetchone()
                if not tenant:return JSONResponse({'detail':'Project not provisioned for tenant access'},status_code=403)
                membership=next((r for r in members if r['tenant_id']==tenant['tenant_id']),None)
                minimum=3 if ('/approvals' in path or re.search(r'/intelligence/proposals/[^/]+/(approve|reject)$',path)) else (2 if request.method in MUTATE else 1)
                if not membership or ROLE_RANK[membership['role']]<minimum:
                    return JSONResponse({'detail':'Project access denied'},status_code=403)
                request.state.tenant_id=tenant['tenant_id'];request.state.role=membership['role']
            elif path=='/api/projects' and request.method in MUTATE:
                chosen=request.headers.get('x-powerpath-tenant','')
                mem=next((r for r in members if r['tenant_id']==chosen and ROLE_RANK[r['role']]>=2),None)
                if not mem:return JSONResponse({'detail':'Authorized X-PowerPath-Tenant required'},status_code=403)
                request.state.tenant_id=chosen;request.state.role=mem['role']
        actor_token=ACTOR.set(request.state.user_id)
        tenant_token=TENANT.set(getattr(request.state,'tenant_id',None))
        try:return await call_next(request)
        finally:
            ACTOR.reset(actor_token)
            TENANT.reset(tenant_token)

    @app.post('/api/v27/auth/login')
    def login(data:LoginIn):
        from server import supabase_identity
        if supabase_identity.enabled():
            result=supabase_identity.auth_request('token?grant_type=password',payload={'email':data.email,'password':data.password})
            return {'access_token':result['access_token'],'token_type':'bearer','expires_in':result.get('expires_in'),'mode':'SUPABASE_MANAGED_IDENTITY'}
        with db() as con:
            user=con.execute('SELECT * FROM v27_users WHERE email=? AND active=1',(data.email.strip().lower(),)).fetchone()
            # Run a dummy password comparison when user unknown, to reduce timing leakage.
            stored=user['password_hash'] if user else password_hash('dummy-placeholder-long-password')
            if not password_ok(data.password,stored):return JSONResponse({'detail':'Invalid credentials'},status_code=401)
            raw=secrets.token_urlsafe(32);expires=(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()
            con.execute('INSERT INTO v27_sessions(token_hash,user_id,expires_at) VALUES(?,?,?)',(hashlib.sha256(raw.encode()).hexdigest(),user['id'],expires))
            append_audit(con,None,user['id'],'session.created',user['id'])
            return {'access_token':raw,'token_type':'bearer','expires_at':expires,'mode':'V27_LOCAL_IDENTITY_PREVIEW'}

    @app.get('/api/v27/me')
    def me(request:Request):
        if AUTH_MODE!='required':return {'mode':'LOCAL_ONLY','authenticated':False}
        return {'id':request.state.user_id,'email':request.state.email,'memberships':request.state.members}

    @app.post('/api/v27/auth/logout')
    def logout(request:Request):
        from server import supabase_identity
        if supabase_identity.enabled():
            raw_token=request.headers['authorization'][7:]
            with db() as con:
                con.execute('INSERT INTO v27_sessions(token_hash,user_id,expires_at,revoked) VALUES(?,?,?,1) ON CONFLICT(token_hash) DO UPDATE SET revoked=1',(hashlib.sha256(raw_token.encode()).hexdigest(),request.state.user_id,'9999-12-31T23:59:59+00:00'))
            supabase_identity.auth_request('logout?scope=local',raw_token)
            return {'revoked':True}
        if AUTH_MODE!='required':return {'revoked':False}
        hashval=hashlib.sha256(request.headers['authorization'][7:].encode()).hexdigest()
        with db() as con:
            con.execute('UPDATE v27_sessions SET revoked=1 WHERE token_hash=?',(hashval,))
            append_audit(con,None,request.state.user_id,'session.revoked',request.state.user_id)
        return {'revoked':True}

    @app.get('/api/v27/audit/verify')
    def verify(request:Request):
        if AUTH_MODE=='required' and not any(m['role']=='admin' for m in request.state.members):
            return JSONResponse({'detail':'Admin required'},status_code=403)
        with db() as con:return verify_audit(con)

    @app.get('/api/projects/{pid}/approvals')
    def list_approvals(pid:str):
        with db() as con:return [dict(r) for r in con.execute('SELECT * FROM v27_approvals WHERE project_id=? ORDER BY created_at DESC',(pid,))]

    @app.post('/api/projects/{pid}/approvals',status_code=201)
    def approval(pid:str,data:ApprovalIn,request:Request):
        if AUTH_MODE!='required':return JSONResponse({'detail':'Named auth required for approval'},status_code=403)
        with db() as con:
            if data.object_type=='scenario':
                obj=con.execute('SELECT version FROM scenarios WHERE id=? AND project_id=?',(data.object_id,pid)).fetchone()
                if not obj or str(obj['version'])!=data.version:return JSONResponse({'detail':'Stale or missing scenario version'},status_code=409)
            elif data.object_type=='milestone':
                obj=con.execute('SELECT updated_at FROM delivery_milestones WHERE id=? AND project_id=?',(data.object_id,pid)).fetchone()
                if not obj or obj['updated_at']!=data.version:return JSONResponse({'detail':'Stale or missing milestone version'},status_code=409)
            else:
                # Proposal status and identity are resolved in intelligence module; no approval duplication here.
                return JSONResponse({'detail':'Use existing proposal review route; standalone approval blocked'},status_code=409)
            approval_id=secrets.token_hex(12)
            try:
                con.execute('BEGIN IMMEDIATE')
                con.execute('INSERT INTO v27_approvals VALUES(?,?,?,?,?,?,?,?,?)',(approval_id,pid,data.object_type,data.object_id,data.version,data.decision,request.state.user_id,data.reason,utc()))
                append_audit(con,request.state.tenant_id,request.state.user_id,'approval.'+data.decision,data.object_id,{'type':data.object_type,'version':data.version,'reason':data.reason})
                con.execute('COMMIT')
            except sqlite3.IntegrityError:
                con.execute('ROLLBACK');return JSONResponse({'detail':'Decision already exists for this version'},status_code=409)
        return {'id':approval_id,'actor_id':request.state.user_id,'decision':data.decision,'version':data.version}
