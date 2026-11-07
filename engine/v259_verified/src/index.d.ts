// Type declarations for @powerpath/engine. Generated from runtime shapes, then annotated.
// Units: $M for money, MW for capacity, months for time, % as 0-100.

export type CapacityBasis = 'IT' | 'gross';
export type PowerResponsibility = 'landlord' | 'tenant_direct' | 'reimbursed';

export interface Building {
  name: string;
  itMW: number;
  constructionStart: number;
  constructionMonths: number;
  powerMonth: number;
  leaseMonth: number;
  leaseTermMonths?: number;
  rentEscalatorPct?: number;
  rentInputMode?: 'starting' | 'total' | 'schedule';
  rentPerKwMonth?: number;
  contractedRentM?: number;
  annualRentM?: number[] | string;
  leaseSourceRef?: string;
  capacityBasis?: CapacityBasis;
  tenantCapexPct?: number;
  tenantRentCreditPct?: number;
  tenantCreditMonths?: number;
  powerResponsibility?: PowerResponsibility;
  powerPassThroughPct?: number;
}

export interface PowerTranche {
  month: number;
  mw: number;
  /** Omit for shared supply. */
  building?: string;
  basis?: CapacityBasis;
}

export type EvidenceLabel =
  | 'Executed'
  | 'Public approximate'
  | 'Management expectation'
  | 'Assumption'
  | 'Unknown';

export interface EvidenceEntry {
  label: EvidenceLabel;
  factId?: string;
  source?: string;
}

export type FacilityAmortization =
  | { type: 'none' }
  | { type: 'unknown' }
  | { type: 'pctOriginalPerYear'; annualPct: number }
  | { type: 'explicit'; amountsM: number[] };

export type FacilityAmortStart =
  | { type: 'fixedMonth'; month?: number; date?: string }
  | { type: 'afterFirstRent'; offsetMonths: number }
  | { type: 'afterFinalCommencement'; offsetMonths: number };

export type FacilityDsra =
  | { type: 'none' }
  | { type: 'fixed'; amountM: number }
  | { type: 'nextPeriod' }
  | { type: 'constructionThenNextPeriod'; constructionAmountM: number };

/** v25.9 fixed-rate note facility (FACILITY_SPEC_v259 §1). Integer month fields take precedence over dates. */
export interface Facility {
  id: string;
  name: string;
  type: 'fixed_note';
  faceM: number;
  couponPct: number;
  issuePricePct: number;
  feePct?: number;
  issueMonth?: number;
  issueDate?: string;
  firstPaymentMonth?: number;
  firstPaymentDate?: string;
  maturityMonth?: number;
  maturityDate?: string;
  /** Collateral scope; names must exist in buildings. */
  buildings: string[];
  /** Lower pays first; ties keep input order. Default 1. */
  priority?: number;
  amortization: FacilityAmortization;
  /** May be omitted only with amortization 'none' or 'unknown'. */
  amortStart?: FacilityAmortStart;
  dsra?: FacilityDsra;
  /** Default 1.20. */
  lockupDscr?: number;
  evidence?: Record<string, EvidenceEntry>;
  /** Template flag; the engine refuses a facility marked false. */
  modelable?: boolean;
  modelableReason?: string;
}

export interface FacilityScheduleRow {
  month: number;
  opening: number;
  accrual: number;
  interestPaid: number;
  principalPaid: number;
  closing: number;
  accruedEnd: number;
  dsraRequired: number;
  dsraBalance: number;
  cfadsShare: number;
  /** Extension: scheduled installment (at maturity, the installment excluded from the balloon). */
  scheduledPrincipal: number;
  /** Extension: deposits +, releases -, draws -. */
  dsraMovement: number;
  /** Extension: DSRA drawn before sponsor support this month. */
  dsraDraw: number;
}

export interface FacilityDscrTest {
  month: number;
  dscr: number | null;
}

