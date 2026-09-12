from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data"
app = FastAPI(title="Post-Award Contract Change Monitoring System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

contracts = pd.read_csv(BASE/"contracts.csv", parse_dates=["award_date","baseline_end_date","revised_end_date"])
materials = pd.read_csv(BASE/"materials.csv")
changes = pd.read_csv(BASE/"changes.csv", parse_dates=["change_date"])
history = pd.read_csv(BASE/"contract_history.csv")

COST_THRESHOLD = 10.0      # % above awarded value
SCHEDULE_DAYS = 30          # days slippage
MATERIAL_THRESHOLD = 15.0   # % change on a single pay item

def analyze():
    x = contracts.copy()

    # Cost variance vs original commitment
    x["cost_delta_pct"] = (x.current_approved_value_mn - x.awarded_value_mn) / x.awarded_value_mn * 100

    # Schedule variance vs original commitment
    duration = (x.baseline_end_date - x.award_date).dt.days
    x["schedule_delta_days"] = (x.revised_end_date - x.baseline_end_date).dt.days
    x["schedule_delta_pct"] = x.schedule_delta_days / duration.replace(0, np.nan) * 100

    # Contractor / subcontractor substitution
    x["contractor_changed"] = (x.contractor_baseline != x.contractor_current).astype(int)

    # Material / scope variance vs baseline bill of quantities
    mat = materials.copy()
    mat["qty_delta_pct"] = (mat.current_qty - mat.baseline_qty) / mat.baseline_qty.replace(0, np.nan) * 100
    mat_agg = (
        mat.groupby("contract_id").apply(
            lambda g: g.qty_delta_pct.abs().max(), include_groups=False
        ).reset_index(name="material_delta_pct")
    )
    x = x.merge(mat_agg, on="contract_id", how="left")
    x["material_delta_pct"] = x.material_delta_pct.fillna(0)

    # Change-order volume
    co = changes.groupby("contract_id").agg(
        co_count=("change_id", "count"),
        net_value_delta=("delta_value_mn", "sum"),
    ).reset_index()
    x = x.merge(co, on="contract_id", how="left")
    x["co_count"] = x.co_count.fillna(0).astype(int)
    x["net_value_delta"] = x.net_value_delta.fillna(0)

    # Evidence completeness (supporting documents attached vs referenced)
    ev = changes.groupby("contract_id").agg(
        docs=("evidence_doc", "count"),
        missing=("evidence_doc", lambda s: (s == "MISSING").sum()),
    ).reset_index()
    x = x.merge(ev, on="contract_id", how="left")
    x["docs"] = x.docs.fillna(0).astype(int)
    x["missing"] = x.missing.fillna(0).astype(int)
    x["evidence_ratio"] = np.where(x.docs > 0, 1 - x.missing / x.docs, 1.0).clip(0, 1)

    # Significant variation triggers (meaningful change flags)
    flags = []
    for _, r in x.iterrows():
        f = []
        if r.cost_delta_pct > COST_THRESHOLD:
            f.append(f"Approved value is {r.cost_delta_pct:.0f}% above the awarded value (was ₹{r.awarded_value_mn:.0f} cr, now ₹{r.current_approved_value_mn:.0f} cr).")
        if r.schedule_delta_days > SCHEDULE_DAYS:
            f.append(f"Completion slipped {r.schedule_delta_days:.0f} days vs baseline (-{r.schedule_delta_pct:.0f}% of planned duration).")
        if r.contractor_changed == 1:
            f.append(f"Contractor substituted: {r.contractor_baseline} → {r.contractor_current}. Re-mobilisation may affect cost and quality continuity.")
        if r.material_delta_pct > MATERIAL_THRESHOLD:
            f.append(f"Bill of quantities deviates from baseline by up to {r.material_delta_pct:.0f}% on one pay item.")
        if r.missing > 0:
            f.append(f"{r.missing} of {r.docs} referenced change document(s) are missing — additional evidence required.")
        if r.co_count > 3:
            f.append(f"{r.co_count} change orders raised; frequent amendment pattern warrants closer review.")
        flags.append("||".join(f))
    x["flags"] = flags

    # Explainable scrutiny score: cost, schedule, substitution, scope, evidence
    x["cost_risk"] = np.clip(x.cost_delta_pct / 30.0, 0, 1)
    x["sched_risk"] = np.clip(x.schedule_delta_days / 120.0, 0, 1)
    x["contractor_risk"] = x.contractor_changed.astype(float)
    x["scope_risk"] = np.clip(x.material_delta_pct / 30.0, 0, 1)
    x["evidence_risk"] = 1 - x.evidence_ratio
    x["scrutiny_score"] = (
        0.35 * x.cost_risk + 0.25 * x.sched_risk + 0.20 * x.contractor_risk +
        0.10 * x.scope_risk + 0.10 * x.evidence_risk
    ) * 100

    # Floor rules: substitution or >50% missing evidence always needs review
    x["scrutiny_score"] = np.maximum(x.scrutiny_score, np.where(x.contractor_changed == 1, 55, 0))
    x["scrutiny_score"] = np.maximum(x.scrutiny_score, np.where(x.evidence_ratio < 0.5, 45, 0))
    x["scrutiny_score"] = x.scrutiny_score.round(1)

    x["review_priority"] = pd.cut(x.scrutiny_score, [-1, 30, 60, 100], labels=["Low", "Medium", "High"]).astype(str)
    return x

def row_extra(r):
    rec = r.to_dict()
    rec["flags"] = rec["flags"].split("||") if rec.get("flags") else []
    rec["awarded_value_mn"] = round(float(rec["awarded_value_mn"]), 1)
    rec["current_approved_value_mn"] = round(float(rec["current_approved_value_mn"]), 1)
    for k in ["cost_delta_pct","schedule_delta_days","schedule_delta_pct","material_delta_pct","net_value_delta","evidence_ratio","scrutiny_score"]:
        if k in rec:
            rec[k] = round(float(rec[k]), 1)
    for k in ["award_date","baseline_end_date","revised_end_date"]:
        if k in rec:
            rec[k] = str(pd.Timestamp(rec[k]).date())
    return rec

@app.get("/contracts")
def contracts_all():
    x = analyze()
    cols = ["contract_id","title","agency","region","category","contractor_baseline","contractor_current",
            "awarded_value_mn","current_approved_value_mn","cost_delta_pct","schedule_delta_days",
            "contractor_changed","material_delta_pct","co_count","evidence_ratio","scrutiny_score","review_priority"]
    return x[cols].sort_values("scrutiny_score", ascending=False).apply(row_extra, axis=1).tolist()

@app.get("/analytics/overview")
def overview():
    x = analyze()
    return {
        "date": str(contracts.award_date.max().date()),
        "contracts": len(x),
        "high_priority": int((x.review_priority == "High").sum()),
        "medium_priority": int((x.review_priority == "Medium").sum()),
        "low_priority": int((x.review_priority == "Low").sum()),
        "cost_overruns": int((x.cost_delta_pct > 10).sum()),
        "schedule_slips": int((x.schedule_delta_days > 30).sum()),
        "contractor_changes": int(x.contractor_changed.sum()),
        "evidence_gaps": int((x.missing > 0).sum()),
        "total_change_orders": int(x.co_count.sum()),
    }

@app.get("/scrutiny")
def scrutiny():
    x = analyze()
    return x[["contract_id","title","agency","region","awarded_value_mn","current_approved_value_mn",
              "cost_delta_pct","schedule_delta_days","contractor_changed","contractor_baseline",
              "contractor_current","material_delta_pct","co_count","missing","docs","evidence_ratio",
              "scrutiny_score","review_priority","flags"]].sort_values("scrutiny_score", ascending=False).apply(row_extra, axis=1).tolist()

@app.get("/contract/{contract_id}")
def contract_detail(contract_id: str):
    x = analyze()
    if contract_id not in set(x.contract_id):
        raise HTTPException(404, "Contract not found")
    rec = row_extra(x[x.contract_id == contract_id].iloc[0])
    rec["changes"] = changes[changes.contract_id == contract_id].sort_values("change_date").assign(
        change_date=lambda d: d.change_date.dt.strftime("%Y-%m-%d"),
        delta_value_mn=lambda d: d.delta_value_mn.round(1),
    ).to_dict("records")
    rec["materials_progress"] = materials[materials.contract_id == contract_id].assign(
        qty_delta_pct=lambda d: ((d.current_qty - d.baseline_qty) / d.baseline_qty * 100).round(1),
    ).to_dict("records")
    rec["history"] = history[history.contract_id == contract_id].to_dict("records")
    return rec

@app.get("/evidence/{contract_id}")
def evidence(contract_id: str):
    if contract_id not in set(contracts.contract_id):
        raise HTTPException(404, "Contract not found")
    c = changes[changes.contract_id == contract_id].copy()
    c["change_date"] = c.change_date.dt.strftime("%Y-%m-%d")
    c["evidence"] = c.evidence_doc.map(lambda x: "Missing" if x == "MISSING" else "On file")
    return c.to_dict("records")