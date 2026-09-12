
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from pathlib import Path
from math import radians, sin, cos, asin, sqrt

BASE = Path(__file__).resolve().parent.parent / "data"
app = FastAPI(title="Medicine Shortage Early Warning System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fac = pd.read_csv(BASE/"facilities.csv")
med = pd.read_csv(BASE/"medicines.csv")
inv = pd.read_csv(BASE/"inventory.csv", parse_dates=["date"])

def haversine(a_lat, a_lon, b_lat, b_lon):
    p = np.pi/180
    a = 0.5 - np.cos((b_lat-a_lat)*p)/2 + np.cos(a_lat*p)*np.cos(b_lat*p)*(1-np.cos((b_lon-a_lon)*p))/2
    return 12742 * np.arcsin(np.sqrt(a))

def analyze():
    latest_date = inv.date.max()
    latest = inv[inv.date == latest_date].copy()
    latest = latest.merge(med, on="medicine_id").merge(fac, on="facility_id")

    # Rolling demand and days-of-stock features
    inv2 = inv.sort_values("date").copy()
    inv2["consumption_14d"] = inv2.groupby(["facility_id","medicine_id"])["daily_consumption"].transform(
        lambda x: x.rolling(14, min_periods=3).mean()
    )
    last = inv2[inv2.date == latest_date].copy()
    last = last.merge(med, on="medicine_id").merge(fac, on="facility_id")
    last["days_of_stock"] = last["stock_on_hand"] / last["consumption_14d"].replace(0, np.nan)
    last["days_of_stock"] = last["days_of_stock"].replace([np.inf,-np.inf], np.nan).fillna(999)

    # Trend: compare recent demand to prior demand
    def trend(g):
        g = g.sort_values("date")
        recent = g.tail(14)["daily_consumption"].mean()
        prior = g.tail(42).head(28)["daily_consumption"].mean()
        return (recent-prior)/max(prior,1)
    trends = inv.groupby(["facility_id","medicine_id"]).apply(trend, include_groups=False).reset_index(name="demand_trend")
    last = last.merge(trends, on=["facility_id","medicine_id"])

    # Risk score: stockout proximity + demand acceleration + low stock vs normal
    last["stock_risk"] = np.clip((14-last.days_of_stock)/14, 0, 1)
    last["demand_risk"] = np.clip(last.demand_trend/0.5, 0, 1)
    last["inventory_ratio"] = last.stock_on_hand / last.normal_stock
    last["low_inventory_risk"] = np.clip((0.45-last.inventory_ratio)/0.45, 0, 1)
    last["risk_score"] = (0.55*last.stock_risk + 0.30*last.demand_risk + 0.15*last.low_inventory_risk)*100

    last["risk_level"] = pd.cut(
        last.risk_score, [-1,30,60,100], labels=["Low","Medium","High"]
    ).astype(str)

    last["confidence"] = np.clip(
        55 + 25*np.minimum(last.days_of_stock.notna(),1) + 20*np.minimum(last["consumption_14d"]/5,1), 0, 100
    ).round()

    return last

@app.get("/facilities")
def facilities():
    return fac.to_dict("records")

@app.get("/medicines")
def medicines():
    return med.to_dict("records")

@app.get("/analytics/overview")
def overview():
    x = analyze()
    return {
        "date": str(inv.date.max().date()),
        "high_risk": int((x.risk_level=="High").sum()),
        "medium_risk": int((x.risk_level=="Medium").sum()),
        "low_risk": int((x.risk_level=="Low").sum()),
        "potential_stockouts_14d": int((x.days_of_stock <= 14).sum()),
        "facilities": len(fac),
        "medicines": len(med),
    }

@app.get("/shortages")
def shortages():
    x = analyze()
    cols = ["facility_id","facility_name","city","medicine_id","medicine_name",
            "stock_on_hand","days_of_stock","demand_trend","risk_score","risk_level","confidence"]
    return x[cols].sort_values("risk_score", ascending=False).round(2).to_dict("records")

@app.get("/facility/{facility_id}")
def facility_detail(facility_id: str):
    if facility_id not in set(fac.facility_id):
        raise HTTPException(404, "Facility not found")
    x = analyze()
    out = x[x.facility_id == facility_id].copy()
    return out.round(2).to_dict("records")

@app.get("/redistribution/{medicine_id}")
def redistribution(medicine_id: str):
    x = analyze()
    x = x[x.medicine_id == medicine_id].copy()
    if x.empty:
        raise HTTPException(404, "Medicine not found")
    needy = x[x.days_of_stock < 14].copy()
    donors = x[x.days_of_stock > 30].copy()
    recs = []
    for _, n in needy.iterrows():
        best = None
        for _, d in donors.iterrows():
            if d.facility_id == n.facility_id: continue
            dist = haversine(n.lat,n.lon,d.lat,d.lon)
            if best is None or dist < best["distance_km"]:
                best = {"donor":d,"distance_km":dist}
        if best:
            recs.append({
                "medicine": n.medicine_name,
                "from_facility": best["donor"].facility_name,
                "to_facility": n.facility_name,
                "distance_km": round(best["distance_km"],1),
                "donor_days_stock": round(float(best["donor"].days_of_stock),1),
                "recipient_days_stock": round(float(n.days_of_stock),1),
                "priority": "High" if n.days_of_stock < 7 else "Medium"
            })
    return recs
