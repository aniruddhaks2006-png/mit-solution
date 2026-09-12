from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data"
app = FastAPI(title="Procurement Anomaly & Relationship Auditing System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vendors = pd.read_csv(BASE/"vendors.csv")
tenders = pd.read_csv(BASE/"tenders.csv", parse_dates=["award_date"])
bids = pd.read_csv(BASE/"bids.csv", parse_dates=["bid_date"])
payments = pd.read_csv(BASE/"payments.csv", parse_dates=["pay_date"])
relationships = pd.read_csv(BASE/"relationships.csv")

SPLIT_THRESHOLD = 1.0
IDENTITY = {"shared phone", "shared domain", "shared address", "shared director"}

# ------------------------------------------------------------------ detection
def signals():
    rows = {}
    for _, v in vendors.iterrows():
        vid = v.vendor_id
        w = tenders[tenders.winner == vid]
        b = bids[bids.vendor_id == vid]
        won = b[b.status == "win"]
        lost = b[b.status == "lose"]

        wins_by_cat = w.groupby("category").size()
        totals_by_cat = tenders.groupby("category").size()
        shares = (wins_by_cat / totals_by_cat.reindex(wins_by_cat.index).fillna(1)).round(3)

        # connected parties (any relation) + identity links
        rels = relationships[(relationships.vendor_a == vid) | (relationships.vendor_b == vid)]
        partners = set()
        identity_types = set()
        co_bids = []
        for _, r in rels.iterrows():
            other = r.vendor_b if r.vendor_a == vid else r.vendor_a
            partners.add(other)
            if r.relation_type in IDENTITY:
                identity_types.add(r.relation_type)
            if r.relation_type == "co-bid":
                co_bids.append((other, int(r.strength)))

        n_conn = len(partners)
        max_overlap = max([s for _, s in co_bids], default=0)
        has_identity = len(identity_types) > 0
        in_ring = has_identity and max_overlap >= 3

        # price behaviour: win margin vs estimate, vs peers in same categories
        if len(w):
            win_margin = (w.award_value_mn - w.est_value_mn) / w.est_value_mn * 100
            peer_margin = []
            for cat in w.category.unique():
                cw = tenders[(tenders.category == cat) & (tenders.winner != vid)]
                if len(cw):
                    peer_margin.append(((cw.award_value_mn - cw.est_value_mn) / cw.est_value_mn * 100).median())
            peer_m = np.nanmedian(peer_margin) if peer_margin else 0
            price_gap = win_margin.mean() - peer_m
            pct_above_est = win_margin.mean()
        else:
            price_gap, pct_above_est = 0, 0

        # single-bidder wins (specialized market) as share of wins
        single_win_share = (w.bid_count.apply(lambda c: 1 if c == 1 else 0).mean()) if len(w) else 0

        # award concentration (dampened when market itself is thin / single-bidder)
        conc = shares.max() if len(shares) else 0
        thin = min(1.0, sum(1 for c in w.category.unique() if totals_by_cat.get(c, 0) < 6) / max(1, w.category.nunique()))
        conc_risk = conc * (1 - 0.5 * thin * (1 - single_win_share))

        # payments
        pp = payments[payments.vendor_id == vid]
        split_tenders = 0
        fast_pays = 0
        for tid, g in pp.groupby("tender_id"):
            if len(g) > 2 and (g.amount_mn < SPLIT_THRESHOLD).all() and g.amount_mn.sum() > 2:
                split_tenders += 1
            if g.days_after_award.max() < 20:
                fast_pays += 1
        n_pay_tenders = pp.tender_id.nunique()

        # new vendor: registered recently relative to first win
        if len(w):
            first_win = w.award_date.min().year
            new_risk = 1.0 if (first_win - v.reg_year) <= 1 else 0.0
        else:
            new_risk = 0.0

        rows[vid] = dict(vendor_id=vid, name=v["name"], city=v["city"], reg_year=int(v["reg_year"]),
                         category_share=conc, markets=int(w.category.nunique()),
                         wins=len(w), bids=len(b), lost=len(lost), single_win_share=single_win_share,
                         connected=n_conn, identity_links=sorted(identity_types),
                         max_co_bid=max_overlap, in_ring=in_ring, price_gap=float(price_gap),
                         pct_above_est=float(pct_above_est), split_tenders=int(split_tenders),
                         fast_pays=int(fast_pays), new_risk=new_risk)
    return rows

def analyze():
    s = signals()
    x = pd.DataFrame(s.values())
    x = x.merge(vendors[["vendor_id", "note"]], on="vendor_id", how="left")

    # normalized explainable risk dimensions
    x["connected_risk"] = np.clip(x.connected / 4.0, 0, 1) * 0.6 + (x.identity_links.apply(len) > 0).astype(float) * 0.4
    hit_rate = np.where(x.bids > 0, x.wins / x.bids, 0)
    x["hit_rate_risk"] = np.clip((hit_rate - 0.5) / 0.3, 0, 1)
    x["rigging_risk"] = np.clip((x.max_co_bid / 8.0) * 0.7 + x.hit_rate_risk * 0.3, 0, 1)
    x["price_risk"] = np.clip((x.price_gap - 5) / 15.0, 0, 1)
    x["concentration_risk"] = np.clip((x.category_share - 0.4) / 0.3, 0, 1)
    x["payment_risk"] = np.clip(((x.split_tenders * 2 + x.fast_pays) / 6.0), 0, 1)
    x["new_vendor_risk"] = x.new_risk.astype(float)

    x["investigation_score"] = (
        0.25 * x.connected_risk +
        0.25 * x.rigging_risk +
        0.20 * x.price_risk +
        0.15 * x.concentration_risk +
        0.10 * x.payment_risk +
        0.05 * x.new_vendor_risk
    ) * 100
    x["investigation_score"] = np.minimum(x.investigation_score, 100).round(1)

    # floors so clear rings never stay low
    x["investigation_score"] = np.where(x.in_ring, np.maximum(x.investigation_score, 66), x.investigation_score)
    x["investigation_score"] = np.where(
        (x.split_tenders > 0) & (x.category_share > 0.6), np.maximum(x.investigation_score, 60), x.investigation_score
    )
    x["investigation_score"] = np.where(
        (x.wins >= 3) & (x.price_gap > 12) & (x.pct_above_est > 5),
        np.maximum(x.investigation_score, 50), x.investigation_score
    )
    x["investigation_score"] = np.where(
        (x.new_risk > 0) & (x.category_share > 0.6), np.maximum(x.investigation_score, 40), x.investigation_score
    )

    # case reasons
    reasons = []
    for _, r in x.iterrows():
        rs = []
        if r.connected > 0:
            rs.append(f"{r.connected} connected vendor(s) share contact details or bidding history: {', '.join(r.identity_links) if r.identity_links else 'co-bidding overlap'}.")
        if r.in_ring:
            rs.append(f"Co-bid overlap of {r.max_co_bid} tenders combined with shared identity details suggests coordinated bidding.")
        elif r.max_co_bid >= 3:
            rs.append(f"Recurring co-bidding with another vendor on {r.max_co_bid} tenders.")
        if r.price_gap > 5:
            rs.append(f"{r.wins} win(s) average {r.price_gap:.0f}% above the estimate, which is above the peer-median margin in the same categories.")
        if r.pct_above_est > 12:
            rs.append(f"Winning prices average {r.pct_above_est:.0f}% above estimated value.")
        if r.category_share > 0.5:
            share_txt = f"won ~{r.category_share*100:.0f}% of awards" 
            if r.single_win_share > 0.7:
                share_txt += " in a niche/single-bidder segment (context-adjusted)"
            rs.append(f"Dominates an award category by market share: {share_txt}.")
        if r.split_tenders > 0:
            rs.append(f"{r.split_tenders} contract(s) paid by multiple payments kept below ₹{SPLIT_THRESHOLD:.0f} Cr each.")
        if r.fast_pays > 0:
            rs.append(f"{r.fast_pays} contract(s) settled unusually fast (payments within 20 days of award).")
        if r.new_risk:
            rs.append("Registered recently; won contracts within ~1 year of registration.")
        reasons.append(rs)
    x["reasons"] = reasons
    x["review_priority"] = pd.cut(x.investigation_score, [-1, 35, 65, 100], labels=["Low", "Medium", "High"]).astype(str)
    return x

# ------------------------------------------------------------------ api
@app.get("/vendors")
def vendors_list():
    return vendors.to_dict("records")

@app.get("/analytics/overview")
def overview():
    x = analyze()
    return {
        "vendors": len(vendors),
        "tenders": len(tenders),
        "payments_total_mn": round(float(payments.amount_mn.sum()), 1),
        "high_priority": int((x.review_priority == "High").sum()),
        "medium_priority": int((x.review_priority == "Medium").sum()),
        "low_priority": int((x.review_priority == "Low").sum()),
        "connected_pairs": len(relationships),
        "connected_groups": connected_groups(),
        "co_bid_clusters": len(set(relationships[relationships.relation_type == "co-bid"].agg(lambda r: frozenset([r.vendor_a, r.vendor_b]), axis=1))),
        "price_anomalies": int((x.price_gap > 5).sum()),
        "split_payment_contracts": int((x.split_tenders > 0).sum()),
    }

def connected_groups():
    parent = {v: v for v in vendors.vendor_id}
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    def union(a, b):
        pa, pb = find(a), find(b)
        if pa != pb:
            parent[pb] = pa
    for _, r in relationships.iterrows():
        union(r.vendor_a, r.vendor_b)
    from collections import Counter
    groups = Counter(find(v) for v in vendors.vendor_id)
    return int(sum(1 for g, n in groups.items() if n > 1))

@app.get("/cases")
def cases():
    x = analyze()
    x["identity_links"] = x.identity_links.apply(lambda t: list(t))
    x["reasons"] = x.reasons.apply(lambda r: list(r))
    cols = ["vendor_id","name","city","reg_year","wins","bids","connected","max_co_bid",
            "price_gap","category_share","single_win_share","split_tenders","fast_pays",
            "new_risk","in_ring","identity_links","investigation_score","review_priority","reasons"]
    return x[cols].sort_values("investigation_score", ascending=False).to_dict("records")

def vendor_row(vid):
    x = analyze()
    if vid not in set(x.vendor_id):
        raise HTTPException(404, "Vendor not found")
    r = x[x.vendor_id == vid].iloc[0]
    d = r.to_dict()
    d["identity_links"] = list(r.identity_links)
    d["reasons"] = list(r.reasons)
    for k in ["investigation_score","price_gap","category_share","single_win_share"]:
        d[k] = round(float(d[k]), 1)
    return d

@app.get("/vendor/{vendor_id}")
def vendor_detail(vendor_id: str):
    d = vendor_row(vendor_id)
    d["wins_detail"] = tenders[tenders.winner == vendor_id].assign(
        award_date=lambda t: t.award_date.dt.strftime("%Y-%m-%d")
    ).to_dict("records")
    d["bids_detail"] = bids[bids.vendor_id == vendor_id].assign(
        bid_date=lambda t: t.bid_date.dt.strftime("%Y-%m-%d")
    ).to_dict("records")
    d["payments_detail"] = payments[payments.vendor_id == vendor_id].assign(
        pay_date=lambda t: t.pay_date.dt.strftime("%Y-%m-%d")
    ).to_dict("records")
    d["relationships_detail"] = relationships[
        (relationships.vendor_a == vendor_id) | (relationships.vendor_b == vendor_id)
    ].assign(
        partner=lambda t: np.where(t.vendor_a == vendor_id, t.vendor_b, t.vendor_a)
    ).to_dict("records")
    return d

@app.get("/network/{vendor_id}")
def network(vendor_id: str):
    if vendor_id not in set(vendors.vendor_id):
        raise HTTPException(404, "Vendor not found")
    seen = {vendor_id}
    edges = []
    rels = relationships[(relationships.vendor_a == vendor_id) | (relationships.vendor_b == vendor_id)]
    for _, r in rels.iterrows():
        other = r.vendor_b if r.vendor_a == vendor_id else r.vendor_a
        seen.add(other)
        edges.append({"source": vendor_id, "target": other, "type": r.relation_type, "strength": int(r.strength)})
    rels2 = relationships[(relationships.vendor_a.isin(seen)) & (relationships.vendor_b.isin(seen))]
    for _, r in rels2.iterrows():
        if r.vendor_a in seen and r.vendor_b in seen:
            edges.append({"source": r.vendor_a, "target": r.vendor_b, "type": r.relation_type, "strength": int(r.strength)})
    # dedupe by (pair, type)
    uniq = {}
    for e in edges:
        key = (frozenset([e["source"], e["target"]]), e["type"])
        if key not in uniq or e["strength"] > uniq[key]["strength"]:
            uniq[key] = e
    nodes = [{"vendor_id": vid, "name": vendors[vendors.vendor_id == vid].iloc[0]["name"],
              "central": vid == vendor_id} for vid in seen]
    return {"nodes": nodes, "edges": list(uniq.values())}