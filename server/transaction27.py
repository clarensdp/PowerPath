"""Public-filed transaction term register; no automatic valuation or certification."""

from __future__ import annotations
import json, secrets
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ISSUER = "Core Scientific Finance I LLC"
FILING = "https://investors.corescientific.com/sec-filings/all-sec-filings/content/0001193125-26-208905/d47435d8k.htm"
RELEASE = "https://www.sec.gov/Archives/edgar/data/1839341/000119312526208905/d47435dex991.htm"
FACTS = [
    ("issuer", ISSUER, "entity", FILING, "Issuer, Item 1.01"),
    ("principal_usd", 3300000000, "USD", FILING, "Item 1.01"),
    ("coupon_pct", 7.750, "percent_per_annum", FILING, "Indenture and Notes"),
    ("issue_price_pct", 99.250, "percent_of_par", FILING, "Offering"),
    ("maturity_date", "2031-05-15", "date", FILING, "Indenture and Notes"),
    ("interest_frequency", "semiannual", "frequency", FILING, "Indenture and Notes"),
    ("first_interest_date", "2026-11-15", "date", FILING, "Indenture and Notes"),
    ("closing_date", "2026-05-06", "date", FILING, "Offering closing"),
    ("initial_net_proceeds_usd_approx", 3240000000, "USD_approx", FILING, "Offering"),
    (
        "completion_guarantee_projects",
        ["Dalton GA", "Denton TX", "Marble NC", "Muskogee OK"],
        "locations",
        RELEASE,
        "Exhibit 99.1, completion guarantee",
    ),
]
GAPS = [
    (
        "executed_indentures_and_all_schedules",
        "Executed indenture and incorporated definitions needed for exact waterfall, reserves and covenants",
    ),
    (
        "collateral_and_security_documents",
        "Security schedules, collateral exceptions, lien waterfall and perfection needed",
    ),
    ("construction_budget_and_draw_schedule", "Actual project-by-project budgets and uses of debt proceeds needed"),
    ("project_cash_flows_and_leases", "Executed leases/credit terms and support agreements needed to project CFADS"),
    ("utility_interconnection_and_power", "Utility agreements and service milestone commitments needed"),
    ("debt_service_reserve_terms", "Indenture details and restrictions required to model reserve balances"),
    ("completion_support_terms", "Executed completion guarantee and triggers required"),
    ("model_independent_review", "Qualified human assurance and G5 signoff required"),
]


def ts():
    return datetime.now(timezone.utc).isoformat()


def install(app, db):
    with db() as con:
        con.executescript(
            """
        CREATE TABLE IF NOT EXISTS v27_transactions (id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, name TEXT NOT NULL, issuer TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PUBLIC_DISCLOSURE_ONLY', created_at TEXT NOT NULL, UNIQUE(project_id,issuer));
        CREATE TABLE IF NOT EXISTS v27_transaction_facts (id TEXT PRIMARY KEY, transaction_id TEXT NOT NULL REFERENCES v27_transactions(id) ON DELETE CASCADE, field TEXT NOT NULL, value_json TEXT NOT NULL, unit TEXT NOT NULL, source_url TEXT NOT NULL, source_locator TEXT NOT NULL, verification TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(transaction_id,field));
        CREATE TABLE IF NOT EXISTS v27_transaction_gaps (id TEXT PRIMARY KEY,transaction_id TEXT NOT NULL REFERENCES v27_transactions(id) ON DELETE CASCADE,code TEXT NOT NULL,description TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'OPEN',UNIQUE(transaction_id,code));
        """
        )

    @app.post("/api/projects/{pid}/transactions/core-scientific-2026", status_code=201)
    def seed_transaction(pid: str, request: Request):
        with db() as con:
            if not con.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone():
                return JSONResponse({"detail": "Project not found"}, status_code=404)
            already = con.execute(
                "SELECT id FROM v27_transactions WHERE project_id=? AND issuer=?", (pid, ISSUER)
            ).fetchone()
            if already:
                return JSONResponse(
                    {
                        "detail": "Transaction already registered; immutable source facts were not replaced",
                        "id": already["id"],
                    },
                    status_code=409,
                )
            tid = secrets.token_hex(12)
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO v27_transactions VALUES(?,?,?,?,?,?)",
                (
                    tid,
                    pid,
                    "Core Scientific $3.3B 7.750% Secured Notes, May 2026",
                    ISSUER,
                    "PUBLIC_DISCLOSURE_ONLY",
                    ts(),
                ),
            )
            for field, value, unit, source, loc in FACTS:
                con.execute(
                    "INSERT INTO v27_transaction_facts VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        secrets.token_hex(12),
                        tid,
                        field,
                        json.dumps(value),
                        unit,
                        source,
                        loc,
                        "PUBLIC_PRIMARY_SOURCE_NOT_CONTRACT_VERIFIED",
                        ts(),
                    ),
                )
            for code, desc in GAPS:
                con.execute(
                    "INSERT INTO v27_transaction_gaps(id,transaction_id,code,description) VALUES(?,?,?,?)",
                    (secrets.token_hex(12), tid, code, desc),
                )
            try:
                from server.institutional import append_audit, AUTH_MODE

                append_audit(
                    con,
                    getattr(request.state, "tenant_id", None),
                    getattr(request.state, "user_id", None),
                    "transaction.public_seeded",
                    tid,
                    {"project_id": pid, "source_count": len(FACTS)},
                )
            except ImportError:
                pass
            con.execute("COMMIT")
        return {
            "id": tid,
            "fact_count": len(FACTS),
            "open_gaps": len(GAPS),
            "g4": "BLOCKED",
            "g5": "BLOCKED",
            "valuation_allowed": False,
        }

    @app.get("/api/projects/{pid}/transactions")
    def transactions(pid: str):
        with db() as con:
            result = []
            for tr in con.execute("SELECT * FROM v27_transactions WHERE project_id=?", (pid,)):
                item = dict(tr)
                item["facts"] = [
                    {**dict(f), "value": json.loads(f["value_json"])}
                    for f in con.execute(
                        "SELECT * FROM v27_transaction_facts WHERE transaction_id=? ORDER BY field", (tr["id"],)
                    )
                ]
                item["gaps"] = [
                    dict(g)
                    for g in con.execute(
                        "SELECT * FROM v27_transaction_gaps WHERE transaction_id=? ORDER BY code", (tr["id"],)
                    )
                ]
                item.update(g4="BLOCKED", g5="BLOCKED", valuation_allowed=False, source_scope="PUBLIC_FILING_ONLY")
                result.append(item)
            return result
