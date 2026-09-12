"""Synthetic patient data generator for "The Vanishing Dose".

No real healthcare data is used anywhere in this project. Every record below is
programmatically synthesised so the demo has realistic timing, noise and missing
data, while never pretending to be a real clinical dataset.

Timeline convention: all time points are expressed as "day" = number of days
after the patient's first recorded pharmacy purchase (day 0).
"""

from __future__ import annotations

import numpy as np

DEFAULT_SEED = 2026

# ---------------------------------------------------------------------------
# Medication profiles (all synthetic)
# ---------------------------------------------------------------------------
MEDICATION_PROFILES = {
    "Metformin": {
        "class": "Antidiabetic",
        "typical_dose_per_day": 1.0,
        "tablets_per_refill": 30,
        "symptom_name": "Glycemic control index (0-10, lower is better)",
        "symptom_base": 6.4,
        "symptom_sigma": 0.5,
        "vitals": {
            "HbA1c (%)": {"base": 7.1, "sigma": 0.15, "worse_direction": "up"},
            "Weight (kg)": {"base": 83.0, "sigma": 0.6, "worse_direction": "up"},
        },
        "wearable_relevance": "high",
    },
    "Lisinopril": {
        "class": "Antihypertensive",
        "typical_dose_per_day": 1.0,
        "tablets_per_refill": 30,
        "symptom_name": "Blood pressure symptom burden (0-10, lower is better)",
        "symptom_base": 5.2,
        "symptom_sigma": 0.45,
        "vitals": {
            "Systolic BP (mmHg)": {"base": 140.0, "sigma": 4.0, "worse_direction": "up"},
            "Heart rate (bpm)": {"base": 78.0, "sigma": 4.0, "worse_direction": "up"},
        },
        "wearable_relevance": "low",
    },
    "Atorvastatin": {
        "class": "Lipid-lowering",
        "typical_dose_per_day": 1.0,
        "tablets_per_refill": 30,
        "symptom_name": "Statin tolerance / risk index (0-10, lower is better)",
        "symptom_base": 3.6,
        "symptom_sigma": 0.4,
        "vitals": {
            "LDL (mg/dL)": {"base": 118.0, "sigma": 4.0, "worse_direction": "up"},
            "Weight (kg)": {"base": 88.0, "sigma": 0.6, "worse_direction": "up"},
        },
        "wearable_relevance": "medium",
    },
    "Sertraline": {
        "class": "Antidepressant (SSRI)",
        "typical_dose_per_day": 1.0,
        "tablets_per_refill": 30,
        "symptom_name": "Mood symptom index (0-10, lower is better)",
        "symptom_base": 5.9,
        "symptom_sigma": 0.6,
        "vitals": {
            "Sleep quality (0-10)": {"base": 6.3, "sigma": 0.5, "worse_direction": "down"},
        },
        "wearable_relevance": "high",
    },
    "Levothyroxine": {
        "class": "Thyroid replacement",
        "typical_dose_per_day": 1.0,
        "tablets_per_refill": 30,
        "symptom_name": "Energy / thyroid control index (0-10, lower is better)",
        "symptom_base": 4.8,
        "symptom_sigma": 0.4,
        "vitals": {
            "TSH (mIU/L)": {"base": 3.3, "sigma": 0.2, "worse_direction": "up"},
            "Weight (kg)": {"base": 71.0, "sigma": 0.6, "worse_direction": "up"},
        },
        "wearable_relevance": "medium",
    },
}

SCENARIOS = {
    "normal_adherence": "Stable, consistent adherence pattern",
    "stable_buffer": "Consistently early purchase with stable interval + medication buffer",
    "occasional_late": "Occasional single late refill",
    "increasingly_late": "Repeated, increasingly late refills",
    "sudden_short": "Repeated, suddenly short refill intervals",
    "legit_dose_change": "Prescribed dose change with matching (legitimate) refill change",
    "worsening_symptoms": "Normal refill history but worsening symptoms",
    "temporary_anomaly": "Temporary anomaly that returns to normal",
    "multi_signal": "Multiple independent signals suggesting a possible adherence issue",
    "short_history": "Very short refill history (low confidence by design)",
}

# Distribution of scenarios across the synthetic cohort.
SCENARIO_WEIGHTS = {
    "normal_adherence": 30,
    "stable_buffer": 18,
    "occasional_late": 12,
    "increasingly_late": 9,
    "sudden_short": 9,
    "legit_dose_change": 10,
    "worsening_symptoms": 12,
    "temporary_anomaly": 12,
    "multi_signal": 8,
    "short_history": 6,
}

AGE_RANGE = (22, 87)
GENDERS = ["F", "M", "Non-binary"]


def _observation_series(day_grid, base, slope, sigma, rng, drift=None):
    """Deterministic series generator: base + trend + noise (+ optional drift)."""
    out = []
    for d in day_grid:
        value = base + slope * d
        if drift is not None:
            value += drift * np.sin(d / 45.0)
        value += rng.normal(0.0, sigma)
        value = float(np.clip(value, 0.0, 100.0))
        out.append({"day": int(d), "value": round(value, 2)})
    return out


