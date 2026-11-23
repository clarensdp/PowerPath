# Connected parcel feasibility

Shortlist parcels in **Explore parcels**. Each shortlisted parcel has a **Parcel feasibility** panel for land, infrastructure and technology cases. **Economics** compares current cases across the shortlist. In **Decision memo**, save a versioned feasibility report and download JSON or print to PDF. The previous project-level decision memo is still available.

For a 75 IT MW project at PUE 1.30, the full target draws 97.5 gross MW. Create an illustrative working scenario, then confirm construction and lease timing. Enter cumulative grid phases as month/MW rows such as `20,32.5`, `30,65` and `36,97.5`. Add separate cases for gas, grid plus solar, or combined grid/gas/solar, with explicit technology values. Zero or insufficient firm supply remains visible as unmet demand. The project can include any number of shortlisted parcels and cases.

## Land and public sources

- The existing FEMA SFHA and USFWS NWI overlays are reused. FEMA coverage is limited to special flood hazard areas.
- [USGS 3D Hydrography waterbodies](https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/FeatureServer/60) provides mapped water polygons. Available coverage varies. FEMA and NWI requests use a bounded source generalization tolerance of 0.00001° for screening.
- [USGS 3DEP elevation](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer) supplies elevations on a bounded 11×11 point grid. The resulting 10×10 slope cells use percent rise, with an adjustable 15% default exclusion threshold. This coarse screen can miss local features.
- [USGS PAD-US](https://www.usgs.gov/programs/gap-analysis-project/science/pad-us-web-services) supplies GAP status 1 and 2 candidate conservation exclusions. Other legal restrictions require separate review.
- Uploaded constraint layers use the existing `kind`, `source`, `features` and optional `coverage_geometry` shape. Accepted kinds include `water` and `slope`. Enter a JSON array of those layer objects. Source-declared footprint coverage for water, slope, wetlands, flood and protected land is required to qualify for the usable-acre filter. No official overlay request establishes complete coverage by itself.

Remote requests require `POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1` and the UI consent checkbox. A missing or failed layer leaves the residual acreage as an incomplete upper bound. Overlaps are unioned before subtraction. Residual and excluded geometry appear on Leaflet.

## Utility and pricing sources

The existing federal transmission source remains available. Reviewed administrator-configured substation and service territory URLs and names still work. No statewide substation or territory default met the ownership, vintage, coverage and reuse requirements. Virginia SCC provides a public service map, while North Carolina's utility commission displays an NC Sustainable Energy Association map. Neither review established a current redistributable parcel polygon feed covering the whole state. [Virginia SCC service map](https://www.scc.virginia.gov/consumers/public-utility/electricity-faqs/regulated-companies-service-map/) · [NCUC overview](https://www.ncuc.gov/documents/overview.pdf).

The [Chatham County GIS electric-district layer](https://gisservices.chathamcountync.gov/opendataagol/rest/services/AdministrativeArea/Chatham_ElectricDistricts/MapServer/0) returned candidate polygons in a live check. Its publisher states the update date is unknown. After reviewing reuse rights, enable `POWERPATH_CHATHAM_TERRITORY_OPT_IN=1` for county GEOID 37125. The observation timestamp and record-edit date are stored separately. No nearby infrastructure implies available MW.

Attach a supporting file in the Evidence room, enter gross MW, connection cost and the date in Site energy data, then explicitly select that utility study in a grid case. An analyst can identify the issuer and attest that the attached document confirms service. The snapshot retains the classification, document hash and transcribed values. PowerPath does not authenticate the issuer or interpret whether the document constitutes a commitment. Explicit hypotheses remain available.

`POWERPATH_EIA_API_KEY` enables EIA references in the existing energy selector. A grid case can use an explicitly entered price or the saved underwriting price for that parcel. `POWERPATH_NREL_API_KEY` enables PVWatts monthly AC estimates. Explicit 12-month solar energy assumptions can be used without keys. Export configured variables before starting the local server.

## Modeling and persistence

The two-block monthly dispatch allocates solar during daylight, then grid, then gas, constrained to the operating load. Gas fuel is generated MWh × 3.412141633 ÷ net efficiency in MMBtu. Direct and optional grid CO₂ use entered factors. Solar contributes no firm MW. Energy is capped by assumed AC inverter capacity using a 1.2 DC-to-AC ratio, and unused energy is reported. There is no storage, hourly weather/dispatch, redundancy, lifecycle emissions, gas supply verification or grid tariff model. Unmet target MWh assumes continuous full target demand. Reported operating MW reflects the underwriting lease and building conditions.

The existing 27.1 engine consumes firm phases as incremental IT power tranches after PUE conversion. Connection, gas and solar capex are allocated through construction spend. Dispatch operating costs flow through a constant energy-weighted price using the base scenario's lease cost allocation. Actual monthly dispatch costs and financial cost timing can therefore differ. Fixed power O&M with zero operating MWh is shown in dispatch and excluded from underwriting. All finance results are screening sensitivities.

SQLite bootstraps additive tables `power_path_inputs`, `parcel_analysis_versions`, `parcel_power_cases`, `parcel_power_results` and `feasibility_reports`. Existing scenarios and power records are retained. New connected routes are SQLite-only. Snapshots hold source geometry, evidence, case inputs, engine inputs and period results. Changed case or base scenario versions and selected utility study values invalidate saved calculations. Reports retain their original contents and are marked historical when current evidence or cases change. A fresh calculation can fetch a new provider estimate. Prior runs preserve the estimate used at calculation time.

## Verification

Run `.venv/bin/python -m pytest -q tests/test_mvp_api.py tests/test_mvp_capacity.py tests/test_mvp_land.py` and the extended release gate. The connected integration test uses three real bundled Loudoun boundaries and synthetic energy/utility inputs. It calculates grid, gas, solar-assisted and hybrid cases on each parcel, checks energy balance and capacity, then saves and invalidates a report after editing a case. The browser acceptance script exercises the user controls and export. Mock observations are test fixtures only.


## Live spot checks

On a bundled Loudoun parcel, FEMA returned two candidate SFHA geometries, NWI returned one wetland geometry, and PAD-US returned zero matching GAP 1/2 features. The waterbody service returned a sample polygon for a separate NC query, but the Loudoun waterbody request timed out. A two-point Loudoun 3DEP sample succeeded, while the full terrain grid returned an upstream gateway error. These outcomes do not establish mapped coverage. The app records failed layers as unavailable and supports analyst-supplied layers for those gaps.

## Files changed

| Area | Files |
|---|---|
| Land | `permitting/footprint.py`, `permitting/footprint_sources.py`, `permitting/land_sources.py` |
| API and persistence | `server/app.py`, `server/parcels28.py`, `server/site_energy_api.py`, `server/site_feasibility_api.py`, `server/services/data_provenance.py`, `server/services/feasibility_store.py` |
| Power and providers | `server/schedule27.py`, `server/services/power_capacity.py`, `server/services/power_dispatch.py`, `server/services/site_energy_data.py`, `server/providers/infrastructure/public_grid.py`, `server/providers/renewables/nrel.py` |
| Workspace | `web/public/site-energy.js`, `web/public/site-feasibility.js`, `web/public/workspace28.js`, `web/public/workspace28.css` |
| Tests and checks | `tests/test_mvp_api.py`, `tests/test_mvp_capacity.py`, `tests/test_mvp_land.py`, `tests/test_site_energy_providers.py`, `tests/browser_site_energy.py`, `package.json`, `.github/workflows/ci.yml` |
| Configuration and docs | `.env.example`, `README.md`, `docs/CONNECTED_FEASIBILITY.md` |
