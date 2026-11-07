"""Role workflow. Offline rules are explicitly NOT AI. Live runner calls independent Responses requests."""

ROLES = [
    "Chief of Staff",
    "CFO",
    "CTO",
    "CPO",
    "Head of Product Design",
    "CDO",
    "COO",
    "CRO",
    "CMO",
    "Chief Risk Officer",
]
DUTIES = {
    "Chief of Staff": "Summarize decisions, owners, dependencies, and outstanding approvals.",
    "CFO": "Estimate which changed source assumptions could alter debt-service capacity and liquidity; do not compute unsourced valuations.",
    "CTO": "Identify reproducible engine and data integration checks with test acceptance gates.",
    "CPO": "Prioritize user problems, workflow sequencing and acceptance criteria.",
    "Head of Product Design": "Specify a clear evidence-to-decision interface and preserve visible blocked status.",
    "CDO": "Verify row identity, source vintage, normalization, missing data, geography, and known limits of public sources.",
    "COO": "Propose owners, permit dependency tracking, and controlled follow-up tasks.",
    "CRO": "Identify interview hypotheses; no external customer contact without explicit approval.",
    "CMO": "Write accurate positioning without claiming grid availability or lender-grade assurance.",
    "Chief Risk Officer": "Enforce G4/G5 blocked, flag unsupported MW and unreviewed schedules; separate observed vs inferred.",
}


def offline_council(mission, changes, pending):
    counts = {}
    for c in changes:
        counts[c["source_key"]] = counts.get(c["source_key"], 0) + 1
    summary = ", ".join(f"{v} {k} observed row changes" for k, v in sorted(counts.items())) or "No observed row changes"
    return {
        "mode": "OFFLINE_RULES",
        "not_independent_model_calls": True,
        "mission": mission,
        "observed": summary,
        "unreviewed_proposals": pending,
        "messages": [
            {
                "role": role,
                "content": f"{DUTIES[role]} Input summary: {summary}. Suggested next action: inspect source row diffs, record evidence quality, and leave milestone/valuation decisions for approval.",
            }
            for role in ROLES
        ],
        "safety": "Screening only. Observed queue changes are not utility service rights. No external messages, automatic approvals, or model edits.",
    }
