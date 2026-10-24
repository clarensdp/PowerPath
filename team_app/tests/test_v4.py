import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gridpilot.advisor import (Preferences, Options, Requirements, execution_shifts, scenario_shifts,
                               make_scenario, _ckey, CODE_VERSION, MAX_VALUE_PER_MONTH, MAX_CARBON_PRICE)
from gridpilot.execution import DEFAULT_STEPS
from gridpilot.engine import avail_month


class V4Tests(unittest.TestCase):
    def test_slider_caps(self):
        v, lam = Preferences(speed=100, cost=0, env=100).implied()
        self.assertLessEqual(v, MAX_VALUE_PER_MONTH)
        self.assertLessEqual(lam, MAX_CARBON_PRICE)
        v2, _ = Preferences(override_value=50e6).implied()
        self.assertEqual(v2, 50e6)   # typed overrides are respected

    def test_execution_shift_matches_lead_times(self):
        sh = execution_shifts(Options(execution_aware=True, today=0))
        st = DEFAULT_STEPS["gas_turbine"]
        expect = max(0, st["build"] + max(st["permit"], st["procure"]) - avail_month("gas_turbine"))
        self.assertEqual(sh["gas_turbine"], expect)
        self.assertEqual(sh["wind"], 0)      # PPA negotiation fits before the month-12 offer

    def test_shifts_combine_with_manual_slip(self):
        opt = Options(execution_aware=True, today=0, slips=(("gas_turbine", 99),))
        self.assertIn(("gas_turbine", 99), scenario_shifts(opt))

    def test_overrides_change_shift(self):
        a = execution_shifts(Options(execution_aware=True))["gas_engine"]
        b = execution_shifts(Options(execution_aware=True, lead_overrides=(("gas_engine", 1, 1, 1),)))["gas_engine"]
        self.assertLess(b, a + 1)

    def test_cache_key_versioned_and_n1_distinct(self):
        s1 = make_scenario(20, Requirements(), Options(), 0.0)
        s2 = make_scenario(20, Requirements(n_minus_1=True), Options(), 0.0)
        self.assertNotEqual(_ckey(s1), _ckey(s2))
        self.assertEqual(len(CODE_VERSION), 8)


if __name__ == "__main__":
    unittest.main()
