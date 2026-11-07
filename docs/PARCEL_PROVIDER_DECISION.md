# PowerPath parcel-provider pilot — 28 October 2026

## Decision

Use Regrid for the first technical evaluation; compare an enterprise quote with LightBox and ReportAll before purchasing. This is a recommendation based on documentation and a single sample test, not a finding that Regrid has the best nationwide accuracy or lowest cost.

The national subscription is **not activated**. No account was created, no supplier was contacted, and no paid plan was purchased. The delivered app still contains only the previously connected Loudoun production pilot. Vendor sample records are not redistributed in this archive.

## Provider comparison

| Provider | Verified offer | Fit for PowerPath | Open commercial questions |
|---|---|---|---|
| Regrid | Parcel API, parcel tiles, public county download samples; self-serve and enterprise plans | First technical pilot; adapter tested on a real county sample | SaaS display, long-term evidence snapshots, geometry in exported memos, price and minimum commitment |
| LightBox | Parcel API with persistent IDs, geometry queries and map tiles; sample offering includes linked parcel, assessment, building and address layers | Alternative when linked property datasets matter | Evaluation access, field coverage in target markets, retention/export rights, API/tiles pricing |
| ReportAll | Parcel API supporting raster/vector tiles and mapping formats; advertises a 30-day trial | Alternative for parcel mapping and usage-cost comparison | Token/account, limits, cache and redistribution terms, quote |

Provider nationwide marketing claims are not a parcel-by-parcel completeness audit. Compare county counts, attributes and dates against county sources before describing any market as complete.

## What was actually tested

Downloaded the public Fillmore County, Nebraska GeoJSON sample from Regrid. Parsed and normalized all **7,741** features: 7,589 Polygon and 152 MultiPolygon. All had a valid stable identifier, area and provider refresh date; the reported refresh date was 8 July 2026. Imported all records into an isolated temporary spatial database and verified lookup/query functionality, then deleted that database. No sample data was added to production coverage. Machine-readable results are in REGRID_SAMPLE_VALIDATION.json.

This verifies compatibility and basic geometry checks, not survey accuracy, topology, title, buildability, data currency nationwide or power access. The acreage is provider-computed geometry. It must not be called deeded/recorded acreage. Vendor scores are discarded, not used as PowerPath feasibility or electrical-reliability scores.

## Pricing and consumption

Regrid's current getting-started documentation describes 2,000 included parcel records and 200,000 tiles in self-serve monthly plans. It lists extra records at $0.10 Standard or $0.15 Premium and extra tiles at $0.001. The base monthly price was not visible in the retrieved plans page; it remains unverified. These figures are documentation, not a quote. For illustration, 5,000 returned records would create 3,000 overage records: $300 Standard or $450 Premium, **plus the unknown base price and any tile overage**. Repeated responses count again. [1]

Plan documentation positions enterprise access for higher volumes and additional datasets. Ask for three quotes: a small internal pilot, a customer-facing beta, and a national production product. Do not treat app-subscription pricing as an API license. [2]

Recommended production design: parcel tiles for visual browsing and narrow record requests for selected sites, subject to provider approval. This is a future implementation choice; a nationwide live tile layer is not implemented in this release.

## Contract requirements to resolve

Regrid's documentation describes a 30-day cache window; the API terms separately discuss storing records and deleting them at termination. Those provisions do not establish PowerPath's needed perpetual evidence rights. The terms also distinguish API records from tiles and describe trial conversion to paid service. Obtain written clarification for the actual plan before activation. [1][3]

Request explicit answers for customer-facing display, derived feasibility outputs, customer memo/PDF/JSON exports, saved geometry after updates, retention after termination, required attribution, deletion duties, authorized tenants/users and any AI-related processing. PowerPath currently retains versions indefinitely and exports parcel geometry, so a short-lived evaluation license cannot be treated as permission for those workflows.

## Concrete activation path

1. Open Regrid's account/sandbox flow and review the actual trial and billing terms. Set its token only in the local environment as POWERPATH_REGRID_TOKEN; do not paste it into chat, commit it, or put it in browser code. [4]
2. Run the supplied count-only point lookup, then one explicitly bounded fetch. The CLI defaults to one record, never automatically paginates/retries, and does not persist API responses.
3. Obtain a quote and confirmed rights for the workflows above. Importing a bulk snapshot requires a license metadata file; the supplied template defaults to not authorized.
4. Evaluate at least 25 known sites in each pilot market (VA, TX, OH, AZ and GA), checking parcel ID, geometry alignment, date and missing fields. Include boundary-edge cases, multiple-parcel sites and stacked parcels. Record disagreements against the county source; do not invent accuracy scores.
5. After a chosen agreement is approved, implement the licensed tile/record connection, enforce its actual retention/deletion rules, and validate the live map. Only then mark the vendor feed active.

## Sources checked

[1] https://support.regrid.com/docs/getting-started-api

[2] https://support.regrid.com/reference/plan-options

[3] https://regrid.com/terms/api

[4] https://regrid.com/api

Regrid samples: https://app.regrid.com/store/samples

Regrid response schema: https://support.regrid.com/docs/search-parcels

LightBox: https://developer.lightboxre.com/apis/parcels and https://go.lightboxre.com/sample-data

ReportAll: https://reportallusa.com/products/api
