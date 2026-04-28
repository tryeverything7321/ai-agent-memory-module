# Submission Logic Summary

## Core Thesis

The paper argues that graph-based memory systems face a structural failure mode if they adopt unfiltered invalidation propagation over co-occurrence graphs. The key mechanism is simple:

1. Agent memory systems increasingly store facts in entity graphs.
2. Propagation-style invalidation is a plausible next step for maintaining consistency when one fact changes.
3. However, co-occurrence is not dependency. Two facts can share an entity without one fact depending on the other.
4. Naive BFS propagation treats all graph neighbors as equally relevant, so invalidation cascades through hub entities and damages unrelated valid memories.
5. A dependency-aware guardrail, even a lightweight object-to-subject directional filter, can greatly reduce this collateral damage without LLM calls at propagation time.

The intended contribution is not that current production systems already deploy naive BFS forgetting. The claim is proactive: if graph-based memory systems explore propagation over existing co-occurrence structures, unfiltered traversal creates a predictable structural risk.

## Why This Fits SCALE

The work is positioned around scalable agentic memory rather than multimodal perception. Its fit comes from:

- memory consolidation, retrieval, and forgetting;
- robustness of agent memory systems under scale;
- evaluation of memory-management policies;
- deployment-oriented failure analysis before a risky design pattern becomes common.

The paper is therefore best read as a workshop-style failure-mode study: it identifies a scaling risk, quantifies it, shows an amplification path, and proposes a lightweight mitigation.

## Experimental Narrative

### 1. Propagation Trade-off

Purpose: establish why propagation is tempting in the first place.

The controlled fact-change experiment compares no propagation, BFS propagation, and ATTR-AWARE propagation. No propagation avoids collateral damage but leaves stale memories. BFS improves forgetting accuracy but damages unrelated memories. ATTR-AWARE keeps most of the forgetting benefit while reducing collateral damage.

Implication: propagation is not an obviously bad idea; it addresses a real consistency gap. The problem is unfiltered propagation over co-occurrence edges.

### 2. Scale Trend on FactConsolidation

Purpose: test whether the collateral damage grows or persists as memory scale increases.

Across 6K, 32K, and 64K MemoryAgentBench FactConsolidation runs, BFS applies nonzero weight decay to 69--79% of valid memories. ATTR-AWARE remains near 15% damage on the tested scales.

Implication: the failure is not a small-graph artifact. As memory graphs grow, hub structure keeps unfiltered propagation dangerous. The result supports the paper's scaling claim.

### 3. Entity-Extraction Sanity Check

Purpose: defend against the concern that the main topology result is caused by extraction artifacts.

The top hubs in the FactConsolidation scale runs are content entities such as United States, America, University, Catholic Church, and United Kingdom, not function words or pronouns.

Implication: the main scale result is tied to real entity hubs. The EventQA cross-task diagnostic still exposes some raw-ranking artifacts, so the paper reports an artifact-aware named-entity subset there.

### 4. Graph Topology Analysis

Purpose: explain why BFS damage emerges structurally.

The memory graphs have heavy-tailed degree distributions, and degree heterogeneity grows with scale. BFS reachability from high-degree hubs therefore expands rapidly.

Implication: collateral forgetting is not only a parameter issue. It follows from hub topology in co-occurrence graphs.

### 5. Graph Construction Control

Purpose: check whether clique-style co-occurrence graph construction artificially inflates the result.

The typed-relation control at 6K removes clique edges and keeps subject-to-object edges. Edge count drops, but BFS damage changes only modestly in the 5-fact attack setting.

Implication: the vulnerability is driven primarily by high-frequency entity hubs rather than only by clique construction.

### 6. Cross-task Contamination

Purpose: show that structural damage can translate into downstream retrieval degradation.

In the 64K EventQA diagnostic, the two highest named-entity hubs cause -10.0pp and -11.9pp F1 drops on unrelated Accurate Retrieval queries under BFS propagation. ATTR-AWARE preserves retrieval within measurement noise.

