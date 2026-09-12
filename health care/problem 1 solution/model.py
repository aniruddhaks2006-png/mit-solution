"""Hybrid adherence-anomaly model for "The Vanishing Dose".

Approach (deliberately pragmatic, prototype-grade):

1. Rule-based, explainable scoring of refill timing against BOTH the
   prescription expectation and the patient's own established interval.
2. A small IsolationForest fitted on well-behaved synthetic patients to flag
   unusual multi-signal configurations (the ML component).
3. A transparent weighted combination -> Under-use risk, Over-use risk, Overall
   anomaly risk (each 0-100) plus a Low/Medium/High confidence label.

Medical safety is baked into the outputs: everything is phrased as "possible",
"pattern", "suggests"; refill data only proves medication was obtained, not that
it was ingested.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

import feature_engineering as fe

HEALTHY_SCENARIOS = {
    "normal_adherence",
    "stable_buffer",
}

RISK_CUT = 25.0   # below this overall risk we treat patients as routine monitoring
RISK_MED = 45.0   # above this overall risk the patient lands in the high band

IF_COLS = [
    "n_intervals",
    "expected_supply_days",
    "actual_refill_interval",
    "patient_baseline_refill_interval",
    "deviation_from_patient_baseline",
    "refill_pattern_consistency",
    "consecutive_early_or_short_intervals",
    "consecutive_late_or_long_intervals",
    "interval_slope",
    "sudden_slope",
    "refill_gap_risk",
    "symptom_z_change",
    "vital_z_change",
    "wearable_z_change",
    "response_z_change",
    "signals_worsening",
    "n_signal_groups",
]

def _clamp01(x):
    return 0.0 if np.isnan(x) else float(min(1.0, max(0.0, x)))


def _lerp(x, lo, hi):
    if hi == lo:
        return 0.0
    return _clamp01((float(x) - lo) / (hi - lo))


def _when_not_nan(v, default=0.0):
    return float(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else default


class AdherenceModel:
    """Fit + score pipeline. Fit once on the whole synthetic cohort."""

    def __init__(self, random_state=42, contamination=0.1):
        self.random_state = random_state
        self.contamination = contamination
        self.iso_forest = None
        self.if_scale = None
        self.if_offset = None
        self.column_medians = None
        self.feature_cols = IF_COLS

    # ------------------------------------------------------------------ fit
    def fit(self, patients):
        features = fe.build_feature_frame(patients)
        healthy = features[features["scenario"].isin(HEALTHY_SCENARIOS)].copy()
        healthy["_fit_sort"] = np.arange(len(healthy))
        healthy = healthy.sort_values("_fit_sort")

        self.column_medians = healthy[self.feature_cols].median()

        X_healthy = healthy[self.feature_cols].fillna(value=0.0).to_numpy(dtype=float)
        # Replace remaining infinities, then fit.
        X_healthy = np.nan_to_num(X_healthy, nan=0.0, posinf=0.0, neginf=0.0)

        self.iso_forest = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=120,
        ).fit(X_healthy)

        scores = self.iso_forest.score_samples(X_healthy)
        self.if_offset = float(np.quantile(scores, 0.10))
        self.if_scale = max(1e-9, float(-(scores.min() - self.if_offset)))
        return self

    # -------------------------------------------------------------- risk
    def _iso_risk(self, row):
        """Map an IsolationForest score to a 0-100 anomaly risk."""
        if self.iso_forest is None:
            return 0.0
        x = np.full(len(self.feature_cols), np.nan, dtype=float)
        for j, col in enumerate(self.feature_cols):
            v = row.get(col, np.nan)
            x[j] = self.column_medians[col] if pd.isna(v) else v
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        score = float(self.iso_forest.score_samples(x.reshape(1, -1))[0])
        risk = 100.0 * _clamp01((self.if_offset - score) / self.if_scale)
        return risk

    def _under_use_risk(self, f):
        dev = _when_not_nan(f["deviation_from_patient_baseline"])
        dev_exp = _when_not_nan(f["refill_deviation_from_expected"])
        streak = _when_not_nan(f["consecutive_late_or_long_intervals"])
        slope = _when_not_nan(f["interval_slope"])
        gap = _when_not_nan(f["refill_gap_risk"])

        dev_w = _lerp(max(0.0, dev), 0.0, 0.5)
        streak_w = _clamp01(streak / 3.0)
        trend_w = _lerp(max(0.0, slope), 0.0, 0.6)
        gap_w = _lerp(max(0.0, gap - 1.0), 0.0, 2.0)
        exp_w = _lerp(max(0.0, dev_exp), 0.0, 1.0)
        agree_w = 1.0 if f.get("signal_agreement") else 0.0

        weights = np.array([0.35, 0.25, 0.10, 0.15, 0.10, 0.15])
        comps = np.array([dev_w, streak_w, trend_w, gap_w, exp_w, agree_w])
        raw = float(np.dot(weights, comps) / weights.sum())

        # Repeated/trending lateness matters far more than a single late refill.
        if streak >= 2:
            raw *= 1.30
        if streak >= 3:
            raw *= 1.25
        if f.get("dose_changed_recently") and _when_not_nan(f["regime_intervals"]) < 3:
            raw *= 0.6  # recalibrating baselines after a legitimate dose change
        return _clamp01(raw) * 95.0

    def _over_use_risk(self, f):
        dev = _when_not_nan(f["deviation_from_patient_baseline"])
        dev_exp = _when_not_nan(f["refill_deviation_from_expected"])
        streak = _when_not_nan(f["consecutive_early_or_short_intervals"])
        sudden = _when_not_nan(f["sudden_slope"])
        total_early = _when_not_nan(f["short_intervals_total"])

        short_w = _lerp(max(0.0, -dev), 0.0, 0.6)
        streak_w = _clamp01(streak / 3.0)
        sudden_w = _lerp(max(0.0, -sudden), 0.0, 0.5)
        exp_w = _lerp(max(0.0, -dev_exp), 0.0, 0.7)
        persistence_w = _clamp01(total_early / 5.0)

        weights = np.array([0.42, 0.26, 0.14, 0.12, 0.06])
        comps = np.array([short_w, streak_w, sudden_w, exp_w, persistence_w])
        raw = float(np.dot(weights, comps) / weights.sum())

        # Consistency attenuation: a patient who ALWAYS refills 5 days early with
        # a rock-stable interval is maintaining a buffer, not demonstrating a new
        # over-utilisation pattern. High consistency dampens the score heavily.
        cv = _when_not_nan(f["refill_pattern_consistency"])
        consistency_bonus = 1.0 - _lerp(cv, 0.08, 0.4)
        raw *= (1.0 - 0.85 * consistency_bonus)

        # A sudden change (not a stable buffer) is far more interesting.
        if cv > 0.25 and streak >= 2:
            raw = min(1.0, raw * 1.25)
        if f.get("dose_changed_recently") and _when_not_nan(f["regime_intervals"]) < 3:
            raw *= 0.5
        return _clamp01(raw) * 100.0

    def _confidence(self, f, under, over, if_risk):
        n_refills = _when_not_nan(f["n_refills"])
        n_intervals = _when_not_nan(f["n_intervals"])
        n_groups = _when_not_nan(f["n_signal_groups"])
        agreement = 1.0 if f.get("signal_agreement") else 0.0

        score = 20.0
        score += min(n_refills, 8) * 3.0
        score += n_groups * 4.0
        score += 12.0 * agreement
        directional_max = max(under, over)
        if if_risk > 40.0 and directional_max > 40.0:
            score += 12.0  # refill rules AND ML agree on an anomaly
        if n_intervals < 3:
            score -= 20.0
        if n_intervals < 1:
            score -= 10.0
        if n_groups < 2:
            score -= 8.0
        score = float(np.clip(score, 8.0, 99.0))

        if score < 45.0:
            label = "Low"
        elif score < 70.0:
            label = "Medium"
        else:
            label = "High"
        return round(score), label

    def _overall_risk(self, f, under, over, if_risk):
        directional = max(under, over)
        worsening_rate = _when_not_nan(f["signals_worsening"]) / max(1.0, _when_not_nan(f["n_signal_groups"]))
        combo = _clamp01(0.6 * (1.0 if f.get("signal_agreement") else 0.0) + 0.4 * worsening_rate)
        clinical_concern = 100.0 * combo

        n_intervals = _when_not_nan(f["n_intervals"])
        if n_intervals < 2:
            # Not enough history to trust multi-signal machinery -> rules only.
            overall = directional
        else:
            blend = 0.55 * directional + 0.2 * if_risk + 0.25 * clinical_concern
            # A patient whose refills look fine but whose symptoms/vitals/activity
            # all worsen concurrently deserves a clinical (non-adherence) review.
            overall = max(blend, clinical_concern)

        if f.get("dose_changed_recently") and _when_not_nan(f["regime_intervals"]) < 3:
            overall = min(overall, 35.0)  # legitimate regime change; don't over-flag
        return float(_clamp01(overall / 100.0) * 100.0)

    # ---------------------------------------------------------- evaluation
    def evaluate(self, patients):
        results = []
        for p in patients:
            f = fe.patient_features(p)
            under = self._under_use_risk(f)
            over = self._over_use_risk(f)
            if_risk = self._iso_risk(f)
            overall = self._overall_risk(f, under, over, if_risk)
            conf_score, conf_label = self._confidence(f, under, over, if_risk)

            if overall < RISK_CUT:
                band = "Low"
            elif overall < RISK_MED:
                band = "Medium"
            else:
                band = "High"

            evidence = build_evidence(f, under, over)
            alt = alternative_explanations(f, under, over)
            recommendation = recommend(overall, under, over, conf_label)
            conclusion = (
                "Further clinical review is recommended. This is a decision-support "
                "indicator based on medication acquisition records and indirect signals; "
                "it is not proof of non-adherence."
            )

            results.append(
                {
                    "patient_id": p["patient_id"],
                    "scenario": p.get("scenario", "unknown"),
                    "scenario_label": p.get("scenario_label", ""),
                    "medication": p["medication"],
                    "medication_class": p["medication_class"],
                    "under_use_risk": round(float(under), 1),
                    "over_use_risk": round(float(over), 1),
                    "overall_anomaly_risk": round(float(overall), 1),
                    "risk_band": band,
                    "confidence_score": conf_score,
                    "confidence": conf_label,
                    "iso_risk": round(float(if_risk), 1),
                    "flagged_under": float(under) >= 35.0,
                    "flagged_over": float(over) >= 35.0,
                    "evidence": evidence,
                    "alternative_explanations": alt,
                    "recommendation": recommendation,
                    "conclusion": conclusion,
                    "_features": f,
                }
            )
        df = pd.DataFrame(
            [
                {k: v for k, v in r.items() if not k.startswith("_") and k != "_features"}
                for r in results
            ]
        )
        return df, results


# ---------------------------------------------------------------------------
# Explainability
# ---------------------------------------------------------------------------
def _round1(x):
    return 0.0 if x is None or np.isnan(x) else round(float(x), 1)


def build_evidence(f, under, over):
    ev = []
    dev = _when_not_nan(f["deviation_from_patient_baseline"])
    dev_exp = _when_not_nan(f["refill_deviation_from_expected"])
    baseline = f["patient_baseline_refill_interval"]
    last_len = _when_not_nan(f["actual_refill_interval"])
    base = _round1(baseline) if baseline else None
    rows = f.get("_interval_rows", [])

    if under >= 35.0 and dev > 0.15 and baseline:
        ev.append(
            f"Most recent refill interval ({_round1(last_len)} days) is ~{abs(round(dev * 100))}% "
            f"longer than the patient's established {base:.0f}-day interval."
        )
    if over >= 35.0 and dev < -0.15 and baseline:
        ev.append(
            f"Most recent refill interval ({_round1(last_len)} days) is ~{abs(round(dev * 100))}% "
            f"shorter than the patient's established {base:.0f}-day interval."
        )

    short_streak = int(_when_not_nan(f["consecutive_early_or_short_intervals"]))
    long_streak = int(_when_not_nan(f["consecutive_late_or_long_intervals"]))
    if short_streak >= 2:
        ev.append(f"{short_streak} consecutive short refill intervals detected in a row.")
    if long_streak >= 2:
        ev.append(f"{long_streak} consecutive late refill intervals detected in a row.")

    # Clinical-status story: refills look fine, but signals turned for the worse.
    sym_z = _when_not_nan(f["symptom_z_change"])
    vit_z = _when_not_nan(f["vital_z_change"])
    wear_z = _when_not_nan(f["wearable_z_change"])
    if under < 35.0 and over < 35.0 and _when_not_nan(f["signals_worsening"]) >= 2:
        ev.append(
            "Refill timing itself shows no anomaly, but symptom / vital / activity "
            "trends worsened concurrently - this may reflect clinical status rather "
            "than an adherence problem."
        )

    # Trend story from the actual interval series.
    if len(rows) >= 2 and (under >= 30 or over >= 30):
        recent = rows[-4:]
        nums = [int(round(r["length"])) for r in recent]
        ref = baseline if baseline else None
        if ref:
            if over >= 30 and nums[-1] < nums[0]:
                ev.append(f"Refill intervals shortened from {nums[0]} to {nums[-1]} days across recent refills.")
            elif under >= 30 and nums[-1] > nums[0]:
                ev.append(f"Refill intervals lengthened from {nums[0]} to {nums[-1]} days across recent refills.")

    gap = _when_not_nan(f["refill_gap_risk"])
    if gap > 1.3:
        ev.append(
            f"Estimated {round(gap * 100)}% of the last prescribed supply has elapsed without a new "
            "pharmacy purchase (gap risk)."
        )

    if _when_not_nan(f["refill_deviation_from_expected"]) < -0.15 and (
        over >= 35.0 or _when_not_nan(f["refill_pattern_consistency"]) > 0.2
    ):
        ev.append(
            f"Refill timing is consistently earlier than the prescribed supply would allow "
            f"(expected ~{_round1(f['expected_supply_days'])} days per refill)."
        )

    cv = _when_not_nan(f["refill_pattern_consistency"])
    dev_exp = _when_not_nan(f["refill_deviation_from_expected"])
    if over < 35.0 and cv < 0.08 and dev_exp < -0.05 and _when_not_nan(f["n_intervals"]) >= 5:
        ev.append(
            "Refills are consistently a little ahead of the prescribed supply with a highly "
            "stable rhythm - this strongly resembles a deliberate medication buffer rather "
            "than an over-utilisation pattern."
        )

    if sym_z > 0.5:
        ev.append(f"Symptom scores rose ~{sym_z:.1f} standard deviations above baseline during the observation window.")
    if vit_z > 0.5:
        ev.append(f"Vital-sign trends drifted in a worsening direction (~{vit_z:.1f} SD from baseline).")
    if wear_z > 0.5:
        ev.append(f"Wearable activity / sleep indicators declined (~{wear_z:.1f} SD from baseline).")
    resp_z = _when_not_nan(f["response_z_change"])
    if resp_z > 0.5:
        ev.append("Follow-up reports of treatment response have declined.")

    if f.get("dose_changed_recently"):
        ev.append("A recent prescription change was recorded; refill baselines may still be recalibrating.")
    elif under >= 35 or over >= 35:
        ev.append("No recent prescription change was recorded that would explain the refill pattern change.")

    # Keep the list concise and ordered strongest-first.
    if not ev:
        ev.append("No single strong pattern detected; overall picture is routine.")
    return ev[:8]


# ---------------------------------------------------------------------------
# Alternative explanations (always show uncertainty)
# ---------------------------------------------------------------------------
def alternative_explanations(f, under, over):
    alts = [
        "Difficulty accessing the pharmacy, transport, or financial barriers",
        "Medication may have been obtained through another channel (records may be incomplete)",
        "Prescription / dispensing records may be incomplete or split across pharmacies",
        "Temporary change in the patient's schedule or clinical condition",
        "The patient may keep a deliberate reserve or buffer of medication",
        "Possession of medication does not confirm it was taken",
    ]
    if over >= 35:
        specifics = [
            "A dose escalation or titration may not yet be recorded",
            "A different pack size may have been dispensed at the pharmacy",
            "Medication may be shared with a household member",
        ]
        alts = specifics + alts
    if under >= 35:
        specifics = [
            "The patient may have been advised to pause or adjust therapy",
            "Symptoms may relate to a separate or evolving condition",
            "The medication may have been switched to a different brand or route not captured here",
        ]
        alts = specifics + alts
    return list(dict.fromkeys([a for a in alts]))


def recommend(overall, under, over, confidence):
    deducs = []
    if overall < RISK_CUT:
        deducs.append("Continue routine monitoring")
    if RISK_CUT <= overall < RISK_MED:
        deducs.append("Review at next follow-up")
    if RISK_MED <= overall < 70:
        deducs.append("Consider contacting the patient to discuss refill patterns")
    if overall >= 70 or (overall >= RISK_MED and confidence in ("Medium", "High") and (under >= 50 or over >= 50)):
        deducs.append("Further clinical investigation recommended")
    if not deducs:
        deducs.append("Continue routine monitoring")
    return deducs