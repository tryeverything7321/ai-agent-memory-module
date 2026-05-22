# Preprint Evidence Matrix

Date: 2026-05-22

## Core Claim

Propagation-style memory maintenance should not use co-occurrence topology as a
proxy for semantic dependency.  When topology and dependency diverge, unfiltered
propagation creates false-positive invalidation at scale; dependency-aware
guardrails reduce the blast radius but introduce under-propagation tradeoffs
that must be measured.

## Evidence Stack

| Evidence block | Why it is included | Main result | Claim supported | Main caveat |
| --- | --- | --- | --- | --- |
| Controlled synthetic sweep | Isolates mechanism with known dependency ground truth | Clean graphs: BFS FP = 0; high-noise/high-hub graphs: BFS FP rises to 49.69 / 70.66 / 76.64 for 30 / 100 / 300 entities | The failure is caused by topology-dependency mismatch, not only benchmark artifacts | Synthetic graphs are mechanism evidence, not deployment evidence |
| EventQA named hubs | Tests real benchmark-derived memory graphs after raw hub artifact mitigation | Named-entity hubs create large structural blast radius under BFS | Real content entities can become dangerous propagation triggers | Same benchmark family as original workshop paper |
| Artificial hub injection | Tests whether repeated generic phrases can create triggerable topology surfaces | High repetition can push an injected phrase into top-hub diagnostics while BFS collateral remains high | Graph construction can be poisoned through repeated benign-looking phrases | Query evaluation disabled; structural attack surface only |
| LongMemEval raw clean gate | Tests cross-family generalization under raw serialized conversation text | Raw hubs are dominated by template artifacts such as chat/instruction words | Raw graph extraction can fail before propagation policy matters | Negative result, not a successful propagation replication |
| LongMemEval structured graph gate | Checks whether using structured metadata recovers content-bearing hubs | Structured modes recover content hubs on 5/5 samples | Graph construction is a safety boundary, not preprocessing detail | Still rule-based entity extraction |
| LongMemEval structured propagation | Tests cross-family structural blast radius after clean graph gate | 4/5 samples have actionable hubs; BFS collateral mean 59.3 vs ATTR-AWARE 1.25 | Cross-family structural collateral pattern survives after structured graph construction | Structural-only run used mock embeddings and disabled queries |
| LongMemEval support retrieval | Measures retrieval-side harm without LLM generation noise | support hit@20: baseline 32.50, BFS 20.00 (-12.5pp), ATTR-AWARE 31.88 (-0.62pp) | BFS can push answer-support evidence out of decay-weighted top-k retrieval | Support-string matching undercounts paraphrases; baseline support is modest |
| ATTR-AWARE balanced audit set | Prepares measurement of missed true dependencies | 50 blocked candidates + 50 accepted controls, stratified across sample/hub groups | Guardrails must be evaluated for both over- and under-propagation | Labels are not complete yet |

## Recommended Paper Framing

Use the evidence in this order:

1. Start with the synthetic sweep because it proves the mechanism under known
   dependency ground truth.
2. Move to EventQA to show the mechanism appears in a real benchmark family.
3. Use LongMemEval raw failure as a graph-construction warning, not as a failed
   replication.
4. Use LongMemEval structured propagation and support retrieval as the clean
   cross-family stress test.
5. End with ATTR-AWARE as a guardrail whose tradeoff is measurable, not a final
   solved defense.

## Claims to Avoid

- Do not claim all graph-memory systems are vulnerable.
- Do not claim nonzero decay equals user-visible corruption.
- Do not claim LongMemEval end-to-end QA degradation from the current LLM F1
  runs.
- Do not claim ATTR-AWARE false-negative rate until manual labels are completed.

## Strongest Current Sentence

> Across controlled graphs and two benchmark-derived memory families, the
> unsafe condition is not graph use itself but unfiltered propagation over
> co-occurrence structure: when high-degree topology stops matching dependency,
> BFS creates broad false-positive invalidation, while dependency-aware filters
> sharply reduce collateral damage but require explicit under-propagation audits.
