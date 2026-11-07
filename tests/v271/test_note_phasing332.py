"""Focused read-only v30.3.2 note-phasing proof. Run isolated from required-auth tests."""
import copy
import os
import tempfile
import unittest
from pathlib import Path

# Import in a private data root: test must never write the bundled demonstration DB.
TEMP = tempfile.TemporaryDirectory(prefix='pp_note_phase_')
os.environ['POWERPATH_DATA_DIR'] = TEMP.name
os.environ.pop('POWERPATH_V27_AUTH_MODE', None)
from fastapi.testclient import TestClient
from server.app import app, calculate
from server import transaction271 as n
from server.note_phasing import NotePhasingIn, phased_note_preview, build_phased_config

INPUTS = {x[0]: {'value':copy.deepcopy(x[1]), 'classification':x[3]} for x in n.INPUTS}
BASE = {'scenario':'base'}
SPLIT = {'scenario':'base','site_schedules':[
    {'site':'Denton','tranches':[{'mw':100,'power_month':20}, {'mw':160,'power_month':40}]}
]}


def run(payload):
    return phased_note_preview(INPUTS, NotePhasingIn(**payload), calculate)


class PhasedNoteProof(unittest.TestCase):
    def test_no_override_reproduces_existing_reserve_gap_and_note_dates(self):
        x = run(BASE)
        self.assertAlmostEqual(x['legacy_single_date_reference']['simple_pre_rent_reserve_gapM'],428.84375,places=5)
        self.assertAlmostEqual(x['simple_pre_rent_reserve_gapM'],428.84375,places=5)
        self.assertEqual(x['delta_vs_legacy_simple_gapM'],0)
        self.assertEqual(x['first_installment_date'],'2029-11-15')
        self.assertEqual(len(x['periods']),10)

    def test_two_tranches_change_gap_without_changing_note_trigger(self):
        x = run(SPLIT)
        self.assertEqual(x['first_rent_month'],20)
        self.assertEqual(x['full_rent_month'],40)
        self.assertEqual(x['first_installment_date'],'2029-11-15')
        self.assertLess(x['simple_pre_rent_reserve_gapM'],428.84375)
        self.assertNotAlmostEqual(x['peak_funding_gap_after_static_dsra_ex_balloonM'],x['simple_pre_rent_reserve_gapM'])
        self.assertEqual(x['g4'],'BLOCKED')
        self.assertEqual(x['g5'],'BLOCKED')

    def test_phasing_advances_rent_but_never_changes_note_principal_calendar(self):
        a,b=run(BASE),run(SPLIT)
        self.assertEqual([p['scheduled_debt_serviceM'] for p in a['periods']],
                         [p['scheduled_debt_serviceM'] for p in b['periods']])
        self.assertEqual([p['balloonM'] for p in a['periods']], [p['balloonM'] for p in b['periods']])
        self.assertNotEqual([p['lease_revenueM'] for p in a['periods']],
                            [p['lease_revenueM'] for p in b['periods']])

    def test_manual_trigger_requires_two_explicit_dates(self):
        with self.assertRaises(ValueError):
            NotePhasingIn(**{**BASE,'trigger_rent_commencement':'2027-06-30'})
        with self.assertRaises(ValueError):
            NotePhasingIn(**{**BASE,'note_trigger':'explicit_hypothetical',
                               'trigger_rent_commencement':'2028-01-01'})
        payload={**SPLIT,'note_trigger':'explicit_hypothetical',
                 'trigger_rent_commencement':'2028-01-31','trigger_revenue_credit_abatement':'2028-04-30'}
        y=run(payload)
        self.assertEqual(y['first_installment_date'],'2028-05-15')
        self.assertNotEqual(y['periods'][5]['scheduled_debt_serviceM'],run(SPLIT)['periods'][5]['scheduled_debt_serviceM'])

    def test_site_mw_must_reconcile_and_duplicate_or_unknown_fails(self):
        wrong=copy.deepcopy(SPLIT)
        wrong['site_schedules'][0]['tranches'][1]['mw']=159
        with self.assertRaisesRegex(ValueError,'total'):
            run(wrong)
        unknown=copy.deepcopy(SPLIT)
        unknown['site_schedules'][0]['site']='Synthetic Site G'
        with self.assertRaisesRegex(ValueError,'Unknown site'):
            run(unknown)
        dup=copy.deepcopy(SPLIT)
        dup['site_schedules'].append(copy.deepcopy(dup['site_schedules'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            run(dup)

    def test_construction_and_lease_dates_bind(self):
        data=NotePhasingIn(**{'scenario':'base', 'site_schedules':[{'site':'Denton','tranches':[
            {'mw':260,'power_month':8,'construction_ready_month':26,'lease_eligible_month':31}]}]})
        _, phases=build_phased_config(INPUTS,data)
        self.assertEqual(phases[0]['modeled_rent_start_month'],31)
        self.assertEqual(phases[0]['power_month'],8)

    def test_cannot_mix_global_shift_and_phase_dates(self):
        with self.assertRaisesRegex(ValueError,'rent_shift_months'):
            NotePhasingIn(**{**SPLIT,'rent_shift_months':2})

    def test_no_trigger_case_no_amortization_before_maturity(self):
        x=run({'scenario':'no_trigger'})
        self.assertIsNone(x['first_installment_date'])
        self.assertTrue(all(p['balloonM']==0 for p in x['periods'][:-1]))
        self.assertEqual(x['balloon_at_maturityM'],3300)

    def test_periods_reconcile_to_engine_derived_monthly_flow(self):
        x=run(SPLIT)
        cfg,_=build_phased_config(INPUTS,NotePhasingIn(**SPLIT))
        row=calculate('underwrite',cfg)['rows']
        self.assertAlmostEqual(sum(p['cfadsM'] for p in x['periods']),sum(r['cfads'] for r in row),places=7)
        self.assertAlmostEqual(sum(p['lease_revenueM'] for p in x['periods']),sum(r['leaseRevenue'] for r in row),places=7)
        self.assertAlmostEqual(x['periods'][-1]['cumulative_cash_before_reservesM'],
            sum(p['cfadsM']-p['scheduled_debt_serviceM'] for p in x['periods']),places=7)

    def test_input_catalog_remains_identical(self):
        old=copy.deepcopy(INPUTS)
        run(SPLIT)
        self.assertEqual(INPUTS,old)

    def test_api_is_read_only_and_validation_rejects_bad_site(self):
        client=TestClient(app,base_url='http://127.0.0.1')
        created=client.post('/api/projects',json={'name':'Phased Notes Audit'}); self.assertEqual(created.status_code,201,created.text)
        pid=created.json()['id']; base=f'/api/projects/{pid}/transactions/core-scientific-2026'
        self.assertEqual(client.post(base+'/model').status_code,201)
        before=client.get(base+'/inputs').json()['stored_versions']
        res=client.post(base+'/illustrative-power-paths',json=SPLIT)
        self.assertEqual(res.status_code,200,res.text)
        self.assertEqual(res.json()['g4'],'BLOCKED')
        self.assertEqual(client.get(base+'/inputs').json()['stored_versions'],before)
        bad=copy.deepcopy(SPLIT)
        bad['site_schedules'][0]['tranches'][0]['mw']+=1
        self.assertEqual(client.post(base+'/illustrative-power-paths',json=bad).status_code,422)

if __name__=='__main__':unittest.main()
