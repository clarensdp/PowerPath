#!/usr/bin/env python3
"""Offline import of an operator-downloaded official Census cartographic county layer.

Examples:
    python scripts/prepare_tiger_counties.py /path/to/cb_2025_us_county_500k.zip \
        --source-url https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip
    python scripts/prepare_tiger_counties.py /path/to/counties.geojson --source-url ...

Optional build dependency: pip install geopandas pyogrio shapely.
This script never downloads data automatically, and never changes database records.
Source is 1:500k generalization: not a survey, municipal zoning layer or legal boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DEST=ROOT/'data_sources'/'us_counties_500k.geojson'
STATES={'01','02','04','05','06','08','09','10','11','12','13','15','16','17','18','19','20','21','22',
        '23','24','25','26','27','28','29','30','31','32','33','34','35','36','37','38','39','40',
        '41','42','44','45','46','47','48','49','50','51','53','54','55','56'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input_file',type=Path,help='Downloaded cartographic county ZIP or GeoJSON')
    p.add_argument('--source-url',required=True,help='Official Census download URL and year')
    p.add_argument('--allow-overwrite',action='store_true')
    a=p.parse_args()
    if not a.input_file.is_file() or not a.source_url.startswith('https://www2.census.gov/'):
        p.error('Require an existing file and its official https://www2.census.gov/ source URL')
    if DEST.exists() and not a.allow_overwrite:p.error('County geometry already imported; use --allow-overwrite to update')
    import geopandas as gpd
    frame=gpd.read_file(a.input_file)
    if frame.crs is None:raise ValueError('Missing projection; cannot assume WGS84')
    frame=frame.to_crs('EPSG:4326')
    fields={'GEOID','NAME','STATE'}
    if fields-set(frame.columns):raise ValueError('Missing official Census county fields: '+str(fields-set(frame.columns)))
    if frame.geometry.isna().any():raise ValueError('Null geometry detected')
    frame=frame[frame['STATE'].isin(STATES)].copy()
    if len(frame)<3000 or frame['GEOID'].nunique()!=len(frame):raise ValueError('Incomplete or duplicate nationwide county dataset')
    if any(not isinstance(g.type,str) or g.type not in ('Polygon','MultiPolygon') or not g.is_valid for g in frame.geometry):
        raise ValueError('Invalid county geometry')
    geo=json.loads(frame[['GEOID','STATE','NAME','geometry']].to_json())
    geo['powerpath_source']={
        'provider':'U.S. Census Bureau Cartographic Boundary Files',
        'url':a.source_url,
        'input_sha256':hashlib.sha256(a.input_file.read_bytes()).hexdigest(),
        'imported_at':datetime.now(timezone.utc).isoformat(),
        'count':len(frame),
        'scope':'Generalized counties and county equivalents in 50 states + DC; no municipal, tribal, special district or site zoning delineation',
        'accuracy':'1:500,000 cartographic boundary; not survey-grade or legal permit approval evidence'}
    temp=DEST.with_suffix('.tmp');temp.write_text(json.dumps(geo,separators=(',',':')))
    temp.replace(DEST)
    print('Imported',len(frame),'county geometries to',DEST,'source SHA-256',geo['powerpath_source']['input_sha256'])


if __name__=='__main__':main()
