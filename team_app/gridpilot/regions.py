"""
Regional screening data for PowerPath's location screener.

Sourced (public):
  price_c   - EIA, average retail electricity price by state, 2024 (cents/kWh), "Electricity Data
              Browser / State Electricity Profiles" (eia.gov/electricity/state)
  co2_lb    - EPA eGRID2023 state total output CO2 emission rate (lb/MWh), summary tables rev2
  land_usd  - USDA NASS Land Values 2025, farm real estate average value per acre
Screening estimates (labelled, editable, NOT measured site data):
  solar_cf, wind_cf - typical utility-scale capacity factors by state resource class
  water             - water-stress tier 1 (low) to 5 (extremely high), WRI-Aqueduct-style judgement
  delay             - months of grid-connection delay vs the benchmark schedule (large-load queue proxy)
  policy            - notable large-load / data-center rules to verify (not legal conclusions)
Countries are coarse, order-of-magnitude defaults for screening only.

The benchmark (Williamson County, TX, ERCOT) is the ground truth. Other locations re-run the same
87,600-hour engine with the benchmark's hourly shapes scaled by these indices.
"""
from __future__ import annotations

import re

BENCH = "TX"
TX_PRICE_C, TX_CO2_LB, TX_SOLAR, TX_WIND = 9.79, 768.3, 0.25, 0.37

