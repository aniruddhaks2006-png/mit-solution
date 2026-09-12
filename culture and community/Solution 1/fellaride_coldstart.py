#!/usr/bin/env python3
"""
FellaRide Cold-Start Simulator
================================

Simulates the four-layer system described in the design doc, using MOCK data
(no real scraping — this is a runnable model of the pipeline, not a live crawler):

  Layer 1: Discovery Engine       -> finds candidate people from public-style signals
  Layer 2: Persona & Signal Graph -> scores people as driver / passenger / connector / early adopter
  Layer 3: Contextual Engagement  -> drafts personalized, non-promotional outreach
  Layer 4: Growth Loop            -> simulates rides, referrals, repeat activity over weeks

Run it:
    python3 fellaride_coldstart.py

Optional:
    python3 fellaride_coldstart.py --community "Tech Park North" --weeks 8 --seed 7

Output:
    - A readable report printed to the terminal
    - A JSON file (fellaride_report.json) with the full simulation results,
      written next to this script
"""

import argparse
import json
import random
import textwrap
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Layer 1: Discovery Engine (mock public-signal generator)
# ---------------------------------------------------------------------------

FIRST_NAMES = ["Asha", "Rohan", "Meera", "Vikram", "Priya", "Karan", "Divya",
               "Suresh", "Ananya", "Farhan", "Lakshmi", "Arjun", "Neha", "Tariq",
               "Sneha", "Manoj", "Ritu", "Sameer", "Pooja", "Deepak"]

LAST_NAMES = ["Shetty", "Iyer", "Kapoor", "Reddy", "Nair", "Menon", "Rao",
              "Bhat", "Pillai", "Kulkarni", "Gowda", "Das", "Chatterjee", "Verma"]

PUBLIC_POST_TEMPLATES = [
    ("commute_pain", "Ugh, {route} traffic was brutal again this morning. 45 min for a 12km drive."),
    ("commute_pain", "Bus to {route} was late AGAIN. Third time this week."),
    ("driver_signal", "Filled up the tank for the {route} commute, petrol prices are killing me."),
    ("driver_signal", "Anyone else driving to {route} around 8:30? My car's usually half empty."),
    ("event_context", "Reminder: Society Diwali Mela this Saturday, parking will be very limited near the gate."),
    ("event_context", "Fest attendees from out of town — drop your arrival time here, some of us are coordinating pickups."),
    ("connector_signal", "As RWA secretary, sharing this week's maintenance and event updates for the community."),
    ("connector_signal", "Posting this on behalf of the placement cell for students commuting to the job fair."),
    ("early_adopter_signal", "Tried three different apps this month just to shave 10 min off my commute, worth it."),
    ("early_adopter_signal", "Always down to try a new tool if it saves money or time, DM me your carpool app recs."),
    ("sustainability_signal", "We really should be carpooling more, one car per person to {route} makes no sense."),
]

GROUP_TEMPLATES = [
    "{community} Residents WhatsApp Group",
    "{community} Employees Community Page",
    "{community} Alumni Network",
    "{community} Commute & Carpool Discussion",
]


@dataclass
class PublicSignal:
    person: str
    signal_type: str
    text: str
    source_group: str


@dataclass
class Person:
    name: str
    role_hint: str  # e.g. "employee", "student", "resident"
    signals: list = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    outreach: dict = None
    invited_by: str = None
    completed_rides: int = 0
    referrals_made: int = 0


