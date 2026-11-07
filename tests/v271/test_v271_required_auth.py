"""v27.1 required-auth tests (Part VI test 18 and the positive path of test 17). Separate process: auth mode is read at import.
Run: python -m unittest tests.v271.test_v271_required_auth -v
"""
import os, tempfile, unittest
TD = tempfile.TemporaryDirectory(prefix='pp_v271_auth_')
os.environ['POWERPATH_DATA_DIR'] = TD.name
os.environ['POWERPATH_V27_AUTH_MODE'] = 'required'
from fastapi.testclient import TestClient
from server.app import app, db
from server.institutional import init, password_hash, utc
C = TestClient(app, base_url='http://localhost')
PW = 'secure-long-test-password'
with db() as con:
    init(con)
    for t in ('a', 'b'): con.execute('INSERT INTO v27_tenants VALUES(?,?,?)', (t, t.upper(), utc()))
    for uid, email, role, tenant in [('approver', 'ap@a.test', 'approver', 'a'), ('analyst', 'an@a.test', 'analyst', 'a'), ('viewer', 'v@a.test', 'viewer', 'a'), ('other', 'o@b.test', 'admin', 'b')]:
        con.execute('INSERT INTO v27_users VALUES(?,?,?,?,?)', (uid, email, password_hash(PW), 1, utc()))
        con.execute('INSERT INTO v27_memberships VALUES(?,?,?)', (uid, tenant, role))
TOK = {u: C.post('/api/v27/auth/login', json={'email': e, 'password': PW}).json()['access_token'] for u, e in [('approver', 'ap@a.test'), ('analyst', 'an@a.test'), ('viewer', 'v@a.test'), ('other', 'o@b.test')]}
H = lambda u, tenant=None: {'Authorization': 'Bearer ' + TOK[u], **({'X-PowerPath-Tenant': tenant} if tenant else {})}


class T18_CrossTenant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pid = C.post('/api/projects', headers=H('analyst', 'a'), json={'name': 'Core'}).json()['id']
        cls.B = f'/api/projects/{cls.pid}/transactions/core-scientific-2026'
        assert C.post(cls.B + '/model', headers=H('analyst')).status_code == 201

    def test_other_tenant_denied_everywhere(self):
        for m, u, body in (('post', '/model', None), ('get', '/inputs', None), ('get', '/terms', None), ('get', '/debt-schedule', None), ('get', '/scenarios', None),
                           ('get', '/reconciliation', None), ('post', '/illustrative-project', {'scenario': 'base'}),
                           ('post', '/inputs/coupon/reclassify', {'classification': 'UNVERIFIED', 'rationale': 'cross tenant attempt'})):
            r = getattr(C, m)(self.B + u, headers=H('other'), **({'json': body} if body is not None else {}))
            self.assertEqual(r.status_code, 403, f'{m} {u}: {r.status_code}')
        for u in ('/paths/x/schedule', '/paths/x/schedule-impact'):
            self.assertEqual(C.get(f'/api/projects/{self.pid}{u}', headers=H('other')).status_code, 403)
        self.assertEqual(C.get(self.B + '/inputs').status_code, 401)

    def test_viewer_cannot_write(self):
        r = C.post(self.B + '/inputs/coupon/reclassify', headers=H('viewer'), json={'classification': 'UNVERIFIED', 'rationale': 'viewer attempt to write'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(C.get(self.B + '/terms', headers=H('viewer')).status_code, 200)


class T17_PromotionPositivePath(unittest.TestCase):
    def test_executed_promotion_requires_approver_and_document(self):
        pid = C.post('/api/projects', headers=H('analyst', 'a'), json={'name': 'Core2'}).json()['id']
        B = f'/api/projects/{pid}/transactions/core-scientific-2026'; C.post(B + '/model', headers=H('analyst'))
        body = {'classification': 'EXECUTED_CONTRACT_VERIFIED', 'rationale': 'Indenture section verified', 'source_url': 'https://dataroom.example/indenture.pdf'}
        self.assertEqual(C.post(B + '/inputs/coupon/reclassify', headers=H('analyst'), json=body).status_code, 403)       # analyst is not an approver
        self.assertEqual(C.post(B + '/inputs/coupon/reclassify', headers=H('approver'), json=body).status_code, 422)      # no document
        ev = C.post(f'/api/projects/{pid}/evidence', headers=H('analyst'), json={'title': 'Indenture (test bytes)', 'evidence_status': 'executed_document'}).json()['id']
        self.assertEqual(C.post(B + '/inputs/coupon/reclassify', headers=H('approver'), json={**body, 'evidence_id': ev}).status_code, 422)  # record has no file
        up = C.post(f'/api/projects/{pid}/evidence/{ev}/file', headers=H('analyst'), files={'attachment': ('indenture.pdf', b'%PDF-1.4 synthetic test bytes', 'application/pdf')})
        self.assertEqual(up.status_code, 200, up.text)
        bad = C.post(B + '/inputs/coupon/reclassify', headers=H('approver'), json={**body, 'evidence_id': ev, 'source_url': 'https://www.sec.gov/Archives/edgar/data/1839341/x.htm'})
        self.assertEqual(bad.status_code, 422)                                                                             # a filing is not an executed contract
        ok = C.post(B + '/inputs/coupon/reclassify', headers=H('approver'), json={**body, 'evidence_id': ev})
        self.assertEqual(ok.status_code, 201, ok.text)
        self.assertEqual((ok.json()['g4'], ok.json()['g5']), ('BLOCKED', 'BLOCKED'))                                     # gates never unlock via API
        inp = {x['name']: x for x in C.get(B + '/inputs', headers=H('viewer')).json()['inputs']}
        self.assertEqual(inp['coupon']['reviewer'], 'approver'); self.assertEqual(len(inp['coupon']['document_sha256']), 64)
        self.assertEqual(C.get(B + '/terms', headers=H('viewer')).json()['g4'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
