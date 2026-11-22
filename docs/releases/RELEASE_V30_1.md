# PowerPath v30.1 — Feasibility Engine Phase 1 (alpha)

Preserves all v30 NC/VA functionality. Adds standalone `feasibility/` scoring prototype, versioned workbook parameters and five workbook fixtures. No scoring is exposed in the UI yet; no live data evidence is represented as verified utility capacity.

Run: `python3 -m pip install -r requirements-feasibility.txt && python3 -m pytest -q feasibility/test_phase1.py`

Limitations: workbook fixture parity checks cover 23 utility metrics, pillar totals and default-mode final scoring for all five examples (within 0.01). Alternative modes and Dollar curve are NOT certified. The fixture sites are illustrative. Existing v30 financial release exceptions persist.
