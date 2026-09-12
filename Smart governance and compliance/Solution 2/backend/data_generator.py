import argparse
import pandas as pd
import numpy as np
from pathlib import Path

ap = argparse.ArgumentParser(description="Generate synthetic procurement audit data.")
ap.add_argument("--scenario", default="all",
                choices=["all", "clean", "rings", "dominant", "price", "newvendor"],
                help="which planted anomaly pattern(s) to include (see README)")
ap.add_argument("--seed", type=int, default=11)
args = ap.parse_args()
SC = args.scenario
rng = np.random.default_rng(args.seed)

RINGS = SC in ("all", "rings")
DOM = SC in ("all", "dominant")
PRICE = SC in ("all", "price")
NEWV = SC in ("all", "newvendor")

OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(parents=True, exist_ok=True)

CATEGORIES = ["IT Infrastructure","Civil Works","Medical Supplies","Office Consumables",
              "Security Services","IT Services","Furniture","Transport"]
RAND_CATS = ["IT Infrastructure","Civil Works","Medical Supplies",
             "Security Services","IT Services","Furniture","Transport"]
BUYERS = ["Transport Department","Municipal Corporation","Health Department",
          "Education Department","Public Works Department"]
CITIES = ["Bengaluru","Mysuru","Mangaluru","Hubballi","Tumakuru"]
SPLIT_THRESHOLD = 1.0   # Cr per payment

NAMES = [
    "Aarav Systems","Bharath Infotech","Chandra Logistics","Dhanraj Traders","Eldora Tech",
    "Falcon Engineering","Ganga Constructions","Horizon Electronics","Indus Software",
    "Jain Hardware","Karnataka Tech Park","Lakshmi Agencies","Mahima Solutions","Navya Enterprises",
    "Omkar Industries","Prakash Builders","Quill Office Supplies","Ravi Security Services",
    "SRK Medical Equipments","Trident Glass Works","Uday Cables","Vidya Infra","Westline IT",
    "Yash Fibre Works","Zephyr Services","Amar Auto Parts","Bindu Steel","Chetan Solar",
]

def pick(seq):  return seq[int(rng.integers(0, len(seq)))]

# ---------------------------------------------------------------- vendors
# Planted patterns (each can be switched off per scenario):
# RING_A  V001-V003  shared phone/domain/director, co-bid rigging in IT Infrastructure
# RING_B  V004-V005  shared director, alternating wins in Civil Works
# DOMINANT V006      medical supplies dominance + split payments just under threshold
# PRICE    V007      wins repeatedly ~+20% above estimate
# NEW      V008      registered recently, wins quickly after registration
# BENIGN   V009      specialized single-bidder market at fair prices (false-positive control)

def ring_a_identity(vid):
    if RINGS:
        base = ("11-22-33", "@eldora.in", "R. Sharma")
        if vid == "V003":
            base = ("11-22-33", "@eldora.in", "S. Verma")
        return base
    return ("", f"@{vid.lower()}.in", f"D{v_id_n(vid)}")

def ring_b_identity(vid):
    if RINGS:
        return ("44-55-66" if vid == "V004" else "77-88-99", f"@{vid.lower()}.in", "K. Rao")
    return ("", f"@{vid.lower()}.in", f"D{v_id_n(vid)}")

def v_id_n(vid):  return int(vid[1:])

vendor_rows = []
def add_v(vid, name, reg, city, phone, domain, directors, note):
    vendor_rows.append({"vendor_id": vid, "name": name, "reg_year": reg, "city": city,
                        "contact_phone": phone, "email_domain": domain,
                        "directors": directors, "note": note})

p, d, dr = ring_a_identity("V001"); add_v("V001","Eldora Tech","2015","Bengaluru",p,d,dr,"ring A")
p, d, dr = ring_a_identity("V002"); add_v("V002","Chandra Logistics","2016","Bengaluru",p,d,dr,"ring A")
p, d, dr = ring_a_identity("V003"); add_v("V003","Bharath Infotech","2014","Bengaluru",p,d,dr,"ring A")
p, d, dr = ring_b_identity("V004"); add_v("V004","Ganga Constructions","2012","Bengaluru",p,d,dr,"ring B")
p, d, dr = ring_b_identity("V005"); add_v("V005","Prakash Builders","2013","Bengaluru",p,d,dr,"ring B")
add_v("V006","SRK Medical Equipments","2010","Mysuru","","@srkmed.in","A. Kumar","dominant")
add_v("V007","Indus Software","2017","Mangaluru","","@indus.in","M. Shetty","price anomaly")
add_v("V008","Mahima Solutions","2025","Hubballi","","@mahima.in","P. Patil","new vendor")
add_v("V009","Zephyr Services","2011","Bengaluru","","@zephyr.in","T. Gowda","benign specialized")
for i in range(10, 25):
    vid = f"V{i:03d}"
    add_v(vid, pick(NAMES), int(rng.integers(2008, 2023)), pick(CITIES), "",
          f"@{vid.lower()}_co.in", f"D{i}", "normal")

