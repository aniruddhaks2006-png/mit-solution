# Hackathon Explanation

## Title
**Post-Award Contract Change Monitor**

## One-line solution
A decision-support dashboard that compares every contract's baseline commitment with current project information during execution and surfaces significant variations — with evidence and review priority — so oversight teams see what changed and whether it warrants review.

## Problem in one paragraph
Contracts are scrutinised before award, then drift during execution: contractors change, quantities grow, costs rise, deadlines slip. Without a way to track drift against the original approval, authorities cannot tell whether a contract still looks like what was approved, or whether a change needs scrutiny or additional evidence.

## How the system solves it
For every contract it maintains two snapshots:

- **Baseline commitment** — as awarded: contractor, value, planned completion, bill of quantities.
- **Current status** — execution reality: approved value, revised completion, current contractor, quantities, change orders, evidence attachments.

It compares these snapshots and converts differences into explicit, configurable variation signals:

- cost overrun (% above award)
- schedule slippage (days vs baseline)
- contractor substitution (who is delivering)
- scope change (pay-item quantity drift)
- evidence gap (referenced documents missing)
- amendment frequency

## Why is this better than reading contract files
A file-based review is retrospective and only covers what someone thinks to pull. This system gives:

- **Live visibility** — comparison happens continuously against the original commitment.
- **Explainability** — every flag comes with the reason phrased in plain language.
- **Evidence linkage** — change orders are attached to documents, and missing evidence is itself a flag.
- **Prioritisation** — an explainable weighted score routes the review queue (Low / Medium / High).

## Is every change "wrong"?
No. The system deliberately uses neutral language and floors rather than verdicts:

> "Approved value is 38% above the awarded value."

not

> "This contract is corrupt."

Most variations are legitimate (rate revisions, site conditions, scope requested by the department itself). Review priority just means a human should confirm the change is justified, recorded and evidenced.

## Core innovation
Connecting the **original approval** to the **execution record** and scoring the *drift*, not the contract. Stability is as informative as change: a contract that tracks its baseline exactly is shown as Low priority, proving the system does not just find problems everywhere.

## The review score
- 35% cost variance · 25% schedule slippage · 20% contractor substitution · 10% scope variance · 10% evidence gap
- Floor rules: contractor substitution → at least Medium; evidence ratio < 50% → at least Medium.

## Recommended demo
1. Overview: 12 contracts, a handful flagged High.
2. Cost overrun: the approved-value curve climbs away from the awarded baseline.
3. Contractor substitution: "Contractor substituted: X → Y."
4. Evidence gap: "2 of 4 documents missing — request evidence."
5. Stable contract: Low priority, "no significant variation."
6. Close with: the system is oversight support — humans decide.