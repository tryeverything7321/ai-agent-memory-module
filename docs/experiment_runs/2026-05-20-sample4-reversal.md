# 2026-05-20 Sample 4 Retrieval Reversal

## Observation

Sample 4 is the exception in the 5-sample named-hub run: BFS increases F1 from
43.7 to 55.2 while still causing high collateral damage.

## Query-Level Pattern

The largest BFS gains are mostly cases where the baseline answer is a refusal or
negative fallback such as `None of the provided events occur in the excerpt`,
while BFS returns one of the listed candidate events. Examples include:

| Query | Ground truth | Baseline | BFS | F1 delta |
|---:|---|---|---|---:|
| 44 | Edie Arkadyevitch ordered oysters for dinner. | None of the provided events occur in the excerpt. | Edie Arkadyevitch ordered oysters for dinner | +1.0 |
| 58 | Clarisse expressed interest in experiencing table-turning. | None of the above. | Clarisse expressed interest in experiencing table-turning. | +1.0 |
| 61 | Ladonna left the gathering unnoticed after the conversation. | None of the provided events occur in the text. | Ladonna left the gathering unnoticed after the conversation. | +1.0 |

The largest BFS drops show the opposite pattern: the baseline returns the target
event, while BFS falls back to a refusal or retrieves an unrelated event.

| Query | Ground truth | Baseline | BFS | F1 delta |
|---:|---|---|---|---:|
| 80 | Karissa observed the children playing around her after dinner. | Karissa observed the children playing around her after dinner | None of the provided events occur in the excerpt. | -1.0 |
| 98 | Ladonna resolved to never forget his brother Nikolay. | Ladonna resolved to never forget his brother Nikolay | None of the provided events occur in the excerpt. | -1.0 |

## Working Interpretation

This does not refute the structural collateral-damage claim. It shows that
retrieval F1 can improve when broad downweighting changes which memories dominate
retrieval, especially when the baseline often produces negative fallback
answers. In this sample, BFS appears to suppress some distractors or alter the
retrieval context enough to make the generator choose a candidate event more
often.

## Paper Implication

The paper should avoid equating nonzero structural damage with deterministic
retrieval failure. Report retrieval outcomes as practical-risk evidence with
variance, and use structural blast radius as the mechanism-level metric.