Implication: the damage metric is not purely cosmetic. At least in hub-triggered cross-task settings, unfiltered propagation can degrade unrelated retrieval behavior.

### 7. Hub-targeted Structural Amplification

Purpose: show that the structural risk can be deliberately amplified.

A small number of injected facts targeting hub entities causes broad propagation. Five facts at 32K affect 57.3% of valid memories, with 19.3% killed under the paper's weight threshold.

Implication: once propagation exists, maintenance itself can become an amplification path. The attack requires gray-box or white-box hub knowledge, so the paper frames it as structural amplification rather than a fully black-box exploit.

### 8. Black-box / Gray-box / White-box Comparison

Purpose: clarify the threat model.

Random black-box targeting fails to hit hubs in the tested setting. Gray-box targeting achieves part of the white-box damage. White-box targeting gives the strongest amplification.

Implication: the attack is not claimed to be universally easy. Its risk depends on hub knowledge, which is realistic in some deployments but not assumed in fully black-box settings.

### 9. ATTR-AWARE Method

Purpose: provide a simple mitigation aligned with the causal intuition.

ATTR-AWARE follows object-to-subject chains: if a fact says "the CEO of Acme is Alice," then facts about Alice may depend on Alice's role, while arbitrary facts about Acme need not. The method uses existing metadata and string matching, not LLM calls at propagation time.

Implication: substantial protection does not require a heavy verifier. A simple dependency-aware propagation rule can reduce the blast radius.

### 10. Propagation Strategy Comparison

Purpose: compare ATTR-AWARE against simpler controls and threshold methods.

The paper compares BFS variants, degree caps, k-hop thresholds, weighted BFS, and ATTR-AWARE. Threshold methods can work well at chosen thresholds, but require per-deployment tuning and can show cliff effects. ATTR-AWARE is hyperparameter-free and has low damage in the tested setting.

Implication: the key design question is not only how much to dampen propagation, but whether traversal respects dependency direction.

### 11. Direction vs. Dampening Ablation

Purpose: isolate what makes ATTR-AWARE work.

Removing dampening changes severity but not reach. Directional filtering accounts for the damage reduction in the controlled attack setting. Downstream object-to-subject propagation performs best among the tested directional variants.

Implication: the main benefit comes from filtering the propagation frontier, not from merely reducing decay magnitude.

### 12. Robustness to BFS Variants

Purpose: rule out implementation artifacts such as redundant decay or a specific decay parameter.

BFS damage remains the same when redundant decay is removed and across decay parameters, because the headline damage measures reachability. Severity and kill rates vary, but the set of affected memories is structurally determined.

Implication: the 39.8% and 57.3% attack damage rates reflect graph reachability, not a fragile implementation choice.

## Main Reviewer-facing Takeaways

1. The paper is a proactive risk characterization, not a claim about deployed BFS forgetting.
2. The central mechanism is structural: co-occurrence graphs create hub-mediated reachability that does not respect dependency.
3. The damage metric is broad, but the paper separately reports severe damage, kill rates, and cross-task retrieval degradation.
4. The artifact concern is acknowledged and partly controlled: main FactConsolidation hubs are content entities; cross-task results are reported on named-entity hubs.
5. ATTR-AWARE is intentionally lightweight. Its value is not that it solves dependency reasoning completely, but that it shows dependency-aware filtering can prevent most collateral damage without LLM-time verification.

## Remaining Limitations to Be Ready to Discuss

- Single benchmark and single model pipeline.
- Rule-based entity extraction and subject-key construction.
- False negatives for ATTR-AWARE remain unmeasured.
- The attack is gray-box or white-box, not fully black-box.
- Text-memory only; multimodal memory graphs remain future work.
- Weighted BFS can match or outperform ATTR-AWARE in some adversarial damage settings if a good threshold is tuned.

## One-sentence Defense

This paper is valuable as a SCALE workshop submission because it identifies a plausible scaling failure mode in agentic memory maintenance, quantifies the structural blast radius of unfiltered propagation, and shows that lightweight dependency-aware filtering can substantially reduce the risk.
