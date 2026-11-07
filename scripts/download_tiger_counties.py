#!/usr/bin/env python3
"""One-command *optional* official Census county import; needs internet and geopandas.

The download host/path is hard-coded; no user-supplied URL or unsafe ZIP extraction.
Source is 2025 generalized 1:500,000, not a cadastral/municipal/zoning layer.

    python3 scripts/download_tiger_counties.py --allow-overwrite
"""
from __future__ import annotations
import argparse
import hashlib
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from prepare_tiger_counties import main as import_main

SOURCE = "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip"
MAX_SIZE = 30_000_000


def download(dst):
    req = Request(SOURCE, headers={"User-Agent": "PowerPath-PermitIQ/30.6 GIS installer"})
    total = 0
    with urlopen(req, timeout=45) as r, open(dst, "wb") as out:
        if r.geturl().split("/")[2] != "www2.census.gov":
            raise RuntimeError("Unexpected redirect host")
        while True:
            block = r.read(262144)
            if not block:
                break
            total += len(block)
            if total > MAX_SIZE:
                raise RuntimeError("County download too large")
            out.write(block)
    if total < 100_000:
        raise RuntimeError("Census ZIP unexpectedly small")
    return total, hashlib.sha256(Path(dst).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-overwrite", action="store_true")
    a = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="permitiq_county_") as tmp:
        z = Path(tmp) / "cb_2025_us_county_500k.zip"
        count, shasum = download(z)
        print("Downloaded official Census county ZIP:", count, "bytes; SHA-256:", shasum)
        import sys

        sys.argv = ["prepare_tiger_counties.py", str(z), "--source-url", SOURCE] + (
            ["--allow-overwrite"] if a.allow_overwrite else []
        )
        import_main()


if __name__ == "__main__":
    main()