def _observation_grid(start, end, cadence):
    return list(np.arange(start, end + 1, cadence, dtype=int))


def _build_refills(first_day, intervals, tablets, dose_at, rng, change_day=None):
    """Materialise a refill event list from a list of intervals (days).

    ``dose_at(day)`` returns the daily dose the patient is prescribed on a day,
    so refill events that occur after a prescription change record the new dose.
    """
    refills = []
    day = int(first_day)
    for i, interval in enumerate(intervals):
        refills.append(
            {
                "day": day,
                "tablets": int(tablets),
                "dose_per_day": float(dose_at(day)),
                "pharmacy": f"PH{101 + (i % 7)}",
            }
        )
        day = day + int(round(interval))
    refills.append({"day": day, "tablets": int(tablets), "dose_per_day": float(dose_at(day)), "pharmacy": "PH108"})
    return refills


def _noisy_intervals(base, n, cv, rng):
    return [float(max(5.0, base + rng.normal(0.0, base * cv))) for _ in range(n)]


def _generate_refill_events(scenario, profile, rng):
    """Return dict {refills, changes, last_refill_day, expected_hint}."""
    tablets = profile["tablets_per_refill"]
    dose = profile["typical_dose_per_day"]
    expected = tablets / dose  # expected supply duration in days
    changes = []
    intervals = []

    if scenario == "normal_adherence":
        intervals = _noisy_intervals(expected, 11, 0.14, rng)
        intervals = [float(np.clip(v, expected * 0.75, expected * 1.3)) for v in intervals]
    elif scenario == "stable_buffer":
        buffer = float(rng.integers(4, 9))
        base = expected - buffer
        intervals = _noisy_intervals(base, 11, 0.03, rng)
    elif scenario == "occasional_late":
        intervals = _noisy_intervals(expected, 11, 0.06, rng)
        i1, i2 = int(rng.integers(3, 8)), int(rng.integers(8, 11))
        intervals[i1] += 9.0
        intervals[i2] += 6.0
    elif scenario in ("increasingly_late", "multi_signal"):
        intervals = [expected, expected, expected * 1.25, expected * 1.55, expected * 1.9]
        intervals = [float(round(v, 1)) for v in intervals]
    elif scenario == "sudden_short":
        intervals = [expected, expected, expected * 0.93, expected * 0.5, expected * 0.43]
        intervals = [float(round(v, 1)) for v in intervals]
    elif scenario == "legit_dose_change":
        intervals = [expected] * 4
        second_dose = dose * 2.0  # dose escalation
        # The 5th interval begins right after the dose change -> shorter rhythm.
        intervals += [float(expected * 0.55), float(expected * 0.5), float(expected * 0.52)]
        # ... and the patient continues normally on the adjusted dose.
        intervals += _noisy_intervals(expected * 0.52, 18, 0.07, rng)
        pre_refill_count = 4
        change_day = int(round(sum(intervals[:pre_refill_count]) + 10))  # day of refill #5
        changes = [{"day": change_day, "dose_per_day": second_dose, "note": "Dose increased by clinician"}]
    elif scenario == "worsening_symptoms":
        intervals = _noisy_intervals(expected, 11, 0.1, rng)
    elif scenario == "temporary_anomaly":
        intervals = _noisy_intervals(expected, 11, 0.05, rng)
        intervals[5] += 14.0  # a single late interval, then back to normal
    elif scenario == "short_history":
        intervals = [expected * 2.1]  # one, long gap; barely any history
    else:
        intervals = _noisy_intervals(expected, 11, 0.14, rng)

    first_day = int(rng.integers(0, 15))

    def _dose_at(day):
        dose = float(profile["typical_dose_per_day"])
        for ch in sorted(changes, key=lambda c: c["day"]):
            if day >= ch["day"]:
                dose = float(ch["dose_per_day"])
        return dose

    refills = _build_refills(first_day, intervals, tablets, _dose_at, rng)
    expected_hint = expected
    return {"refills": refills, "changes": changes, "expected_hint": expected_hint}


def _signal_slope_for(scenario):
    """Symptom trend slope per day (positive = worsening) for the scenario."""
    mapping = {
        "normal_adherence": -0.004,
        "stable_buffer": -0.005,
        "occasional_late": 0.001,
        "increasingly_late": 0.021,
        "sudden_short": 0.001,
        "legit_dose_change": -0.004,
        "worsening_symptoms": 0.024,
        "temporary_anomaly": 0.001,
        "multi_signal": 0.026,
        "short_history": 0.002,
    }
    return mapping.get(scenario, 0.0)