vendors = pd.DataFrame(vendor_rows)

# ---------------------------------------------------------------- tenders & bids
RING_A = ["V001","V002","V003"]; RING_B = ["V004","V005"]
ring_rot = {"A": 0, "B": 0}

def generic_ids():
    ids = [f"V{i:03d}" for i in range(10, 25)]
    if not DOM:  ids.append("V006")
    if not PRICE: ids.append("V007")
    if not NEWV:  ids.append("V008")
    if not RINGS: ids += RING_A + RING_B
    return ids

tenders, bids = [], []
bid_seq = 0
for t in range(1, 96):
    tid = f"T{t:03d}"
    buyer = pick(BUYERS); cat = pick(RAND_CATS)
    if 71 <= t <= 74:
        cat = "Civil Works"
    if 75 <= t <= 79:
        cat = "IT Services"
    if 80 <= t <= 84:
        cat = "Security Services"
    if 85 <= t <= 95:
        cat = "Office Consumables"
    est = round(float(rng.uniform(0.5, 14.0)), 1)
    a_date = pick(pd.date_range("2024-01-01", "2026-06-30", freq="2D"))
    city = pick(CITIES)

    pool = {}
    winner = None

    # --- deterministic planted patterns per category (respect scenario flags) ---
    if cat == "Medical Supplies":
        if DOM and rng.random() < 0.25:
            pool = {"V006": est * rng.uniform(1.06, 1.12),
                    pick(generic_ids()): est * rng.uniform(0.9, 1.0)}
        elif DOM:
            pool = {"V006": est * rng.uniform(1.06, 1.12)}
        else:
            cand = rng.choice(generic_ids(), size=int(rng.integers(2, 4)), replace=False)
            pool = {v: est * rng.uniform(0.95, 1.06) for v in cand}
        winner = "V006" if DOM else None
    elif cat == "IT Services":
        if PRICE and 75 <= t <= 79:
            pool = {"V007": est * rng.uniform(1.18, 1.22),
                    pick(generic_ids()): est * rng.uniform(0.92, 0.98)}
            winner = "V007"
        elif PRICE and rng.random() < 0.85:
            pool = {"V007": est * rng.uniform(1.16, 1.22),
                    pick(generic_ids()): est * rng.uniform(0.92, 0.98)}
            winner = "V007"
        else:
            cand = rng.choice(generic_ids(), size=int(rng.integers(2, 4)), replace=False)
            pool = {v: est * rng.uniform(0.95, 1.06) for v in cand}
            winner = None
    elif cat == "Office Consumables":
        if NEWV:
            pool = {"V008": est * rng.uniform(0.96, 1.01),
                    pick(generic_ids()): est * rng.uniform(1.0, 1.08)}
            winner = "V008"
        else:
            cand = rng.choice(generic_ids(), size=int(rng.integers(2, 4)), replace=False)
            pool = {v: est * rng.uniform(0.95, 1.06) for v in cand}
            winner = None
    elif cat == "IT Infrastructure":
        if RINGS:
            pool = {v: est * rng.uniform(0.9, 1.15) for v in RING_A}
            winner = None
        else:
            cand = rng.choice(generic_ids(), size=int(rng.integers(2, 4)), replace=False)
            pool = {v: est * rng.uniform(0.85, 1.22) for v in cand}
            winner = None
    elif cat == "Civil Works":
        if RINGS:
            pool = {v: est * rng.uniform(0.9, 1.15) for v in RING_B}
            winner = None
        else:
            cand = rng.choice(generic_ids(), size=int(rng.integers(2, 4)), replace=False)
            pool = {v: est * rng.uniform(0.85, 1.22) for v in cand}
            winner = None
    elif cat == "Security Services" and 80 <= t <= 84:
        pool = {"V009": est * rng.uniform(0.9, 0.98)}
        winner = "V009"
    else:
        cand = rng.choice(generic_ids(), size=int(rng.integers(2, 4)), replace=False)
        pool = {v: est * rng.uniform(0.85, 1.22) for v in cand}
        winner = None

    if winner is not None:
        pass
    elif cat in ("IT Infrastructure", "Civil Works") and RINGS:
        ring = "A" if cat == "IT Infrastructure" else "B"
        ring_members = RING_A if ring == "A" else RING_B
        win = ring_members[ring_rot[ring] % len(ring_members)]
        ring_rot[ring] += 1
        rivals = [amt for v, amt in pool.items() if v not in ring_members]
        base = min(rivals) if rivals else list(pool.values())[0]
        pool[win] = base * rng.uniform(0.97, 0.995)
        winner = win
    else:
        winner = min(pool, key=lambda v: pool[v])

    statuses = {v: "win" if v == winner else "lose" for v in pool}
    for v in pool:
        if statuses[v] == "lose" and v in (RING_A + RING_B) and RINGS and rng.random() < 0.35:
            statuses[v] = "withdrawn"

    for v, amt in pool.items():
        bid_seq += 1
        bids.append({"bid_id": f"B{bid_seq:04d}", "tender_id": tid, "vendor_id": v,
                     "amount_mn": round(amt, 2), "bid_date": a_date.date().isoformat(),
                     "status": statuses[v]})

    tenders.append({"tender_id": tid, "buyer": buyer, "category": cat, "city": city,
                    "est_value_mn": est, "award_value_mn": round(pool[winner], 2),
                    "award_date": a_date.date().isoformat(), "winner": winner, "bid_count": len(pool)})

