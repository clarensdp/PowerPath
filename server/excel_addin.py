"""Serves the v31.5 Excel add-in (web/excel) from a fixed allow-list of files.

Office requires HTTPS for add-ins outside local sideloading; run behind TLS
(or `office-addin-dev-certs` for https://localhost) before loading the manifest.
"""
from fastapi import HTTPException
from fastapi.responses import FileResponse

OFFICE_JS = 'https://appsforoffice.microsoft.com'
OFFICE_FRAMES = ('https://*.officeapps.live.com https://*.office.com https://*.office365.com '
                 'https://*.sharepoint.com https://*.cloud.microsoft https://*.microsoft.com')
CSP = (f"default-src 'none'; script-src 'self' {OFFICE_JS}; style-src 'self'; connect-src 'self'; "
       f"img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'self' {OFFICE_FRAMES}")
FILES = {
    'manifest.xml': 'application/xml',
    'taskpane.html': 'text/html; charset=utf-8',
    'taskpane.js': 'text/javascript; charset=utf-8',
    'taskpane.css': 'text/css; charset=utf-8',
    'functions.js': 'text/javascript; charset=utf-8',
    'functions.json': 'application/json',
    'powerpath-core.js': 'text/javascript; charset=utf-8',
    'icon-32.png': 'image/png',
    'icon-80.png': 'image/png',
}


def install(app, root):
    base = root / 'web' / 'excel'

    @app.get('/excel/{name}', include_in_schema=False)
    def excel_file(name: str):
        if name not in FILES or not (base / name).is_file():
            raise HTTPException(404, 'Not found')
        return FileResponse(base / name, media_type=FILES[name])
