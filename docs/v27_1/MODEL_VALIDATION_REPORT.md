# MODEL_VALIDATION_REPORT — PowerPath v27.1.0

**Reviewer:** Claude (AI). This is not a qualified human model review and does not satisfy G5.

**Environment:**

| Component | Version |
|---|---|
| Linux kernel | 6.18 |
| Python | 3.13.17 |
| FastAPI | 0.162.0 |
| Pydantic | 2.13.5 |
| Node | 22.23.4 |
| TypeScript | 5.9.3 (the repo pins none; TS 7.x rejects the inherited tsconfig) |
| Chromium | 153, via Playwright 1.63 |

**Evidence base.** All results below come from a **clean extraction of `PowerPath_v27_1_Financial_Validation.zip`**, not from the working tree. The package's `SHA256_MANIFEST.json` was re-verified on extraction: 484/484 files match.

## 1. Sequence followed

1. **Reproduced v27.0 before changing anything:**
   - RT-A02: minimum cash −$50.07M, 98 negative months, $58.99M of interest "paid" after the halt;
   - RT-E04b: 16 vs 9 months, NPV $780.9M vs $906.7M on the same path;
   - a packaging regression: inherited audit 36/37, because `transactions_v259.json` was missing.
2. **Wrote an independent oracle** (`tests/v271/oracle_waterfall.py`) before the engine was integrated into the server.
3. **Built the corrected engine** as a new version; the legacy engine is frozen.
4. **Built one schedule engine** and pointed every interface at it.
5. **Rechecked Core Scientific terms** against the 8-K, Ex. 99.1 and the Q2 10-Q, then built the schedule, scenarios and reconciliation.
6. **Ran the full regression, mutation and security suites**, then packaged the release and validated it from the zip.

## 2. Release runner (`python tests/run_v268_audit.py`): 18/18 PASS

| Check | Tests | Result |
|---|---|---|
| TypeScript build | — | PASS |
| v26.4–26.8 APIs | 5 | PASS |
| Live-agent mocked provider (no real calls) | 4 | PASS |
| Red-team API (B/C/D/E/G) | 34 | PASS. 1 expected failure: RT-D03, no approver identity in local-only mode (by design; required-auth mode records it) |
| Red-team agents (F) | 14 | PASS |
| Adversarial finance, legacy engine | 25 | PASS. A02 is a documented legacy-only defect, kept for reproducibility |
| Python reference parity, legacy engine | 80,240 fields | PASS, max gap 1.4e-12 |
| v27.0 security / transaction register | 5 | PASS |
| **v27.1 waterfall oracle** | 15 | PASS |
| **v27.1 delay convention and interface parity** | 11 | PASS |
| **v27.1 Core Scientific, evidence, immutability, gates** | 16 | PASS |
| **v27.1 required-auth tenancy and promotion** | 3 | PASS |
| Adversarial finance, **corrected engine** | 25 | PASS. A02 now passes |
| Reference parity with changed-treatment localisation | 80,240 fields | PASS: 27 cases identical; 4 identical up to month 60 then intentionally different; ΔNPV 0 |
| Corrected engine rebuilds byte-for-byte from the frozen source | — | PASS |
| Full inherited audit (`tests/run_audit.py`) | 37 jobs | **37/37** (includes 51/51 v25.9 note-engine subtests) |
| Browser at 1440/1024/390 | 3 | PASS. A separate real-server check confirmed the Decision Center shows the canonical COD delay, with no console errors and no overflow |
| Engine hashes against in-tree baselines (7 files) | — | PASS: frozen engines unchanged; new engines pinned |

**Unexplained failures: zero.** The single expected failure is explained above and in `ISSUES`.

## 3. Coverage of the 20 required test areas