# abbr: (name, iso, price_c, co2_lb, land_usd, solar_cf, wind_cf, water, delay_m, lat, lon)
STATES = {
    "AL": ("Alabama", "SERC (vertically integrated)", 11.90, 711.0, 4150, .21, .20, 2, 12, 32.8, -86.8),
    "AK": ("Alaska", "Non-RTO (isolated)", 22.17, 809.8, 1000, .11, .30, 1, 24, 64.2, -152.5),
    "AZ": ("Arizona", "WestTEC / non-RTO", 12.74, 686.7, 4180, .29, .26, 5, 12, 34.2, -111.7),
    "AR": ("Arkansas", "MISO / SPP", 9.59, 993.4, 4250, .21, .27, 2, 12, 34.9, -92.4),
    "CA": ("California", "CAISO", 27.04, 393.5, 13700, .27, .30, 4, 18, 37.2, -119.5),
    "CO": ("Colorado", "WestTEC / non-RTO", 12.07, 1085.0, 2290, .25, .37, 4, 12, 39.0, -105.5),
    "CT": ("Connecticut", "ISO-NE", 24.37, 538.3, 14400, .17, .27, 1, 18, 41.6, -72.7),
    "DE": ("Delaware", "PJM", 13.56, 703.2, 9550, .19, .28, 1, 24, 39.0, -75.5),
    "DC": ("District of Columbia", "PJM", 16.88, 394.1, 20000, .19, .25, 1, 24, 38.9, -77.0),
    "FL": ("Florida", "SERC (vertically integrated)", 12.53, 786.6, 8700, .22, .18, 2, 12, 28.6, -82.4),
    "GA": ("Georgia", "SERC (vertically integrated)", 11.40, 713.8, 4720, .22, .22, 2, 12, 32.7, -83.4),
    "HI": ("Hawaii", "Non-RTO (isolated)", 38.00, 1385.1, 15000, .22, .35, 2, 24, 20.8, -156.3),
    "ID": ("Idaho", "Non-RTO (Northwest)", 9.51, 313.3, 4580, .23, .30, 3, 12, 44.4, -114.6),
    "IL": ("Illinois", "PJM / MISO", 12.21, 471.7, 8930, .19, .34, 1, 18, 40.0, -89.2),
    "IN": ("Indiana", "MISO / PJM", 11.38, 1457.2, 8850, .19, .32, 1, 12, 39.9, -86.3),
    "IA": ("Iowa", "MISO", 9.34, 630.2, 9790, .20, .38, 1, 12, 42.1, -93.5),
    "KS": ("Kansas", "SPP", 11.21, 728.2, 3100, .23, .43, 3, 6, 38.5, -98.4),
    "KY": ("Kentucky", "PJM / SERC", 10.07, 1735.0, 5480, .19, .22, 1, 12, 37.5, -85.3),
    "LA": ("Louisiana", "MISO", 8.80, 761.4, 3850, .21, .25, 1, 12, 31.1, -92.0),
    "ME": ("Maine", "ISO-NE", 19.66, 311.8, 3350, .17, .30, 1, 18, 45.4, -69.2),
    "MD": ("Maryland", "PJM", 15.04, 520.0, 9750, .19, .27, 1, 24, 39.0, -76.8),
    "MA": ("Massachusetts", "ISO-NE", 23.94, 822.4, 14900, .17, .30, 1, 18, 42.3, -71.8),
    "MI": ("Michigan", "MISO", 14.16, 793.2, 6800, .17, .31, 1, 12, 44.3, -85.4),
    "MN": ("Minnesota", "MISO", 12.35, 747.5, 6790, .19, .37, 1, 12, 46.3, -94.3),
    "MS": ("Mississippi", "MISO / SERC", 10.93, 826.3, 3580, .21, .20, 2, 12, 32.7, -89.7),
    "MO": ("Missouri", "MISO / SPP", 11.06, 1444.1, 5000, .20, .34, 2, 12, 38.4, -92.5),
    "MT": ("Montana", "Non-RTO (Northwest)", 10.83, 1056.2, 1230, .21, .38, 2, 12, 47.0, -109.6),
    "NE": ("Nebraska", "SPP", 9.07, 1018.2, 4250, .22, .42, 3, 6, 41.5, -99.8),
    "NV": ("Nevada", "WestTEC / non-RTO", 11.47, 642.4, 1200, .29, .28, 5, 12, 39.3, -116.6),
    "NH": ("New Hampshire", "ISO-NE", 20.61, 272.9, 6500, .16, .27, 1, 18, 43.7, -71.6),
    "NJ": ("New Jersey", "PJM", 16.29, 468.3, 16600, .18, .28, 1, 24, 40.2, -74.7),
    "NM": ("New Mexico", "WestTEC / SPP", 9.18, 770.2, 725, .29, .40, 5, 12, 34.4, -106.1),
    "NY": ("New York", "NYISO", 19.66, 465.1, 4300, .17, .29, 1, 18, 42.9, -75.5),
    "NC": ("North Carolina", "SERC (vertically integrated)", 11.65, 624.0, 5470, .22, .26, 2, 12, 35.5, -79.4),
    "ND": ("North Dakota", "MISO / SPP", 7.93, 1288.4, 2360, .20, .42, 2, 12, 47.5, -100.5),
    "OH": ("Ohio", "PJM", 11.29, 1063.8, 9350, .18, .30, 1, 24, 40.3, -82.8),
    "OK": ("Oklahoma", "SPP", 9.09, 647.2, 2540, .24, .42, 3, 6, 35.6, -97.5),
    "OR": ("Oregon", "Non-RTO (Northwest)", 11.11, 364.2, 3780, .21, .30, 2, 12, 43.9, -120.6),
    "PA": ("Pennsylvania", "PJM", 12.51, 645.8, 8490, .18, .29, 1, 24, 40.9, -77.8),
    "RI": ("Rhode Island", "ISO-NE", 24.15, 839.1, 22500, .17, .30, 1, 18, 41.7, -71.5),
    "SC": ("South Carolina", "SERC (vertically integrated)", 10.90, 557.2, 4740, .22, .22, 2, 12, 33.9, -80.9),
    "SD": ("South Dakota", "SPP / MISO", 10.87, 334.0, 2970, .21, .41, 2, 6, 44.4, -100.2),
    "TN": ("Tennessee", "TVA (SERC)", 10.90, 657.3, 6150, .20, .22, 2, 12, 35.9, -86.4),
    "TX": ("Texas", "ERCOT", 9.79, 768.3, 2970, .25, .37, 3, 0, 31.0, -97.6),
    "UT": ("Utah", "Non-RTO (West)", 9.97, 1413.0, 3500, .27, .30, 4, 12, 39.3, -111.7),
    "VT": ("Vermont", "ISO-NE", 18.41, 43.0, 4400, .16, .27, 1, 18, 44.1, -72.7),
    "VA": ("Virginia", "PJM", 10.62, 536.9, 6100, .21, .25, 1, 24, 37.5, -78.9),
    "WA": ("Washington", "Non-RTO (Northwest)", 10.13, 265.1, 3710, .19, .30, 2, 12, 47.4, -120.5),
    "WV": ("West Virginia", "PJM", 11.05, 1954.4, 3520, .19, .30, 1, 24, 38.6, -80.6),
    "WI": ("Wisconsin", "MISO", 12.72, 1157.0, 6420, .18, .30, 1, 12, 44.6, -89.9),
    "WY": ("Wyoming", "WestTEC / non-RTO", 9.14, 1820.3, 1000, .23, .40, 3, 12, 43.0, -107.6),
}
# Williamson County, TX coordinates (benchmark campus) used for TX ZIPs 765xx-767xx & default TX view
BENCH_LATLON = (30.65, -97.6)

