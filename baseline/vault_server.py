"""PowerPath v23 loopback-only document vault prototype. NOT production / internet facing.
Launch: POWERPATH_VAULT_PASSWORD='long-secret' python3 vault_server.py
No TLS, multi-user isolation, encryption at rest or authorization roles.
"""
import base64, hashlib, hmac, json, mimetypes, os, re, secrets, sqlite3, sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote

BASE=Path(__file__).resolve().parent
DATA=Path(os.environ.get('POWERPATH_VAULT_DIR',str(BASE/'.private_vault'))).resolve()
MAX_BYTES=12*1024*1024
ID=re.compile(r'^[a-zA-Z0-9_-]{1,96}$')

def now(): return datetime.now(timezone.utc).isoformat()
def init_db():
    DATA.mkdir(mode=0o700,parents=True,exist_ok=True)
    try: os.chmod(DATA,0o700)
    except OSError: pass
    (DATA/'blobs').mkdir(mode=0o700,exist_ok=True)
    with sqlite3.connect(DATA/'vault.db') as c:
        c.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, project TEXT NOT NULL, name TEXT NOT NULL, category TEXT, source TEXT, reviewer TEXT, sha256 TEXT NOT NULL, size INTEGER, created TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT, document TEXT, action TEXT NOT NULL, at TEXT NOT NULL)')
    try: os.chmod(DATA/'vault.db',0o600)
    except OSError: pass

def db(): return sqlite3.connect(DATA/'vault.db')
def safeid(x): return bool(ID.fullmatch(x))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(BASE),**kwargs)
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def log_message(self,*args): pass
    def json_response(self,status,payload):
        b=json.dumps(payload).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def authorized(self):
        auth=self.headers.get('Authorization','')
        expected='Basic '+base64.b64encode(('powerpath:'+os.environ.get('POWERPATH_VAULT_PASSWORD','')).encode()).decode()
        return hmac.compare_digest(auth,expected)
    def check(self):
        if not self.authorized():
            self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="PowerPath Local Vault"');self.send_header('Content-Length','0');self.end_headers();return False
        if self.command in ('POST','DELETE'):
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                self.json_response(403,{'error':'Cross-origin write rejected'});return False
        return True
    def parsed(self):
        parts=[unquote(s) for s in urlparse(self.path).path.split('/') if s]
        if len(parts)<4 or parts[:3]!=['api','v23','projects'] or not safeid(parts[3]): return None
        if len(parts)>6:return None
        return parts
    def do_GET(self):
        if self.path.startswith('/api/'):
            if not self.check():return
            parts=self.parsed()
            if not parts: return self.json_response(400,{'error':'Invalid resource'})
            project=parts[3]
            with db() as c:
                if len(parts)==5 and parts[4]=='documents':
                    rows=c.execute('SELECT id,name,category,source,reviewer,sha256,size,created FROM documents WHERE project=? ORDER BY created DESC',(project,)).fetchall()
                    return self.json_response(200,{'documents':[dict(zip(['id','name','category','source','reviewer','sha256','size','created'],r)) for r in rows]})
                if len(parts)==5 and parts[4]=='audit':
                    rows=c.execute('SELECT document,action,at FROM audit WHERE project=? ORDER BY seq DESC LIMIT 250',(project,)).fetchall()
                    return self.json_response(200,{'events':[dict(zip(['document','action','at'],r)) for r in rows]})
                if len(parts)==6 and parts[4]=='documents' and safeid(parts[5]):
                    row=c.execute('SELECT name FROM documents WHERE project=? AND id=?',(project,parts[5])).fetchone()
                    if not row:return self.json_response(404,{'error':'Not found'})
                    data=(DATA/'blobs'/parts[5]).read_bytes()
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+__import__('urllib.parse',fromlist=['quote']).quote(row[0]));self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            return self.json_response(404,{'error':'Not found'})
        if urlparse(self.path).path.startswith(('/.private_vault','/workspace/','/vault_server.py','/tests/','/.')):return self.send_error(404)
        return super().do_GET()
    def do_POST(self):
        if not self.check():return
        parts=self.parsed()
        if not parts or len(parts)!=5 or parts[4]!='documents':return self.json_response(404,{'error':'Not found'})
        n=int(self.headers.get('Content-Length','0') or 0)
        if n<1 or n>MAX_BYTES:return self.json_response(413,{'error':'Upload must be 1 byte to 12 MB'})
        raw=self.rfile.read(n);name=self.headers.get('X-PP-Name','attachment')[:200].replace('/','_').replace('\\','_');category=self.headers.get('X-PP-Category','Other')[:100];source=self.headers.get('X-PP-Source','')[:800];reviewer=self.headers.get('X-PP-Reviewer','')[:100]
        uid=secrets.token_hex(16);checksum=hashlib.sha256(raw).hexdigest()
        target=DATA/'blobs'/uid
        with target.open('xb') as f:f.write(raw)
        os.chmod(target,0o600)
        with db() as c:
            c.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)',(uid,parts[3],name,category,source,reviewer,checksum,n,now()))
            c.execute('INSERT INTO audit(project,document,action,at) VALUES(?,?,?,?)',(parts[3],uid,'upload',now()))
        return self.json_response(201,{'id':uid,'sha256':checksum,'size':n})
    def do_DELETE(self):
        if not self.check():return
        parts=self.parsed()
        if not parts or len(parts)!=6 or parts[4]!='documents' or not safeid(parts[5]):return self.json_response(404,{'error':'Not found'})
        with db() as c:
            cur=c.execute('DELETE FROM documents WHERE project=? AND id=?',(parts[3],parts[5]));found=cur.rowcount
            if found:c.execute('INSERT INTO audit(project,document,action,at) VALUES(?,?,?,?)',(parts[3],parts[5],'delete',now()))
        if not found:return self.json_response(404,{'error':'Not found'})
        (DATA/'blobs'/parts[5]).unlink(missing_ok=True)
        return self.json_response(200,{'deleted':True})

if __name__=='__main__':
    if len(os.environ.get('POWERPATH_VAULT_PASSWORD',''))<12:sys.exit('Set POWERPATH_VAULT_PASSWORD to a unique 12+ character password.')
    init_db()
    httpd=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('POWERPATH_VAULT_PORT','8766'))),Handler)
    print(f'PowerPath local vault at http://127.0.0.1:{httpd.server_port}/PowerPath.html (loopback only)')
    httpd.serve_forever()