def _wearable_slope_for(scenario):
    mapping = {
        "normal_adherence": 0.0,
        "stable_buffer": 0.0,
        "occasional_late": 0.0,
        "increasingly_late": -0.01,
        "sudden_short": 0.0,
        "legit_dose_change": 0.0,
        "worsening_symptoms": -0.02,
        "temporary_anomaly": 0.0,
        "multi_signal": -0.028,
        "short_history": 0.0,
    }
    return mapping.get(scenario, 0.0)


def generate_patient(patient_id, scenario, rng):
    """Generate one synthetic patient record."""
    key = str(rng.choice(list(MEDICATION_PROFILES.keys())))
    profile = {**MEDICATION_PROFILES[key], "name": key}

    refill_data = _generate_refill_events(scenario, profile, rng)
    refills = refill_data["refills"]
    changes = refill_data["changes"]
    last_refill_day = max(r["day"] for r in refills)

    last_supply = refills[-1]["tablets"] / max(1e-9, refills[-1]["dose_per_day"])

    # The observation window ends at the patient's natural refill due date
    # (one supply span after the last purchase), except for the deliberate
    # multi-signal story where the patient is genuinely overdue.
    if scenario == "multi_signal":
        observation_end = int(max(180, last_refill_day + max(120.0, 4 * last_supply)))
    elif scenario == "short_history":
        observation_end = 180
    else:
        observation_end = int(max(90, last_refill_day + last_supply))

    current_day = int(observation_end)

    symptom_slope = _signal_slope_for(scenario)
    wearable_slope = _wearable_slope_for(scenario)

    grid = _observation_grid(10, current_day, 15)
    symptoms = _observation_series(
        grid, profile["symptom_base"], symptom_slope, profile["symptom_sigma"], rng
    )

    vitals = {}
    for vname, spec in profile["vitals"].items():
        v_slope = symptom_slope * 0.55 if spec["worse_direction"] == "up" else -symptom_slope * 0.5
        vitals[vname] = _observation_series(grid, spec["base"], v_slope, spec["sigma"], rng)

    wearable = None
    if rng.random() > 0.22:  # ~78% of patients have wearable data
        wearable = {
            "Steps (daily avg)": _observation_series(grid, 7200.0, wearable_slope * 900.0, 350.0, rng),
            "Active minutes": _observation_series(grid, 52.0, wearable_slope * 8.0, 4.0, rng),
            "Sleep (hours)": _observation_series(grid, 7.0, -wearable_slope * 3.0, 0.4, rng),
        }

    followups = None
    if rng.random() > 0.12:  # ~88% of patients have follow-up records
        response_base = 82.0 if scenario not in ("worsening_symptoms", "multi_signal", "sudden_short") else 60.0
        response_trend = -0.02 if scenario in ("worsening_symptoms", "multi_signal") else 0.01
        f_grid = _observation_grid(30, current_day, 90)
        followups = []
        for i, d in enumerate(f_grid):
            value = float(np.clip(response_base + response_trend * d + rng.normal(0, 4), 20, 100))
            followups.append(
                {
                    "day": int(d),
                    "response": round(value, 1),
                    "note": _followup_note(round(value, 1)),
                }
            )

    return {
        "patient_id": patient_id,
        "scenario": scenario,
        "scenario_label": SCENARIOS[scenario],
        "age": int(rng.integers(*AGE_RANGE)),
        "gender": str(rng.choice(GENDERS)),
        "medication": profile["name"],
        "medication_class": profile["class"],
        "symptom_name": profile["symptom_name"],
        "base_daily_dose": float(profile["typical_dose_per_day"]),
        "tablets_per_refill": int(profile["tablets_per_refill"]),
        "current_day": current_day,
        "refills": refills,
        "prescription_changes": changes,
        "symptoms": symptoms,
        "vitals": vitals,
        "wearable": wearable,
        "followups": followups,
        "signals_present": _signals_present(patient_id, wearable, followups, vitals),
    }


def _signals_present(patient_id, wearable, followups, vitals):
    present = ["refills", "symptoms"]
    if vitals:
        present.append("vitals")
    if wearable is not None:
        present.append("wearable")
    if followups is not None:
        present.append("followups")
    return present


def _followup_note(response):
    if response >= 80:
        return "Patient reports feeling stable; no concerns raised."
    if response >= 60:
        return "Patient reports some symptoms; no acute concerns."
    return "Patient reports ongoing symptoms; clinician advises review."


def generate_dataset(num_patients=120, seed=DEFAULT_SEED, scenario_weights=None):
    """Generate a cohort of synthetic patients with a fixed seed (reproducible)."""
    weights = scenario_weights or SCENARIO_WEIGHTS
    scenarios = list(weights.keys())
    weights_arr = np.array([weights[s] for s in scenarios], dtype=float)
    weights_arr = weights_arr / weights_arr.sum()

    rng = np.random.default_rng(seed)
    chosen = rng.choice(scenarios, size=num_patients, p=weights_arr).tolist()

    patients = []
    for i, scenario in enumerate(chosen):
        patients.append(generate_patient(f"P{i + 1:03d}", scenario, rng))
    return patients