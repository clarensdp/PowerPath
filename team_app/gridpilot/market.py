"""
Market tape for the PowerPath ticker (CapIQ-style): energy prices, power equities, headlines.

Static snapshot: values below were collected for the build day and are labelled with their
session date and source. They are context for the decision; they do not enter the benchmark
model (which uses the packet's 2023 reference year and trajectory).
To refresh: edit QUOTES / NEWS, or wire a data provider in `live_quotes()`.
"""
AS_OF = "Session of Oct 22, 2026"

# (group, symbol, value, unit, change_text, source)
QUOTES = [
    ("GAS", "Henry Hub (front)", 2.80, "$/MMBtu", "+0.2%", "Energy Brief, Oct 23 2026"),
    ("GAS", "HH X26/Z26 spread", -0.36, "$/MMBtu", "contango", "Energy Brief, Oct 23 2026"),
    ("GAS", "EIA STEO HH 2026 avg", 3.67, "$/MMBtu", "Jul STEO", "EIA via Rigzone, Jul 2026"),
    ("GAS", "TTF", 29.55, "$/MMBtu", "+3.0%", "Energy Brief, Oct 23 2026"),
    ("GAS", "JKM", 30.62, "$/MMBtu", "+1.9%", "Energy Brief, Oct 23 2026"),
    ("POWER", "ERCOT North DA", 35.73, "$/MWh", "prev 36.25", "Energy Brief, Oct 23 2026"),
    ("POWER", "PJM West DA", 59.66, "$/MWh", "prev 67.38", "Energy Brief, Oct 23 2026"),
    ("POWER", "CAISO SP15 DA", 45.60, "$/MWh", "prev 52.70", "Energy Brief, Oct 23 2026"),
    ("SPARK", "ERCOT North spark", 14.76, "$/MWh", "HR 12.8", "Energy Brief, Oct 23 2026"),
    ("SPARK", "PJM West spark", 38.69, "$/MWh", "HR 21.3", "Energy Brief, Oct 23 2026"),
    ("SPARK", "CAISO SP15 spark", 24.63, "$/MWh", "HR 16.3", "Energy Brief, Oct 23 2026"),
    ("OIL", "WTI", 99.47, "$/bbl", "+2.4%", "Energy Brief, Oct 23 2026"),
    ("OIL", "Brent", 113.17, "$/bbl", "+4.0%", "Energy Brief, Oct 23 2026"),
    ("EQUITY", "VST", 140.83, "$", "-9.8%", "Energy Brief, Oct 23 2026"),
    ("EQUITY", "KMI", 33.72, "$", "-0.7%", "Energy Brief, Oct 23 2026"),
    ("EQUITY", "WMB", 70.63, "$", "-3.0%", "Energy Brief, Oct 23 2026"),
    ("EQUITY", "RRC", 43.86, "$", "+2.1%", "Energy Brief, Oct 23 2026"),
    ("EQUITY", "NVDA", 212.21, "$", "-4.4%", "Energy Brief, Oct 23 2026"),
    ("PPA", "Solar PPA index (NA)", None, "", "-4.8% QoQ (Q2)", "LevelTen Q2 2026"),
    ("PPA", "Wind PPA index (NA)", None, "", "+5.5% QoQ, +17.5% YoY", "LevelTen Q2 2026"),
]

# (date, headline paraphrase, source, url)
NEWS = [
    ("Oct 2026", "Henry Hub slides below $3 as storage builds; winter strip in contango", "Energy Brief",
     "https://buttondown.com/WeeMee101/archive/meta-70-28-u03c3-hh-280-11-others/"),
    ("Oct 2026", "ERCOT data-center buildout forecast updated for large-load growth", "Modo Energy",
     "https://modoenergy.com/research/en/ercot-data-center-buildout-forecast-october-2026"),
    ("Aug 2026", "ERCOT sets 91,090 MW peak; summer prices stay far calmer than PJM's", "FactSet Insight",
     "https://insight.factset.com/ercot-prices-remain-steady-despite-record-load"),
    ("Jul 2026", "EIA lifts 2026 Henry Hub forecast to $3.67/MMBtu", "Rigzone",
     "https://www.rigzone.com/news/usa_eia_raises_henry_hub_price_forecast_for_2026_2027-15-jul-2026-184139-article/"),
    ("Jul 2026", "Wind PPA prices climb, solar dips ahead of tax-credit deadline", "LevelTen / pv magazine",
     "https://www.leveltenenergy.com/post/levelten-north-american-ppa-price-index-q2-2026"),
    ("2025", "ERCOT and PJM hold 72% of high-confidence US large-load pipelines", "Wood Mackenzie",
     "https://www.woodmac.com/news/opinion/us-utility-large-load-pipelines-a-reality-check/"),
    ("2025", "Texas SB 6 sets large-load interconnection and curtailment rules above 75 MW", "Bracewell",
     "https://www.bracewell.com/resources/texas-senate-bill-6-ushers-in-major-overhaul-of-large-load-interconnection-and-grid-access-rules/"),
]


def live_quotes():
    """Hook for a live data provider (e.g. an exchange or EIA API key). Returns None offline."""
    return None


def tape_items():
    q = live_quotes() or QUOTES
    out = []
    for grp, sym, val, unit, chg, _src in q:
        v = "" if val is None else (f"{val:,.2f}" if abs(val) < 1000 else f"{val:,.0f}")
        out.append((grp, sym, v, unit, chg))
    return out
