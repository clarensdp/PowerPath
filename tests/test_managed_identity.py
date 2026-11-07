import pytest
from fastapi import FastAPI,Request,HTTPException
from fastapi.testclient import TestClient
from contextlib import contextmanager
from server import supabase_identity as identity
from server.institutional import ACTOR,TENANT

UID='e4fa97c1-a1ce-4a1b-b458-455abb54f877'

@pytest.mark.parametrize('data',[
 {'id':UID,'user_metadata':{'role':'admin','tenant':'other'}},
 {'id':'invalid','email_confirmed_at':'2026'},
 {'id':UID,'email_confirmed_at':'2026','is_anonymous':True},
])
def test_unconfirmed_anonymous_or_malformed_identity_rejected(monkeypatch,data):
 monkeypatch.setattr(identity,'auth_request',lambda *a,**k:data)
 with pytest.raises(HTTPException) as e:identity.verified_user('opaque')
 assert e.value.status_code==401

def test_verified_identity_ignores_metadata(monkeypatch):
 monkeypatch.setattr(identity,'auth_request',lambda *a,**k:{'id':UID,'email_confirmed_at':'2026','email':'x@example.com','user_metadata':{'role':'admin'}})
 assert identity.verified_user('opaque')=={'id':UID,'email':'x@example.com'}

class Rows:
 def __init__(self,rows):self.rows=rows
 def fetchone(self):return self.rows[0] if self.rows else None
 def __iter__(self):return iter(self.rows)

@pytest.mark.parametrize('path,method,provisioned,role,status',[
 ('/api/projects/p1','GET',True,'viewer',200),
 ('/api/projects/p2','GET',True,'admin',403),
 ('/api/projects/p1','POST',True,'viewer',403),
 ('/api/projects/p1/approvals','POST',True,'analyst',403),
 ('/api/projects/p1/approvals','POST',True,'approver',200),
 ('/api/projects/p1','GET',False,'admin',403),
 ('/api/projects/p1','GET',True,'revoked',401),
 ('/api/geo29/import','POST',True,'admin',403),
])
def test_managed_authorization_and_context_cleanup(monkeypatch,path,method,provisioned,role,status):
 monkeypatch.setattr(identity,'verified_user',lambda token:{'id':UID,'email':'x@example.com'})
 class Con:
  def execute(self,sql,args):
   assert ACTOR.get()==UID
   if 'v27_users' in sql:return Rows([{'id':UID}] if provisioned else [])
   if 'v27_sessions' in sql:return Rows([{'token_hash':'denied'}] if role=='revoked' else [])
   if 'v27_memberships' in sql:return Rows([{'tenant_id':'a','role':role}])
   if 'v27_project_tenants' in sql:return Rows([{'tenant_id':'a' if args[0]=='p1' else 'b'}])
   raise AssertionError(sql)
 @contextmanager
 def db():yield Con()
 app=FastAPI()
 @app.middleware('http')
 async def gate(req,next):return await identity.gate(req,next,db)
 @app.api_route('/{path:path}',methods=['GET','POST'])
 def endpoint(request:Request,path:str):return {'actor':ACTOR.get(),'tenant':TENANT.get()}
 client=TestClient(app)
 r=client.request(method,path,headers={'authorization':'Bearer opaque'})
 assert r.status_code==status,r.text
 if status==200:assert r.json()=={'actor':UID,'tenant':'a'}
 assert ACTOR.get() is None and TENANT.get() is None
 assert client.get('/api/projects/p1').status_code==401
