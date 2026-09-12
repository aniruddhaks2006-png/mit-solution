# System Architecture

## Overview

MIT Solution is a collection of two healthcare decision-support prototypes built for a hackathon, focusing on medication adherence monitoring and medicine supply chain management.

```
┌─────────────────────────────────────────────────────────────────┐
│                     MIT Solution Hackathon                       │
└─────────────────────────────────────────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
       ┌────────▼─────────┐         ┌────────▼────────┐
       │   Problem 1      │         │   Problem 2     │
       │ Medication       │         │   Medicine      │
       │ Adherence        │         │   Shortage      │
       │ (Streamlit)      │         │   (Full Stack)  │
       └──────────────────┘         └─────────────────┘
```

---

## Problem 1: The Vanishing Dose (Medication Adherence)

**Directory:** `health care/problem 1 solution/`

### Architecture Diagram

```
┌──────────────────┐
│  data_generator  │  ← Synthetic patient cohort (120 patients, 10 scenarios)
└────────┬─────────┘
         │ (raw events)
         ▼
┌──────────────────────────┐
│ feature_engineering.py   │  ← Extract signals from events
│                          │    - Refill intervals
│                          │    - Deviation from baseline
│                          │    - Symptom/vital trends
└────────┬─────────────────┘
         │ (structured features)
         ▼
┌──────────────────────────┐
│ model.py                 │  ← Hybrid ML approach
│                          │    - Deterministic rules
│                          │    - IsolationForest anomaly detection
│                          │    - Confidence scoring
└────────┬─────────────────┘
         │ (risk scores + evidence)
         ▼
┌──────────────────────────┐
│ app.py (Streamlit)       │  ← Interactive dashboard
│                          │    - Patient overview
│                          │    - Timeline visualization
│                          │    - Risk assessment
│                          │    - Evidence & recommendations
└──────────────────────────┘
```

### Data Flow

1. **Patient Events** (synthetic)
   - Refill dates, tablet counts, dosage
   - Prescription changes
   - Symptom scores, vital signs
   - Activity/wearable data
   - Treatment response records

2. **Feature Engineering**
   - Calculate expected supply days
   - Compute rolling refill intervals
   - Establish patient-specific baselines (excluding most recent)
   - Detect consecutive early/late patterns
   - Flag recent prescription changes

3. **Hybrid Model**
   - **Rules Component:** Deterministic scoring (0–100) for under-use and over-use
   - **ML Component:** IsolationForest fitted on "healthy" patients to detect unusual multi-signal combinations
   - **Confidence:** Low/Medium/High based on data volume and signal agreement
   - **Evidence:** Narrative explanation + alternative explanations

4. **Dashboard (Streamlit)**
   - Patient selector
   - Timeline view with events and flags
   - Risk breakdown (under-use, over-use, anomaly)
   - Key evidence and recommendations

### Key Innovation: Patient-Specific Baselines

Unlike one-size-fits-all detection, the system computes per-patient baselines:

| Baseline | Formula |
|----------|---------|
| **Expected interval** | tablets_supplied ÷ daily_dose |
| **Patient baseline** | median(refill_intervals in current regime, excluding most recent) |

This prevents false positives for patients who consistently refill early but within their own pattern.

---

## Problem 2: Medicine Shortage Early Warning System

**Directory:** `health care/problem 2 solution/`

### Architecture Diagram

```
┌────────────────────────────────────────────┐
│           Data Layer                       │
│  ├─ Facility inventory                    │
│  ├─ Historical consumption                │
│  ├─ Facility coordinates                  │
│  └─ Replenishment events                  │
└────────────┬─────────────────────────────┘
             │
      ┌──────▼──────┐
      │   Backend   │
      │  (FastAPI)  │
      └──────┬──────┘
             │
    ┌────────┼─────────┐
    │        │         │
┌───▼───┐ ┌──▼──┐ ┌───▼───┐
│ Risk  │ │Data │ │Donor  │
│Engine │ │API  │ │Search │
└───┬───┘ └──┬──┘ └───┬───┘
    │        │        │
    └────────┼────────┘
             │
      ┌──────▼──────┐
      │  Frontend   │
      │(React+Vite) │
      └─────────────┘
```

### Backend (FastAPI)

**Entry point:** `backend/main.py`

**Core Components:**

1. **Data Generator** (`data_generator.py`)
   - 8 facilities with geographic coordinates
   - 5 essential medicines
   - 120 days of inventory history
   - Daily consumption and replenishment events
   - Synthetic demand shock scenario

2. **Risk Engine**
   - **Stockout Proximity (55%):** Days of stock remaining from recent consumption
   - **Demand Acceleration (30%):** Rate of consumption increase
   - **Low Inventory (15%):** Stock relative to historical normal
   
   **Formula:**
   ```
   risk_score = 0.55 × stockout_risk 
              + 0.30 × demand_trend 
              + 0.15 × low_inventory_risk
   ```

