"""Streamlit dashboard for "The Vanishing Dose".

Run with:  streamlit run app.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import data_generator as dg
import feature_engineering as fe
import model as mdl

st.set_page_config(
    page_title="The Vanishing Dose - Medication Adherence Anomaly Detection",
    page_icon="\U0001F48A",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Shared data layer (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Generating synthetic patient cohort...")
def run_pipeline():
    patients = dg.generate_dataset(num_patients=120, seed=2026)
    engine = mdl.AdherenceModel().fit(patients)
    df_results, results = engine.evaluate(patients)
    df_results = df_results.copy()
    label_map = {p["patient_id"]: p for p in patients}
    return patients, df_results, results, label_map


patients, df_results, results, label_map = run_pipeline()

result_by_id = {r["patient_id"]: r for r in results}


def patient_dict_by_id(pid):
    return label_map[pid]


def plot(fig):
    """plotly chart that tolerates Streamlit API differences."""
    try:
        return st.plotly_chart(fig, width="stretch")
    except TypeError:
        return st.plotly_chart(fig, use_container_width=True)


def render_table(df):
    """dataframe that tolerates Streamlit API differences."""
    try:
        return st.dataframe(df, width="stretch", hide_index=True)
    except TypeError:
        return st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Chart builders
# ---------------------------------------------------------------------------
def _refill_supply_end(refill):
    return int(refill["day"] + refill["tablets"] / max(1e-9, refill["dose_per_day"]))


def _patient_timeline(pat, feats):
    refills = pat["refills"]
    figure = go.Figure()

    rows = list(range(len(refills)))
    for i, r in enumerate(refills):
        end = _refill_supply_end(r)
        figure.add_trace(
            go.Scatter(
                x=[r["day"], end],
                y=[rows[i], rows[i]],
                mode="lines",
                line=dict(color="#b7cdb3", width=12),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[r["day"]],
                y=[rows[i]],
                mode="markers",
                marker=dict(color="#2c6e33", size=11, symbol="circle"),
                name="Refill",
                hovertemplate=f"Refill {i + 1} day {r['day']}<extra></extra>",
                showlegend=(i == 0),
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[end],
                y=[rows[i]],
                mode="markers",
                marker=dict(color="#e8a23d", size=10, symbol="star-diamond"),
                name="Expected next refill",
                hovertemplate=f"Expected ~day {end} (supply of refill {i + 1})<extra></extra>",
                showlegend=(i == 0),
            )
        )

    for ch in pat.get("prescription_changes") or []:
        figure.add_vline(
            x=ch["day"],
            line_dash="dash",
            line_color="#7b4f9e",
            annotation_text=f"Dose change → {ch['dose_per_day']}/day",
            annotation_position="top left",
        )

    current_day = pat["current_day"]
    figure.add_vline(x=current_day, line_dash="dot", line_color="#555",
                     annotation_text="today", annotation_position="bottom right")

    if pat.get("symptoms"):
        sym = pat["symptoms"]
        figure.add_trace(
            go.Scatter(
                x=[s["day"] for s in sym],
                y=[s["value"] for s in sym],
                mode="lines",
                name=pat["symptom_name"],
                yaxis="y2",
                line=dict(color="#d64550", width=2, dash="dot"),
            )
        )

    figure.update_layout(
        title="Pharmacy refills over time (x = day since first purchase)",
        height=420,
        yaxis=dict(title="Refill #", showticklabels=False),
        yaxis2=dict(title="Symptom / vital score", overlaying="y", side="right",
                    range=[0, 10], showgrid=False),
        xaxis=dict(range=[-5, current_day + 5]),
        legend=dict(orientation="h", y=-0.25),
        margin=dict(l=10, r=10, t=40, b=10),
        template="plotly_white",
    )
    plot(figure)


def _interval_chart(pat, feats):
    rows = feats.get("_interval_rows", [])
    if not rows:
        st.info("Not enough refill history to plot intervals.")
        return
    idx = [r["index"] + 1 for r in rows]
    lengths = [r["length"] for r in rows]
    expected = [r["expected"] for r in rows]
    baseline = feats["patient_baseline_refill_interval"]

    fig_iv = go.Figure()
    fig_iv.add_trace(
        go.Scatter(x=idx, y=lengths, mode="lines+markers", name="Actual interval (days)",
                   line=dict(color="#1f77b4", width=3), marker=dict(size=9))
    )
    fig_iv.add_trace(
        go.Scatter(x=idx, y=expected, mode="lines", name="Expected supply duration (days)",
                   line=dict(color="#7b4f9e", width=2, dash="dash"))
    )
    mean4 = pd.Series(lengths).rolling(3, min_periods=1).mean().tolist()
    fig_iv.add_trace(
        go.Scatter(x=idx, y=mean4, mode="lines", name="Rolling mean (last 3)",
                   line=dict(color="#e8a23d", width=2, dash="dot"))
    )
    if baseline:
        fig_iv.add_hline(y=baseline, line_dash="dot", line_color="#d64550",
                         annotation_text=f"Patient baseline {baseline:.0f} days",
                         annotation_position="left")

    fig_iv.update_layout(
        title="Refill interval pattern (deviation from the patient's own baseline)",
        height=400,
        xaxis_title="Interval #",
        yaxis_title="Days",
        legend=dict(orientation="h", y=-0.25),
        template="plotly_white",
    )
    plot(fig_iv)

    last_len = lengths[-1] if lengths else np.nan
    dev = feats.get("deviation_from_patient_baseline")
    dev_txt = f"{dev * 100:.0f}%" if dev == dev else "n/a"
    st.markdown(
        f"Last interval: **{last_len:.0f} days** · baseline **{baseline:.0f} days** · "
        f"deviation **{dev_txt}**"
    )


def _signal_chart(pat):
    n_rows = 1 + int(bool(pat.get("vitals"))) + int(bool(pat.get("wearable")))
    specs = [[{"secondary_y": False}] for _ in range(n_rows)]
    fig = make_subplots(rows=n_rows, cols=1, subplot_titles=("Symptoms", "Vitals", "Activity / sleep")[:n_rows])
    r = 1
    if pat.get("symptoms"):
        sym = pat["symptoms"]
        fig.add_trace(
            go.Scatter(x=[s["day"] for s in sym], y=[s["value"] for s in sym],
                       mode="lines", name="Symptoms",
                       line=dict(color="#d64550", width=2), fill="tozeroy", fillcolor="rgba(214,69,80,0.08)"),
            row=r, col=1,
        )
        r += 1
    if pat.get("vitals"):
        for name, obs in pat["vitals"].items():
            fig.add_trace(
                go.Scatter(x=[o["day"] for o in obs], y=[o["value"] for o in obs],
                           mode="lines", name=name),
                row=r, col=1,
            )
        r += 1
    if pat.get("wearable"):
        for name, obs in pat["wearable"].items():
            fig.add_trace(
                go.Scatter(x=[o["day"] for o in obs], y=[o["value"] for o in obs],
                           mode="lines", name=name),
                row=r, col=1,
            )
    fig.update_layout(height=200 + 170 * n_rows, template="plotly_white", margin=dict(l=10, r=10, t=40, b=10))
    plot(fig)

    if pat.get("followups"):
        fu = pat["followups"]
        st.markdown("**Follow-up records**")
        render_table(
            pd.DataFrame(fu)[["day", "response", "note"]]
            .rename(columns={"day": "Day", "response": "Response (0-100)", "note": "Note"})
        )


def _risk_gauge(label, value, bar_color):
    figaux = go.Figure()
    figaux.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "/100", "font": {"size": 22}},
            title={"text": label, "font": {"size": 13}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#ccc"},
                "bar": {"color": bar_color, "thickness": 0.3},
                "steps": [
                    {"range": [0, 35], "color": "#eef5ee"},
                    {"range": [35, 70], "color": "#fdf3e4"},
                    {"range": [70, 100], "color": "#fbeae9"},
                ],
                "threshold": {"line": {"color": "#777", "width": 2},
                              "thickness": 0.8, "value": 50},
            },
        )
    )
    figaux.update_layout(
        height=185,
        margin=dict(l=10, r=10, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    plot(figaux)


def _risk_and_evidence(ires):
    st.markdown("#### Risk profile")
    gauges = st.columns(3)
    with gauges[0]:
        _risk_gauge("Under-use", ires["under_use_risk"], "#2e9e6b")
    with gauges[1]:
        _risk_gauge("Over-use / abnormal utilization", ires["over_use_risk"], "#d64550")
    with gauges[2]:
        _risk_gauge("Overall adherence anomaly", ires["overall_anomaly_risk"], "#1f77b4")

    confcolor = {"Low": "#a0a0a0", "Medium": "#e8a23d", "High": "#2e9e6b"}[ires["confidence"]]
    st.markdown(
        f"**Confidence:** <span class='pill' style='background:{confcolor}'>"
        f"{ires['confidence']} ({ires['confidence_score']}/100)</span> "
        "- driven by history length, number of independent signal groups and "
        "whether several signals point the same way.",
        unsafe_allow_html=True,
    )

    heading = "No clear adherence anomaly - routine picture."
    if ires["under_use_risk"] >= 35 and ires["over_use_risk"] >= 35:
        heading = "Mixed possible use pattern detected - requires review."
    elif ires["under_use_risk"] >= 35:
        heading = "Possible medication under-use pattern detected."
    elif ires["over_use_risk"] >= 35:
        heading = "Possible over-utilisation pattern detected."

    st.markdown(f"### {heading}")
    st.markdown("**Evidence**")
    for item in ires["evidence"]:
        st.markdown(f"- {item}")

    st.markdown("**Alternative possible explanations**")
    for alt in ires["alternative_explanations"]:
        st.markdown(f"- {alt}")

    st.markdown("**Suggested next step**")
    for rec in ires["recommendation"]:
        st.markdown(f"- **{rec}**")

    st.info(ires["conclusion"])

    with st.expander("View raw refill records"):
        rows = []
        for i, r in enumerate(pat["refills"]):
            rows.append(
                {
                    "Refill": i + 1,
                    "Day": r["day"],
                    "Tablets": r["tablets"],
                    "Dose/day": r["dose_per_day"],
                    "Supply (days)": round(r["tablets"] / max(1e-9, r["dose_per_day"]), 1),
                }
            )
        render_table(pd.DataFrame(rows))
RISK_BAND_COLOR = {"Low": "#2e9e6b", "Medium": "#e8a23d", "High": "#d64550"}

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.4rem; }
      .score-table td { padding: 0.15rem 0.6rem 0.15rem 0; }
      .score-table .lab { color: #5b6472; font-size: 0.9rem; }
      .score-table .val { font-weight: 700; font-size: 1.5rem; }
      .pill {
        display: inline-block; padding: 0.15rem 0.7rem; border-radius: 999px;
        color: #fff; font-weight: 600; font-size: 0.85rem;
      }
      .banner {
        padding: 0.7rem 1rem; border-radius: 0.5rem; border: 1px solid #dcdcdc;
        background: #f7f9fb; color: #3a4351; font-size: 0.92rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.markdown("## \U0001F48A The Vanishing Dose")
st.sidebar.caption("Detecting possible medication non-adherence from indirect signals.")

scenario_names = sorted(df_results["scenario"].unique())
sel_scenarios = st.sidebar.multiselect(
    "Scenario filter", scenario_names, default=scenario_names
)

band_options = ["All"] + ["Low", "Medium", "High"]
sel_band = st.sidebar.selectbox("Risk band", band_options, index=0)

flagged_only = st.sidebar.checkbox("Only flagged patients (under / over-use)", value=False)

df_filtered = df_results[df_results["scenario"].isin(sel_scenarios)].copy()
if sel_band != "All":
    df_filtered = df_filtered[df_filtered["risk_band"] == sel_band]
if flagged_only:
    df_filtered = df_filtered[df_filtered["flagged_under"] | df_filtered["flagged_over"]]

if df_filtered.empty:
    st.sidebar.warning("No patients match these filters.")
    st.stop()

ordered = (
    df_filtered.sort_values("overall_anomaly_risk", ascending=False)["patient_id"].tolist()
)
sel_pid = st.sidebar.selectbox("Select patient", ordered)

pat = patient_dict_by_id(sel_pid)
resa = result_by_id[sel_pid]

st.sidebar.divider()
st.sidebar.markdown("**Selected patient**")
st.sidebar.markdown(
    f"`{sel_pid}`  {pat['age']} y · {pat['gender']}  \n"
    f"{pat['medication']} ({pat['medication_class']})  \n"
    f"Scenario: _{pat['scenario_label']}_"
)

# ---------------------------------------------------------------------------
# Overview page
# ---------------------------------------------------------------------------
st.title("The Vanishing Dose")
st.caption(
    "Clinical decision-support prototype - analyzes medication acquisition records, "
    "symptoms, vitals, and wearables over time to surface **possible** adherence "
    "anomalies. Refill data indicates that medication was *obtained*, not that it was *taken*."
)

total = len(df_results)
n_low = int((df_results["risk_band"] == "Low").sum())
n_med = int((df_results["risk_band"] == "Medium").sum())
n_high = int((df_results["risk_band"] == "High").sum())
n_under = int(df_results["flagged_under"].sum())
n_over = int(df_results["flagged_over"].sum())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total patients", total)
c2.metric("Low risk", n_low)
c3.metric("Medium risk", n_med)
c4.metric("High risk", n_high)
c5.metric("Possible under-use", n_under)
c6.metric("Possible over-use", n_over)

tab1, tab2, tab3 = st.tabs(["Risk overview", "Cohort explorer", "About this tool"])

with tab1:
    col_a, col_b = st.columns([1, 1.3])
    with col_a:
        counts = df_results.groupby("risk_band")["patient_id"].count().reindex(
            ["Low", "Medium", "High"], fill_value=0
        )
        figb = go.Figure(
            go.Bar(
                x=counts.index,
                y=counts.values,
                marker_color=[RISK_BAND_COLOR[b] for b in counts.index],
                text=counts.values,
                textposition="outside",
            )
        )
        figb.update_layout(title="Risk band distribution", height=320, yaxis_title="Patients")
        plot(figb)
    with col_b:
        scatter = go.Figure(
            go.Scatter(
                x=df_results["under_use_risk"],
                y=df_results["over_use_risk"],
                mode="markers",
                text=df_results["patient_id"],
                marker=dict(
                    color=[RISK_BAND_COLOR[b] for b in df_results["risk_band"]],
                    size=9,
                    opacity=0.85,
                    line=dict(color="white", width=0.5),
                ),
                customdata=df_results[["overall_anomaly_risk", "confidence"]],
                hovertemplate=(
                    "%{text}<br>under-use %{x:.0f} · over-use %{y:.0f}"
                    "<br>overall %{customdata[0]:.0f} · conf %{customdata[1]}<extra></extra>"
                ),
            )
        )
        scatter.add_hline(y=35, line_dash="dot", line_color="#aaa")
        scatter.add_vline(x=35, line_dash="dot", line_color="#aaa")
        scatter.update_layout(
            title="Under-use vs over-use risk (each patient)",
            height=320,
            xaxis_title="Under-use risk",
            yaxis_title="Over-use risk",
            xaxis=dict(range=[0, 100]),
            yaxis=dict(range=[0, 100]),
        )
        plot(scatter)

with tab2:
    top = df_results.sort_values("overall_anomaly_risk", ascending=False).head(12)[
        ["patient_id", "scenario_label", "under_use_risk", "over_use_risk",
         "overall_anomaly_risk", "confidence", "risk_band"]
    ].copy()
    top.columns = ["Patient", "Scenario", "Under-use", "Over-use", "Overall", "Confidence", "Band"]
    st.dataframe(top.set_index("Patient"))

with tab3:
    st.markdown(
        """
        ### How it works
        For each patient the tool:
        1. **Estimates the expected refill rhythm** from the prescription
           (tablets supplied vs daily dose).
        2. **Learns the patient's own baseline interval** from their refill history,
           ignoring the most recent refill so the latest behaviour can be judged.
        3. **Searches for patterns** - consecutive or widening late intervals,
           suddenly shortened intervals, gaps beyond the expected supply.
        4. **Cross-references non-refill signals** - symptoms, vitals, wearables and
           follow-up response - to corroborate (never to prove) the refill story.
        5. **Ranks patients** with a hybrid rule + IsolationForest model and explains
           its reasoning in plain language.

        ### Why consistent early purchases are *not* automatically over-use
        A patient who always refills 8 days before running out, every single month,
        keeps a deliberate personal buffer. Their refill interval barely varies, so
        their deviation from their *own* baseline is ~0. A suddenly shortened rhythm
        (30 → 28 → 15 → 13 days) is a different story entirely.

        ### What this is not
        This is a decision-support prototype on **synthetic** data. Refills show that
        medication was dispensed, not ingested. There is no clinical accuracy claim.
        """
    )

st.divider()

# ---------------------------------------------------------------------------
# Patient detail
# ---------------------------------------------------------------------------
st.markdown(f"## Patient {sel_pid}  ·  {pat['medication']}")
st.caption(f"Scenario flagged in the data: _{pat['scenario_label']}_")

feats = fe.patient_features(pat)
ires = result_by_id[sel_pid]

band = ires["risk_band"]
color = RISK_BAND_COLOR[band]
st.markdown(
    f"<div class='banner'>Overall anomaly risk <b>{ires['overall_anomaly_risk']:.0f}/100</b> "
    f"<span class='pill' style='background:{color}'>{band}</span> "
    f"· confidence <b>{ires['confidence']}</b> ({ires['confidence_score']}/100) "
    f"· {pat['age']}y {pat['gender']}</div>",
    unsafe_allow_html=True,
)

t_tl, t_iv, t_sig, t_risk = st.tabs(
    ["Timeline", "Refill intervals", "Symptoms / signals", "Risk & evidence"]
)

with t_tl:
    _patient_timeline(pat, feats)
with t_iv:
    _interval_chart(pat, feats)
with t_sig:
    _signal_chart(pat)
with t_risk:
    _risk_and_evidence(ires)

st.divider()
disclaimer = st.container()
with disclaimer:
    st.caption(
        "\U000026A0 This output is generated from synthetic data for demonstration only. "
        "It must never be used to accuse a patient of non-adherence. Clinical assessment "
        "of medication adherence requires patient engagement, dispensing audits and "
        "objective measures of drug exposure. Possession of medication does not equal ingestion."
    )


