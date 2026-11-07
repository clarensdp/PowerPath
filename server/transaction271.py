"""v27.1 Core Scientific Finance I LLC 7.750% Senior Secured Notes due 2031 — evidence register, instrument schedule,
filing reconciliation and a SEPARATE illustrative project scenario.

Three layers are kept apart in code, storage and API responses:
  Layer 1  PUBLIC facts: values read from identified SEC filings (classification PUBLIC_PRIMARY_SOURCE).
  Layer 2  Reconstructed financing cash flows from engine/fixed_note27.cjs under documented assumptions.
  Layer 3  Illustrative project economics from labelled hypothetical inputs. Never a Core Scientific valuation.
G4 and G5 are BLOCKED in every response and no request can change that.
"""
from __future__ import annotations
import hashlib, json, secrets
from datetime import date, datetime, timedelta, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

INSTRUMENT = 'CORE-SCIENTIFIC-FINANCE-I-7.750-2031'
SLUG = 'core-scientific-2026'
CLASSES = ('PUBLIC_PRIMARY_SOURCE', 'EXECUTED_CONTRACT_VERIFIED', 'USER_ASSUMPTION', 'MODEL_DERIVED', 'UNVERIFIED', 'CONFLICTING_EVIDENCE')
K8 = 'https://investors.corescientific.com/sec-filings/all-sec-filings/content/0001193125-26-208905/d47435d8k.htm'
EX99 = 'https://www.sec.gov/Archives/edgar/data/1839341/000119312526208905/d47435dex991.htm'
Q2 = 'https://www.sec.gov/Archives/edgar/data/1839341/000183934126000014/core-20260630.htm'
PRIOR = 'HISTORY/CLAUDE_AUDIT_VERDICT.md and baseline/independent_audit_claude (prior AI review, not a primary source)'
PUBLIC_FILING_HOSTS = ('sec.gov', 'corescientific.com', 'businesswire.com', 'prnewswire.com', 'globenewswire.com')
G_BLOCKS = {'g4': 'BLOCKED', 'g5': 'BLOCKED', 'valuation_allowed': False, 'lender_certified': False}
G4_REASONS = ['Executed indenture, schedules and definitions not attached or reconciled', 'Executed leases, rent-commencement and revenue-credit records not available',
              'Security/collateral and DSRA mechanics not verified', 'No named reviewer has completed the executed-document evidence assessment']
G5_REASONS = ['No qualified independent human model review or sign-off; automated tests and AI review cannot satisfy G5']

