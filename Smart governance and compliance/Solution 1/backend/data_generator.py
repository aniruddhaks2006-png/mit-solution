import pandas as pd
import numpy as np
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)

TODAY = pd.Timestamp("2026-09-01")

AGENCY = {
    "PWD": "Public Works Department",
    "HUD": "Urban Development Authority",
    "Health": "State Health Department",
    "Water": "Water Supply and Sewerage Board",
    "Power": "Power Distribution Company",
    "Rural": "Rural Development Department",
}

TITLES = {
    "PWD": ["Construction of District Office Annex", "NH-48 Road Widening Package", "Ring Road Flyover Approach Ramp"],
    "HUD": ["Market Redevelopment Block B", "Affordable Housing Township Phase II", "City Parking Complex Upgrade"],
    "Health": ["District Hospital Tower Extension", "Public Health Laboratory Upgrade", "Primary Care Center Network"],
    "Water": ["Water Treatment Plant Expansion", "Pipeline Network Replacement Zone 4", "Sewerage Outfall Rehabilitation"],
    "Power": ["Substation Capacity Augmentation", "Rural Feeder Upgrade Phase II", "Smart Meter Rollout Zone 7"],
    "Rural": ["Irrigation Canal Modernization", "Rural Road Connectivity Program", "Solar Water Supply Schemes"],
}

REGIONS = ["Bengaluru","Mysuru","Mangaluru","Hubballi","Belagavi","Tumakuru","Davangere","Shivamogga"]

CONTRACTORS = [
    "Akshaya Constructions","Srinivasa Civil Works","Nandi Builders","Vijay Infrastructure",
    "Kaveri Projects","Himalaya Engineering","Om Sai Developers","Icon Construction Co.",
]

MAT_POOL = {
    "PWD": [("cement","t"), ("steel","t"), ("aggregate","m3"), ("asphalt","t"), ("culverts","nos")],
    "HUD": [("cement","t"), ("steel","t"), ("tiles","m2"), ("glass","m2"), ("electrical","nos")],
    "Health": [("cement","t"), ("steel","t"), ("HVAC units","nos"), ("medical gas points","pts"), ("tiles","m2")],
    "Water": [("DI pipes","km"), ("pumps","nos"), ("treatment units","nos"), ("butterfly valves","nos")],
    "Power": [("transformers","nos"), ("conductors","km"), ("smart meters","nos"), ("poles","nos")],
    "Rural": [("canal lining","km"), ("gates","nos"), ("pumps","nos"), ("pipes","km")],
}

def pick(lst):  return lst[int(rng.integers(0, len(lst)))]

def build_contracts():
    # (agency key, region, awarded value in Cr, duration months, baseline-end margin days, scenario)
    specs = [
        ("PWD",    "Bengaluru",  142.0, 24, 120, "stable"),
        ("Water",  "Mangaluru",   96.0, 22, 100, "cost_overrun"),
        ("Health", "Mysuru",      71.0, 18,  80, "schedule_gap"),
        ("HUD",    "Bengaluru",   118.0, 30, 150, "substitution"),
        ("Power",  "Hubballi",    88.0, 20,  90, "stable"),
        ("Rural",  "Davangere",   54.0, 15,  60, "cost_overrun"),
        ("PWD",    "Tumakuru",    67.0, 19,  85, "schedule_gap"),
        ("Health", "Belagavi",    42.0, 13,  55, "substitution"),
        ("Water",  "Shivamogga",  121.0, 27, 130, "stable"),
        ("Power",  "Mysuru",      39.0, 12,  50, "cost_overrun"),
        ("HUD",    "Mangaluru",   63.0, 16,  70, "schedule_gap"),
        ("Rural",  "Tumakuru",    77.0, 21,  95, "substitution"),
    ]
    rows = []
    for i, (ak, region, value, dur, margin, scen) in enumerate(specs):
        award = TODAY - pd.Timedelta(days=int(dur*30.4))
        baseline_end = TODAY + pd.Timedelta(days=margin)
        c = f"C{int(i+1):03d}"
        title = TITLES[ak][i % 3]
        con_b = pick(CONTRACTORS)
        rows.append({
            "contract_id": c, "title": f"{title} ({c})", "agency_key": ak,
            "agency": AGENCY[ak], "region": region, "category": ak,
            "contractor_baseline": con_b, "contractor_current": con_b,
            "awarded_value_mn": value, "current_approved_value_mn": value,
            "award_date": award.date().isoformat(),
            "baseline_end_date": baseline_end.date().isoformat(),
            "revised_end_date": baseline_end.date().isoformat(),
            "status": "Under execution", "scenario": scen,
        })
    return rows

def build_materials(contract_rows):
    mats, mat_by_c = [], {}
    for i, r in enumerate(contract_rows):
        pool = MAT_POOL[r["agency_key"]]
        n = len(pool)
        items = []
        for j, (item, unit) in enumerate(pool):
            nitem = int(rng.integers(3, 8))
            qty = float(rng.integers(200, 2000)) if unit in ("m3","m2") else float(rng.integers(10, 900))
            qty = round(qty * (r["awarded_value_mn"]/70.0), 0)
            unit_cost = round(rng.uniform(0.02, 0.12), 3)  # Cr per unit-ish
            items.append([r["contract_id"], item, unit, nitem, qty, qty, unit_cost])
        mat_by_c[r["contract_id"]] = items
        mats.extend(items)
    return pd.DataFrame(mats, columns=["contract_id","item","unit","item_count","baseline_qty","current_qty","unit_cost"]), mat_by_c

