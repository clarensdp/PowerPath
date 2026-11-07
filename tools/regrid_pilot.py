"""Evaluate Regrid files or make one operator-triggered API lookup; no automatic production import."""
import argparse, json, sys
from pathlib import Path
from server.providers.regrid import normalize, summarize, fetch_point, import_snapshot

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    a = sub.add_parser('evaluate'); a.add_argument('geojson')
    a = sub.add_parser('point'); a.add_argument('--lat', type=float, required=True); a.add_argument('--lon', type=float, required=True)
    a.add_argument('--fetch', action='store_true', help='Fetch up to --limit records; may consume paid allowance. Default is count-only.')
    a.add_argument('--limit', type=int, default=1)
    a = sub.add_parser('import'); a.add_argument('geojson'); a.add_argument('license_metadata')
    args = p.parse_args()
    try:
        if args.action == 'point':
            result = fetch_point(args.lat, args.lon, args.limit, count_only=not args.fetch)
            result = summarize(result) if args.fetch else result
        else:
            collection = normalize(json.loads(Path(args.geojson).read_text()))
            if args.action == 'evaluate':
                result = summarize(collection)
            else:
                from server.app import db, ROOT
                from server.geo29 import GeoStore
                result = import_snapshot(GeoStore(db, ROOT), collection, json.loads(Path(args.license_metadata).read_text()))
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
if __name__ == '__main__':
    raise SystemExit(main())
