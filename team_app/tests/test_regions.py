import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gridpilot.regions import resolve, zip_to_state, region_params, STATES
from gridpilot.screener import illustrative_parcels, score_parcels


class RegionTests(unittest.TestCase):
    def test_zip_and_names(self):
        self.assertEqual(zip_to_state("20147"), "VA")
        self.assertEqual(zip_to_state("78626"), "TX")
        self.assertEqual(zip_to_state("10001"), "NY")
        self.assertEqual(resolve("78626-1234")["abbr"], "TX")
        self.assertEqual(resolve("iowa")["abbr"], "IA")
        self.assertEqual(resolve("OK")["abbr"], "OK")
        self.assertEqual(resolve("Ireland")["kind"], "country")
        self.assertEqual(resolve("UK")["abbr"], "GB")
        self.assertIsNone(resolve("Atlantis"))

    def test_all_states_present(self):
        self.assertEqual(len(STATES), 51)

    def test_benchmark_is_ground_truth(self):
        self.assertIsNone(region_params("US-TX"))
        self.assertTrue(resolve("78626")["benchmark"])
        self.assertAlmostEqual(region_params("US-VA")["price_index"], 10.62 / 9.79, places=4)

    def test_parcels_deterministic_and_gated(self):
        loc = resolve("20147")
        a, b = illustrative_parcels(loc), illustrative_parcels(loc)
        self.assertTrue(a.equals(b))
        s = score_parcels(a, needs_gas=True)
        self.assertTrue((s.loc[~s.passes, "parcel_score"] <= 35).all())


if __name__ == "__main__":
    unittest.main()
