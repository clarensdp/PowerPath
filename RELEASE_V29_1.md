# PowerPath v29.1 — Provider evaluation build

This build prepares national data acquisition and tests a real vendor sample. **It does not activate nationwide parcel coverage.** Read docs/PARCEL_PROVIDER_DECISION.md for the recommendation, cost assumptions, actual sample results and required activation steps.

## Added

- Regrid normalization for flat bulk GeoJSON and nested API payloads.
- Stable IDs, county validation, polygon checks and explicit area basis.
- Local sample evaluation without changing the app's database.
- Token-based point API client: count-only default; explicit fetch capped at 25 records; no automatic pagination or retries; no API responses saved.
- Complete-county snapshot importer with explicit rights metadata. Supports up to 100,000 features per snapshot for this local pilot. It is not a national-scale bulk warehouse.
- UI labels now say source acres and explain the area's basis.

The archive contains code and aggregate test results, not the vendor sample or any credentials. Source versions and financial engines from v29 are preserved.

## Launch the app

```
python3 -m pip install -r requirements.txt
./run_local.sh
```

Open http://127.0.0.1:8768. Existing coverage remains the Loudoun snapshot. v29 launch and coverage documentation remains in RELEASE_V29.md; the v29.1 import cap supersedes its 5,000-feature cap.

## Reproduce the sample evaluation

Download/unzip a US county GeoJSON sample from https://app.regrid.com/store/samples. For the validated sample, select Fillmore County, Nebraska. From this release directory:

```
python3 -m tools.regrid_pilot evaluate /absolute/path/to/ne_fillmore.json
python3 -m tools.validate_regrid_sample /absolute/path/to/ne_fillmore.json
```

The first command validates and reports aggregate results. The second tests spatial ingestion in a temporary database that is deleted after execution. Neither changes production coverage.

## API pilot after account setup

Set POWERPATH_REGRID_TOKEN through your local environment/secret manager. Do not put the value in files or the browser. Then:

```
python3 -m tools.regrid_pilot point --lat 42.36511 --lon -83.073107
python3 -m tools.regrid_pilot point --lat 42.36511 --lon -83.073107 --fetch --limit 1
```

The first command requests a count. The second returns only an aggregate validation summary and can consume plan allowance. These calls were unit-tested using synthetic responses, **not tested against a live account**. No token is bundled. This is an operator tool, not a live UI connection.

## Licensed bulk import

Complete examples/regrid_license_metadata.json using the actual agreement and source information. Authorization flags are a record of confirmed rights, not a grant of rights. If retention/export rights are time-limited, do not import into this indefinite-retention workspace; first implement the applicable expiry/deletion behavior.

```
python3 -m tools.regrid_pilot import /absolute/path/to/county.json /absolute/path/to/license_metadata.json
```

Each import replaces the active snapshot for one county. Supply a complete snapshot, never a partial API page. Prior versions stay available for saved decisions. Import one county at a time; multi-county atomic ingestion and production-scale processing are not provided.

## Verification and limits

19 provider/national/parcel tests and 3 required-auth tests pass. Sample QA successfully normalized and spatially imported all 7,741 vendor records. JavaScript syntax and DOM smoke tests pass. Full browser map verification and live authenticated provider testing remain outstanding. The inherited v28 financial fixture issue is not resolved; financial engine files are unchanged.
