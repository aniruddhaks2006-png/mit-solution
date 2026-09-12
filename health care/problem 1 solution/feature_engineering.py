"""Feature engineering for "The Vanishing Dose".

Turns raw per-patient records (refills, prescription changes, symptoms, vitals,
wearables, follow-up notes) into a fixed set of numeric features that a
rule-based scorer and a small anomaly-detection model can consume.

Key idea - patient-specific baselines:

Instead of only comparing refill timing against the prescription, we also learn
the patient's *own* established refill cadence. A patient who has always
refilled 5 days early with a stable interval is NOT treated as an over-user:
their deviation from their personal baseline is ~0 and their rhythm is highly
consistent. A patient whose rhythm suddenly shortens from 30 -> 15 -> 13 days
deviates strongly from their own baseline and IS flagged.

Everything is computed on a "day since first purchase" axis. Missing data
(e.g. no wearables) degrades gracefully to NaN / neutral values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Refill interval helpers
# ---------------------------------------------------------------------------
SHORT_THRESHOLD = 0.82   # interval < 82% of baseline counts as a short interval
LONG_THRESHOLD = 1.18    # interval > 118% of baseline counts as a long interval
OVERDUE_GAP = 1.3        # gap ratio above which the patient is effectively overdue


def _active_dose(day, base_dose, changes):
    """Dose prescribed on a given day, honouring the most recent change."""
    dose = float(base_dose)
    for ch in sorted(changes, key=lambda c: c["day"]):
        if day >= ch["day"]:
            dose = float(ch["dose_per_day"])
    return dose


def _effective_expected_interval(a, b, tablets_a, base_dose, changes):
    """Expected supply duration for interval (a, b].

    If the dose changes mid-interval the effective expected length is computed
    from the time-weighted average daily dose over that interval.
    """
    if b <= a:
        return np.nan
    points = sorted({int(a), int(b)} | {int(ch["day"]) for ch in changes if a < ch["day"] < b})
    total_dose_days = 0.0
    total_time = 0.0
    for x, y in zip(points, points[1:]):
        dose = _active_dose(x, base_dose, changes)
        total_dose_days += dose * (y - x)
        total_time += y - x
    if total_time <= 0:
        return np.nan
    eff_dose = total_dose_days / total_time
    if eff_dose <= 0:
        return np.nan
    return float(tablets_a / eff_dose)


def _interval_features(refills, changes, base_dose):
    """Per-interval records: start/end day, length, expected, regime dose."""
    changes = changes or []
    n = len(refills)
    rows = []
    for i in range(n - 1):
        a = int(refills[i]["day"])
        b = int(refills[i + 1]["day"])
        tablets_a = float(refills[i]["tablets"])
        expected = _effective_expected_interval(a, b, tablets_a, base_dose, changes)
        regime_dose = _active_dose(b, base_dose, changes)  # regime of the interval's end
        transition = int(any(a < ch["day"] < b for ch in changes))
        rows.append(
            {
                "index": i,
                "start_day": a,
                "end_day": b,
                "length": float(b - a),
                "expected": expected,
                "regime_dose": regime_dose,
                "transition": transition,  # interval spans a prescription change
            }
        )
    return rows


def _establish_baseline(interval_rows):
    """Median interval of the current dosage regime, excluding the most recent.

    This is the patient's *established* cadence against which the latest
    behaviour is judged. Intervals that span a prescription change are
    transitional and are excluded - their length mixes two dosage regimes.
    """
    if not interval_rows:
        return None
    last_regime = interval_rows[-1]["regime_dose"]
    clean = [r for r in interval_rows if not r["transition"]]
    regime = [r["length"] for r in clean if abs(r["regime_dose"] - last_regime) < 1e-9]

    pool = regime if len(regime) >= 2 else [r["length"] for r in clean]
    # Reference rhythm = the *established* cadence, so exclude the most recent
    # intervals that we want to judge (2 when enough history, 1 otherwise). This
    # matters for sudden changes: 30,30,28,15,13 must not drag its own baseline
    # down to ~21 and mask a ~54% shortening.
    n_exclude = 2 if len(pool) >= 4 else (1 if len(pool) >= 3 else 0)
    pool = pool[:-n_exclude] if n_exclude else pool
    if len(pool) >= 2:
        return float(np.median(pool))
    if len(regime) >= 1:
        return float(np.median(regime))
    if clean:
        return float(np.median([r["length"] for r in clean]))
    return None


def _streaks(lengths, baseline):
    """Consecutive short/long intervals scanning backwards from the most recent."""
    short_streak = 0
    long_streak = 0
    for length in reversed(lengths):
        if baseline and length < baseline * SHORT_THRESHOLD:
            short_streak += 1
        else:
            break
    for length in reversed(lengths):
        if baseline and length > baseline * LONG_THRESHOLD:
            long_streak += 1
        else:
            break
    return short_streak, long_streak


def _totals(lengths, baseline):
    if not baseline:
        return 0, 0
    short_total = sum(1 for x in lengths if x < baseline * SHORT_THRESHOLD)
    long_total = sum(1 for x in lengths if x > baseline * LONG_THRESHOLD)
    return short_total, long_total


def _rolling(lengths, window=3):
    arr = np.asarray(lengths, dtype=float)
    if len(arr) < window:
        return float(np.mean(arr)), float(np.std(arr))
    recent = arr[-window:]
    return float(np.mean(recent)), float(np.std(recent))


def _slope(xs, ys):
    """Least-squares slope of (x, y)."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    if len(xs) < 2:
        return 0.0
    if np.allclose(xs, xs[0]):
        return 0.0
    slope = np.polyfit(xs, ys, 1)[0]
    return float(slope)


