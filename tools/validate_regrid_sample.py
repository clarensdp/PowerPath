"""Validate a downloaded evaluation sample in an isolated temporary database; production stays unchanged."""
import argparse, hashlib, json, os, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('geojson');args=p.parse_args()
with tempfile.TemporaryDirectory(prefix='powerpath_regrid_evaluation_') as tmp:
 os.environ['POWERPATH_DATA_DIR']=tmp
 from server.app import db,ROOT
 from server.geo29 import GeoStore, stamp
 from server.providers.regrid import normalize,summarize
 raw=Path(args.geojson).read_bytes();coll=normalize(json.loads(raw));report=summarize(coll)
 counties={f['properties']['geoid'] for f in coll['features']}
 if len(counties)!=1:raise ValueError('Evaluation accepts one county sample at a time')
 geoid=next(iter(counties));store=GeoStore(db,ROOT)
 source={'id':'regrid-eval','name':'Regrid sample: isolated evaluation only','state_fips':geoid[:2],'county_fips':geoid[2:],'source_url':'https://app.regrid.com/store/samples','license_note':'Vendor-provided sample evaluated only in a temporary database; no production redistribution rights assumed.','coverage_scope':'Downloaded county evaluation sample; not live product coverage','retrieved_at':stamp(),'provenance':'provider_evaluation_sample'}
 result=store.ingest(source,coll,'provider_id','area_sqft')
 found=store.query(state=geoid[:2],limit=1)
 # The bundled pilot is VA, so this evaluation command uses a non-VA sample.
 count=sum(s['feature_count'] for s in store.registry() if s['id']=='regrid-eval')
 assert count==len(coll['features'])
 f=coll['features'][0];stored=store.get(geoid+':regrid-eval:'+f['properties']['provider_id'])
 assert stored is not None
 report.update({'source':'https://app.regrid.com/store/samples','evaluated_at':stamp(),'input_sha256':hashlib.sha256(raw).hexdigest(),'spatial_import_records':count,'spatial_query_returned_features':len(found['features']),'stable_id_lookup_passed':True,'evaluation_database':'temporary; deleted after evaluation','production_coverage_changed':False})
 print(json.dumps(report,indent=2))
