"""Read-only parcel footprint GIS. Local alpha only: required-auth mode remains gated.

No database tables or permit status are modified. A stored parcel ID resolves
against existing versioned GeoStore; otherwise a bounded GeoJSON boundary is used.
"""
from __future__ import annotations
import json,os
from fastapi import HTTPException,Request
from permitting.footprint import FootprintError,assess
from permitting.footprint_sources import official_overlays
from permitting.official_gis import remote_enabled

MAX_REQUEST_BYTES=3_000_000

def install(app,db,root):
    from server.geo29 import GeoStore
    store=GeoStore(db,root)
    def gate():
        if os.getenv('POWERPATH_V27_AUTH_MODE')=='required':
            raise HTTPException(503,'Footprint alpha unavailable in required-auth mode until tenant-scoped controls are implemented')

    @app.get('/api/permitting/footprint/status')
    def footprint_status():
        gate()
        return {'version':'permitiq-footprint-0.1','mode':'read-only parcel polygon intersections',
            'official_polygon_service_enabled':remote_enabled(),
            'municipal_zoning':'SOURCE_REQUIRED: operator-supplied GeoJSON polygons, not automatically discovered',
            'coverage':'Unknown unless an explicit mapped-extent geometry is supplied',
            'preserves_financial_engine':True}

    @app.post('/api/permitting/footprint')
    async def footprint(request:Request):
        gate()
        parts=[];byte_count=0
        async for part in request.stream():
            byte_count+=len(part)
            if byte_count>MAX_REQUEST_BYTES:raise HTTPException(413,'Footprint request exceeds 3 MB')
            parts.append(part)
        raw=b''.join(parts)
        try:
            body=json.loads(raw)
            if not isinstance(body,dict) or set(body)-{'parcel_id','geometry','parcel_source','layers','official','consent_remote'}:
                raise FootprintError('Unexpected fields in footprint request')
            identifier=body.get('parcel_id')
            geometry=body.get('geometry')
            if bool(identifier)==bool(geometry):raise FootprintError('Supply exactly one of parcel_id or geometry')
            if identifier:
                if not isinstance(identifier,str) or len(identifier)>200:raise FootprintError('Invalid parcel ID')
                row=store.get(identifier)
                if not row:raise HTTPException(404,'Parcel ID unavailable in connected source cache')
                record=json.loads(row['feature_json'])
                geometry=record['geometry']
                properties=record.get('properties') or {}
                source={'title':properties.get('source_id',row['source_id']),
                        'version_id':row['version_id'],
                        'retrieved_at':properties.get('retrieved_at'),
                        'url':properties.get('source_url',''),
                        'data_provenance':properties.get('source_provenance','unknown')}
            else:
                source=body.get('parcel_source') or {'title':'Operator-supplied boundary (unverified)'}
            layers=body.get('layers',[])
            if not isinstance(layers,list):raise FootprintError('layers must be a list')
            warning=[];stats={}
            if body.get('official') is True:
                if body.get('consent_remote') is not True:
                    raise FootprintError('Explicit consent required to transmit the parcel boundary to government GIS services')
                if not remote_enabled():raise HTTPException(503,'Official remote GIS disabled by operator')
                extra,stats,warning=official_overlays(geometry,consent=True)
                layers=[*layers,*extra]
            elif body.get('official') not in (False,None):
                raise FootprintError('official must be a boolean')
            result=assess(geometry,layers,parcel_source=source)
            result['official_services']=stats
            result['warnings'].extend(warning)
            result['input_type']='CACHED_SOURCE_PARCEL' if identifier else 'USER_SUPPLIED_GEOMETRY'
            return result
        except HTTPException:raise
        except (json.JSONDecodeError,FootprintError,TypeError,KeyError,ValueError) as exc:
            raise HTTPException(422,str(exc)[:250]) from exc
