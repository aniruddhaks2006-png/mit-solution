"""FellaRide dashboard API: runs the cold-start simulator on demand and can
route AI-generated outreach to a local Ollama model (gemma3:1b, ~800 MB).
If Ollama is unavailable it falls back to the built-in rule-based drafts.

Run:  uvicorn fellaride_api:app --port 8095
Open:  http://localhost:8095
"""
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import fellaride_coldstart as f

HERE = Path(__file__).resolve().parent
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:1b"

app = FastAPI(title="FellaRide Dashboard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def run_sim(population=40, weeks=6, seed=42, community="Riverside Tech Park"):
    discovery = f.DiscoveryEngine(community, population=population, seed=seed)
    people, groups = discovery.discover()
    signals = Counter(s.signal_type for p in people.values() for s in p.signals)
    roles = Counter(p.role_hint for p in people.values())

    scorer = f.PersonaScorer()
    people = scorer.score_all(people)
    top_by_archetype = {a: scorer.top_candidates(people, a, n=5) for a in f.ARCHETYPES}

    engine = f.EngagementEngine()
    connectors = top_by_archetype["connector"]
    seed_targets = {p.name: p for p in (
        top_by_archetype["connector"] + top_by_archetype["driver"]
        + top_by_archetype["passenger"] + top_by_archetype["early_adopter"][:3]
    )}.values()
    samples = []
    for person in seed_targets:
        samples.append({"name": person.name, **engine.draft_message(person, community)})

    sim = f.GrowthLoopSimulator(people, connectors=connectors,
                                seeds=[p for p in seed_targets if p not in connectors], seed=seed)
    weekly = sim.run(weeks=weeks)
    report = f.build_report(community, people, groups, top_by_archetype, samples, weekly)
    return report, dict(signals), dict(roles)


def budget_estimate(total_rides, active, population):
    fill = active / population if population else 0
    weekly = total_rides / (active or 1)
    return f"{weekly:.1f} rides/user/wk at {fill * 100:.0f}% reach \u2014 density is {'high' if fill > .8 else 'building'}."


class RunIn(BaseModel):
    community: str = "Riverside Tech Park"
    population: int = 40
    weeks: int = 6
    seed: int = 42


class DraftIn(BaseModel):
    community: str
    name: str = "Neighbor"
    role: str = "employee"
    signal_type: str = "commute_pain"
    signal_text: str = ""


@app.get("/")
def index():
    return FileResponse(HERE / "fellaride_dashboard.html")


@app.get("/models")
def models():
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
            return [m["name"] for m in json.load(r)["models"]]
    except Exception:
        return []


@app.post("/run")
def run_job(body: RunIn):
    t0 = time.time()
    report, signals, roles = run_sim(body.population, body.weeks, body.seed, body.community)
    weeks = report["growth_simulation"]
    last = weeks[-1]
    return {
        "community": report["community"],
        "population": report["population_discovered"],
        "seed": body.seed, "weeks": body.weeks,
        "report": report, "signals": signals, "roles": roles,
        "summary": {
            "total_rides": last["total_completed_rides"],
            "active": last["active_users"],
            "referrals": sum(w["new_referrals_this_week"] for w in weeks),
            "connectors": len(report["top_candidates"]["connector"]),
            "note": budget_estimate(last["total_completed_rides"], last["active_users"], body.population),
        },
        "took_ms": int((time.time() - t0) * 1000),
    }


@app.post("/draft")
def draft(body: DraftIn):
    signal_ctx = body.signal_text or {
        "driver_signal": "filling the tank for the daily commute",
        "commute_pain": "a rough commute each morning",
        "sustainability_signal": "wanting to carpool more",
        "event_context": "an upcoming community event",
        "connector_signal": "sharing community updates",
        "early_adopter_signal": "trying new commute apps",
    }.get(body.signal_type, "your commute")
    fallback = (
        f"Hi {body.name.split()[0]}, saw your note about {signal_ctx} around "
        f"{body.community} \u2014 a small group there is quietly coordinating shared rides "
        f"for the normal route. No commitment, no app pitch \u2014 happy to intro you "
        f"this week and let you decide. \u2014 FellaRide (community ping)"
    )
    prompt = (
        "You draft ONE warm, personal, NON-promotional 50-70 word outreach message "
        "for a community carpool initiative. It must reference the person's real signal, "
        "sound human (never like an ad), and suggest a low-commitment next step. "
        f"Community: {body.community}. Person: {body.name} ({body.role}). "
        f"Findable public signal: \"{signal_ctx}\". Reply with only the message."
    )
    payload = json.dumps({"model": MODEL, "prompt": prompt, "stream": False,
                          "temperature": 0.6, "options": {"num_predict": 180}}).encode()
    t0 = time.time()
    try:
        req = urllib.request.Request(OLLAMA_URL, payload, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.load(r).get("response", "").strip()
        if not out:
            out = fallback
        return {"message": out, "model": MODEL, "fallback": out == fallback,
                "took_ms": int((time.time() - t0) * 1000)}
    except Exception:
        return {"message": fallback, "model": "rule-based (ollama unavailable)",
                "fallback": True, "took_ms": int((time.time() - t0) * 1000)}