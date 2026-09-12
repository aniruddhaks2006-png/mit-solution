
# Hackathon Explanation

## Title
**From One Empty Shelf to a Regional Shortage**

## One-line solution
An explainable early-warning system that combines inventory, consumption, replenishment and geography to predict emerging medicine shortages and identify redistribution opportunities before facilities stock out.

## How is the problem effectively solved?

Instead of monitoring each hospital independently, the system builds a shared regional view.

For every facility and medicine it estimates:
- how much stock remains
- how quickly the medicine is being consumed
- how demand is changing
- how many days of supply remain
- whether multiple facilities are showing the same deterioration
- which nearby facilities may have surplus

The system then produces a risk score and explains the factors behind it.

## Why is this better than a simple stock alert?

A normal alert says:

“Hospital A has low stock.”

Our system asks:

“Is Hospital A becoming part of a wider shortage?”

For example:

Hospital A → 7 days stock, demand rising
Hospital B → 10 days stock, demand rising
Hospital C → 45 days stock, stable
Hospital D → 52 days stock, stable

The system detects a regional risk for that medicine and proposes C/D as possible redistribution sources.

## Core innovation

The most important idea is **connecting facilities as a regional supply network**.

Facilities are not independent.

```text
       Surplus
          |
          v
A ---- B ---- C
|      |
v      v
D ---- E
```

A shortage at one node can be reduced using another node before the problem spreads.

## What the ML/analytics layer does

The prototype calculates temporal features from historical inventory and consumption.

A future version can train a forecasting model to estimate:

`Probability(stockout within 7 days)`

and

`Probability(stockout within 14 days)`

rather than only giving a static risk score.

## Why uncertainty matters

Healthcare supply data is imperfect.

A facility may receive an emergency shipment that has not yet been recorded. Demand can change suddenly. A data feed can be delayed.

Therefore the dashboard reports confidence and uses language such as:

**“Potential shortage emerging — verify inventory and replenishment status.”**

rather than claiming certainty.

## Recommended demo

Use the dashboard to tell this story:

**Day 1:** One hospital has declining stock.

**Day 5:** Consumption accelerates.

**Day 10:** A second hospital shows the same pattern.

**System:** Regional shortage risk increases.

**System:** Finds another hospital with 50+ days of supply.

**Recommendation:** Investigate redistribution from surplus facility to high-risk facility.

This demonstrates detection, prediction, explanation and intervention in one workflow.