def _trend_stats(obs):
    """From observation series [(day, value)...] return (slope_per_day, recent_z_change)."""
    if not obs:
        return 0.0, 0.0, 0
    arr = np.asarray(obs, dtype=float)
    if arr.ndim != 2 or len(arr) < 2 or arr.shape[1] < 2:
        return 0.0, 0.0, len(arr)
    x = arr[:, 0]
    y = arr[:, 1]
    slope = _slope(x - x.min(), y)
    n = len(y)
    baseline_window = y[: min(3, n)]
    recent_window = y[-2:] if n >= 3 else y
    scale = float(np.std(y))
    if scale <= 1e-9:
        scale = 1.0
    change = float((np.mean(recent_window) - np.mean(baseline_window)) / scale)
    return slope, change, len(y)


def _series(series_maybe):
    return series_maybe if series_maybe else []


def _vital_change(patient, worse_direction="up"):
    """Aggregate vitals into a single worsening-direction z-change."""
    vitals = patient.get("vitals") or {}
    if not vitals:
        return 0.0, 0
    changes = []
    for obs in vitals.values():
        _, z, _ = _trend_stats([(o["day"], o["value"]) for o in _series(obs)])
        if worse_direction == "down":
            z = -z
        changes.append(z)
    return float(np.mean(changes)), sum(1 for o in vitals.values() if len(o) >= 2)


def _wearable_change(patient):
    wearable = patient.get("wearable")
    if not wearable:
        return 0.0, 0
    changes = []
    for obs in wearable.values():
        _, z, _ = _trend_stats([(o["day"], o["value"]) for o in _series(obs)])
        changes.append(-z)  # activity/sleep: declining = worse
    return float(np.mean(changes)), sum(1 for o in wearable.values() if len(o) >= 2)


def _response_change(patient):
    followups = patient.get("followups")
    if not followups:
        return 0.0, 0
    _, z, _ = _trend_stats([(f["day"], f["response"]) for f in followups])
    return -z, len(followups)  # lower response = worse


