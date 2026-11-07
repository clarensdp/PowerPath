#!/usr/bin/env python3
"""PowerPath official-data snapshot ingestion (network needed for live fetch).
No credentials are stored. Fail closed on API errors and missing/invalid dates.
FERC/EPA evidence intake is explicit human-curated evidence, not automated permit verification.
"""
import argparse, csv, datetime as dt, json, os, pathlib, urllib.parse, urllib.request
SCHEMA='powerpath.connector.v1'

def fetch(url,headers=None):
    request=urllib.request.Request(url,headers={'User-Agent':'PowerPath-Connector/0.1 (+analyst supplied credentials)',**(headers or {})})
    with urllib.request.urlopen(request,timeout=35) as r:
        return json.load(r)

def ts(t):
    z=dt.datetime.fromisoformat(t.replace('Z','+00:00'))
    if z.tzinfo is None: raise ValueError('Timezone required; UTC explicitly')
    return z.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')

def snap(kind,url,rows,warning):
    if not rows: raise ValueError('No records returned; refusing to create empty snapshot')
    return {'schema':SCHEMA,'source':kind,'source_url':url,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'quality':{'status':'unreviewed','warning':warning},'records':rows}

def eia(args):
    # API v2 /electricity/rto/region-data/; demand in MW, BA key from EIA
    key=os.getenv('EIA_API_KEY','')
    params=[('frequency','hourly'),('data[0]','value'),('facets[respondent][]',args.region),('facets[type][]','D'),('start',args.start),('end',args.end),('sort[0][column]','period'),('sort[0][direction]','asc'),('offset','0'),('length','5000')]
    if key:params.append(('api_key',key))
    url='https://api.eia.gov/v2/electricity/rto/region-data/data/?'+urllib.parse.urlencode(params)
    obj=fetch(url);raw=obj.get('response',{}).get('data',[])
    rows=[]
    for v in raw:
        # EIA period is local EIA reported hour without reliable unambiguous UTC offset for DST.
        # Store original period as a timestamp string and do NOT claim UTC until disambiguated.
        period=str(v.get('period',''))
        if not period:raise ValueError('Missing EIA period')
        val=float(v['value']);rows.append({'period_reported':period,'value':val,'unit':'MW','respondent':v.get('respondent',args.region),'type':'D'})
    return snap('eia930',url,rows,'EIA reported timestamps require timezone/DST alignment before hourly model activation; values are balancing-area demand, not site capacity')

def pjm(args):
    key=os.getenv('PJM_API_KEY')
    if not key:raise ValueError('Set PJM_API_KEY in environment (PJM Data Miner API subscription key); not stored')
    if not args.node:raise ValueError('--node pnode ID required')
    q={'datetime_beginning_utc':args.start+' 00:00 to '+args.end+' 23:59','pnode_id':args.node,'rowCount':50000,'startRow':1,'order':'Asc'}
    url='https://api.pjm.com/api/v1/da_hrl_lmps?'+urllib.parse.urlencode(q)
    obj=fetch(url,{'Ocp-Apim-Subscription-Key':key});raw=obj if isinstance(obj,list) else obj.get('items',obj.get('data',[]))
    rows=[]
    for v in raw:
        t=v.get('datetime_beginning_utc');value=v.get('total_lmp_da')
        if value is None:value=v.get('total_lmp')
        if t is None or value is None:raise ValueError('Missing PJM timestamp or LMP; check feed schema')
        rows.append({'time_utc':ts(t if ('Z' in t or '+' in t) else t+'Z'),'value':float(value),'unit':'USD/MWh','node':str(v.get('pnode_id',args.node))})
    rows.sort(key=lambda x:x['time_utc'])
    if len(rows)>1 and len({x['time_utc'] for x in rows})!=len(rows):raise ValueError('Duplicate hours, page/feed issue')
    return snap('pjm_lmp',url.split('?')[0],rows,'Wholesale day-ahead nodal price; does not include retail tariff, delivered capacity or distribution service; verify PJM redistribution rights')

def evidence(args):
    kind=args.cmd;url='https://echo.epa.gov/' if kind=='epa_echo' else 'https://elibrary.ferc.gov/eLibrary/'
    rows=[]
    with open(args.csv,encoding='utf-8-sig',newline='') as f:
        for x in csv.DictReader(f):
            if not (x.get('reference') and x.get('status') and x.get('as_of')):raise ValueError('CSV requires reference,status,as_of fields')
            if not x['as_of'][:4].isdigit():raise ValueError('Invalid evidence date')
            rows.append({k:x.get(k,'') for k in ['reference','status','as_of','project_id','facility_id','docket','url','notes']})
    return snap(kind,url,rows,'User-curated official-document references, unverified by PowerPath. Filing/permit appearance does not establish project approvals')

def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='cmd',required=True)
    x=sub.add_parser('eia930');x.add_argument('--region',required=True);x.add_argument('--start',required=True);x.add_argument('--end',required=True)
    x=sub.add_parser('pjm_lmp');x.add_argument('--node',required=True);x.add_argument('--start',required=True);x.add_argument('--end',required=True)
    for name in ('epa_echo','ferc_docket'):sub.add_parser(name).add_argument('--csv',required=True)
    ap.add_argument('--out',required=True);a=ap.parse_args()
    obj=eia(a) if a.cmd=='eia930' else pjm(a) if a.cmd=='pjm_lmp' else evidence(a)
    pathlib.Path(a.out).write_text(json.dumps(obj,indent=2))
    print(f'Wrote {a.out}: {len(obj["records"])} {a.cmd} records (unreviewed)')
if __name__=='__main__':main()
