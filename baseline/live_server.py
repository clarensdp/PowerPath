#!/usr/bin/env python3
"""PowerPath v20.1 local-only live-data gateway. No external packages. Secrets remain server-side."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os, json, urllib.request, urllib.parse, datetime as dt, re, socketserver
ROOT=Path(__file__).resolve().parent
CACHE=ROOT/'live_cache';CACHE.mkdir(exist_ok=True)
ALLOWED={'PJM','ERCO','MISO','SWPP','CISO','NYIS','ISNE','BPAT','TVA','DUK','SOCO'}
def request(url,headers=None):
    req=urllib.request.Request(url,headers={'User-Agent':'PowerPath/20.1 live connector research',**(headers or {})})
    with urllib.request.urlopen(req,timeout=22) as x:
        if x.status!=200: raise ValueError('Upstream HTTP '+str(x.status))
        return json.loads(x.read(8_000_000))
def iso(s):return dt.datetime.now(dt.timezone.utc).isoformat()
def eia(q):
    reg=q.get('region',['PJM'])[0].upper();day=q.get('date',[(dt.date.today()-dt.timedelta(days=4)).isoformat()])[0]
    if not re.fullmatch(r'[A-Z]{3,5}',reg): raise ValueError('Bad region')
    dt.date.fromisoformat(day)
    params=[('frequency','hourly'),('data[0]','value'),('facets[respondent][]',reg),('facets[type][]','D'),('start',day+'T00'),('end',day+'T23'),('sort[0][column]','period'),('sort[0][direction]','asc'),('offset','0'),('length','100')]
    if os.getenv('EIA_API_KEY'):params.append(('api_key',os.environ['EIA_API_KEY']))
    url='https://api.eia.gov/v2/electricity/rto/region-data/data/?'+urllib.parse.urlencode(params)
    raw=request(url).get('response',{}).get('data',[])
    rows=[{'period_reported':v.get('period'),'value':float(v['value']),'unit':'MW','respondent':v.get('respondent',reg)} for v in raw if v.get('value') not in (None,'')]
    if not rows:raise ValueError('No EIA observations returned')
    return dict(schema='powerpath.connector.v1',source='eia930',source_url='https://api.eia.gov/v2/electricity/rto/region-data/data/',retrieved_at=iso(day),records=rows,quality={'status':'live-unreviewed','warning':'BA reported hour; verify daylight-saving alignment. Demand is not available site capacity.'},parameters={'region':reg,'date':day})
def pjm(q):
    key=os.getenv('PJM_API_KEY');node=q.get('node',[''])[0];day=q.get('date',[(dt.date.today()-dt.timedelta(days=4)).isoformat()])[0]
    if not key: raise ValueError('PJM_API_KEY not configured on server')
    if not re.fullmatch(r'\d{1,15}',node):raise ValueError('PJM numeric pnode ID required')
    dt.date.fromisoformat(day)
    params={'pnode_id':node,'datetime_beginning_ept':f'{day} 00:00 to {day} 23:59','rowCount':'100','startRow':'1','order':'Asc'}
    url='https://api.pjm.com/api/v1/da_hrl_lmps?'+urllib.parse.urlencode(params)
    raw=request(url,{'Ocp-Apim-Subscription-Key':key});values=raw if isinstance(raw,list) else raw.get('items',[])
    rows=[]
    for v in values:
        stamp=v.get('datetime_beginning_utc');price=v.get('total_lmp_da',v.get('total_lmp'))
        if stamp is None or price is None:continue
        # Do not make unsupported UTC assumptions. Keep original timestamp, format later after QA.
        rows.append({'time_utc':(stamp.replace(' ','T')+'Z' if 'Z' not in stamp and '+' not in stamp else stamp.replace(' ','T')),'value':float(price),'unit':'USD/MWh','node':node})
    if not rows: raise ValueError('PJM returned no valid rows; review node/feed/date')
    return dict(schema='powerpath.connector.v1',source='pjm_lmp',source_url='https://api.pjm.com/api/v1/da_hrl_lmps',retrieved_at=iso(day),records=rows,quality={'status':'live-unreviewed','warning':'PJM wholesale day-ahead LMP; verify UTC/DST and license before activation.'},parameters={'node':node,'date':day})
class H(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT),**kw)
    def do_GET(self):
        p=urllib.parse.urlparse(self.path)
        if p.path=='/api/health':return self.out(200,{'ok':True,'service':'PowerPath local live gateway','pjmConfigured':bool(os.getenv('PJM_API_KEY')),'eiaConfigured':bool(os.getenv('EIA_API_KEY'))})
        if p.path in ['/api/live/eia','/api/live/pjm']:
            try:
                q=urllib.parse.parse_qs(p.query);kind='eia' if p.path.endswith('eia') else 'pjm';obj=(eia(q) if kind=='eia' else pjm(q));return self.out(200,obj)
            except Exception as exc:return self.out(502,{'error':str(exc),'source':'upstream-unavailable','live':False})
        return super().do_GET()
    def out(self,status,o):
        b=json.dumps(o,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
if __name__=='__main__':
    print('PowerPath live gateway: http://127.0.0.1:8765/PowerPath.html (local machine only)')
    ThreadingHTTPServer(('127.0.0.1',8765),H).serve_forever()
