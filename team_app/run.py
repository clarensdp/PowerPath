"""
Headless runs (reproducible exports + cache warm-up). From the packet folder:

  python team_app/run.py recommend --out outputs                 # default customer, balanced
  python team_app/run.py recommend --full-by 24 --speed 60 --cost 30 --env 10 --out outputs/alt_speed
  python team_app/run.py recommend --max-kg 100 --speed 80 --cost 20 --env 0 --out outputs/alt_clean
  python team_app/run.py warm                                      # precompute the demo presets

Then check:  python starter/check_submission.py outputs/portfolio.json outputs/dispatch.csv > outputs/check_results.json
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gridpilot.advisor import Preferences, Requirements, Options, recommend  # noqa: E402
from gridpilot.export import write_submission, summary_md  # noqa: E402


def build(a):
    prefs = Preferences(a.speed, a.cost, a.env)
    req = Requirements(full_demand_by=a.full_by, open_by=a.open_by, max_intensity_kg=a.max_kg,
                       min_clean_share=a.min_clean, no_tier2=a.no_tier2,
                       max_premium_pct=a.max_premium, n_minus_1=a.n1)
    opt = Options(earliest_open=a.lo, latest_open=a.hi, step=a.step, grid_delay=a.delay,
                  workers=a.workers, execution_aware=a.exec_aware, today=a.today if a.exec_aware else 0)
    return prefs, req, opt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["recommend", "warm"])
    ap.add_argument("--speed", type=float, default=34)
    ap.add_argument("--cost", type=float, default=33)
    ap.add_argument("--env", type=float, default=33)
    ap.add_argument("--full-by", type=int)
    ap.add_argument("--open-by", type=int)
    ap.add_argument("--max-kg", type=float)
    ap.add_argument("--min-clean", type=float)
    ap.add_argument("--max-premium", type=float)
    ap.add_argument("--no-tier2", action="store_true")
    ap.add_argument("--n1", action="store_true", help="survive loss of the largest onsite unit")
    ap.add_argument("--exec-aware", action="store_true", help="respect lead times from --today")
    ap.add_argument("--today", type=int, default=0)
    ap.add_argument("--delay", type=int, default=0)
    ap.add_argument("--lo", type=int, default=14)
    ap.add_argument("--hi", type=int, default=26)
    ap.add_argument("--step", type=int, default=2)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", default="outputs")
    a = ap.parse_args()
    if a.cmd == "warm":
        presets = [dict(), dict(full_by=24, speed=60, cost=30, env=10),
                   dict(full_by=36, speed=0, cost=100, env=0), dict(max_kg=100, speed=80, cost=20, env=0),
                   dict(no_tier2=True), dict(delay=6, full_by=24, speed=60, cost=30, env=10),
                   dict(full_by=24, max_premium=10, speed=50, cost=40, env=10),
                   dict(n1=True), dict(exec_aware=True, today=0)]
        for p in presets:
            ns = argparse.Namespace(**{**vars(a), **p})
            t = time.time()
            rec = recommend(*build(ns))
            print(p, "->", rec.best.scenario.initial_service_month if rec.best else "no feasible",
                  f"{time.time() - t:.0f}s", flush=True)
        return
    prefs, req, opt = build(a)
    rec = recommend(prefs, req, opt)
    if rec.best is None:
        print("No portfolio meets every must-have. Nearest fixes:")
        for r in rec.relaxations:
            print(" -", r["change"], "|", r["note"])
        sys.exit(1)
    write_submission(rec.best, a.out, rec, prefs, req, opt)
    print(summary_md(rec.best, rec, prefs, req, opt))


if __name__ == "__main__":
    main()
