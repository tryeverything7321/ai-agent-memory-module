# Artificial Hub Injection Experiment

## Goal

Test whether repeated generic phrases can fabricate high-degree hubs and amplify
forgetting/invalidation propagation.

## Dataset

Start with `eventqa_65536` because it already produces clean content hubs and
fast runs. Use one sample for smoke, then three to five samples for the real
experiment.

## Injection Phrases

Use three phrase types:

1. `Project Note`: generic operational phrase.
2. `Current Context`: memory-management-like phrase.
3. `Important Reminder`: plausible user-authored phrase.

## Conditions

1. `clean_control`: original context.
2. `low_injection`: phrase inserted into 5 facts.
3. `medium_injection`: phrase inserted into 20 facts.
4. `high_injection`: phrase inserted into 50 facts.

## Metrics

- injected phrase hub rank;
- injected phrase degree;
- BFS blast radius from injected hub;
- ATTR-AWARE blast radius from injected hub;
- collateral/retrievable loss;
- whether filtering removes the fabricated hub.

## Success Criterion

Topology poisoning is supported if injected phrases enter top-k hubs and produce
higher blast radius than clean controls at matched sample/context size.