POLICY = {
    "TX": "Texas SB 6 (2025): large-load interconnection standards above 75 MW, backup disclosure, ERCOT curtailment rights. Verify applicability.",
    "VA": "Northern Virginia transmission constraints and utility large-load queue; local data-center zoning scrutiny. Verify county rules.",
    "GA": "Georgia PSC rules for very large new loads (2025). Verify tariff terms.",
    "OH": "AEP Ohio data-center tariff with minimum-demand commitments (2025). Verify tariff terms.",
    "OR": "Oregon POWER Act (2025): separate rate class for large loads. Verify.",
    "IN": "Large-load tariff proceedings at utilities; verify current terms.",
    "AZ": "Water constraints are a gating diligence item for cooling design.",
    "NV": "Water constraints are a gating diligence item for cooling design.",
}

# country: (name, grid, price_index_vs_TX, co2_kg_per_mwh, land_index_vs_TX, solar_cf, wind_cf, water, delay_m, lat, lon, policy)
COUNTRIES = {
    "CA": ("Canada", "Provincial utilities", 0.9, 110, 1.2, .16, .33, 1, 12, 56.1, -106.3, ""),
    "GB": ("United Kingdom", "NESO (GB)", 2.6, 125, 4.0, .11, .35, 2, 36, 54.0, -2.0, "Long grid-connection queue; connection reform under way. Verify."),
    "IE": ("Ireland", "EirGrid", 2.6, 250, 4.0, .11, .35, 1, 36, 53.4, -8.2, "Dublin-area data-center connection restrictions. Verify current EirGrid/CRU policy."),
    "DE": ("Germany", "TSOs (ENTSO-E)", 2.2, 340, 4.0, .12, .25, 2, 24, 51.2, 10.4, "Energy Efficiency Act data-center requirements (PUE, renewables, heat reuse). Verify."),
    "NL": ("Netherlands", "TenneT", 2.1, 270, 6.0, .11, .32, 1, 24, 52.1, 5.3, "Hyperscale restrictions in parts of the country; grid congestion. Verify."),
    "FR": ("France", "RTE", 1.6, 45, 2.0, .14, .25, 2, 18, 46.2, 2.2, ""),
    "ES": ("Spain", "REE", 1.6, 110, 1.5, .20, .27, 4, 24, 40.5, -3.7, "Grid-access tenders; water stress in the south. Verify."),
    "SE": ("Sweden", "Svenska kraftnät", 1.0, 40, 1.0, .10, .32, 1, 12, 62.2, 17.6, ""),
    "NO": ("Norway", "Statnett", 0.9, 30, 1.0, .09, .33, 1, 18, 61.0, 8.5, "Grid capacity constrained in some regions. Verify."),
    "FI": ("Finland", "Fingrid", 1.0, 70, 0.8, .09, .32, 1, 12, 64.0, 26.0, ""),
    "JP": ("Japan", "Regional utilities", 2.4, 460, 8.0, .14, .22, 2, 24, 36.2, 138.3, ""),
    "SG": ("Singapore", "SP Group / EMA", 2.5, 470, 30.0, .14, .05, 3, 36, 1.35, 103.8, "Capacity allocated through government calls for application. Verify."),
    "IN": ("India", "Grid-India", 1.0, 700, 1.5, .20, .25, 4, 12, 22.0, 79.0, ""),
    "AU": ("Australia", "AEMO (NEM)", 1.8, 550, 1.0, .22, .33, 3, 18, -25.3, 133.8, ""),
    "BR": ("Brazil", "ONS", 1.4, 90, 0.8, .20, .40, 2, 12, -14.2, -51.9, ""),
    "MX": ("Mexico", "CENACE", 1.3, 400, 0.8, .24, .30, 4, 18, 23.6, -102.5, ""),
    "AE": ("United Arab Emirates", "DEWA / TAQA", 1.0, 380, 1.5, .25, .20, 5, 12, 23.4, 53.8, ""),
}
COUNTRY_ALIASES = {"UK": "GB", "USA": "US", "UNITED STATES": "US", "US": "US", "UAE": "AE", "ENGLAND": "GB",
                   "SCOTLAND": "GB", "BRITAIN": "GB", "GREAT BRITAIN": "GB", "HOLLAND": "NL", "KOREA": None}