3. **Redistribution Engine**
   - Finds facilities with surplus (>30 days stock)
   - Calculates geographic distance
   - Ranks donor options by proximity and stability
   - Recommends best redistribution routes (not executed)

4. **API Endpoints**
   - `GET /facilities` – List all facilities
   - `GET /medicines` – List all medicines
   - `GET /analytics/overview` – System-wide metrics
   - `GET /shortages` – Facilities at risk
   - `GET /facility/{facility_id}` – Facility detail + history
   - `GET /redistribution/{medicine_id}` – Donor recommendations

### Frontend (React + Vite)

**Entry point:** `frontend/src/main.jsx`

**Dashboard Views:**

1. **Overview**
   - Summary statistics (facilities at risk, medicines affected)
   - Regional risk trend
   - Critical facilities list

2. **Facility Map**
   - Geographic plot of facilities
   - Color-coded by risk level
   - Click for details

3. **Timeline**
   - Historical consumption and stock levels
   - Demand acceleration visualization
   - Projected stockout dates

4. **Redistribution**
   - High-risk facility selection
   - Donor facility ranking
   - Distance and stock metrics
   - Recommendation rationale

### Data Flow

```
Inventory + Consumption
        │
        ▼
  Process (calculate DSO, demand trend)
        │
        ├──────────────┬──────────────┐
        │              │              │
        ▼              ▼              ▼
    Risk Score    Trend Analysis   Inventory Check
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ▼
                 Risk Classification
                (Low/Medium/High)
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
    API Response  Visualization  Redistribution
                                   Recommendations
```

---

## Shared Infrastructure

### Environment Configuration

**File:** `.env.example`

```bash
# Problem 1 (Streamlit)
STREAMLIT_SERVER_PORT=8501

# Problem 2 Backend (FastAPI)
BACKEND_PORT=8000
VITE_API_URL=http://localhost:8000
```

Copy to `.env` and customize as needed.

### Dependencies

**Problem 1:**
- `streamlit` – Interactive dashboard
- `pandas`, `numpy` – Data processing
- `scikit-learn` – IsolationForest, preprocessing
- `plotly` – Visualizations

**Problem 2 Backend:**
- `fastapi` – API framework
- `uvicorn` – ASGI server
- `pydantic` – Data validation
- `pandas` – Data processing

**Problem 2 Frontend:**
- `react` – UI framework
- `vite` – Build tool
- `axios` – HTTP client
- `recharts` – Charting library

---

## Deployment

### Local Development

```bash
# Problem 1
cd "health care/problem 1 solution"
pip install -r requirements.txt
streamlit run app.py

# Problem 2 Backend
cd "health care/problem 2 solution/backend"
pip install -r requirements.txt
python data_generator.py
uvicorn main:app --reload

# Problem 2 Frontend
cd "health care/problem 2 solution/frontend"
npm install
npm run dev
```

### Production Considerations

- Use environment variables for config (see `.env.example`)
- Replace synthetic data with real data sources
- Implement database persistence (currently in-memory)
- Add authentication/authorization (if multi-user)
- Set up monitoring and logging
- Use HTTPS in production
- Consider containerization (Docker)

---

## Design Decisions

### Problem 1: Hybrid ML vs. Pure Supervised

**Why:** Clinical decision support requires explainability. Rules provide baseline logic; IsolationForest catches unexpected patterns.

**Trade-off:** Less accurate than a large-scale supervised model, but clinically interpretable.

### Problem 2: Interpretable Risk Engine vs. Black-box Forecasting

**Why:** Supply-chain decision makers need to understand why a shortage is predicted.

**Future:** Time-series forecasting (Prophet, XGBoost) can augment or replace static risk scores.

### Synthetic Data

**Why:** Avoids real patient/facility data; makes the demo reproducible and self-contained.

**Limitation:** Calibration and accuracy are demonstration-grade only.

---

## Security Notes

- **No patient/facility data is stored permanently** (in-memory, reset on restart)
- **No authentication implemented** (prototype only)
- **API is unencrypted** (use HTTPS in production)
- **Environment variables should not include secrets in version control** (use `.env.local` or secrets management)

---

## Future Improvements

### Problem 1
- Integrate real EHR/pharmacy data standards (HL7, RxNorm, NDC)
- Add MEMS (electronic pill bottle) data
- Machine learning calibration on real patient data
- Multi-drug interaction detection
- Temporal disease progression modeling

### Problem 2
- Time-series forecasting (ARIMA, Prophet, LSTM)
- Multi-echelon supply-chain modeling
- Cold-chain and expiry tracking
- Route optimization for redistribution
- Scenario simulation engine
- Real-time alert prioritization

---

## Contact & Questions

Refer to `CONTRIBUTING.md` for how to report issues or suggest improvements.