export interface FacilitySummary {
  id: string;
  name: string;
  faceM: number;
  couponPct: number;
  issuePricePct: number;
  proceedsM: number;
  oidM: number;
  feesM: number;
  issueMonth: number;
  firstPaymentMonth: number;
  maturityMonth: number;
  amortStartMonth: number | null;
  amortStartBasis: 'fixedMonth' | 'afterFirstRent' | 'afterFinalCommencement' | 'none';
  /** Amendment 1 AM1: construction-end event month E (no look-ahead), or null if it never occurred. */
  constructionEndMonth: number | null;
  /** Amendment 1 AM3: first month every collateral building has gross rent > 0, or null. */
  constructionLockupEndMonth: number | null;
  totalInterestPaidM: number;
  totalPrincipalPaidM: number;
  balloonM: number;
  endingBalanceM: number;
  unpaidAtExitM: number;
  minDscr: number | null;
  dscrTests: FacilityDscrTest[];
  lockupMonths: number[];
  dsraDeficiencyMonths: number[];
  schedule: FacilityScheduleRow[];
  evidence: Record<string, EvidenceEntry>;
  warnings: string[];
}

export interface Assumptions {
  months: number;
  calendarStartYear: number;
  calendarStartMonth: number;
  discount: number;
  rate: number;
  ltc: number;
  debtFee: number;
  termMonths: number;
  amortMonths: number;
  dscrCovenant: number;
  minLiquidity: number;
  initialCash: number;
  reserveTargetM: number;
  rentPerKwMonth: number;
  pue: number;
  powerCostMWh: number;
  powerResponsibility: PowerResponsibility;
  powerPassThroughPct: number;
  powerReimbursementLagDays: number;
  otherOpexPct: number;
  fixedOpexM: number;
  constructionCostMW: number;
  delayMonths: number;
  overrunPct: number;
  rateShockPct: number;
  energyShockPct: number;
  refinanceLtvPct: number;
  refinanceValueM: number;
  refinanceRatePct: number;
  refinanceFeePct: number;
  exitValueM: number;
  exitCostPct: number;
  loanMaturityMode: 'refinance' | 'equity' | 'default';
  distributionPolicy: 'excess' | string;
  capacityBasis: CapacityBasis;
  tenantCapexPct: number;
  tenantFundingLagMonths: number;
  tenantRentCreditPct: number;
  tenantCreditMonths: number;
  debtYieldMinPct: number;
  refinanceDscrMin: number;
  refinanceAmortMonths: number;
  mezzLtcPct: number;
  mezzRatePct: number;
  mezzFeePct: number;
  cashSweepPct: number;
  rateShockAllFacilities: boolean;
  exitTenantReceivableRecoveryPct: number;
  exitWorkingCapitalRecoveryPct: number;
  distributionDscrMin: number;
  lockDistributionsOnBreach: boolean;
  dsraMonths: number;
  dsraReleaseAtExit: boolean;
  sponsorCommitmentM: number | null;
  cashTaxRatePct: number;
  maintenanceCapexMWYearM: number;
  workingCapitalDays: number;
  fundingDefaultPolicy: 'halt' | 'continue';
  refinanceTenorPolicy: 'fixed' | 'leaseTail';
  leaseTailBufferMonths: number;
  minRefinanceAmortMonths: number;
  leaseExpiryPolicy: 'vacate' | 'renew';
  renewalProbabilityPct: number;
  renewalRentPct: number;
  renewalTermMonths: number;
  exitValuePolicy: 'fixed' | 'contracted';
  vacantValuePct: number;
  buildings: Building[];
  powerTranches: PowerTranche[];
  trancheCapacityBasis?: CapacityBasis;
  strictDebtPolicyValidation?: boolean;
  /** v25.9 debt facilities. Absent or empty: outputs identical to v25.8.4-ca.1. Requires ltc = 0 and mezzLtcPct = 0. */
  facilities?: Facility[];
}

