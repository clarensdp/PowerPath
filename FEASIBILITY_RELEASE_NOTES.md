# PowerPath Feasibility — Release notes

## Added
- New **🧭 Site feasibility** tab inside the existing Streamlit interface.
- Project intake fields (name, region, parcel ID, demand and diligence stage).
- 30 structured screening requirements across six assessment domains.
- Critical development gates versus advisory due-diligence checks.
- Evidence tracking: status, source/reference, reviewer and suggested documentation.
- Conservative tri-state overall determination and actionable evidence gaps.
- Exportable structured JSON and markdown diligence memo.
- Connection to existing grid-delay scenario input, with explicit user action.
- Four focused feasibility unit tests.

## Safeguards and limitations
- No automatic site selection, GIS retrieval, live regulatory intelligence, or real permitting claims.
- Statuses are user assertions. The application checks for evidence presence, not authenticity.
- The status counter is document completeness, **not** a weighted probability or certified feasibility grade.
- Full commercial critical-path calculations and regulatory delay feedback are not implemented; only optional grid connection slips are linked to the energy model.
- Original benchmark assumptions and optimization/checking implementation are unchanged.

## Run
`pip install -r team_app/requirements.txt`
`streamlit run team_app/app.py`
`python -m unittest discover -s team_app/tests -v`