class DiscoveryEngine:
    """Simulates crawling public community pages/groups and extracting signals."""

    def __init__(self, community_name, population=40, seed=None):
        self.community_name = community_name
        self.population = population
        self.rng = random.Random(seed)

    def _random_name(self, used):
        while True:
            name = f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"
            if name not in used:
                used.add(name)
                return name

    def discover(self):
        used_names = set()
        people = {}
        groups = [g.format(community=self.community_name) for g in GROUP_TEMPLATES]

        for _ in range(self.population):
            name = self._random_name(used_names)
            role_hint = self.rng.choice(["employee", "student", "resident", "alumnus"])
            people[name] = Person(name=name, role_hint=role_hint)

        # Each person leaves 0-3 public-style posts/signals
        names = list(people.keys())
        for name in names:
            n_signals = self.rng.choices([0, 1, 2, 3], weights=[15, 40, 30, 15])[0]
            for _ in range(n_signals):
                sig_type, template = self.rng.choice(PUBLIC_POST_TEMPLATES)
                text = template.format(route=f"{self.community_name} corridor")
                group = self.rng.choice(groups)
                people[name].signals.append(
                    PublicSignal(person=name, signal_type=sig_type, text=text, source_group=group)
                )

        # Guarantee at least one clear connector and one clear event trigger exist
        connector_name = self.rng.choice(names)
        people[connector_name].signals.append(
            PublicSignal(person=connector_name, signal_type="connector_signal",
                         text="As community coordinator, sharing this week's updates and events.",
                         source_group=groups[0])
        )

        return people, groups


# ---------------------------------------------------------------------------
# Layer 2: Persona & Signal Graph
# ---------------------------------------------------------------------------

SIGNAL_WEIGHTS = {
    "driver_signal": {"driver": 35},
    "commute_pain": {"passenger": 25, "early_adopter": 5},
    "event_context": {"connector": 10, "early_adopter": 5},
    "connector_signal": {"connector": 50},
    "early_adopter_signal": {"early_adopter": 40},
    "sustainability_signal": {"driver": 10, "early_adopter": 15},
}

ARCHETYPES = ["driver", "passenger", "connector", "early_adopter"]


class PersonaScorer:
    """Converts raw discovered signals into archetype scores (0-100 per archetype)."""

    def score_all(self, people: dict):
        for person in people.values():
            raw = {a: 0 for a in ARCHETYPES}
            for sig in person.signals:
                bumps = SIGNAL_WEIGHTS.get(sig.signal_type, {})
                for archetype, weight in bumps.items():
                    raw[archetype] += weight

            # role_hint gives small priors (students skew passenger, employees skew driver)
            if person.role_hint == "student":
                raw["passenger"] += 10
            elif person.role_hint == "employee":
                raw["driver"] += 8
            elif person.role_hint == "resident":
                raw["connector"] += 3

            # normalize to 0-100 cap
            person.scores = {a: min(100, v) for a, v in raw.items()}
        return people

    def top_candidates(self, people: dict, archetype: str, n=5, min_score=1):
        ranked = sorted(
            (p for p in people.values() if p.scores.get(archetype, 0) >= min_score),
            key=lambda p: p.scores.get(archetype, 0),
            reverse=True,
        )
        return ranked[:n]


# ---------------------------------------------------------------------------
# Layer 3: Contextual Engagement Engine
# ---------------------------------------------------------------------------

class EngagementEngine:
    """Drafts personalized, context-grounded outreach instead of generic promotion."""

    def draft_message(self, person: Person, community_name: str):
        # Pick the strongest signal to anchor the message in something real
        anchor = None
        if person.signals:
            anchor = max(
                person.signals,
                key=lambda s: SIGNAL_WEIGHTS.get(s.signal_type, {}).get(
                    max(person.scores, key=person.scores.get), 0
                ),
            )

        top_archetype = max(person.scores, key=person.scores.get) if person.scores else "passenger"

        if anchor and anchor.signal_type == "event_context":
            msg = (f"Hi {person.name.split()[0]}, saw the note in {anchor.source_group} about "
                   f"this week's event/parking crunch — a few neighbors are splitting rides for it. "
                   f"Want me to add you to that one-off group?")
        elif anchor and anchor.signal_type == "driver_signal":
            msg = (f"Hi {person.name.split()[0]}, noticed your post about the {community_name} commute "
                   f"and fuel costs — a couple of people nearby are doing the same route around the same time. "
                   f"Want an intro so you're not driving with empty seats?")
        elif anchor and anchor.signal_type == "commute_pain":
            msg = (f"Hi {person.name.split()[0]}, saw your post about the rough commute to {community_name} — "
                   f"there's someone driving that route most mornings with room in the car. "
                   f"Want me to connect you two for this week only, no commitment?")
        elif top_archetype == "connector":
            msg = (f"Hi {person.name.split()[0]}, you clearly keep {community_name} informed — "
                   f"would you be open to sharing a one-time carpool sign-up thread for people on the "
                   f"usual commute route? Framed as community logistics, not an app pitch.")
        else:
            msg = (f"Hi {person.name.split()[0]}, a few people in {community_name} are quietly coordinating "
                   f"shared rides for the regular commute — thought you might want in, no pressure.")

        person.outreach = {
            "channel": "connector-relayed" if top_archetype == "connector" else "direct",
            "anchor_signal": anchor.text if anchor else None,
            "message": msg,
        }
        return person.outreach


