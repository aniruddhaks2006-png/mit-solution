# Project Explanation — FellaRide Cold-Start Simulator

## 1. Problem
Getting a two-sided community utility (riders × drivers) started is a classic cold-start trap: no rides because no users, no users because no rides. In dense communities the unlock isn't ads — it's *specific humans who already behave like the product*: people complaining about commutes, RWA secretaries who coordinate, early adopters who try tools to save time. Finding and hand-approaching them doesn't scale; fully-automated spam destroys trust.

## 2. The four-layer architecture
1. **Discovery** — collect public-style signals (posts/mentions) from community groups. Mock generator reproduces realistic mixes: commute pain, driver signals, event context, connector activity, early-adopter behaviour.
2. **Persona scoring** — each signal votes toward archetypes (driver 35 for fuel posts, passenger 25 for commute complaints, connector 50 for community-posters, early adopter 40 for tool-tryers) plus role priors (students skew passenger, employees skew driver), capped at 100.
3. **Contextual engagement** — outreach is *anchored on a real signal* ("saw your post about the rough commute…"), low-commitment ("for this week only, no pressure") and explicitly framed as community logistics — never an app pitch. Connectors get a relayed ask so the message arrives via a trusted neighbour.
4. **Growth loop** — weekly simulation: existing users ride (65%), completed rides seed referrals (40%), connectors give a one-time endorsement boost in weeks 1–2.

## 3. Why this is a credible answer for the brief
- **Trust-safe**: personal + non-promotional by prompt and by design; the AI (local `gemma3:1b`) is instructed the same way and audited in the UI with model/latency/fallback badges.
- **Measurable**: every run produces KPIs (reach %, rides/user/wk, referrals, activation curve), so you can compare communities/seeds without guessing.
- **Reproducible & replayable**: seeded simulation means judges can re-run the exact demo; inputs (community, population, weeks, seed) are live-editable in the dashboard.
- **On-device AI**: entire pipeline runs locally (FastAPI + stdlib + Ollama) — no API keys, no cloud dependency, works offline.

## 4. Testing / demonstration flow
1. `uvicorn fellaride_api:app --port 8095`
2. Page loads a default run (40 people, 6 weeks, seed 42 → sees 40/40 activation, 118 rides, 3.0 rides/user/wk).
3. Change seed/community → instant re-simulation; charts/leaderboards/outreach update.
4. Pick a top persona → **✦ Draft with gemma3:1b** → ~17 s on CPU, message appears pinned to outreach with model + fallback status.

## 5. Limitations
- Mock signals (legal + scalable to swap: public group posts, event pages, directories).
- 1b-parameter model = charming drafts, not sales copy; fallback path covers offline cases.
- Simulation probabilities are placeholders to be calibrated against a real pilot.