| # | Requirement | Test(s) | Independent of production formulas? |
|---|---|---|---|
| 1 | Full funding halt, capped sponsor | `oracle T01`; adversarial A02 | Yes: cash roll, conservation and claim checks written from first principles |
| 2 | Partial interest payment | `oracle T02` (hand case: 49 full payments, then a partial of 0.08258) | Yes: closed-form |
| 3 | Unpaid interest across periods | `oracle T02` (month 100 = 99·i − 15.045, no compounding) | Yes |
| 4 | PIK only when enabled | `oracle T03` (refused without instrument term; compounds when permitted) | Yes |
| 5 | Senior/mezz priority | `oracle T05` (default and alternative order; invalid order rejected) | Yes |
| 6 | Restricted reserves and releases | `oracle T06` (none / dsra_only / all; DSRA draw after refinancing) | Yes |
| 7 | Maturity without refinancing | `oracle T07` | Yes |
| 8 | Refinance with insufficient proceeds | `oracle T08` | Yes |
| 9 | Terminal liquidation shortfall | `oracle T09` (recovery = 19.6 proceeds + 10 reserve; interest first) | Yes |
| 10 | Zero or negative CFADS | `oracle T10` (operating losses become payables, never vanish) | Yes |
| 11 | Parallel delays | `schedule T11` | Yes: worked examples |
| 12 | Sequential delays | `schedule T12` (accumulation, float, completed, cycle, conflict) | Yes |
| 13 | Same result across interfaces | `schedule T13` (6 entry points: same COD, version and NPV to 1e-9) | Yes |
| 14 | Bond dates, day count, stub | `core T14`: own date generator, own 30/360, own Newton yield | Yes |
| 15 | Amortisation start from scenario events | `core T15` (exact-15-day edge, later-event rule, none before maturity) | Yes |
| 16 | Principal, OID, fees, carrying amount, balloon | `core T16` (maturity table exact; net-proceeds variance stays OPEN; carrying roll-forward) | Yes |
| 17 | Unsupported assumptions never become verified | `core T17` (local) + `auth T17` (approver, hashed executed document and non-filing source all required) | Yes |
| 18 | Cross-tenant denial on new endpoints | `auth T18` (8 transaction endpoints plus schedule/impact; viewer read-only) | Yes |
| 19 | Historical outputs immutable after a new engine | `core T19` (legacy fixtures byte-identical; stored run unchanged; missing `engineVersion` means legacy; unknown version rejected) | Yes |
| 20 | G4/G5 preserved | `core T20`, `auth T17`, inherited notes and red-team G02 | Yes |

## 4. Numerical tolerances

| Quantity | Tolerance | Worst observed |
|---|---|---|
| Monthly identities (cash, interest, principal, reserve, payables) | 1e-6 $M (oracle) | ≤1.1e-13 |
| Legacy parity in unconstrained cases | 1e-9 per field | 3.6e-15 |
| Reference parity (Python port) | 1e-6 per field | 1.4e-12 |
| Note schedule vs independent oracle | 1e-9 $M per period | exact to 9 places |
| Effective yield vs independent Newton solve | 1e-6 percentage points | passes |
| Interface parity (NPV) | 1e-9 $M | passes |

## 5. Mutation testing (`tests/v271/mutation_v271.py`): 17/18 detected

| Mutation | Detected by |
|---|---|
| W01 cash may go negative; W02 arrears from all cash; W03 unpaid interest dropped; W04 PIK without permission; W05 priority ignored; W06 dsra_only uses base reserve; W07 exit pays principal before interest; W09 default interest on full principal; W10 matured principal not past due | waterfall oracle |
| S01 drivers summed; S02 chain not accumulated; S03 float ignored; S04 path estimate added | schedule parity |
| N01 actual/360 instead of 30/360; N02 amortisation on outstanding balance; N03 OID ignored; T01 trigger 14 days | Core Scientific suite |
| **W08** arrears no longer lock distributions | **Not detected. Equivalent mutant:** arrears can only exist after a default, and the sticky `defaulted` flag already locks distributions. The arrears lock is defence in depth. |

For comparison, the v26.8 review found that the v26 API suites detected 0/18 legacy-engine mutations. The v27.1 suites cover the new financial code directly.

## 6. Security checks touching the new code

- **Tenancy and roles.** The new endpoints sit under `/api/projects/{pid}/…`, so the v27 tenant middleware applies. Cross-tenant requests return 403, unauthenticated requests 401, and viewers are read-only.
- **Promotion guard.** It cannot be satisfied in local-only mode, by an analyst, without an uploaded and hashed executed document, or with a filing or press-release source.
- **Reclassification history.** Every reclassification is a new version; earlier versions are retained.
- **Read-only previews.** Impact and preview endpoints persist nothing (asserted).

## 7. Not done, or not verifiable here

- **Indenture review.** No executed indenture, leases or DSRA terms were available. Day count, accrual start and DSRA mechanics are assumptions.
- **Notes-specific filing figures.** The Q2 10-Q excerpt read did not give a notes-specific carrying amount or accrued interest. The Q3 10-Q is due after 5 Nov 2026.
- **External testing.** No penetration test, load test or hosted deployment.
- **Live services.** No live model or provider calls were made.
- **Human review.** No human model review (G5) and no executed-document reconciliation (G4).
