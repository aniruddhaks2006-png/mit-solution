# FellaRide Cold-Start Simulator + Dashboard

**Problem:** a ride-sharing/community-transport initiative can't succeed if it can't find its first users. Door-to-door ads fail in tight-knit communities; the people who matter are the quiet ones with real, findable signals — someone who posts about a brutal commute, an RWA secretary who organizes things, an early adopter who tries every app. Manually reading groups and drafting messages per person doesn't scale.

**Solution (this repo):** a four-layer cold-start pipeline, modelled end-to-end:

| Layer | What it does |
|---|---|
| 1 · Discovery Engine | scans community groups / pages for public-style signals (mock) |
| 2 · Persona & Signal Graph | scores each person as driver / passenger / connector / early adopter (0–100) |
| 3 · Contextual Engagement | drafts personalized, non-promotional outreach anchored on a real signal |
| 4 · Growth Loop | simulates weeks of rides, referrals, repeat activity |

Plus a beautiful live dashboard with input controls (community / population / weeks / seed), full visualisation (KPIs, growth chart, signal mix, role mix, archetype leaderboards, outreach feed) and an **AI draft** button that calls a local Ollama model (`gemma3:1b`, ~800 MB) to write fresh outreach for any discovered person.

## Run it (3 steps)
```
# terminal 1 — backend + dashboard
cd "culture and community/Solution 1"
pip install -r requirements.txt
uvicorn fellaride_api:app --port 8095
```
Open http://localhost:8095 — change inputs, hit **Run simulation**, or pick a person and hit **✦ Draft with gemma3:1b**.

Standalone (no dashboard, report to terminal + JSON):
```
python fellaride_coldstart.py --community "Tech Park North" --weeks 8 --seed 7
```

## API
| Endpoint | Purpose |
|---|---|
| `POST /run` | `{community, population, weeks, seed}` → fresh simulation JSON (report + signals + roles + summary) |
| `POST /draft` | `{community, name, role, signal_type, signal_text}` → AI outreach (Ollama `gemma3:1b`; auto-falls back to rule-based) |
| `GET /models` | installed Ollama models |

## Notes
- Data is **mock** — the pipeline is a runnable model, not a live scraper. Swap `DiscoveryEngine`'s source for real legally-accessible public signals to go live.
- AI endpoint prefers local Ollama: `gemma3:1b` (815 MB). If Ollama isn't running, drafts fall back to the built-in rule-based generator (both shown in the UI).
- No API keys, no network calls to cloud models, nothing leaves the machine.