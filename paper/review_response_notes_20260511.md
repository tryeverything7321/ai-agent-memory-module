# Review Response Notes (2026-05-11)

## Current Review Snapshot

Observed reviews:

| Reviewer | Rating | Confidence | Overall signal |
|----------|--------|------------|----------------|
| s7CX | 6 | 4 | Weak accept / above threshold |
| reviewer 2 | 5 | 5 | Marginally below threshold, but positive about novelty relative to other submissions |
| reviewer 3 | 3 | 3 | Clear reject, mainly due to evaluation scope and missing cost analysis |

Current read: borderline leaning reject if decisions are score-averaged, but not hopeless. The reviews mostly understand the paper and do not claim the central mechanism is wrong. The main objection is evidence breadth and practical generality.

## What Reviewers Agree On

Positive consensus:

- The problem is timely, novel, and underexplored.
- The co-occurrence vs. dependency distinction is clear and meaningful.
- The paper is well written and easy to follow.
- The BFS propagation setup is understood as a plausible stress test, not a deployed-system claim.
- The hub amplification result is interesting.
- ATTR-AWARE is attractive because it is simple, efficient, hyperparameter-free, and does not require LLM calls at propagation time.

Negative consensus:

- Evaluation is narrow: one benchmark family, one graph-construction pipeline, one LLM setup.
- The damage metric is broad because it counts any nonzero weight decay.
- The strongest downstream result, cross-task contamination, is too small and placed in the appendix.
- ATTR-AWARE false negatives are unmeasured.
- Practical relevance to deployed memory frameworks needs more evidence.

## Strategic Interpretation

The reviews are not saying "this paper is technically wrong." They are saying:

1. The paper's conceptual framing is good.
2. The empirical package is not broad enough for the strength of the structural/generalization claim.
3. The defense is promising but under-characterized on under-propagation cost.

This means the strongest rebuttal strategy is not to over-defend. The response should:

- accept the scope limitations;
- emphasize that the paper is intentionally a proactive structural risk characterization;
- highlight the controls already included to reduce the chance that the result is an artifact;
- promise camera-ready clarifications rather than new claims.

## Main Rebuttal Goals

If an author response/rebuttal phase opens, the goal is not to convert all reviews to strong accept. The realistic goal is:

- move the 3 to a 4/5 by showing the paper is scoped honestly and has enough controls for workshop discussion;
- keep the 5 from becoming a reject by emphasizing discussion value;
- preserve the 6 by agreeing with its requested clarifications.

## Response Pillars

### 1. Narrow Evaluation

Reviewer concern:

- Only MemoryAgentBench.
- Only Gemma-4-31B-it.
- One graph-construction pipeline.
- No direct Mem0/Zep deployment replication.

Best response:

- Acknowledge this directly.
- Emphasize that the goal is mechanism characterization, not deployment-level generality.
- Point to internal controls already in the paper:
  - scale trend across 6K/32K/64K;
  - graph construction control;
  - BFS variant robustness;
  - threshold and weighted-BFS baselines;
  - direction/dampening ablation;
  - manual residual audit.
- State that camera-ready will sharpen this framing and future work will replicate on additional memory systems.

Suggested wording:

> We agree that the evaluation is scoped to one benchmark family and one model pipeline. Our goal is not to claim deployment-level generality, but to characterize a structural failure mode that can arise when propagation-style invalidation is applied to co-occurrence memory graphs. To reduce pipeline-specific concerns, the paper includes scale trends, a graph-construction control, BFS variants, threshold baselines, and direction/dampening ablations. These results show that the main effect is driven by graph reachability and hub structure rather than a single decay parameter or implementation artifact.

### 2. Broad Damage Metric

Reviewer concern:

- "Damage" as any nonzero decay may overstate practical harm.

Best response:

- Agree.
- Emphasize that the paper separates:
  - nonzero damage;
  - severe damage;
  - kill rate;
  - cross-task F1 degradation.
- Promise to foreground the practical-impact metrics more clearly.

Suggested wording:

> We agree that nonzero decay is a broad metric. For this reason, we separately report severe damage, kill rates, and cross-task retrieval degradation. In the camera-ready version, we will make this distinction more prominent and avoid presenting nonzero decay alone as practical corruption.

### 3. Cross-task Contamination Placement and Size

Reviewer concern:

- Cross-task contamination is the strongest practical evidence, but it uses few hubs/queries and is in the appendix.

Best response:

- Agree that it is important.
- Explain that it was scoped as a targeted downstream diagnostic, not a full benchmark.
- State that camera-ready can bring its interpretation forward in the main text.
- Avoid pretending n=2 hubs is more than it is.

Suggested wording:

> We agree that the cross-task contamination result is the strongest downstream signal and should be emphasized more clearly. It is intentionally a targeted diagnostic rather than a full downstream benchmark: two named-entity hub triggers cause -10.0pp and -11.9pp F1 drops on unrelated retrieval, while ATTR-AWARE remains within measurement noise. We will move this interpretation earlier in the paper and clarify the limited sample size.

### 4. ATTR-AWARE False Negatives

Reviewer concern:

- Object-to-subject directionality may miss true dependencies.
- Under-propagation cost is unmeasured.

Best response:

