"""Bounded public parcel queries for NC OneMap and Virginia VGIN.
No bulk crawling. Source geometry/date do not establish site or power availability.
"""
import hashlib,json,math,time,threading,urllib.parse,urllib.request
from collections import OrderedDict,defaultdict
from datetime import datetime,timezone
from fastapi import HTTPException,Query
from server.geo29 import geometry_bounds,parse_bbox,stamp

SOURCES={
 '37':{'id':'nc-onemap','name':'NC OneMap','url':'https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1',
       'fields':'nparno,parno,stcntyfips,gisacres,cntyname,sourcedate,revisedate',
       'bounds':[-84.33,33.84,-75.45,36.59], 'license':'NC OneMap / county and Eastern Band of Cherokee Indians sources. Public planning data; retain attribution. Not a survey.',
       'scope':'Statewide source: all 100 counties plus Eastern Band of Cherokee Indians; bounded viewport results only.'},
 '51':{'id':'va-vgin','name':'Virginia VGIN','url':'https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VA_Base_Layers/VA_Parcels/FeatureServer/0',
       'fields':'VGIN_QPID,FIPS,LOCALITY,PARCELID,PTM_ID,LASTUPDATE',
       'bounds':[-83.68,36.53,-75.2,39.47], 'license':'VGIN Virginia Parcels catalog: CC0. Virginia locality sources; not a survey. Locality completeness and dates vary.',
       'scope':'Statewide aggregation; locality participation and update dates vary. Bounded viewport results only.'}}

def overlaps(a,b):return a[0]<=b[2] and a[2]>=b[0] and a[1]<=b[3] and a[3]>=b[1]
def date_text(value):
 if value is None:return None
 try:return datetime.fromtimestamp(float(value)/1000,timezone.utc).date().isoformat()
 except (ValueError,TypeError,OverflowError,OSError):return None

def area_sqft(g):
 """Spherical polygon area; approximate, subtracting holes. WGS84 degrees in."""
 polygons=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
 def ring_area(ring):
  total=0
  for a,b in zip(ring,ring[1:]):
   dx=math.radians(b[0]-a[0]);dx=(dx+math.pi)%(2*math.pi)-math.pi
   total+=dx*(2+math.sin(math.radians(a[1]))+math.sin(math.radians(b[1])))
  return abs(total)*6371008.8**2/2
 return sum(max(0,ring_area(p[0])-sum(ring_area(h) for h in p[1:])) for p in polygons)*10.76391041671

def normalize(state,f):
 p=f['properties'];g=f['geometry'];geometry_bounds(g)
 if state=='37':
  geoid=str(p.get('stcntyfips') or '')
  native=str(p.get('nparno') or '')
  parcel=str(p.get('parno') or native)
  acres=p.get('gisacres')
  sqft=float(acres)*43560 if acres is not None else area_sqft(g)
  basis='source GIS acreage' if acres is not None else 'approximate spherical geometry'
  source_date=date_text(p.get('sourcedate'));locality=p.get('cntyname')
 else:
  geoid=str(p.get('FIPS') or '')
  qpid=p.get('VGIN_QPID')
  if isinstance(qpid,(int,float)) and math.isfinite(qpid) and qpid==int(qpid):native=str(int(qpid))
  else:native=str(qpid or '')
  parcel=str(p.get('PARCELID') or p.get('PTM_ID') or native)
  sqft=area_sqft(g);basis='approximate spherical geometry';source_date=date_text(p.get('LASTUPDATE'));locality=p.get('LOCALITY')
 if len(geoid)!=5 or not geoid.isdigit() or not geoid.startswith(state) or not native.strip():raise ValueError('Missing jurisdiction or stable source parcel ID')
 if not math.isfinite(sqft) or sqft<0:raise ValueError('Invalid acreage')
 # Safe fixed-length storage ID retains the original agency identifier separately.
 key=hashlib.sha256((geoid+':'+native).encode()).hexdigest()[:32]
 return {'type':'Feature','geometry':g,'properties':{'cache_id':key,'native_id':native,'parcelnumb':parcel,'geoid':geoid,
  'area_sqft':sqft,'area_basis':basis,'source_document_date':source_date,'locality':locality,
  'source_agency':SOURCES[state]['name']}}

