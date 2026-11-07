#!/usr/bin/env python3
"""Approved-domain source page fingerprint monitoring, not permit/filing API or auto approval."""
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json, hashlib, datetime, os
ROOT=Path(__file__).resolve().parent
STATE=ROOT/'evidence_watch_state.json'
HOSTS=('ferc.gov','epa.gov','pjm.com','ercot.com','tva.com','misoenergy.org')
def approved(url):
    u=urlparse(url)
    return u.scheme=='https' and bool(u.hostname) and any(u.hostname==h or u.hostname.endswith('.'+h) for h in HOSTS) and u.username is None and u.password is None

def check(config_path):
    cfg=json.loads(Path(config_path).read_text());previous=json.loads(STATE.read_text()) if STATE.exists() else {};updated=dict(previous);events=[]
    for item in cfg.get('watches',[]):
        url=item.get('url','');ident=item.get('id','');
        if not ident or not approved(url):
            events.append({'id':ident,'status':'rejected','reason':'Only HTTPS official-domain sources supported'});continue
        try:
            with urlopen(Request(url,headers={'User-Agent':'PowerPath evidence verification monitor (research contact via operator)'}),timeout=15) as res:
                if res.url!=url and not approved(res.url):raise ValueError('Redirect to disallowed domain')
                raw=res.read(2_000_001)
                if len(raw)>2_000_000:raise ValueError('Source exceeds size limit')
            h=hashlib.sha256(raw).hexdigest();old=previous.get(ident)
            result='new-source' if not old else ('changed-review-required' if old['sha256']!=h else 'unchanged')
            updated[ident]={'url':url,'sha256':h,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_type':'unreviewed-public-page','approval_status':'NOT_VERIFIED'}
            events.append({'id':ident,'status':result,'url':url,'approval_status':'NOT_VERIFIED'})
        except Exception as e:events.append({'id':ident,'status':'fetch-error','error':str(e)[:240]})
    STATE.write_text(json.dumps(updated,indent=2));return events
if __name__=='__main__':
    import sys
    if len(sys.argv)!=2:raise SystemExit('Usage: python3 evidence_watch.py watch_config.json')
    print(json.dumps(check(sys.argv[1]),indent=2))