CHANGE_NO = {"cost_overrun": 0, "schedule_gap": 0, "substitution": 0, "stable": 0}

def build_changes(contract_rows):
    rows = []
    counter = 0
    for r in contract_rows:
        cid = r["contract_id"]; value = r["awarded_value_mn"]; scen = r["scenario"]
        award = pd.Timestamp(r["award_date"])
        baseline_end = pd.Timestamp(r["baseline_end_date"])
        deltas_value, deltas_days, cos = [], [], []
        target_today = max(award + pd.Timedelta(days=150), baseline_end - pd.Timedelta(days=45), TODAY - pd.Timedelta(days=30))
        step = (target_today - award).days / 3.0

        if scen == "stable":
            for _ in range(int(rng.integers(1, 3))):
                dv = float(round(value*rng.uniform(-0.02, 0.02), 1))
                dd = int(rng.integers(-15, 15))
                cos.append((pick(["cost","schedule","materials"]), dv, dd, "Minor adjustment", "on_file"))
        elif scen == "cost_overrun":
            pct = rng.uniform(0.25, 0.45)
            n = int(rng.integers(3, 5))
            for k in range(n):
                dv = round(value*pct/n, 1)
                dd = int(rng.integers(10, 45))
                typ = "cost" if k < n-1 else "schedule"
                cos.append((typ, dv, dd,
                            "Additional work items / rate revision during execution",
                            "on_file" if rng.random() > 0.25 else "MISSING"))
            cos.append(("schedule", round(value*rng.uniform(0.0, 0.03), 1),
                        int(rng.integers(45, 90)), "Unforeseen site conditions", "on_file"))
        elif scen == "schedule_gap":
            for _ in range(int(rng.integers(2, 4))):
                dd = int(rng.integers(45, 70))
                dv = round(value*rng.uniform(-0.01, 0.03), 1)
                cos.append(("schedule", dv, dd, "Workfront delays / sub-contractor mobilization",
                            "MISSING" if rng.random() > 0.5 else "on_file"))
        elif scen == "substitution":
            cos.append(("contractor", 0.0, int(rng.integers(10, 30)),
                        "Contractor replaced; works re-mobilized to new agency", "on_file"))
            pct = rng.uniform(0.2, 0.4)
            cos.append(("materials", round(value*rng.uniform(0.05, 0.10), 1), int(rng.integers(20, 45)),
                        f"Bill of quantities revised: {pct*100:.0f}% increase on one pay item", "on_file"))
            if rng.random() > 0.4:
                cos.append(("schedule", round(value*rng.uniform(0.0, 0.02), 1), int(rng.integers(50, 80)),
                            "Re-tendering of residual works", "MISSING"))

        # evolve current contractor for substitution
        if scen == "substitution":
            now = pick(CONTRACTORS)
            while now == r["contractor_baseline"]:
                now = pick(CONTRACTORS)
            r["contractor_current"] = now

        # change orders
        for k, (typ, dv, dd, desc, ev) in enumerate(cos):
            counter += 1
            cdate = award + pd.Timedelta(days=int(k*step)) if int(k*step) >= 60 else award + pd.Timedelta(days=90)
            rows.append({
                "change_id": f"CO-{counter:04d}", "contract_id": cid,
                "change_date": cdate.date().isoformat(), "change_type": typ,
                "description": desc, "delta_value_mn": dv, "delta_days": dd,
                "evidence_doc": ev,
            })
            deltas_value.append(dv); deltas_days.append(dd)
        r["current_approved_value_mn"] = round(value + sum(deltas_value), 1)
        r["revised_end_date"] = (baseline_end + pd.Timedelta(days=int(sum(deltas_days)))).date().isoformat()
    return pd.DataFrame(rows, columns=["change_id","contract_id","change_date","change_type","description","delta_value_mn","delta_days","evidence_doc"])

def build_history(contract_rows, changes):
    hist = []
    for r in contract_rows:
        cid = r["contract_id"]
        ch = changes[changes.contract_id == cid]
        award = pd.Timestamp(r["award_date"])
        base = r["awarded_value_mn"]
        rev_end = pd.Timestamp(r["revised_end_date"])
        last_m = min(TODAY, rev_end)
        nmonths = max(4, int((last_m - award).days/30.4))
        month = award + pd.Timedelta(days=30)
        for m in range(nmonths):
            d = award + pd.Timedelta(days=(m+1)*30)
            # days between award and this month accumulates? no - approved at that time
            applied = ch[ch.change_date.isna() | (pd.to_datetime(ch.change_date) <= d)]
            approved = base + applied.delta_value_mn.sum()
            hist.append({"contract_id": cid, "month": d.strftime("%b %y"), "approved_value_mn": round(approved,1), "awarded_value_mn": base})
    return pd.DataFrame(hist, columns=["contract_id","month","approved_value_mn","awarded_value_mn"])

contract_rows = build_contracts()
changes = build_changes(contract_rows)
materials, mat_by_c = build_materials(contract_rows)
history = build_history(contract_rows, changes)

contracts = pd.DataFrame(contract_rows, columns=[
    "contract_id","title","agency_key","agency","region","category",
    "contractor_baseline","contractor_current","awarded_value_mn","current_approved_value_mn",
    "award_date","baseline_end_date","revised_end_date","status"
])
contracts.to_csv(OUT/"contracts.csv", index=False)
materials.to_csv(OUT/"materials.csv", index=False)
changes.to_csv(OUT/"changes.csv", index=False)
history.to_csv(OUT/"contract_history.csv", index=False)
print("Generated contract monitoring data in", OUT)