tenders = pd.DataFrame(tenders)
bids = pd.DataFrame(bids)

# ---------------------------------------------------------------- payments
def split_amounts(total, n=None, n_cap=20):
    if n:
        parts = [round(min(0.99, total / n + rng.uniform(-0.03, 0.03)), 2) for _ in range(n)]
        parts[-1] = round(total - sum(parts[:-1]), 2)
        return parts
    amounts, limit = [], 0.99
    while True:
        remainder = round(total - sum(amounts), 2)
        if remainder <= 0.02:
            break
        k = min(max(3, int(round(remainder / 0.65))), n_cap, int(round(remainder / 0.30)))
        part = min(limit, max(0.05, remainder / max(1, k) + rng.uniform(-0.05, 0.05)))
        amounts.append(round(part, 2))
    amounts[-1] = round(total - sum(amounts[:-1]), 2)
    return amounts

pays, pay_seq = [], 0
for _, tr in tenders.iterrows():
    w = tr.winner; val = tr.award_value_mn
    if w == "V006" and DOM:
        amts = split_amounts(val)
        days = rng.integers(12, 25)
        for amt in amts:
            pay_seq += 1
            pays.append({"payment_id": f"P{pay_seq:05d}", "tender_id": tr.tender_id, "vendor_id": w,
                         "amount_mn": round(amt, 2), "pay_date": (pd.Timestamp(tr.award_date) + pd.Timedelta(days=days)).date().isoformat(),
                         "days_after_award": int(days)})
    else:
        n = 1 if rng.random() > 0.6 else 2
        amts = split_amounts(val, n)
        for amt in amts:
            pay_seq += 1
            d = int(rng.integers(25, 90))
            pays.append({"payment_id": f"P{pay_seq:05d}", "tender_id": tr.tender_id, "vendor_id": w,
                         "amount_mn": round(amt, 2), "pay_date": (pd.Timestamp(tr.award_date) + pd.Timedelta(days=d)).date().isoformat(),
                         "days_after_award": d})

payments = pd.DataFrame(pays)

# ---------------------------------------------------------------- relationships (co-bid + identity links)
def shared_identity(a, b):
    va = vendors[vendors.vendor_id == a].iloc[0]; vb = vendors[vendors.vendor_id == b].iloc[0]
    links = []
    if va.contact_phone and va.contact_phone == vb.contact_phone:
        links.append(("shared phone", 2))
    if va.email_domain and va.email_domain == vb.email_domain:
        links.append(("shared domain", 2))
    dv = set(va.directors.split(",")) & set(vb.directors.split(","))
    if dv:
        links.append(("shared director", min(2 * len(dv), 3)))
    return links

rel_rows, seen = [], set()
bid_pairs = bids[bids.status != "withdrawn"].merge(bids[bids.status != "withdrawn"], on="tender_id")
co_count = (
    bid_pairs[bid_pairs.vendor_id_x < bid_pairs.vendor_id_y]
    .groupby(["vendor_id_x", "vendor_id_y"]).size().reset_index(name="overlap")
)
for _, r in co_count.iterrows():
    a, b = r.vendor_id_x, r.vendor_id_y
    if r.overlap >= 3:
        key = (a, b, "co-bid")
        if key not in seen:
            rel_rows.append({"vendor_a": a, "vendor_b": b, "relation_type": "co-bid", "strength": int(r.overlap)})
            seen.add(key)
    for (typ, strength) in shared_identity(a, b):
        key = (a, b, typ)
        if key not in seen:
            rel_rows.append({"vendor_a": a, "vendor_b": b, "relation_type": typ, "strength": strength})
            seen.add(key)

relationships = pd.DataFrame(rel_rows,
                             columns=["vendor_a","vendor_b","relation_type","strength"])

vendors.to_csv(OUT/"vendors.csv", index=False)
tenders.to_csv(OUT/"tenders.csv", index=False)
bids.to_csv(OUT/"bids.csv", index=False)
payments.to_csv(OUT/"payments.csv", index=False)
relationships.to_csv(OUT/"relationships.csv", index=False)
print("Generated procurement audit data in", OUT)
print("tenders:", len(tenders), " bids:", len(bids), " payments:", len(payments), " relationships:", len(relationships))