"""v30.3.3 independent proof of the v30.3.2 note-phasing layer. Run isolated (own data dir, no auth)."""
import copy
import os
import tempfile
import unittest

TEMP = tempfile.TemporaryDirectory(prefix='pp_note_phase333_')
os.environ['POWERPATH_DATA_DIR'] = TEMP.name
os.environ.pop('POWERPATH_V27_AUTH_MODE', None)
from server.app import calculate
from server import transaction271 as n
from server.note_phasing import NotePhasingIn, phased_note_preview, build_phased_config

INPUTS = {x[0]: {'value': copy.deepcopy(x[1]), 'classification': x[3]} for x in n.INPUTS}
MW = INPUTS['site_leased_mw']['value']
KEYS = ('scheduled_service_before_any_rentM', 'simple_pre_rent_reserve_gapM',
        'peak_cumulative_cash_funding_need_ex_balloonM', 'first_rent_month', 'full_rent_month')


def run(p):
    return phased_note_preview(INPUTS, NotePhasingIn(**p), calculate)


def denton(first, full):
    return {'scenario': 'base', 'site_schedules': [{'site': 'Denton', 'tranches': [
        {'mw': 100, 'power_month': first}, {'mw': 160, 'power_month': full}]}]}


class NotePhasingProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = run({'scenario': 'base'})
        cls.start = cls.base['first_rent_month']

    def assertSameKeys(self, a, b):
        for k in KEYS:
            self.assertAlmostEqual(a[k], b[k], places=9, msg=k)

    def test_explicit_restatement_of_single_date_is_identity(self):
        same = {'scenario': 'base', 'site_schedules': [{'site': s, 'tranches': [{'mw': float(v), 'power_month': self.start,
                'construction_ready_month': 2, 'lease_eligible_month': self.start}]} for s, v in MW.items()]}
        self.assertSameKeys(self.base, run(same))

    def test_same_date_split_is_neutral(self):
        self.assertSameKeys(self.base, run(denton(self.start, self.start)))

    def test_delay_never_lowers_pre_rent_service_or_peak_need(self):
        prev = None
        for pm in range(10, self.start + 13, 4):
            x = run(denton(pm, max(pm, 40)))
            if prev:
                self.assertGreaterEqual(x['scheduled_service_before_any_rentM'], prev['scheduled_service_before_any_rentM'] - 1e-9)
                self.assertGreaterEqual(x['peak_cumulative_cash_funding_need_ex_balloonM'],
                                        prev['peak_cumulative_cash_funding_need_ex_balloonM'] - 1e-9)
            prev = x

    def test_simple_gap_is_lower_bound_and_can_hide_a_large_need(self):
        x = run(denton(10, 40))
        self.assertEqual(x['simple_pre_rent_reserve_gapM'], 0)
        self.assertGreater(x['peak_cumulative_cash_funding_need_ex_balloonM'], x['dsra_balanceM'])
        self.assertEqual(x['headline_funding_metric'], 'peak_funding_gap_after_static_dsra_ex_balloonM')
        for p in (denton(20, 40), denton(30, 50), {'scenario': 'base'}):
            y = run(p)
            self.assertGreaterEqual(y['peak_cumulative_cash_funding_need_ex_balloonM'], y['scheduled_service_before_any_rentM'] - 1e-9)

    def test_period_cfads_reconciles_to_monthly_engine(self):
        p = denton(20, 40)
        cfg, _ = build_phased_config(INPUTS, NotePhasingIn(**p))
        rows = calculate('underwrite', cfg)['rows']
        x = run(p)
        last = x['periods'][-1]['through_month']
        self.assertAlmostEqual(sum(r['cfads'] for r in rows if 1 <= r['month'] <= last), sum(q['cfadsM'] for q in x['periods']), places=6)

    def test_reported_rent_start_matches_engine(self):
        for ready in (1, 2, 5):
            p = {'scenario': 'base', 'site_schedules': [{'site': 'Austin', 'tranches': [
                {'mw': float(MW['Austin']), 'power_month': 1, 'construction_ready_month': ready, 'lease_eligible_month': 1}]}]}
            cfg, phases = build_phased_config(INPUTS, NotePhasingIn(**p))
            rows = calculate('underwrite', {**cfg, 'buildings': [b for b in cfg['buildings'] if b['name'].startswith('Austin')]})['rows']
            engine_first = next(r['month'] for r in rows if r['leaseRevenue'] > 1e-9)
            reported = next(q['modeled_rent_start_month'] for q in phases if q['site'] == 'Austin')
            self.assertEqual(reported, engine_first, f'construction_ready_month={ready}')

    def test_power_alone_never_moves_note_calendar(self):
        early = run({'scenario': 'base', 'site_schedules': [{'site': s, 'tranches': [{'mw': float(v), 'power_month': 3}]} for s, v in MW.items()]})
        self.assertEqual(early['first_installment_date'], self.base['first_installment_date'])
        self.assertEqual([p['scheduled_debt_serviceM'] for p in early['periods']], [p['scheduled_debt_serviceM'] for p in self.base['periods']])

    def test_every_scenario_reproduces_legacy_without_overrides(self):
        for sc in n.SCENARIOS:
            y = run({'scenario': sc})
            self.assertAlmostEqual(y['simple_pre_rent_reserve_gapM'], y['legacy_single_date_reference']['simple_pre_rent_reserve_gapM'], places=9)


if __name__ == '__main__':
    unittest.main()
