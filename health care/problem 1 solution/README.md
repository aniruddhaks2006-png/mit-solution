# The Vanishing Dose

> **The healthcare problem it targets** · medication non-adherence is one of the
> most common and under-detected causes of preventable disease progression. This
> project is a decision-support prototype that surfaces **possible** adherence
> anomalies from indirect signals — never accusing the patient.

**Clinical decision-support prototype for detecting *possible* medication
non-adherence from indirect healthcare signals.**

> This tool never accuses a patient. It surfaces **unusual medication
> utilization patterns** — possible under-use / missed-dose risk, possible
> over-use risk, an overall adherence anomaly risk, a confidence level, the
> concrete evidence behind the flag, and a set of alternative explanations.

![stack](https://img.shields.io/badge/Python-3.10%2B-blue) ![ui](https://img.shields.io/badge/UI-Streamlit-green) ![ml](https://img.shields.io/badge/ML-hybrid%20rule%20%2B%20IsolationForest-orange)

---

## The problem being solved

Non-adherence to chronic medication is one of the leading causes of preventable
disease progression, yet it is almost never detected in routine care. Asking a
patient "are you taking your medicine?" has well-documented limits, and directly
confronting a patient with an adherence accusation damages trust and care.

The Vanishing Dose takes a different route. It watches the *trail a patient
leaves behind*:

- **Pharmacy refill dates** (acquisition records) — a strong indirect signal
- **Symptom scores** and **vitals** over time
- **Wearable / activity data** where available
- **Follow-up response records**
- **Prescription changes** (which legitimately alter the refill rhythm)

It then asks: *is the medication utilization pattern consistent with what was
prescribed, and consistent with the patient's own history?* If a pattern
deviates, the patient is flagged for **possible** review — with evidence, with
uncertainty, and with alternatives — never accused.

---

## How the solution works

```
synthetic patients ──► feature engineering ──► hybrid model ──► Streamlit dashboard
 (data_generator)      (feature_engineering)    (model)          (app.py)
```

1. **Data generation** (`data_generator.py`) creates a reproducible cohort of
   120+ synthetic patients covering distinct, realistic scenarios, including a
   poorly-behaved-but-legitimate one: patients who *always* refill early with a
   stable rhythm.

2. **Feature engineering** (`feature_engineering.py`) turns raw events into
   indicators:
   - `expected_supply_days = tablets_purchased / prescribed_daily_dose`
   - `actual_refill_interval`, `rolling_mean/std_refill_interval`
   - `patient_baseline_refill_interval` (see below)
   - `deviation_from_patient_baseline`
   - `consecutive_early/short_intervals`, `consecutive_late/long_intervals`
   - `refill_gap_risk` (time since last purchase vs expected supply)
   - symptom / vital / wearable / treatment-response changes
   - `prescription_changed_recently`

3. **Hybrid model** (`model.py`):
   - Deterministic explainable rules score under-use and over-use (0–100).
   - An **IsolationForest** is fitted on well-behaved patients to detect unusual
     multi-signal combinations (this is the trained-ML component).
   - A weighted combination produces the **Overall Adherence Anomaly Risk**.
   - A **confidence** label (Low / Medium / High) reflects how much data exists
     and whether independent signals agree.
   - Every result ships with narrative **evidence**, **alternative
     explanations**, and a **recommendation**.

---

## How patient-specific baselines work

For each patient we compute two reference rhythms:

| Rhythm | Definition |
|---|---|
| **Expected interval** | tablets supplied ÷ daily dose (what the prescription implies) |
| **Patient baseline** | median of the patient's *own* refill intervals in the current dosage regime, **excluding the most recent interval** |

The most recent interval is judged against **both** references. This is what
makes the system personal rather than one-size-fits-all.

## Why consistent early purchases are *not* automatically over-use

Consider the classic "suspicious" case from the literature: a patient whose 1
tablet/day / 30-tablet prescription (expected supply 30 days) refills on days
20, 50, 80, 110.

- Naive rule: "first refill came 10 days early → overuse." **Wrong.**
- Our approach: the patient's intervals are 30, 30, 30 — perfectly consistent
  with their **own baseline** of ~30 days. Deviation from baseline ≈ 0,
  consistency is high, and the single early purchase reads as a personal buffer.

By contrast:

- **Genuine shortening:** intervals 30 → 28 → 15 → 13 days. Here the recent
  interval is ~54% shorter than the patient's own ~28-day baseline, with a
  streak of short intervals and a sharp downward slope → **possible over-use /
  abnormal utilization**.
- **Genuine lateness:** intervals 30 → 38 → 47 → 58 days. The recent interval is
  ~52% longer than the established baseline with 3 consecutive late intervals →
  **possible under-use**, especially if symptoms worsen in the same window.

Both cases are always reported *with uncertainty and alternatives*.

---

## Architecture

```
vanishing-dose/
├── app.py                  # Streamlit dashboard (overview, timeline, risk, evidence)
├── data_generator.py       # Synthetic cohort generation (120 patients, 10 scenarios)
├── feature_engineering.py  # Refill-interval + signal feature extraction
├── model.py                # Rule scoring + IsolationForest + confidence + explainability
├── requirements.txt
└── README.md
```

### Data model (per patient)

- Patient ID, age, gender, medication & class
- Refill events: `day, tablets, dose_per_day, pharmacy`
- Prescription changes: `day, dose_per_day, note`
- Symptom series, vital series, optional wearable series, follow-up records
- All times use a common "day since first purchase" axis

---

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Open the printed local URL (typically `http://localhost:8501`).

---

## Synthetic data scenarios

| Scenario | Expected behaviour |
|---|---|
| Normal consistent adherence | low risk, high confidence |
| Consistently early purchase, stable interval + buffer | **low** over-use risk (baseline-aware) |
| Occasional single late refill | low-to-moderate under-use risk |
| Repeated increasingly late refills | high possible under-use |
| Suddenly shortened refill intervals | high possible over-use / abnormal utilization |
| Legitimate dose change shifting the rhythm | recalibrated baselines, not an adherence flag |
| Worsening symptoms despite normal refills | clinical review, not an adherence accusation |
| Temporary anomaly that returns to normal | low residual risk |
| Multiple independent signals pointing together | high overall risk, high confidence |

## Limitations

- **All data is synthetic.** No clinical accuracy claim is made.
- Refill data proves **acquisition**, not **ingestion**. A patient could stock
  up, throw tablets away, or obtain them elsewhere.
- This is a decision-support prototype, **not a diagnostic system**.
- The IsolationForest is fitted on synthetic "healthy" patients; its calibration
  is demonstration-grade only.

## Future improvements

- Integrate real dispensing data standards (RxNorm, NDC, pharmacy claims).
- Add MEMS/ingestion biomarkers and patient-reported outcomes.
- Replace scenario labels with ground-truth event adjudication.
- Add temporal Kaplan-Meier-style progression and multi-drug interactions.
- Model-level: calibration on real data, uncertainty intervals, and
  out-of-distribution detection.