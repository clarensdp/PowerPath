// Compile-time contract check: fails `npm run typecheck` if the declared API drifts.
import {
  evaluate,
  defaults,
  type AssumptionsInput,
  type EvaluateResult,
  type Facility,
  type FacilitySummary,
} from '../src/index';
const input: AssumptionsInput = {
  powerResponsibility: 'reimbursed',
  powerPassThroughPct: 100,
  refinanceTenorPolicy: 'leaseTail',
  buildings: [
    {
      name: 'A',
      itMW: 50,
      constructionStart: 1,
      constructionMonths: 12,
      powerMonth: 13,
      leaseMonth: 13,
      powerResponsibility: 'tenant_direct',
    },
  ],
};
const r: EvaluateResult = evaluate(input);
const npv: number = r.summary.npvM;
const dscr: number | null = r.rows[0].dscr;
const months: number = defaults().months;
// @ts-expect-error invalid enum value must not type-check
evaluate({ powerResponsibility: 'utility' });
const note: Facility = {
  id: 'n1',
  name: 'Synthetic note',
  type: 'fixed_note',
  faceM: 100,
  couponPct: 8,
  issuePricePct: 99,
  issueMonth: 2,
  firstPaymentMonth: 8,
  maturityDate: '2030-08-15',
  buildings: ['A'],
  amortization: { type: 'pctOriginalPerYear', annualPct: 5 },
  amortStart: { type: 'afterFinalCommencement', offsetMonths: 1 },
  dsra: { type: 'constructionThenNextPeriod', constructionAmountM: 5 },
  evidence: { couponPct: { label: 'Assumption' } },
};
const withNotes: EvaluateResult = evaluate({ ...input, ltc: 0, facilities: [note] });
const fs: FacilitySummary[] | undefined = withNotes.summary.facilities;
const ds: number | undefined = withNotes.rows[0].facilityDebtService;
// @ts-expect-error unknown DSRA type must not type-check
const badDsra: Facility = { ...note, dsra: { type: 'monthsOfDebtService' } };
void npv;
void dscr;
void months;
void fs;
void ds;
void badDsra;
