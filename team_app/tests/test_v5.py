import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gridpilot.interconnect import profile_for, energization, grid_mw_by_month, decide


class Stub:
    def __init__(self, s, cost, status="ok"):
        self.status = status
        self.metrics = {"decision_cost_usd_per_requested_mwh": cost}
        self.scenario = type("S", (), {"initial_service_month": s})()


class V5Tests(unittest.TestCase):
    def test_profiles(self):
        self.assertEqual(profile_for("PJM")[1], 150)
        self.assertEqual(profile_for("ERCOT")[0], 6)
        self.assertEqual(profile_for("EirGrid")[1], 150)   # default profile

    def test_energization_and_grid(self):
        e = energization(24, 12)
        self.assertEqual((e["P10"], e["P50"], e["P90"]), (12, 24, 36))
        g = grid_mw_by_month(0)
        self.assertEqual((g[17], g[18], g[24], g[30]), (0, 25, 50, 75))

    def test_decide_uses_value_of_time(self):
        wait, bridge = Stub(18, 53.0), Stub(14, 56.0)   # bridge 4 months sooner, +$3/MWh
        ref = 1_000_000
        self.assertEqual(decide(None, wait, bridge, 1e6, ref)["verdict"], "BRIDGE")   # breakeven 0.75M/month
        self.assertEqual(decide(None, wait, bridge, 0.5e6, ref)["verdict"], "WAIT")
        self.assertEqual(decide(None, Stub(18, 1, "infeasible"), Stub(14, 1, "infeasible"), 0, ref)["verdict"],
                         "WALK AWAY / RELAX")


if __name__ == "__main__":
    unittest.main()