class PublicParcels:
 def __init__(self,store,transport=None):
  self.store=store;self.transport=transport or urllib.request.urlopen;self.cache=OrderedDict();self.lock=threading.Lock()
 def fetch(self,state,bbox,limit,min_acres):
  source=SOURCES[state]
  where='1=1'
  if state=='37' and min_acres:where='gisacres >= '+str(float(min_acres))
  params={'f':'geojson','where':where,'geometry':','.join(map(str,bbox)),'geometryType':'esriGeometryEnvelope','inSR':4326,'outSR':4326,
   'spatialRel':'esriSpatialRelIntersects','outFields':source['fields'],'returnGeometry':'true','resultRecordCount':limit,'orderByFields':'objectid ASC' if state=='37' else 'OBJECTID ASC'}
  key=(state,tuple(bbox),limit,min_acres)
  with self.lock:
   entry=self.cache.get(key)
   if entry and time.monotonic()-entry[0]<300:return entry[1],True
  url=source['url']+'/query?'+urllib.parse.urlencode(params)
  with self.transport(url,timeout=15) as response:raw=response.read(16*1024*1024+1)
  if len(raw)>16*1024*1024:raise ValueError('Source response too large')
  data=json.loads(raw)
  if data.get('error') or data.get('type')!='FeatureCollection':raise ValueError('Source query failed')
  fs=data.get('features')
  if not isinstance(fs,list) or len(fs)>limit:raise ValueError('Unexpected source result count')
  grouped=defaultdict(list);invalid=0
  for f in fs:
   try:
    nf=normalize(state,f);grouped[nf['properties']['geoid']].append(nf)
   except (ValueError,TypeError,KeyError,IndexError):invalid+=1
  result=[];retrieved=stamp()
  with self.lock:
   for geoid,features in grouped.items():
    src={'id':source['id']+'-'+geoid,'name':source['name']+' · '+geoid,'state_fips':state,'county_fips':geoid[2:],
     'source_url':source['url'],'license_note':source['license'],'coverage_scope':source['scope'],'retrieved_at':retrieved,'provenance':'public_live_viewport'}
    version=self.store.ingest(src,{'type':'FeatureCollection','features':features},'cache_id','area_sqft')['version_id']
    with self.store.db() as con:
     rows=con.execute('SELECT rid,parcel_key,feature_json FROM geo29_parcels WHERE version_id=?',(version,)).fetchall()
     for row in rows:
      con.execute('INSERT INTO geo30_latest VALUES(?,?) ON CONFLICT(parcel_key) DO UPDATE SET record_id=excluded.record_id',(row['parcel_key'],row['rid']))
      result.append(json.loads(row['feature_json']))
   payload={'features':result,'truncated':bool(data.get('exceededTransferLimit')) or len(fs)==limit,'invalid_records':invalid,'retrieved_at':retrieved}
   self.cache[key]=(time.monotonic(),payload)
   while len(self.cache)>64:self.cache.popitem(last=False)
  return payload,False
 def query(self,bbox,min_acres=0,pin='',limit=200,state=None):
  if bbox[2]-bbox[0]>.8 or bbox[3]-bbox[1]>.8:
   return {'type':'FeatureCollection','features':[],'status':'zoom_required','messages':['Zoom to a county or smaller area to load public parcels.'],'has_more':False,'total_matches':None}
  features=[];messages=[];has_more=False;failures=0;attempted=0
  for sf,src in SOURCES.items():
   if (state and sf!=state) or not overlaps(bbox,src['bounds']):continue
   attempted+=1
   try:
    payload,cached=self.fetch(sf,bbox,limit,min_acres);features+=payload['features'];has_more|=payload['truncated']
    messages.append(src['name']+(': cached query (≤5 minutes).' if cached else ': live query retrieved '+payload['retrieved_at']+'.'))
    if payload['invalid_records']:messages.append(str(payload['invalid_records'])+' invalid records omitted.')
   except Exception:
    failures+=1
    cached=self.store.query(bbox,sf,min_acres,limit=limit)['features']
    features+=cached;messages.append(src['name']+' unavailable; showing previously fetched records where available. These may be stale.')
  # Filtering after VA's bounded query cannot guarantee an exhaustive acreage search.
  features=[f for f in features if (f['properties'].get('area_sqft',f['properties'].get('PA_LEGAL_SQFT')) or 0)/43560>=min_acres and (not pin or pin.casefold() in str(f['properties'].get('parcelnumb',f['properties'].get('PA_MCPI',''))).casefold())]
  dedup={f['properties']['workspace_id']:f for f in features};features=list(dedup.values())
  has_more|=len(features)>limit;features=features[:limit]
  if has_more:messages.append('Result limit reached; zoom in. Acreage/PIN filters apply to returned records and may miss matches outside this subset.')
  if not attempted:messages.append('Live public parcel connections currently cover NC and VA only.')
  if not features:messages.append('No displayed matches does not establish that no suitable parcels exist.')
  return {'type':'FeatureCollection','features':features,'total_matches':None,'displayed_records':len(features),'has_more':has_more,
   'status':'source_unavailable' if failures else 'live' if attempted else 'unsupported','messages':messages}

def install(app,store):
 service=PublicParcels(store)
 @app.get('/api/geo30/sources')
 def sources():return {'sources':[{'state_fips':s,**v} for s,v in SOURCES.items()],'mode':'public services; viewport queries; internet required; no paid API key'}
 @app.get('/api/geo30/parcels')
 def parcels(bbox:str,min_acres:float=Query(0,ge=0,le=1000000),pin:str=Query('',max_length=80),limit:int=Query(200,ge=1,le=200),state:str|None=None):
  if state and state not in SOURCES:raise HTTPException(422,'Live parcels support state FIPS 37 and 51')
  return service.query(parse_bbox(bbox),min_acres,pin,limit,state)
 return service