# ZIP3 prefix ranges -> state (USPS allocation)
_ZIP3 = [(5, 5, "NY"), (10, 27, "MA"), (28, 29, "RI"), (30, 38, "NH"), (39, 49, "ME"), (50, 54, "VT"),
         (55, 55, "MA"), (56, 59, "VT"), (60, 69, "CT"), (70, 89, "NJ"), (100, 149, "NY"), (150, 196, "PA"),
         (197, 199, "DE"), (200, 200, "DC"), (201, 201, "VA"), (202, 205, "DC"), (206, 219, "MD"),
         (220, 246, "VA"), (247, 268, "WV"), (270, 289, "NC"), (290, 299, "SC"), (300, 319, "GA"),
         (320, 349, "FL"), (350, 369, "AL"), (370, 385, "TN"), (386, 397, "MS"), (398, 399, "GA"),
         (400, 427, "KY"), (430, 459, "OH"), (460, 479, "IN"), (480, 499, "MI"), (500, 528, "IA"),
         (530, 549, "WI"), (550, 567, "MN"), (569, 569, "DC"), (570, 577, "SD"), (580, 588, "ND"),
         (590, 599, "MT"), (600, 629, "IL"), (630, 658, "MO"), (660, 679, "KS"), (680, 693, "NE"),
         (700, 714, "LA"), (716, 729, "AR"), (730, 749, "OK"), (750, 799, "TX"), (800, 816, "CO"),
         (820, 831, "WY"), (832, 838, "ID"), (840, 847, "UT"), (850, 865, "AZ"), (870, 884, "NM"),
         (885, 885, "TX"), (889, 898, "NV"), (900, 961, "CA"), (967, 968, "HI"), (970, 979, "OR"),
         (980, 994, "WA"), (995, 999, "AK")]


def zip_to_state(z: str):
    z = re.sub(r"\D", "", z)[:5]
    if len(z) < 3:
        return None
    p = int(z[:3])
    for lo, hi, st in _ZIP3:
        if lo <= p <= hi:
            return st
    return None


def resolve(text: str) -> dict | None:
    """ZIP, 2-letter state, state name, country code or country name -> location record."""
    t = (text or "").strip()
    if not t:
        return None
    u = t.upper()
    mz = re.fullmatch(r"(\d{3,5})(-\d{4})?", t)
    if mz:
        digits = mz.group(1)
        st = zip_to_state(digits)
        if st:
            loc = state_record(st)
            loc["query"], loc["zip"] = t, digits[:5]
            if st == "TX" and digits[:3] in ("765", "766", "767", "786", "787"):
                loc["lat"], loc["lon"] = BENCH_LATLON
                loc["note"] = "Central Texas ZIP: closest to the benchmark campus (Williamson County)."
            return loc
    if u in STATES:
        return state_record(u)
    for ab, rec in STATES.items():
        if rec[0].upper() == u:
            return state_record(ab)
    code = COUNTRY_ALIASES.get(u, u)
    if code == "US":
        return state_record(BENCH)
    if code in COUNTRIES:
        return country_record(code)
    for cc, rec in COUNTRIES.items():
        if rec[0].upper() == u:
            return country_record(cc)
    return None


def state_record(ab):
    n, iso, pc, co2, land, scf, wcf, water, delay, lat, lon = STATES[ab]
    return dict(key=f"US-{ab}", label=f"{n}, US", kind="state", abbr=ab, grid=iso,
                price_index=pc / TX_PRICE_C, price_c=pc, co2_ratio=co2 / TX_CO2_LB, co2_kg=co2 * 0.45359237,
                land_usd=land, solar_ratio=scf / TX_SOLAR, wind_ratio=wcf / TX_WIND, solar_cf=scf, wind_cf=wcf,
                water=water, delay=delay, lat=lat, lon=lon, policy=POLICY.get(ab, ""),
                benchmark=(ab == BENCH), coarse=False,
                provenance="Price: EIA 2024 avg retail (state). CO2: eGRID2023 state output rate. Land: USDA NASS 2025. "
                           "Solar/wind/water/delay: screening estimates.")


def country_record(cc):
    n, grid, pidx, co2kg, lidx, scf, wcf, water, delay, lat, lon, pol = COUNTRIES[cc]
    return dict(key=f"C-{cc}", label=n, kind="country", abbr=cc, grid=grid, price_index=pidx,
                price_c=TX_PRICE_C * pidx, co2_ratio=co2kg / (TX_CO2_LB * 0.45359237), co2_kg=co2kg,
                land_usd=STATES[BENCH][4] * lidx, solar_ratio=scf / TX_SOLAR, wind_ratio=wcf / TX_WIND,
                solar_cf=scf, wind_cf=wcf, water=water, delay=delay, lat=lat, lon=lon, policy=pol,
                benchmark=False, coarse=True,
                provenance="Country-level screening defaults (order of magnitude). Verify with local market data.")


def region_params(key: str) -> dict | None:
    """Parameters the engine needs, from a location key ('US-VA', 'C-IE'). None = benchmark."""
    if not key or key == f"US-{BENCH}":
        return None
    if key.startswith("US-"):
        r = state_record(key[3:])
    elif key.startswith("C-"):
        r = country_record(key[2:])
    else:
        return None
    return dict(price_index=r["price_index"], co2_ratio=r["co2_ratio"], solar_ratio=r["solar_ratio"],
                wind_ratio=r["wind_ratio"], delay=r["delay"])