- Agree strongly.
- Emphasize ATTR-AWARE is a lightweight guardrail, not a complete dependency reasoner.
- Existing manual audit only measures apparent false positives among organic damaged memories; it does not measure false negatives.
- Promise to expand discussion of false-negative cases and verifier/provenance extensions.

Suggested wording:

> We agree that false negatives are an important limitation. ATTR-AWARE is intended as a lightweight dependency-aware guardrail, not a complete dependency reasoner. The current manual audit checks whether residual propagated damage appears legitimate, but it does not measure dependencies that ATTR-AWARE may miss. We will expand this limitation and discuss verifier-based or provenance-based extensions.

### 5. Speculative Threat Model / BFS Baseline

Reviewer concern:

- BFS propagation is not widely deployed.
- Practical relevance to current systems may be limited.

Best response:

- Do not overclaim.
- Reiterate stress-test framing.
- The value is proactive design guidance before propagation becomes standard.

Suggested wording:

> We do not claim that current systems deploy naive BFS invalidation. We use BFS as a stress test for propagation-style maintenance over existing co-occurrence graph infrastructure. The contribution is proactive: it identifies a failure mode that should be guarded against if graph-memory systems add propagation for consistency maintenance.

### 6. Gray-box / White-box Threat Distinction

Reviewer concern:

- Hub names may be inferable, so gray-box vs. white-box may overstate the access barrier.

Best response:

- Agree partially.
- Clarify that this strengthens the practical relevance of gray-box targeting rather than invalidating the result.
- Distinguish hub-name knowledge from full registry access.

Suggested wording:

> We agree that hub entities may often be inferable from repeated interaction or public domain knowledge. This is why we include a gray-box setting based on hub names, distinct from white-box registry access. We can clarify that the gray-box barrier may be low in some deployments, which strengthens the case for safeguards.

### 7. "Naive BFS Is Obvious"

Reviewer concern:

- Researchers familiar with graph diffusion may find BFS damage unsurprising.

Best response:

- The novelty is not that BFS diffuses, but that this failure mode appears in agent memory forgetting and can be measured as collateral memory damage/retrieval contamination.
- The paper connects graph diffusion intuition to memory invalidation semantics and proposes a lightweight guardrail.

Suggested wording:

> We agree that unfiltered graph diffusion can be problematic in the abstract. The contribution here is to instantiate this issue in agent memory forgetting, quantify its collateral effect on valid memories, show a hub-targeted amplification path, and evaluate a dependency-aware propagation rule that avoids LLM-time verification.

## Compact Rebuttal Draft

If response length is short, use something like:

> We thank the reviewers for the constructive feedback. We agree that the evaluation is scoped to one benchmark family and one model pipeline. Our goal is not to claim deployment-level generality, but to characterize a structural failure mode that can arise when propagation-style invalidation is applied to co-occurrence memory graphs. To reduce pipeline-specific concerns, the paper includes scale trends, a graph-construction control, BFS variants, threshold baselines, and direction/dampening ablations, which indicate that the effect is driven by graph reachability and hub structure rather than a single decay parameter or implementation artifact.
>
> We also agree that nonzero decay is a broad damage metric. The paper therefore separately reports severe damage, kill rates, and cross-task retrieval degradation. In a camera-ready version, we will foreground these practical-impact metrics more clearly and bring the cross-task contamination diagnostic earlier in the main text, while noting its limited number of hubs/queries.
>
> Finally, ATTR-AWARE is intended as a lightweight dependency-aware guardrail, not a complete dependency reasoner. We agree that false negatives are important; our current manual audit does not measure missed dependencies. We will expand this limitation and discuss verifier- or provenance-based extensions. We also clarify that BFS is a stress test of a plausible propagation-style maintenance step, not a claim about current deployed behavior.

## Camera-ready / Next-version Action Plan

If accepted:

1. Move cross-task contamination from appendix to main text or summarize it more prominently.
2. Rename/clarify damage in early results as "nonzero decay damage"; foreground kill/severe/retrieval degradation.
3. Add explicit false-negative discussion for ATTR-AWARE:
   - dependencies not captured by object-to-subject chains;
   - multi-entity dependencies;
   - temporal/causal dependencies not reflected in entity roles.
4. Clarify gray-box threat model:
   - hub names can be inferable;
   - white-box means registry-level fact access, not just hub names.
5. Add future work on:
   - additional LLM/model pipelines;
   - Mem0/Zep-style graph schemas;
   - NER-normalized graph extraction;
   - verifier/provenance-based propagation.

If rejected and resubmitting:

1. Add at least one additional graph-construction pipeline:
   - NER-normalized extraction;
   - typed relation extraction;
   - Mem0/Zep-style schema approximation.
2. Add at least one additional model or non-LLM extraction pipeline.
3. Expand cross-task contamination:
   - more hubs;
   - more queries;
   - report confidence intervals;
   - move to main result section.
4. Measure ATTR-AWARE false negatives with a manually labeled dependency set.
5. Reframe headline metrics around:
   - severe/kill damage;
   - downstream retrieval degradation;
   - nonzero decay as reachability/blast-radius metric.

## Practical Decision Read

Current decision odds are uncertain and likely below the earlier optimistic estimate. The paper's conceptual contribution is well received, but the current empirical scope may be considered too narrow by stricter reviewers. If accepted, the reviews give a clear camera-ready path. If rejected, the next version should focus on breadth of evaluation and ATTR-AWARE false-negative analysis, not on rewriting the core thesis.