export type AssumptionsInput = Partial<Assumptions>;

export interface LeaseAudit {
  building: string;
  mode: 'starting' | 'total' | 'schedule';
  contractedRentM: number | null;
  modeledContractRentM: number;
  varianceM: number | null;
  variancePct: number | null;
  startingRentPerKwMonth: number | null;
  sourceRef: string;
  reconciled: boolean;
  hasDocumentReference: boolean;
  status: string;
}

export interface RefinanceSizing {
  ltvLimit: number;
  dscrLimit: number;
  yieldLimit: number;
  selected: number;
  forward12CfadsM: number;
  forward12NoiM: number;
  amortMonths: number;
  remainingLeaseTermMonths: number;
  binding: 'LTV' | 'DSCR' | 'debt yield';
  failed?: boolean;
}

export interface MonthRow {
  month: number;
  onlineMW: number;
  availableMW: number;
  grossRevenue: number;
  rentCredits: number;
  leaseRevenue: number;
  revenue: number;
  grossEnergy: number;
  energy: number;
  powerReimbursement: number;
  tenantDirectPower: number;
  netEnergyCost: number;
  opex: number;
  ebitda: number;
  cashTaxes: number;
  maintenanceCapex: number;
  workingCapitalBalance: number;
  workingCapitalChange: number;
  cfads: number;
  capex: number;
  tenantFundedCapex: number;
  tenantCashReceipt: number;
  tenantFundingReceivable: number;
  draw: number;
  mezzDraw: number;
  fee: number;
  refinanceFee: number;
  interest: number;
  capitalizedInterest: number;
  cashInterest: number;
  principal: number;
  mezzPrincipal: number;
  debt: number;
  mezzDebt: number;
  debtService: number;
  scheduledDebtService: number;
  dscr: number | null;
  breach: boolean;
  liquidityBreach: boolean;
  openingCash: number;
  loanSources: number;
  uses: number;
  operatingCash: number;
  preFundingCash: number;
  sponsorContribution: number;
  equityContribution: number;
  distribution: number;
  netEquity: number;
  cash: number;
  reserve: number;
  reserveMovement: number;
  refinanceProceeds: number;
  sweepPrincipal: number;
  maturityShortfall: number;
  terminalProceeds: number;
  exitCollections: number;
  exitTenantReceivableCollection: number;
  exitWorkingCapitalCollection: number;
  exitDebtPayoff: number;
  unpaidDebtAtExitM: number;
  unfundedGapM: number;
  sourcesUsesResidual: number;
  debtResidual: number;
  mezzResidual: number;
  reserveResidual: number;
  reserveDeficiency: number;
  restrictedTarget: number;
  dsraTarget: number;
  openingSeniorDebt: number;
  openingMezzDebt: number;
  openingReserve: number;
  forward12CfadsM: number | null;
  forward12NoiM: number | null;
  // v25.9 facility fields: emitted only when facilities are modeled (aggregated over facilities).
  notesProceeds?: number;
  notesFees?: number;
  facilityInterestAccrued?: number;
  facilityInterestPaid?: number;
  facilityPrincipalPaid?: number;
  facilityDebtService?: number;
  facilityBalance?: number;
  facilityAccruedInterest?: number;
  facilityDsra?: number;
  facilityDsraMovement?: number;
  facilityDsraDraw?: number;
  facilityLockup?: boolean;
  /** Amendment 1 AM3: any facility with balance > 0 whose collateral has not all paid rent yet. */
  facilityConstructionLockup?: boolean;
}

