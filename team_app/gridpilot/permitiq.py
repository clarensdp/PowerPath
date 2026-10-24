"""Conservative, source-labeled permitting diligence scaffold. Not legal advice."""
from datetime import date

SOURCES = {
    "texas_air": "https://www.tceq.texas.gov/permitting/air/air_permits.html",
    "texas_grid": "https://www.puc.texas.gov/",
    "county": "https://www.wilcotx.gov/",
    "pjm": "https://www.pjm.com/",
}

def preliminary_screen(caps, jurisdiction):
    rows = []
    def add(area, task, agency, source, trigger):
        rows.append(dict(area=area, requirement_or_task=task, authority_to_confirm=agency,
                         official_starting_source=source, trigger=trigger, evidence_status="Unverified - requires review",
                         workflow_status="Not started", owner="", effective_date="Unknown",
                         source_checked_on="Not checked", note="Confirm parcel, technology, governing rule and current status."))
    add("Site", "Confirm parcel, zoning, development controls and possible local approvals", "Local planning / permitting authority", SOURCES["county"] if "Texas" in jurisdiction else SOURCES["pjm"], "Every site")
    add("Grid", "Confirm load service, utility tariff, studies, upgrade and energization milestones", "Serving utility and relevant system operator", SOURCES["texas_grid"] if "Texas" in jurisdiction else SOURCES["pjm"], "Every large-load project")
    for key in ("gas_engine", "gas_turbine", "fuel_cell"):
        if caps.get(key, 0) > 0:
            add("Air", "Determine applicable authorization and required engineering/emissions exhibits for " + key, "State environmental authority", SOURCES["texas_air"] if "Texas" in jurisdiction else "Identify state agency", f"{caps[key]} MW {key}")
    if caps.get("battery_4h",0)>0:
        add("Safety", "Confirm energy-storage fire, electrical, emergency response and site reviews", "Authority having jurisdiction", SOURCES["county"] if "Texas" in jurisdiction else "Identify city/county", f"{caps['battery_4h']} MW BESS")
    if "PJM" in jurisdiction:
        add("Policy", "Check current local moratoria, proposed ordinances, effective dates and carve-outs", "Parcel municipality and county", "Locate official legislative agenda and enacted code", "PJM is not a single zoning jurisdiction")
    add("Documentation", "Verify site control, engineering drawings, equipment specifications and owner signoff", "Developer / project counsel", "Internal project records", "Before submission")
    return rows

def task_template(project, jurisdiction, rows):
    lines = [f"# Preliminary permitting and compliance review — {project}",
             f"Jurisdiction selected: {jurisdiction}", f"Generated: {date.today().isoformat()}",
             "", "NOT A PERMIT APPLICATION OR COMPLIANCE CERTIFICATION. All potential requirements require source verification and owner approval.", ""]
    for n,r in enumerate(rows,1):
        lines.extend([f"## {n}. {r['area']}: {r['requirement_or_task']}",f"- Trigger: {r['trigger']}",
                      f"- Authority to confirm: {r['authority_to_confirm']}", f"- Starting source: {r['official_starting_source']}",
                      "- Assigned owner: [TBD]", "- Effective date and applicability: [VERIFY]", "- Evidence / citation: [ATTACH]", "- Reviewer approval: [PENDING]", ""])
    return "\n".join(lines)