# ---------------------------------------------------------------------------
# Layer 4: Growth Loop Simulator
# ---------------------------------------------------------------------------

class GrowthLoopSimulator:
    """
    Simulates weeks of activity: connector endorsement -> first rides ->
    social-proof shares -> referrals -> repeat rides.
    """

    def __init__(self, people: dict, connectors, seeds, seed=None):
        self.people = people
        self.connectors = connectors
        self.seeds = seeds  # initial drivers/passengers who got direct outreach
        self.rng = random.Random(seed)
        self.weekly_log = []

    def run(self, weeks=6):
        active_pool = list(self.seeds)
        for week in range(1, weeks + 1):
            new_rides = 0
            new_referrals = 0

            # Existing active users complete rides probabilistically
            for person in active_pool:
                if self.rng.random() < 0.65:
                    person.completed_rides += 1
                    new_rides += 1
                    # completed ride -> chance of a referral (growth loop step)
                    if self.rng.random() < 0.4:
                        candidates = [p for p in self.people.values()
                                      if p not in active_pool and p != person]
                        if candidates:
                            invitee = self.rng.choice(candidates)
                            invitee.invited_by = person.name
                            active_pool.append(invitee)
                            person.referrals_made += 1
                            new_referrals += 1

            # Connector endorsement gives a one-time boost in week 1-2
            if week <= 2 and self.connectors:
                for conn in self.connectors:
                    if self.rng.random() < 0.5:
                        candidates = [p for p in self.people.values() if p not in active_pool]
                        if candidates:
                            boosted = self.rng.sample(candidates, k=min(2, len(candidates)))
                            for b in boosted:
                                b.invited_by = f"{conn.name} (connector endorsement)"
                                active_pool.append(b)

            self.weekly_log.append({
                "week": week,
                "active_users": len(active_pool),
                "new_rides_this_week": new_rides,
                "new_referrals_this_week": new_referrals,
                "total_completed_rides": sum(p.completed_rides for p in self.people.values()),
            })

        return self.weekly_log


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def print_section(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def build_report(community_name, people, groups, top_by_archetype, engagement_samples, weekly_log):
    report = {
        "community": community_name,
        "discovered_groups": groups,
        "population_discovered": len(people),
        "top_candidates": {
            archetype: [
                {"name": p.name, "score": p.scores.get(archetype, 0), "role_hint": p.role_hint}
                for p in plist
            ]
            for archetype, plist in top_by_archetype.items()
        },
        "sample_outreach": engagement_samples,
        "growth_simulation": weekly_log,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="FellaRide cold-start pipeline simulator")
    parser.add_argument("--community", default="Riverside Tech Park",
                         help="Name of the target community/wedge (default: Riverside Tech Park)")
    parser.add_argument("--population", type=int, default=40,
                         help="Number of mock people to discover (default: 40)")
    parser.add_argument("--weeks", type=int, default=6,
                         help="Number of weeks to simulate growth (default: 6)")
    parser.add_argument("--seed", type=int, default=42,
                         help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--json-out", default=str(Path(__file__).with_name("fellaride_report.json")),
                         help="Where to save the JSON report")
    args = parser.parse_args()

    print_section(f"LAYER 1: DISCOVERY ENGINE — scanning public signals for '{args.community}'")
    discovery = DiscoveryEngine(args.community, population=args.population, seed=args.seed)
    people, groups = discovery.discover()
    print(f"Discovered {len(people)} people across {len(groups)} public/semi-public groups:")
    for g in groups:
        print(f"  - {g}")
    total_signals = sum(len(p.signals) for p in people.values())
    print(f"Extracted {total_signals} public signals (posts/mentions) in total.")

    print_section("LAYER 2: PERSONA & SIGNAL GRAPH — scoring archetypes")
    scorer = PersonaScorer()
    people = scorer.score_all(people)

    top_by_archetype = {}
    for archetype in ARCHETYPES:
        top = scorer.top_candidates(people, archetype, n=5)
        top_by_archetype[archetype] = top
        print(f"\nTop '{archetype}' candidates:")
        if not top:
            print("  (none found above threshold)")
        for p in top:
            print(f"  - {p.name:<20} score={p.scores[archetype]:<4} role_hint={p.role_hint}")

    print_section("LAYER 3: CONTEXTUAL ENGAGEMENT ENGINE — drafting outreach")
    engine = EngagementEngine()
    # Engage: all connectors + top 5 drivers + top 5 passengers + top 3 early adopters
    connectors = top_by_archetype["connector"]
    seed_targets = {p.name: p for p in (
        top_by_archetype["connector"]
        + top_by_archetype["driver"]
        + top_by_archetype["passenger"]
        + top_by_archetype["early_adopter"][:3]
    )}.values()

    engagement_samples = []
    for person in seed_targets:
        outreach = engine.draft_message(person, args.community)
        engagement_samples.append({"name": person.name, **outreach})

    for sample in engagement_samples[:8]:
        print(f"\n-> To: {sample['name']}  [{sample['channel']}]")
        if sample["anchor_signal"]:
            print(f"   Anchored on: \"{sample['anchor_signal']}\"")
        print(textwrap.fill(f"   Message: {sample['message']}", width=78))
    if len(engagement_samples) > 8:
        print(f"\n... and {len(engagement_samples) - 8} more drafted (see JSON output).")

    print_section("LAYER 4: GROWTH LOOP SIMULATION — rides, referrals, repeat activity")
    seeds = [p for p in seed_targets if p not in connectors]
    sim = GrowthLoopSimulator(people, connectors=connectors, seeds=seeds, seed=args.seed)
    weekly_log = sim.run(weeks=args.weeks)

    print(f"{'Week':<6}{'Active users':<15}{'New rides':<12}{'New referrals':<16}{'Total rides':<12}")
    for row in weekly_log:
        print(f"{row['week']:<6}{row['active_users']:<15}{row['new_rides_this_week']:<12}"
              f"{row['new_referrals_this_week']:<16}{row['total_completed_rides']:<12}")

    print_section("SUMMARY")
    final = weekly_log[-1]
    total_pop = len(people)
    print(f"Community: {args.community}")
    print(f"Discovered population: {total_pop}")
    print(f"Active users after {args.weeks} weeks: {final['active_users']} "
          f"({final['active_users']/total_pop*100:.1f}% of discovered community)")
    print(f"Total completed rides: {final['total_completed_rides']}")
    print(f"Connectors engaged: {len(connectors)}")
    print("\nThis is a MOCK simulation intended to demonstrate the pipeline logic end-to-end.")
    print("Swap DiscoveryEngine's data source for real, legally-accessible public signals")
    print("(public group posts, event pages, directories) to run this against a real wedge community.")

    report = build_report(args.community, people, groups, top_by_archetype, engagement_samples, weekly_log)
    out_path = Path(args.json_out)
    with out_path.open("w") as f:
        json.dump(report, f, indent=2, default=lambda o: asdict(o) if hasattr(o, "__dataclass_fields__") else str(o))
    print(f"\nFull report saved to: {out_path}")


if __name__ == "__main__":
    main()
