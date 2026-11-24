"""Write an Excel add-in manifest pointing at your HTTPS PowerPath address.

    python -m scripts.excel_manifest --base-url https://powerpath.example.com [--out manifest.xml]
"""
import argparse
import pathlib
from urllib.parse import urlparse

SRC = pathlib.Path(__file__).resolve().parents[1] / 'web' / 'excel' / 'manifest.xml'


def build(base_url: str) -> str:
    u = urlparse(base_url)
    if u.scheme != 'https' or not u.netloc or u.path not in ('', '/'):
        raise SystemExit('Office add-ins need an https:// origin with no path, e.g. https://powerpath.example.com')
    return SRC.read_text().replace('https://localhost:8768', f'https://{u.netloc}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', required=True)
    ap.add_argument('--out', default='powerpath-excel-manifest.xml')
    a = ap.parse_args()
    pathlib.Path(a.out).write_text(build(a.base_url))
    print(f'Wrote {a.out}')