export interface Summary {
  financeabilityStatus: string;
  npvM: number;
  leveredIRR: number | null;
  equityMultiple: number | null;
  peakDebtM: number;
  interestM: number;
  feesM: number;
  principalM: number;
  debtDrawsM: number;
  mezzDrawsM: number;
  equityInvestedM: number;
  equityDistributionsM: number;
  minDSCR: number | null;
  minCashM: number;
  breachMonths: number[];
  liquidityBreachMonths: number[];
  maturityMonth: number | null;
  refinanced: boolean;
  refinanceSizing: RefinanceSizing | null;
  defaulted: boolean;
  fundingDefault: boolean;
  unpaidDebtAtExitM: number;
  endingDebtM: number;
  endingReserveM: number;
  sweepPrincipalM: number;
  sourcesUsesMaxResidual: number;
  debtMaxResidual: number;
  reserveMaxResidual: number;
  dsraDeficiencyMonths: number[];
  sponsorCommitmentM: number | null;
  sponsorRemainingM: number | null;
  unfundedMonths: number[];
  operatingMWh: number;
  grossPowerCostM: number;
  landlordPowerExpenseM: number;
  tenantDirectPowerM: number;
  powerReimbursementM: number;
  netLandlordPowerCostM: number;
  tenantFundingM: number;
  rentCreditsM: number;
  cumulativeCfadsM: number;
  leaseAudits: LeaseAudit[];
  screeningReadiness: string;
  creditWarnings: string[];
  lastLeaseEndMonth: number | null;
  leaseReconciliationBlocked: boolean;
  financialValidationStatus: string;
  fundingDefaultPolicy: string;
  refinanceTenorPolicy: string;
  leaseTailTenorWarning: boolean;
  leaseExpiryPolicy: string;
  exitValuePolicy: string;
  refinanceAmortMonthsUsed: number | null;
  exitValueShare: number;
  constructionHaltMonth: number | null;
  abandonedBuildings: string[];
  peakUnfundedGapM: number;
  residualCashRetainedAtExitM: number;
  uncollectedTenantReceivableAtExitM: number;
  workingCapitalBalanceAtExitM: number;
  exitCollectionsM: number;
  rateShockAllFacilities: boolean;
  // v25.9: emitted only when facilities are modeled.
  facilities?: FacilitySummary[];
  /** Months of facility DSCR tests below the facility lock-up threshold (present only when facilities are modeled). */
  facilityDscrBreachMonths?: number[];
  facilityPaymentShortfallMonths?: number[];
}

export interface EvaluateResult {
  assumptions: Assumptions;
  rows: MonthRow[];
  summary: Summary;
  /** Equity flows, index 0 = opening sponsor cash (negative). */
  flows: number[];
}

export function defaults(): Assumptions;
/** Deterministic monthly evaluation. Throws on invalid inputs. */
export function evaluate(input?: AssumptionsInput): EvaluateResult;
/** Annualized IRR of monthly flows, or null if undefined. */
export function irr(flows: number[]): number | null;
export function rentAudit(
  buildings: Building[],
  globalRent: number,
  pue: number,
  globalBasis: CapacityBasis,
): LeaseAudit[];
export const ENGINE_VERSION: string;
export const notes: {
  schedule(terms: Record<string, unknown>): Record<string, unknown>;
  stepMonths(iso: string, n: number): string;
  days30360(a: string, b: string): number;
};

/** Risk assurance gates (see RISK_POLICY.md). Valuation/certification stay BLOCKED without executed evidence and a signed human review bound to engineVersion + inputHash. */
export const assurance: {
  assess(
    result: EvaluateResult,
    evidence?: Record<string, unknown>,
    engineVersion?: string,
  ): {
    engineVersion: string;
    inputHash: string;
    gates: Record<'G0' | 'G1' | 'G2' | 'G3' | 'G4' | 'G5', { name: string; status: string; detail: string }>;
    uses: { screening: string; transactionValuation: string; lenderCertification: string };
    blockingReasons: string[];
    nonExecutedMaterialTerms: string[];
    display: { valuationLabel: string; showCreditWarnings: boolean; creditWarnings: string[] };
  };
  stableHash(obj: unknown): string;
  sha256hex(s: string): string;
  LABELS: string[];
  MATERIAL_TERMS: string[];
};
