"""Run the system against every scenario and report a pass/fail verdict.

Usage:
    python run_cases.py                 # run all scenarios + restore "all"
    python run_cases.py --scenario rings # run a single scenario only
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

SCENARIOS = ["all", "clean", "rings", "dominant", "price", "newvendor"]

PLANTED = {
    "all": ["V001", "V002", "V003", "V004", "V005", "V006", "V007", "V008"],
    "clean": [],
    "rings": ["V001", "V002", "V003", "V004", "V005"],
    "dominant": ["V006"],
    "price": ["V007"],
    "newvendor": ["V008"],
}
CONTROL = ["V009"]  # benign specialized vendor: must always stay Low

def run_scenario():
    out = subprocess.check_output(
        [sys.executable, "-c",
         "import json, main; x = main.analyze(); print(json.dumps(x[['vendor_id','investigation_score','review_priority','wins','connected','max_co_bid']].to_dict('records')))"],
        cwd=HERE, text=True)
    return json.loads(out.strip().splitlines()[-1])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=SCENARIOS, default=None)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    todo = [args.scenario] if args.scenario else SCENARIOS

    print(f"{'scenario':<10}{'planted':<28}{'flagged (High/Med)':<30}{'control V009':<14}verdict")
    print("-" * 100)
    all_pass = True
    for sc in todo:
        subprocess.check_call([sys.executable, "data_generator.py", "--seed", str(args.seed),
                               "--scenario", sc], cwd=HERE, stdout=subprocess.DEVNULL)
        recs = run_scenario()
        flag = {r["vendor_id"]: r for r in recs if r["review_priority"] in ("High", "Medium")}
        low = {r["vendor_id"]: r for r in recs if r["review_priority"] == "Low"}
        planted = PLANTED[sc]
        missed = [v for v in planted if v not in flag]
        ctrl = low.get("V009") is not None
        clean_ok = (sc != "clean") or (len(flag) == 0)
        ok = (not missed) and ctrl and clean_ok
        all_pass &= ok
        flagged_txt = ", ".join(f"{v}({flag[v]['review_priority']}, {flag[v]['investigation_score']:.0f})"
                                for v in sorted(flag)) if flag else "none"
        print(f"{sc:<10}{','.join(planted) if planted else '(none)':<28}{flagged_txt:<30}"
              f"{'Low' if ctrl else 'FLAGGED':<14}{'PASS' if ok else 'FAIL'}")
        for v in missed:
            print(f"  MISSED -> {v} was not flagged")
        for v in sorted(set(flag) - set(planted)):
            print(f"  NOTE  -> {v} flagged (side effect worth reviewing): "
                  f"{flag[v]['review_priority']} {flag[v]['investigation_score']:.0f}")

    print("-" * 100)
    print("ALL PASS" if all_pass else "SOME FAIL")
    print("Final dataset restored to scenario 'all' for the dashboard.")
    subprocess.check_call([sys.executable, "data_generator.py", "--seed", str(args.seed),
                           "--scenario", "all"], cwd=HERE, stdout=subprocess.DEVNULL)

if __name__ == "__main__":
    main()