# (name, value, units, classification, source, locator, source_date, rationale, dependents)
INPUTS = [
 ('issuer', 'Core Scientific Finance I LLC', 'entity', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01', '2026-05-06', 'Issuer named in 8-K', ['terms']),
 ('principal', 3300.0, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01 (also 10-Q Note 7 debt table)', '2026-05-06', 'Aggregate principal at issue', ['debt_schedule', 'reconciliation']),
 ('coupon', 7.75, 'pct_per_annum', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01', '2026-05-06', 'Fixed coupon', ['debt_schedule']),
 ('issue_price', 99.25, 'pct_of_par', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01; Exhibit 99.1', '2026-05-06', 'Issued at a discount', ['debt_schedule', 'reconciliation']),
 ('issue_date', '2026-05-06', 'date', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01 (indenture dated May 6, 2026)', '2026-05-06', 'Closing / indenture date', ['debt_schedule']),
 ('maturity_date', '2031-05-15', 'date', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01', '2026-05-06', 'Stated maturity', ['debt_schedule']),
 ('interest_payment_dates', 'May 15 and November 15', 'calendar', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01', '2026-05-06', 'Semiannual in arrears', ['debt_schedule']),
 ('first_interest_date', '2026-11-15', 'date', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01', '2026-05-06', 'First coupon date (stub period from issue)', ['debt_schedule']),
 ('amortization_rate', 11.5, 'pct_per_annum_of_issue_date_principal', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01; 10-Q Note 7', '2026-05-06', 'Semiannual installments of 5.75% of original principal from the First Installment Payment Date', ['debt_schedule', 'scenarios']),
 ('first_installment_definition', 'First semiannual payment date at least 15 days after the later of rent commencement and abatement of all revenue credits', 'definition', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 (paraphrase of indenture definition; indenture text not reviewed)', '2026-07-28', 'Trigger is contingent; modelled as a scenario variable', ['scenarios']),
 ('issuer_assumed_first_installment', '2029-11-15', 'date', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 maturity table footnote', '2026-07-28', 'ISSUER ASSUMPTION used for its maturity table; not a contractual date', ['scenarios', 'reconciliation']),
 ('maturities_2029', 189.75, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 maturity table', '2026-07-28', 'Under the issuer assumption', ['reconciliation']),
 ('maturities_2030', 379.5, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 maturity table', '2026-07-28', 'Under the issuer assumption', ['reconciliation']),
 ('maturities_2031', 2730.75, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 maturity table (2031/thereafter row)', '2026-07-28', 'Final maturity payment incl. May-2031 installment', ['reconciliation']),
 ('original_issue_discount', 24.8, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7', '2026-07-28', 'Recorded OID (rounded to $0.1M)', ['reconciliation']),
 ('issuance_costs', 42.0, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7', '2026-07-28', 'Debt issuance costs recorded against carrying amount', ['debt_schedule', 'reconciliation']),
 ('effective_interest_rate', 8.3, 'pct', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 debt table', '2026-07-28', 'Reported effective rate (rounded)', ['reconciliation']),
 ('dsra_balance_2026_06_30', 344.8, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 2 / Note 7 (restricted cash)', '2026-07-28', 'Balance on deposit; sizing and release mechanics not disclosed', ['debt_schedule', 'reconciliation']),
 ('restricted_cash_total_2026_06_30', 781.656, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, 'Balance sheet (current 165.745 + noncurrent 615.911)', '2026-07-28', 'Company-wide restricted cash including DSRA', ['reconciliation']),
 ('q2_2026_coupon_interest_all_debt', 48.690, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 interest table (aggregate debt)', '2026-07-28', 'Not notes-specific', ['reconciliation']),
 ('q2_2026_discount_cost_amortization_all_debt', 3.682, 'USD_M', 'PUBLIC_PRIMARY_SOURCE', Q2, '10-Q Note 7 interest table (aggregate debt)', '2026-07-28', 'Not notes-specific', ['reconciliation']),
 ('net_proceeds_8k', 3240.0, 'USD_M_approx', 'CONFLICTING_EVIDENCE', K8, 'Item 8.01 / use of proceeds ("approximately $3.24 billion")', '2026-05-06', 'Conflicts with 3,233.25 derived from 10-Q OID and costs; 8-K figure is an estimate', ['reconciliation']),
 ('guarantors', ['Austin', 'Denton', 'Dalton', 'Marble', 'Muskogee'], 'entities', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01 (Subsidiary Guarantors)', '2026-05-06', 'Collateral scope: Issuer and five subsidiary guarantors', ['scope']),
 ('completion_guarantee_scope', 'All Projects other than the Austin, Texas campus; uncapped; not a guarantee of the notes', 'scope', 'PUBLIC_PRIMARY_SOURCE', K8, 'Item 1.01', '2026-05-06', 'Parent support is completion-only', ['scope']),
 ('day_count', '30/360', 'convention', 'USER_ASSUMPTION', None, None, None, 'Not stated in the 8-K or 10-Q read; US high-yield market convention assumed', ['debt_schedule']),
 ('interest_accrual_start', '2026-05-06', 'date', 'USER_ASSUMPTION', None, None, None, 'Interest assumed to accrue from the issue date (stub to 2026-11-15)', ['debt_schedule']),
 ('dsra_policy', 'hold', 'policy', 'USER_ASSUMPTION', None, None, None, 'Balance held constant; funding/release mechanics unknown until indenture reviewed', ['debt_schedule']),
 ('site_leased_mw', {'Denton': 260, 'Dalton': 175, 'Muskogee': 70, 'Marble': 65, 'Austin': 20}, 'MW_IT', 'UNVERIFIED', PRIOR, 'prior catalog, not re-confirmed', None, 'Per-site MW not confirmed against filings; Layer 3 only', ['illustrative_project']),
]
# Scenario variable: hypothetical rent-commencement / revenue-credit-abatement dates (USER_ASSUMPTION), mapped to the
# First Installment Payment Date with the 10-Q definition. 'base' reproduces the issuer's own 10-Q assumption.
SCENARIOS = {
 'early': {'rent_commencement': '2027-12-31', 'revenue_credit_abatement': '2028-04-30', 'label': 'Early qualifying rent commencement (hypothetical)'},
 'base': {'rent_commencement': '2029-06-30', 'revenue_credit_abatement': '2029-10-31', 'label': 'Base: consistent with the issuer 10-Q assumption of a 2029-11-15 first installment (dates hypothetical)'},
 'delayed': {'rent_commencement': '2030-06-30', 'revenue_credit_abatement': '2030-10-31', 'label': 'Delayed qualifying rent commencement (hypothetical)'},
 'no_trigger': {'rent_commencement': '2031-01-31', 'revenue_credit_abatement': '2031-05-01', 'label': 'Trigger not met before maturity (hypothetical): full principal due 2031-05-15'},
}
PAYMENT_MONTH_DAYS = [(5, 15), (11, 15)]
DSCR_TARGETS = [1.0, 1.2, 1.35]


def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')


def payment_dates(first='2026-11-15', maturity='2031-05-15'):
    f, m = date.fromisoformat(first), date.fromisoformat(maturity)
    return sorted(date(y, mo, d) for y in range(f.year, m.year + 1) for mo, d in PAYMENT_MONTH_DAYS if f <= date(y, mo, d) <= m)


def first_installment_date(rent_commencement: str, abatement: str, maturity='2031-05-15'):
    """10-Q Note 7 definition: first semiannual payment date at least 15 days after the later of the two events.
    Returns None when no such date falls on or before maturity (everything is then due at maturity)."""
    later = max(date.fromisoformat(rent_commencement), date.fromisoformat(abatement)) + timedelta(days=15)
    return next((d.isoformat() for d in payment_dates(maturity=maturity) if d >= later), None)


def note_input(inputs: dict, first_installment, reporting=('2026-06-30', '2026-12-31')):
    v = lambda k: inputs[k]['value']
    return {'instrumentId': INSTRUMENT, 'principalM': v('principal'), 'couponPct': v('coupon'), 'issuePricePct': v('issue_price'), 'issuanceCostsM': v('issuance_costs'),
            'issueDate': v('interest_accrual_start'), 'firstInterestDate': v('first_interest_date'), 'maturityDate': v('maturity_date'), 'dayCount': v('day_count'),
            'paymentMonthDays': [list(x) for x in PAYMENT_MONTH_DAYS], 'amortization': {'annualPctOfOriginal': v('amortization_rate'), 'installmentsPerYear': 2, 'firstInstallmentDate': first_installment},
            'dsra': {'balanceM': v('dsra_balance_2026_06_30'), 'policy': 'hold' if v('dsra_policy') == 'hold' else 'release_at_maturity'},
            'dscrTargets': DSCR_TARGETS, 'reportingDates': list(reporting)}


class ReclassIn(BaseModel):
    classification: str = Field(pattern='^(' + '|'.join(CLASSES) + ')$')
    rationale: str = Field(min_length=10, max_length=2000)
    evidence_id: str | None = None
    source_url: str | None = Field(default=None, max_length=700)
    source_locator: str | None = Field(default=None, max_length=300)
    source_date: str | None = Field(default=None, max_length=10)


class IllustrativeIn(BaseModel):
    scenario: str = Field(default='base', pattern='^(early|base|delayed|no_trigger)$')
    rent_per_kw_month: float = Field(default=170.0, gt=0, le=1000)
    other_opex_pct: float = Field(default=12.0, ge=0, le=100)
    fixed_opex_m_per_month: float = Field(default=0.4, ge=0, le=100)
    discount_rate_pct: float = Field(default=10.0, gt=0, le=50)
    rent_shift_months: int = Field(default=0, ge=-24, le=36)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS v271_inputs (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, instrument TEXT NOT NULL, name TEXT NOT NULL,
 version INTEGER NOT NULL, value_json TEXT NOT NULL, units TEXT NOT NULL, classification TEXT NOT NULL, source_document TEXT, source_locator TEXT,
 source_date TEXT, document_sha256 TEXT, reviewer TEXT, analyst TEXT, rationale TEXT NOT NULL, dependents_json TEXT NOT NULL, modified_at TEXT NOT NULL,
 UNIQUE(project_id,instrument,name,version));
'''


def install(app, db, calculate):
    with db() as con: con.executescript(SCHEMA)

    def actor(request):
        return getattr(request.state, 'user_id', None) or 'local-unauthenticated'

    def current_inputs(con, pid):
        rows = con.execute('SELECT * FROM v271_inputs WHERE project_id=? AND instrument=? ORDER BY name,version', (pid, INSTRUMENT)).fetchall()
        out = {}
        for r in rows:
            d = dict(r); d['value'] = json.loads(d.pop('value_json')); d['dependents'] = json.loads(d.pop('dependents_json')); out[d['name']] = d
        return out, len(rows)

    def require(con, pid):
        if not con.execute('SELECT 1 FROM projects WHERE id=?', (pid,)).fetchone(): raise HTTPException(404, 'Project not found')
        inputs, _ = current_inputs(con, pid)
        if not inputs: raise HTTPException(409, 'Register the v27.1 model inputs first: POST .../transactions/core-scientific-2026/model')
        return inputs

    def run_note(inputs, scenario):
        sc = SCENARIOS[scenario]
        fi = first_installment_date(sc['rent_commencement'], sc['revenue_credit_abatement'], inputs['maturity_date']['value'])
        return fi, calculate('fixed_note27', note_input(inputs, fi))

    base = f'/api/projects/{{pid}}/transactions/{SLUG}'

    @app.post(base + '/model', status_code=201)
    def register(pid: str, request: Request):
        with db() as con:
            if not con.execute('SELECT 1 FROM projects WHERE id=?', (pid,)).fetchone(): raise HTTPException(404, 'Project not found')
            if con.execute('SELECT 1 FROM v271_inputs WHERE project_id=? AND instrument=?', (pid, INSTRUMENT)).fetchone():
                raise HTTPException(409, 'Inputs already registered; values change only through versioned reclassification')
            ts = now(); who = actor(request)
            con.execute('BEGIN IMMEDIATE')
            for name, value, units, cls, src, loc, sdate, why, deps in INPUTS:
                con.execute('INSERT INTO v271_inputs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (secrets.token_hex(12), pid, INSTRUMENT, name, 1, json.dumps(value), units, cls, src, loc, sdate, None, None, who, why, json.dumps(deps), ts))
            con.execute('COMMIT')
        return {'instrument': INSTRUMENT, 'inputs': len(INPUTS), **G_BLOCKS}

    @app.get(base + '/inputs')
    def list_inputs(pid: str):
        with db() as con:
            inputs = require(con, pid); _, versions = current_inputs(con, pid)
        return {'instrument': INSTRUMENT, 'inputs': list(inputs.values()), 'stored_versions': versions, 'classifications': CLASSES, **G_BLOCKS}

    @app.post(base + '/inputs/{name}/reclassify', status_code=201)
    def reclassify(pid: str, name: str, data: ReclassIn, request: Request):
        """Promotion rules (Part V): a press release, filing or analyst assumption can never become EXECUTED_CONTRACT_VERIFIED.
        That requires an authenticated approver, an executed document uploaded to this project's evidence room, and a source
        that is the document itself. Even then G4/G5 stay BLOCKED."""
        from server.institutional import AUTH_MODE, ROLE_RANK
        with db() as con:
            inputs = require(con, pid)
            cur = inputs.get(name)
            if not cur: raise HTTPException(404, 'Unknown input')
            if cur['classification'] == 'MODEL_DERIVED' or data.classification == 'MODEL_DERIVED':
                raise HTTPException(422, 'MODEL_DERIVED values are computed, not reclassified')
            doc_hash = None
            if data.classification == 'EXECUTED_CONTRACT_VERIFIED':
                if AUTH_MODE != 'required' or ROLE_RANK.get(getattr(request.state, 'role', ''), 0) < ROLE_RANK['approver']:
                    raise HTTPException(403, 'Executed-contract verification requires an authenticated approver (required auth mode)')
                if not data.evidence_id: raise HTTPException(422, 'An executed document in this project evidence room is required')
                ev = con.execute('SELECT * FROM evidence WHERE id=? AND project_id=?', (data.evidence_id, pid)).fetchone()
                if not ev or not ev['stored_filename'] or not ev['content_hash']: raise HTTPException(422, 'Evidence record must hold an uploaded, hashed document')
                if ev['evidence_status'] != 'executed_document': raise HTTPException(422, 'Evidence must be recorded as an executed document')
                src = (data.source_url or cur.get('source_document') or '')
                if any(h in src for h in PUBLIC_FILING_HOSTS) or not data.source_url:
                    raise HTTPException(422, 'A filing, press release or analyst assumption cannot be promoted to EXECUTED_CONTRACT_VERIFIED; cite the executed document')
                doc_hash = ev['content_hash']
            if data.classification == 'PUBLIC_PRIMARY_SOURCE':
                if not (data.source_url and data.source_locator and data.source_date): raise HTTPException(422, 'PUBLIC_PRIMARY_SOURCE needs source URL, locator and date')
                if not data.source_url.startswith('https://'): raise HTTPException(422, 'Source URL must be https')
            ts = now(); version = cur['version'] + 1
            con.execute('INSERT INTO v271_inputs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (secrets.token_hex(12), pid, INSTRUMENT, name, version, json.dumps(cur['value']), cur['units'], data.classification,
                        data.source_url or cur.get('source_document'), data.source_locator or cur.get('source_locator'), data.source_date or cur.get('source_date'), doc_hash,
                        actor(request) if data.classification == 'EXECUTED_CONTRACT_VERIFIED' else None, actor(request), data.rationale, json.dumps(cur['dependents']), ts))
        return {'name': name, 'version': version, 'classification': data.classification, 'previous_version_retained': True, **G_BLOCKS, 'g4_reasons': G4_REASONS}

    @app.get(base + '/terms')
    def terms(pid: str):
        with db() as con: inputs = require(con, pid)
        layer1 = [x for x in inputs.values() if x['classification'] in ('PUBLIC_PRIMARY_SOURCE', 'EXECUTED_CONTRACT_VERIFIED', 'CONFLICTING_EVIDENCE')]
        return {'layer': 'LAYER_1_PUBLIC_DISCLOSED_FACTS', 'facts': layer1, 'excluded_assumptions': [x['name'] for x in inputs.values() if x['name'] not in {f['name'] for f in layer1}],
                'note': 'Public-filing facts are not executed-contract verification.', **G_BLOCKS, 'g4_reasons': G4_REASONS, 'g5_reasons': G5_REASONS}

    @app.get(base + '/debt-schedule')
    def debt_schedule(pid: str, scenario: str = 'base'):
        if scenario not in SCENARIOS: raise HTTPException(422, f'Unknown scenario; use {sorted(SCENARIOS)}')
        with db() as con: inputs = require(con, pid)
        fi, out = run_note(inputs, scenario)
        return {'layer': 'LAYER_2_RECONSTRUCTED_FINANCING_CASH_FLOWS', 'scenario': scenario, 'scenario_definition': SCENARIOS[scenario], 'first_installment_date': fi,
                'trigger_rule': inputs['first_installment_definition']['value'], 'assumptions': {k: inputs[k]['value'] for k in ('day_count', 'interest_accrual_start', 'dsra_policy')},
                **out, 'not_a_project_valuation': True, **G_BLOCKS}

    @app.get(base + '/scenarios')
    def scenarios(pid: str):
        with db() as con: inputs = require(con, pid)
        res = []
        for k, sc in SCENARIOS.items():
            fi, out = run_note(inputs, k); s = out['summary']
            res.append({'scenario': k, 'label': sc['label'], 'rent_commencement_hypothetical': sc['rent_commencement'], 'abatement_hypothetical': sc['revenue_credit_abatement'],
                        'first_installment_date': fi, 'installments_before_maturity': s['installmentsBeforeMaturity'], 'total_interestM': s['totalInterestM'], 'total_scheduled_principalM': s['totalScheduledPrincipalM'],
                        'balloonM': s['balloonM'], 'final_maturity_principalM': s['finalMaturityPaymentPrincipalM'], 'principal_by_yearM': s['principalByCalendarYearM'],
                        'effective_yield_bond_equivalent_pct': s['effectiveYieldBondEquivalentPct'], 'dsra_balanceM': s['dsraBalanceM'],
                        'max_semiannual_debt_service_ex_balloonM': max(p['interestM'] + p['scheduledPrincipalM'] for p in out['periods'])})
        return {'layer': 'LAYER_2_RECONSTRUCTED_FINANCING_CASH_FLOWS', 'scenarios': res, 'note': 'Rent-commencement dates are hypothetical scenario variables, not contractual facts.', **G_BLOCKS}

    @app.get(base + '/reconciliation')
    def reconciliation(pid: str):
        with db() as con: inputs = require(con, pid)
        return {'layer': 'RECONCILIATION_LAYER_2_VS_FILINGS', 'rows': reconcile(inputs, calculate), 'no_balancing_plugs': True, **G_BLOCKS}

    @app.post(base + '/illustrative-project')
    def illustrative(pid: str, data: IllustrativeIn):
        with db() as con: inputs = require(con, pid)
        return illustrative_project(inputs, data, calculate)

    # v30.3.2: separate, read-only phased rent / note stress endpoint.
    from server.note_phasing import install as install_note_phasing
    install_note_phasing(app, db, calculate, require, base)


def _row(item, model, filing, units, source, status, explanation, period=None):
    var = (model - filing) if isinstance(model, (int, float)) and isinstance(filing, (int, float)) else None
    return {'item': item, 'model_value': model, 'filing_value': filing, 'units': units, 'period': period, 'variance': var, 'status': status, 'source': source, 'explanation': explanation}


def reconcile(inputs, calculate):
    v = lambda k: inputs[k]['value']
    base = calculate('fixed_note27', note_input(inputs, v('issuer_assumed_first_installment')))
    s = base['summary']; c0630 = s['carrying'][0]
    alt = calculate('fixed_note27', {**note_input(inputs, v('issuer_assumed_first_installment')), 'dayCount': 'ACT/360'})['summary']
    yrs = s['principalByCalendarYearM']
    coupon_12m = sum(p['interestM'] for p in base['periods'] if '2026-07-01' <= p['date'] <= '2027-06-30')
    oid_ok = abs(s['originalIssueDiscountM'] - v('original_issue_discount')) <= 0.05 + 1e-9
    rows = [
        _row('Gross principal', s['principalM'], v('principal'), 'USD_M', 'Core 8-K Item 1.01; 10-Q Note 7', 'RECONCILED', 'Input equals filing.', '2026-05-06'),
        _row('Original issue discount', s['originalIssueDiscountM'], v('original_issue_discount'), 'USD_M', '10-Q Note 7', 'WITHIN_ROUNDING' if oid_ok else 'OPEN_UNEXPLAINED', '3,300 x (1 - 99.25%) = 24.75; filing rounds to $0.1M.', '2026-05-06'),
        _row('Issuance costs', s['issuanceCostsM'], v('issuance_costs'), 'USD_M', '10-Q Note 7', 'INPUT_FROM_FILING', 'Taken from the 10-Q; not independently derivable (fees not itemised).', '2026-05-06'),
        _row('Net proceeds', s['netProceedsM'], v('net_proceeds_8k'), 'USD_M', 'Core 8-K ("approximately $3.24 billion") vs 10-Q OID and costs', 'OPEN_UNEXPLAINED', '10-Q-derived 3,233.25 is $6.75M below the 8-K estimate; the 8-K figure is approximate and pre-dates final costs. Not plugged.', '2026-05-06'),
        _row('Effective interest rate', s['effectiveYieldBondEquivalentPct'], v('effective_interest_rate'), 'pct', '10-Q Note 7', 'WITHIN_ROUNDING', f"Bond-equivalent yield on net proceeds under the issuer's 2029-11-15 assumption = {s['effectiveYieldBondEquivalentPct']:.3f}%, rounds to 8.3%. The annual-compounded equivalent ({s['effectiveAnnualRatePct']:.3f}%) would round to 8.4%, so the filing appears to use a nominal (semiannual) convention - an inference, not confirmed.", '2026-06-30'),
        _row('Principal due 2029', yrs.get('2029', 0), v('maturities_2029'), 'USD_M', '10-Q Note 7 maturity table', 'RECONCILED', 'One installment (5.75% x 3,300) on 2029-11-15 under the issuer assumption.', '2029'),
        _row('Principal due 2030', yrs.get('2030', 0), v('maturities_2030'), 'USD_M', '10-Q Note 7 maturity table', 'RECONCILED', 'Two installments.', '2030'),
        _row('Principal due 2031 (final maturity payment)', yrs.get('2031', 0), v('maturities_2031'), 'USD_M', '10-Q Note 7 maturity table', 'RECONCILED', f"Includes the 2031-05-15 scheduled installment of 189.75; the balloon proper is {s['balloonM']:.2f}. The earlier audit's '$2.73B balloon' is this whole maturity payment.", '2031'),
        _row('Carrying amount (amortised cost)', c0630['carryingAmountM'], None, 'USD_M', '10-Q Note 7', 'NOT_DISCLOSED_IN_SOURCE_READ', 'The 10-Q debt table read shows 3,300.0 principal for the notes; a notes-specific net carrying amount was not found. Model value is effective-interest amortised cost.', '2026-06-30'),
        _row('Unamortised discount and costs (notes)', c0630['unamortizedDiscountAndCostsM'], 87.033, 'USD_M', '10-Q Note 7 (aggregate for ALL debt)', 'NOT_COMPARABLE', 'Filing figure covers all Core Scientific debt; the notes portion modelled here must not exceed it (consistency check only).', '2026-06-30'),
        _row('Coupon accrued 2026-05-06 to 06-30', c0630['accruedCouponM'], v('q2_2026_coupon_interest_all_debt'), 'USD_M', '10-Q Note 7 interest table (aggregate)', 'NOT_COMPARABLE', 'Aggregate Q2 coupon interest also includes other debt (e.g. the term loan repaid May 2026); remainder after the notes is not attributable from the filing read.', 'Q2 2026'),
        _row('Discount/cost amortisation 2026-05-06 to 06-30', c0630['interestExpenseToDateM'] - c0630['accruedCouponM'], v('q2_2026_discount_cost_amortization_all_debt'), 'USD_M', '10-Q Note 7 interest table (aggregate)', 'NOT_COMPARABLE', 'Notes portion (effective-interest method) is below the aggregate, as it must be.', 'Q2 2026'),
        _row('Debt service reserve balance', s['dsraBalanceM'], v('dsra_balance_2026_06_30'), 'USD_M', '10-Q Note 2/7', 'INPUT_FROM_FILING', f'Sizing rule not disclosed: 344.8 equals {344.8 / coupon_12m:.3f}x the modelled coupons payable 2026-07-01..2027-06-30 ({coupon_12m:.2f}); no plug applied.', '2026-06-30'),
        _row('Restricted cash other than DSRA', v('restricted_cash_total_2026_06_30') - v('dsra_balance_2026_06_30'), None, 'USD_M', '10-Q balance sheet', 'OPEN_UNEXPLAINED', 'Company-wide restricted cash (781.656) less DSRA; composition and link to the notes not disclosed in the source read.', '2026-06-30'),
        _row('First coupon (stub, 30/360)', s['firstCouponM'], None, 'USD_M', 'Model (day count is an assumption)', 'MODEL_DERIVED', f"189/360 x 7.75% x 3,300. ACT/360 would give {alt['firstCouponM']:.2f} (+{alt['firstCouponM'] - s['firstCouponM']:.2f}); day count to be confirmed from the indenture.", '2026-11-15'),
        _row('Collateral scope', 'Issuer + 5 guarantors (Austin, Denton, Dalton, Marble, Muskogee)', 'Issuer + 5 guarantors', 'scope', 'Core 8-K Item 1.01', 'RECONCILED', 'Completion guarantee excludes Austin; parent does not guarantee the notes.', '2026-05-06'),
    ]
    return rows


def illustrative_project(inputs, data, calculate):
    """Layer 3. Hypothetical campus economics overlaid on the Layer 2 note schedule. Every input is labelled; nothing here
    is a Core Scientific valuation, debt capacity or equity return."""
    mw = inputs['site_leased_mw']['value']; total_mw = float(sum(mw.values()))
    sc = SCENARIOS[data.scenario]
    fi = first_installment_date(sc['rent_commencement'], sc['revenue_credit_abatement'])
    note = calculate('fixed_note27', note_input(inputs, fi))
    rc = date.fromisoformat(sc['rent_commencement'])
    # month index 1 = May 2026 (note issue month). Rent cash starts the month after the scenario's rent commencement for ALL
    # sites (single-date simplification; real commencement is phased, and revenue credits before abatement are not modelled).
    start_month = (rc.year - 2026) * 12 + rc.month - 5 + 1 + 1 + data.rent_shift_months
    months = 61
    cfg = {'engineVersion': '27.1.0', 'months': months, 'calendarStartYear': 2026, 'calendarStartMonth': 5, 'ltc': 0, 'mezzLtcPct': 0, 'initialCash': 0, 'minLiquidity': 0, 'reserveTargetM': 0,
           'sponsorCommitmentM': None, 'constructionCostMW': 0, 'exitValueM': 0, 'refinanceValueM': 0, 'loanMaturityMode': 'equity', 'powerResponsibility': 'tenant_direct',
           'rentPerKwMonth': data.rent_per_kw_month, 'otherOpexPct': data.other_opex_pct, 'fixedOpexM': data.fixed_opex_m_per_month, 'discount': data.discount_rate_pct,
           'buildings': [{'name': k, 'itMW': float(v), 'constructionStart': 1, 'constructionMonths': 1, 'powerMonth': max(1, start_month), 'leaseMonth': max(1, start_month), 'leaseTermMonths': 144, 'rentEscalatorPct': 2.5} for k, v in mw.items()]}
    run = calculate('underwrite', cfg)
    # CFADS is affine in rent (rent x (1 - opex%) - fixed costs), so a second run at a different rent identifies the line
    # exactly per period; used only to solve breakeven rents.
    run2 = calculate('underwrite', {**cfg, 'rentPerKwMonth': data.rent_per_kw_month * 2})
    def mindex(d): d = date.fromisoformat(d); return (d.year - 2026) * 12 + d.month - 5 + 1
    def by_period(rows):
        cf = {r['month']: r['cfads'] for r in rows}; out, prev = [], 0
        for p in note['periods']:
            end = min(mindex(p['date']), months); out.append(sum(cf.get(m, 0.0) for m in range(prev + 1, end + 1))); prev = end
        return out
    c1, c2 = by_period(run['rows']), by_period(run2['rows'])
    periods = []; prevm = 0
    for p, cfads in zip(note['periods'], c1):
        endm = min(mindex(p['date']), months); full_rent = prevm + 1 >= start_month; prevm = endm
        ds = p['interestM'] + p['scheduledPrincipalM']
        periods.append({'date': p['date'], 'cfadsM': cfads, 'scheduled_debt_serviceM': ds, 'balloonM': p['balloonM'], 'dscr': cfads / ds if ds > 0 else None, 'rent_months': 'full' if full_rent else ('partial' if cfads != 0 else 'none'), 'cfads_after_debt_serviceM': cfads - ds})
    dscrs = [x['dscr'] for x in periods if x['dscr'] is not None]
    r_semi = (1 + data.discount_rate_pct / 100) ** 0.5 - 1
    npv_cfads = sum(x['cfadsM'] / (1 + r_semi) ** (i + 1) for i, x in enumerate(periods))
    npv_resid = sum((x['cfadsM'] - x['scheduled_debt_serviceM'] - x['balloonM']) / (1 + r_semi) ** (i + 1) for i, x in enumerate(periods))
    def rent_for(target):
        """Lowest rent at which every period with scheduled debt service AND rent covers it at `target` (periods before rent
        starts cannot be covered by any rent and are reported separately)."""
        worst = None
        for x, a1, a2 in zip(periods, c1, c2):
            slope = (a2 - a1) / data.rent_per_kw_month
            if x['scheduled_debt_serviceM'] <= 0 or x['rent_months'] != 'full' or slope <= 1e-12: continue
            need = data.rent_per_kw_month + (target * x['scheduled_debt_serviceM'] - a1) / slope
            worst = need if worst is None else max(worst, need)
        return worst
    uncovered = [x['date'] for x in periods if x['scheduled_debt_serviceM'] > 0 and x['rent_months'] == 'none']
    pre_rent_ds = sum(x['scheduled_debt_serviceM'] for x in periods if x['rent_months'] == 'none')
    full = [x['dscr'] for x in periods if x['rent_months'] == 'full' and x['dscr'] is not None]
    labels = {'site_leased_mw': 'UNVERIFIED (prior catalog, not re-confirmed)', 'rent_per_kw_month': 'USER_ASSUMPTION (PowerPath generic default; NOT a CoreWeave contract rent)',
              'other_opex_pct': 'USER_ASSUMPTION', 'fixed_opex_m_per_month': 'USER_ASSUMPTION', 'rent_commencement': 'USER_ASSUMPTION (scenario variable; single date for all sites; revenue credits not modelled)', 'power': 'USER_ASSUMPTION: tenant pays power directly',
              'capex': 'EXCLUDED: sunk/financed outside this view; therefore no equity return or project value is computed', 'escalator': 'USER_ASSUMPTION 2.5%', 'lease_term': 'USER_ASSUMPTION 144 months', 'discount_rate_pct': 'USER_ASSUMPTION'}
    return {'layer': 'LAYER_3_ILLUSTRATIVE_PROJECT_SCENARIO', 'NOT_A_CORE_SCIENTIFIC_VALUATION': True, 'scenario': data.scenario, 'first_installment_date': fi,
            'inputs': {**data.model_dump(), 'total_it_mw': total_mw, 'rent_cash_start_month_index': start_month}, 'input_labels': labels,
            'periods': periods, 'min_dscr_full_rent_periods_ex_balloon': min(full) if full else None, 'periods_below_1x_all': sum(1 for d in dscrs if d < 1),
            'pre_rent_debt_serviceM': pre_rent_ds, 'dsra_balanceM': inputs['dsra_balance_2026_06_30']['value'],
            'pre_rent_funding_gap_vs_dsraM': max(0.0, pre_rent_ds - inputs['dsra_balance_2026_06_30']['value']),
            'pre_rent_note': 'Under the single-date rent assumption, coupons before rent would be met from the DSRA and other sources; a positive gap is an artefact of this hypothetical, not a finding about Core Scientific liquidity.',
            'breakeven_rent_per_kw_month': {f'{t:.2f}x': rent_for(t) for t in DSCR_TARGETS}, 'periods_with_debt_service_before_rent': uncovered,
            'balloon_at_maturityM': note['summary']['balloonM'], 'final_maturity_principalM': note['summary']['finalMaturityPaymentPrincipalM'],
            'illustrative_npv_post_closing_cfadsM': npv_cfads, 'illustrative_npv_cfads_less_note_service_incl_balloonM': npv_resid,
            'npv_caveat': 'Excludes invested capital, refinancing of the balloon, taxes and terminal value. Not an equity return, enterprise value or debt capacity.',
            'engine': {'project': run['summary'].get('engineVersion'), 'note': note['engineVersion']}, **G_BLOCKS}
