# DELAY_CONVENTION — PowerPath schedule method `schedule-27.1.0`

**Status:** the single delay convention used by every PowerPath interface from v27.1. It is a screening convention approved for implementation by the AI model reviewer, and it is **provisional until a qualified human (COO/CFO, ideally with a scheduling engineer) approves it**. It is not a full CPM schedule, and no output is a utility-confirmed date.

**Implementation:** `server/schedule27.py` (`compute`, `apply_to_config`, `financial_impact`). **Tests:** `tests/v271/test_schedule_parity.py`.

## 1. Rule

Neither "always add" nor "always take the maximum" is correct. The structure of the work decides.

1. **Activities.** A path's delivery milestones are typed as interconnection, utility energisation, permitting, construction, equipment procurement, tenant readiness, or financing/notice-to-proceed. An open permit not linked to any milestone is an independent activity.
2. **Dependent work accumulates.** If B cannot start until A finishes, A's slip moves B:
   `shift(B) = own_delay(B) + shift(A)`.
3. **Independent work runs in parallel.** COD moves by the longest critical driver, not the sum:
   `COD delay = max(path-level estimate, max over activities of max(0, shift − float), max unlinked open-permit delay)`.
4. **Float absorbs delay.** `float_months` is the activity's total float to COD. The default is 0, meaning the activity is assumed critical unless the analyst records float.
5. **Finished work contributes nothing.** A completed activity's delay is already in the baseline.
6. **No double counting:**
   - The path-level estimate is an overall analyst figure that may overlap the milestone detail, so it is **never added**.
   - A permit linked to a milestone is evidence for that milestone, not a second driver. If their delays disagree, the milestone governs and the pair is flagged `CONFLICTING_EVIDENCE`.
7. **Versioned.** `schedule_version` is a hash of the method and every input that matters. Every view, sensitivity and preview reports it, and identical inputs always give the same version and the same answer.

## 2. Mapping to the financial model

There is one mapping, `apply_to_config`:

- the COD delay is added to `delayMonths`, which shifts energisation and lease commencement;
- construction spend timing does not change, so the delay shows up as carry cost and postponed revenue;
- the path's capex and energy uplifts are applied identically with and without delay, so the comparison isolates the delay.

The read-only `/paths/{id}/schedule-impact` report contains:

| Output | Field |
|---|---|
| Baseline and revised COD | `schedule.baseline_cod_month`, `schedule.revised_cod_month` |
| Critical path and drivers | `schedule.critical_path`, `schedule.critical_drivers` |
| Milestone changes | `schedule.activities[]`: own, inherited, shift, float, COD impact, revised month |
| Financing carry cost | `deltas.carry_cost_interest_before_revenueM` (cash plus capitalised interest before first rent); `deltas.carry_cost_interest_incurredM` (total) |
| Revenue commencement | `deltas.revenue_commencement_months` |
| DSCR and liquidity | `deltas.minDSCR`, `deltas.breach_months`, `deltas.min_cashM`, `revised.liquidity_breach_months` |
| Equity effects | `deltas.npvM`, `deltas.leveredIRR`, `deltas.sponsor_equityM` |
| Evidence quality and open items | `schedule.evidence_quality`, `schedule.evidence_conflicts`, `schedule.unresolved_dependencies` |

## 3. Worked examples

All examples are tested, and all delays are in months.

| # | Activities | Rule applied | COD delay |
|---|---|---|---|
| A | Permitting slips 6; energisation slips 9; independent | parallel → max | **9** (not 15) |
| B | Permit slips 6; construction (0 own) depends on permit; energisation 9 | 6 inherited by construction; energisation still longest | **9** |
| C | As B, but construction itself also slips 4 | 6 + 4 = 10 along the chain, more than 9 | **10**, critical path = permit → construction |
| D | As C, but construction has 3 months float | 10 − 3 = 7 | **7** |
| E | Permit already completed; construction slips 2 | completed contributes 0 | **2** |
| F | Path estimate 9; milestone chain 5 + 4 = 9 | estimate overlaps the chain, never added | **9** |
| G | Milestone 4; an unrelated open permit 7 | unlinked permit is a parallel driver | **7** |
| H (demo grid path) | Path estimate 9; study milestone 5 (linked to the 7-month study permit) → ESA milestone 4 | chain 9; linked permit is not a driver | **9**. v27.0's v26.2 route said 16 |
| I (parity project) | Permit 6 → construction 4 (chain 10); energisation 7; unlinked easement 8; path 3; tenant fit-out 1 after construction with float 2 | max(3, 10, 7, 9 → 11 − 2 = 9, 8) | **10** from all six entry points, same NPV |

## 4. Parity guarantee

`tests/v271/test_schedule_parity.py::T13` builds one project and checks that six entry points return the same COD delay (10), the same `schedule_version` and the same NPV (to 1e-9):

- `/schedule`
- `/schedule-impact`
- `/sensitivity` (v26.2 route)
- `/sensitivity-v263`
- the change-proposal preview, used by agent-generated proposals
- runs of both created scenarios

## 5. What this convention does not do

- **Activity durations and dates.** It does not model durations, resource limits or calendar dates beyond `planned_month`. Delays are increments relative to an analyst baseline.
- **Float.** Float is analyst-entered, not computed from a network.
- **Evidence.** Nothing here is evidence that a utility, regulator or contractor will meet or miss a date. All activity data is analyst-entered.
- **Gates.** G4 and G5 are unaffected.
