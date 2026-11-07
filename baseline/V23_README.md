# PowerPath v23 — Site evidence and local vault

This release extends v22; no agents have been added.

## What is implemented

1. **Source GIS tab** in **Site & Data room**: uses the existing embedded EIA-derived plant inventory to list closest generation plants to project coordinates. The bundled inventory is historical and is not a live database. The distance is great-circle only.
2. **Point GeoJSON intake**: imports point features from a user-selected `.geojson` / `.json` file after a source reference and dataset date are supplied. Coordinates are checked, imports are capped at 5,000 point features / 3 MB, candidate records are labelled and locally saved to the Infrastructure register.
3. **Team vault tab**: connects to a local Python SQLite + filesystem gateway. The gateway accepts single-file uploads (12 MB max), generates SHA-256 checksums, lists/downloads/deletes project-scoped records, and records immutable-through-API upload/delete events (not tamperproof database audit).
4. **Regression and browser checks**: all 10 JavaScript test files pass; 3 gateway tests pass; Chromium desktop and mobile smoke tests show no JS errors or horizontal overflow for the newly added tabs.

## Running the vault locally

Set a strong unique password (12+ characters) in your terminal. On macOS/Linux:

```bash
cd powerpath_v23
export POWERPATH_VAULT_PASSWORD='replace-with-your-own-long-secret'
python3 vault_server.py
```

Visit **http://127.0.0.1:8766/PowerPath.html** and open **Site & Data room > Team vault**. Enter username `powerpath` and the chosen password when the browser prompts. `vault_server.py` binds only to `127.0.0.1` and uses a local directory `.private_vault/` for SQLite and blobs; back up that directory separately. `POWERPATH_VAULT_DIR` and `POWERPATH_VAULT_PORT` can be configured through environment variables. For historical importer work, the earlier `live_server.py` is still bundled and independent.

A standalone `PowerPath_v23.html` works offline for planning and the Source GIS tab; its **Team vault** requires opening the page through the local server above. The browser-local v22 Data room remains available separately.

## Security limitations

**DO NOT deploy publicly or upload confidential utility agreements to the prototype.** This is a single-password local development server using HTTP Basic authentication. It does **not** have TLS, multi-user roles, tenant isolation, encryption at rest, malware scanning, quotas, verified backups, document versioning, SSO, recovery, external security testing or compliance certification. File metadata and blobs reside on the local machine. Loopback binding and input/path checks reduce exposure but are not a substitute for production hardening. No cloud collaboration is implemented.

## Data and modeling caveats

- A nearby power plant's **nameplate capacity is not available generation or a service commitment**.
- Coordinates and GeoJSON records are **candidate screening layers**. The app does not establish substation headroom, transmission rights, grid constraints, or physical route feasibility.
- GeoJSON imports do not verify the authenticity, licensing or freshness of the source. Users must supply an authoritative reference and dataset date.
- The v20.2 price-data opt-in, v21 underwriting and v22 tariff worksheet are preserved. GIS candidates and vault files do not silently change underwriting assumptions or permit/utility status.
- There are no autonomous agents.

## Production roadmap

Commercial GIS feeds (utility/ISO/API and negotiated licensing), geospatial indexing and parcel geometry, utility-confirmed studies, encrypted cloud object storage, identity and per-project RBAC, short-lived download authorization, audit log immutability, backup/recovery, organizational sharing, and document-to-underwriting evidence review need separate implementation and testing.