def signal_direction_matches(dev_from_baseline, symptom_z, vital_z, wearable_z, response_z):
    """True when the refill deviation and physiological signals point the same way.

    Late refills + worsening symptoms is a much stronger (but still indirect)
    multi-signal story than either alone. A negative deviation (early refills) is
    NOT cross-checked against symptom worsening - early refills do not generally
    cause symptoms to worsen, and this keeps us from over-interpreting a buffer.
    """
    if dev_from_baseline is None or np.isnan(dev_from_baseline):
        return False
    if dev_from_baseline > 0.2 and (
        symptom_z > 0.3 or vital_z > 0.3 or wearable_z > 0.3 or response_z > 0.3
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def patient_features(patient: dict) -> dict:
    """Compute the full feature vector for one patient record."""
    refills = patient.get("refills") or []
    changes = patient.get("prescription_changes") or []
    base_dose = float(patient.get("base_daily_dose", 1.0))
    current_day = int(patient.get("current_day", 0))
    n_refills = len(refills)

    interval_rows = _interval_features(refills, changes, base_dose)
    lengths = [r["length"] for r in interval_rows]
    expected_list = [r["expected"] for r in interval_rows]
    n_intervals = len(lengths)

    baseline = _establish_baseline(interval_rows)

    if lengths:
        last_length = lengths[-1]
        last_expected = expected_list[-1] if expected_list[-1] else (baseline or last_length)
    else:
        last_length = np.nan
        last_expected = np.nan

    dev_from_baseline = (
        (last_length - baseline) / baseline if baseline and baseline > 0 else np.nan
    )
    dev_from_expected = (
        (last_length - last_expected) / last_expected if last_expected and np.isfinite(last_expected) and last_expected > 0 else np.nan
    )

    rolling_mean, rolling_std = _rolling(lengths, 3)
    cv = float(np.std(lengths) / np.mean(lengths)) if lengths and np.mean(lengths) > 0 else 0.0

    short_streak, long_streak = _streaks(lengths, baseline)
    short_total, long_total = _totals(lengths, baseline)

    last_refill_day = max((r["day"] for r in refills), default=0)
    last_supply = expected_list[-1] if expected_list and np.isfinite(expected_list[-1]) else (baseline or 30.0)
    gap_ratio = (current_day - last_refill_day) / last_supply if last_supply > 0 else 0.0

    # Recent interval trend (normalised slope over the current regime or all).
    trend_source = lengths
    if len(trend_source) >= 2:
        idx = np.arange(len(trend_source))
        interval_slope = _slope(idx, np.asarray(trend_source)) / (baseline or 30.0)
        sudden_slope = (
            _slope(np.arange(3), np.asarray(trend_source[-3:])) / (baseline or 30.0)
            if len(trend_source) >= 3
            else interval_slope
        )
    else:
        interval_slope, sudden_slope = 0.0, 0.0

    # Signals.
    symptom_slope, symptom_z, n_sym = _trend_stats(
        [(o["day"], o["value"]) for o in _series(patient.get("symptoms"))]
    )
    vital_z, n_vit = _vital_change(patient)
    wearable_z, n_wear = _wearable_change(patient)
    response_z, n_resp = _response_change(patient)

    last_dose_change_day = max((ch["day"] for ch in changes), default=-1)
    dose_recently_changed = bool(changes) and (
        last_dose_change_day >= last_refill_day - 2 * (baseline or 30.0)
    )

    regime_intervals = 0
    if interval_rows:
        last_regime = interval_rows[-1]["regime_dose"]
        regime_intervals = sum(
            1
            for r in interval_rows
            if not r["transition"] and abs(r["regime_dose"] - last_regime) < 1e-9
        )

    signals_worsening = 0
    if patient.get("symptoms"):
        signals_worsening += int(symptom_z > 0.5)
    if n_vit:
        signals_worsening += int(vital_z > 0.5)
    if n_wear:
        signals_worsening += int(wearable_z > 0.5)
    if n_resp:
        signals_worsening += int(response_z > 0.5)

    symptom_dir = 1.0 if symptom_z > 0.5 else (0.0 if abs(symptom_z) <= 0.5 else -1.0)
    agreement = signal_direction_matches(dev_from_baseline, symptom_z, vital_z, wearable_z, response_z)

    return {
        "patient_id": patient["patient_id"],
        "scenario": patient.get("scenario", "unknown"),
        "n_refills": n_refills,
        "n_intervals": n_intervals,
        "current_day": current_day,
        "last_refill_day": last_refill_day,
        "expected_supply_days": last_expected,
        "actual_refill_interval": last_length,
        "refill_deviation_from_expected": dev_from_expected,
        "rolling_mean_refill_interval": rolling_mean,
        "rolling_std_refill_interval": rolling_std,
        "patient_baseline_refill_interval": baseline,
        "deviation_from_patient_baseline": dev_from_baseline,
        "refill_pattern_consistency": cv,
        "consecutive_early_or_short_intervals": float(short_streak),
        "consecutive_late_or_long_intervals": float(long_streak),
        "short_intervals_total": float(short_total),
        "long_intervals_total": float(long_total),
        "interval_slope": interval_slope,
        "sudden_slope": sudden_slope,
        "refill_gap_risk": gap_ratio,
        "regime_intervals": regime_intervals,
        "dose_changed_recently": int(dose_recently_changed),
        "symptom_slope": symptom_slope,
        "symptom_z_change": symptom_z,
        "vital_z_change": vital_z,
        "wearable_z_change": wearable_z,
        "response_z_change": response_z,
        "symptom_dir": symptom_dir,
        "signal_agreement": agreement,
        "signals_worsening": float(signals_worsening),
        "n_signal_groups": int(bool(patient.get("symptoms")))
        + int(bool(patient.get("vitals")))
        + int(bool(patient.get("wearable")))
        + int(bool(patient.get("followups"))),
        "_interval_rows": interval_rows,
        "_changes": changes,
        "_base_dose": base_dose,
    }


def build_feature_frame(patients: list) -> pd.DataFrame:
    """Compute the feature vector for every patient and return a DataFrame."""
    rows = []
    for p in patients:
        f = patient_features(p)
        keep = {k: v for k, v in f.items() if not k.startswith("_")}
        rows.append(keep)
    df = pd.DataFrame(rows)
    for col in df.columns:
        if col not in ("patient_id", "scenario"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df