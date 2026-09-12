# Project Explanation — Procurement Anomaly & Relationship Auditing System

## 1. Problem
Departments publish tender data, but a human reviewer cannot read thousands of contracts, so genuine risk patterns hide in plain sight. A close reading of national "smart governance" guidelines (e.g., the e-procurement / transparency portals in India) shows that anomalous *behaviour* — not a single expensive award — is what investigators are trained to see.

Two ways to get this wrong:
- **Too aggressive**: flag any high-price win as "corruption" → destroys honest vendors, enormous false positives.
- **Too passive**: stare at scorecards that repeat the obvious → real rings never surface.

## 2. What the system builds
A relationship + behaviour graph over the award cycle:

**Signals per vendor (each explainable):**
| Signal | What it detects | Not to be confused with |
|---|---|---|
| connectedness | shared phone / email domain / director | coincidence; considered only with depth |
| recurring co-bid | A and B bid the same tenders many times | one shared tender |
| collusion ring | identity link *plus* co-bid overlap ≥3 | legitimate joint ventures (still evidence) |
| category dominance | wins most awards in a category | niche single-bidder markets (de-weighted) |
| price gap | win margin >> estimate AND >> peer median | a single fair-priced specialist (needs 3+ wins) |
| split payments | many payments just under ₹1 Cr | genuine milestone billing (needs >2 parts and >₹2 Cr total) |
| fast settlement | paid within 20 days of award | efficient bureaucracy (weak alone, strong in combination) |
| new vendor | wins within ~1 year of registration | established suppliers |

**Score** (0–100, explainable): 25% connectedness · 25% co-bid rigging · 20% price · 15% concentration · 10% payments · 5% new-vendor, with floors that only lift clear rings / dominance / price outliers. Priority = High (≥65) / Medium (35–65) / Low (<35).

## 3. Why it is auditable, not accusatory
- Every flagged vendor lists plain-language **reasons** ("Recurring co-bidding with another vendor on 6 tenders…").
- The dashboard shows the **relationship graph** — the actual evidence, not a verdict.
- Two **built-in negative tests** keep it honest:
  1. `clean` scenario → must produce zero High/Medium flags.
  2. benign single-bidder specialist (V009) → must always stay Low.

## 4. Testing strategy (how to prove it works)
`data_generator.py --scenario …` builds a controlled world where the planted patterns are known; `run_cases.py` then checks that the engine finds exactly them:

```
scenario   planted (must be flagged)    control V009   verdict
all        V001–V008 (rings, dominant, price, new)     Low    PASS
clean      none (zero flags)                           Low    PASS
rings      V001–V005 High                              Low    PASS
dominant   V006 Medium                                 Low    PASS
price      V007 Medium                                 Low    PASS
newvendor  V008 Medium                                 Low    PASS
```

This is the reproducible "various cases" answer: one command exercises six diverse cases (combination, clean control, pure rings, pure dominance, pure price, pure new-vendor) and prints a verdict table.

## 5. Data & stack
- **Data**: deterministic pseudo-random (seed 11) tenders/bids/payments/vendors/relationships, generated into `data/` (git-ignored).
- **Backend**: FastAPI + pandas/numpy (REST: overview, cases, vendor profile, network).
- **Frontend**: React + Vite + Recharts dashboard; click a vendor → reasons, network map, award/payment detail.
- **Run**: see README.md. `python run_cases.py` after any generator change is the regression gate.

## 6. Boundaries
- Synthetic data, seed 11 — designed for a controlled demo, not real procurement.
- Outputs prioritise audit leads; a human confirms before anything is labelled wrongdoing.
- Fine-grained identity fields (address, GSTIN/TAN, bank accounts) are the obvious real-world upgrade for stronger ring detection.