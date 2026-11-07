"""Import an attributed WGS84 GeoJSON snapshot into the local spatial store."""
import argparse,json
from server.app import db,ROOT
from server.geo29 import GeoStore
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('geojson');p.add_argument('source_metadata');p.add_argument('--id-field',required=True);p.add_argument('--square-feet-field')
a=p.parse_args()
store=GeoStore(db,ROOT)
print(json.dumps(store.ingest(json.load(open(a.source_metadata)),json.load(open(a.geojson)),a.id_field,a.square_feet_field),indent=2))
