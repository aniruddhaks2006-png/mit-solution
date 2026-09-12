# Procurement Anomaly & Relationship Auditing System

**Business problem (hackathon set 2):** Public entities award thousands of contracts a year. Buried in the data are unusual patterns — the same vendors repeatedly bidding together, awards concentrating in few hands, payments split to dodge reporting thresholds, winners bidding far above estimate. Naive "corruption finder" AI treats any single win as proof. This tool instead *flags patterns and relationships* for a human auditor to investigate, without ever assuming corruption.

## What it does
1. Reads synthetic tenders / bids / payments / vendor-registration data.
2. Computes explainable risk signals per vendor:
   - **Connected / relationship network** — shared phone, email domain, directors (identity links) and recurring **co-bidding** (two vendors bidding the same tenders repeatedly).
   - **Collusion ring** — identity link + heavy co-bid overlap → likely coordination.
   - **Award dominance** — winning most awards in a category (context-adjusted for niche/single-bidder markets so such markets are **not** auto-flagged).
   - **Price anomaly** — winning margin well above both the estimate *and* the peer-median margin in the same category.
   - **Payment anomalies** — many small payments kept just under ₹1 Cr (possible threshold-splitting) and payments settled unusually fast (<20 days).
   - **New-vendor risk** — winning contracts within ~1 year of registration.
3. Combines them into a **0–100 investigation score** and a **High / Medium / Low** review priority (explainable: each flagged vendor lists *why*).
4. Serves the results via a FastAPI backend + a React dashboard with a relationship-network map per vendor.

## Data generator: test your own cases
`data_generator.py` plants known anomaly patterns with a fixed seed, so you can verify the engine:

| `--scenario` | Planted pattern(s) | Expect |
|---|---|---|
| `all` | everything combined | V001–V005 High, V006–V008 Medium |
| `clean` | no planted pattern (control) | **zero** High/Medium flags |
| `rings` | 2 collusion rings | V001–V005 flagged High |
| `dominant` | medical dominance + split payments | V006 flagged |
| `price` | repeat +20% price anomaly | V007 flagged |
| `newvendor` | recent registration + fast wins | V008 flagged |

Run a scenario: `python data_generator.py --scenario rings --seed 11`
Run the full regression:

```
python run_cases.py
```

V009 is a **benign single-bidder specialist** — it appears in every scenario and must always stay Low (false-positive control).

## How to run the dashboard
```
cd backend
pip install -r requirements.txt
python data_generator.py                # generates data\*.csv (scenario "all")
python run_cases.py                     # optional: verify all scenarios pass
uvicorn main:app --reload --port 8011

# new terminal
cd frontend
npm install
npm run dev
```
Open the Vite link (the `src/main.jsx` points the API at `http://localhost:8011`; edit it if you change the port).

## Repository layout
```
backend/
  data_generator.py   # data + scenario generator (seed 11)
  main.py             # signal engine + REST API
  run_cases.py        # scenario regression runner
  requirements.txt
frontend/
  index.html, package.json, src/main.jsx, src/style.css
data/                 # generated CSV (git-ignored)
```

## API
| Endpoint | Returns |
|---|---|
| GET `/analytics/overview` | summary counts |
| GET `/cases` | every vendor with signals + priority |
| GET `/vendor/{id}` | full profile: reasons, wins, bids, payments, relationships |
| GET `/network/{id}` | relationship graph (nodes + edges) |

## Design notes: avoiding the "corruption label" trap
- Flagged ≠ guilty. Outputs are *priorities with evidence*, written neutrally ("coordinated bidding" not "fraud").
- Niche/single-bidder markets are explicitly de-weighted so honest, specialized suppliers don't become false positives.
- A clean-dataset scenario must produce zero flags; the benign specialist must stay Low.
- Every score is a weighted sum of explainable dimensions (25% connectedness, 25% co-bid rigging, 20% price, 15% concentration, 10% payments, 5% new-vendor) with floors that only lift clear rings/dominance/price outliers — a pure audit-lead generator, not a judgement.