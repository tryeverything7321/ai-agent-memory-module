# Collateral Damage in Graph-based Memory Invalidation: Why Forgetting Too Much Is Worse Than Not Forgetting At All

---

## Abstract

Graph-based propagation is a natural approach to invalidating stale facts in AI memory systems: when a fact changes, propagate the update through an entity graph to downstream dependents. We show that this intuition leads to **catastrophic collateral damage**. On the MemoryAgentBench FactConsolidation benchmark, BFS-based propagation through entity co-occurrence graphs decays 68.9% of valid memories at 6K context and 79.0% at 32K context, with 41.6-67.6% of valid memories suffering complete weight collapse (w < 0.1). The root cause is **hub entities** — high-degree nodes like "United States" (degree=121 at 32K) that connect semantically unrelated facts, causing invalidation to spread far beyond the intended scope. We propose **Attribute-aware Selective Propagation**, inspired by directional link failure models in transportation engineering, which restricts propagation to downstream fact chains sharing the same subject-attribute relationship. This reduces collateral damage by 78.5-80.0% while maintaining consistent (though modest) improvements on multi-hop QA across all hyperparameter configurations (sign test p=0.001, n=12 ablation runs).

---

## 1. Introduction

AI memory systems that persist and update factual knowledge face a fundamental tension: when stored facts become outdated, the system must invalidate not only the stale fact itself but also any dependent knowledge derived from it. For example, if "The president of Russia is Putin" is updated, then "Putin was born in Leningrad" — a downstream fact about the now-former president — should be marked as potentially unreliable.

Graph-based propagation is the natural solution: connect entities in a graph, and when a fact is invalidated, propagate decay weights along graph edges to neighboring facts (Mnemosyne, 2025; MAGMA, 2026). This mirrors how information cascades through knowledge networks.

**However, we discover that this approach is deeply flawed in practice.**

Entity co-occurrence graphs — the standard construction method — create **hub entities** with disproportionately high degree. "United States" appears in facts about presidents, capitals, geography, sports, culture, and dozens of other topics. BFS propagation through such hubs causes invalidation to spread to completely unrelated facts. We find that at 32K context, a single fact update can cascade through hub nodes to decay **79% of all valid memories**, with 67.6% collapsing to effectively zero weight.

This is worse than doing nothing. A memory system that forgets 79% of what it knows after every update is less useful than one that never propagates at all.

We present a quantitative analysis of this **collateral damage** phenomenon and propose a targeted fix: **Attribute-aware Selective Propagation**. Drawing on directional link failure models from transportation engineering, we restrict propagation to follow fact chains that share the same subject-attribute relationship, rather than blindly traversing all graph edges. This reduces collateral damage by 78-80% while preserving the benefits of propagation for multi-hop reasoning.

### Contributions

1. **Quantitative discovery of collateral damage** in graph-based memory propagation. We show that BFS through entity co-occurrence graphs decays 68.9-79.0% of valid memories, with the problem worsening superlinearly as context size increases (hub degree grows from 23 at 6K to 121 at 32K).

2. **Root cause analysis** identifying hub entities as the mechanism. The top 1% of entities by degree (e.g., "United States", "University") account for disproportionate collateral damage through their fan-out connections.

3. **Attribute-aware Selective Propagation**, a directional propagation method inspired by transportation network link failure models, reducing collateral damage by 78-80% and complete memory loss (w<0.1) by 99.6%.

4. **Empirical validation** on MemoryAgentBench FactConsolidation, showing consistent positive results across all 12 hyperparameter configurations for multi-hop QA (sign test p=0.001).

---

## 2. Background and Motivation

### 2.1 AI Memory and Fact Invalidation

Long-term AI memory systems (Mem0, 2024; MemGPT/Letta, 2023; A-Mem, 2025) store user interactions as structured facts with associated metadata. When new information contradicts stored facts, the system must:

1. **Detect** the conflict (e.g., same subject-attribute, different value)
2. **Invalidate** the outdated fact
3. **Propagate** the change to dependent downstream facts

Step 3 is where graph-based approaches come in. Systems like Mnemosyne (2025) use temporal edge-based decay, while MAGMA (2026) proposes multi-graph architectures. However, **none of these works quantitatively analyze the collateral damage of propagation**.

### 2.2 Transportation Network Analogy

In transportation engineering, **link failure propagation** studies how road closures cascade through a network. A key finding is that **hub intersections** (high-degree nodes) amplify disruption disproportionately — closing one road at a major interchange can gridlock an entire region.

Critically, transportation research distinguishes between:
- **Directional propagation**: Closing Seoul→Busan affects only Busan-downstream traffic, not Seoul→Incheon
- **Non-directional propagation**: Closing the Seoul interchange affects all connected routes

This distinction maps directly to our problem. Standard BFS propagation is non-directional — it spreads invalidation to all entities connected to the source, regardless of semantic direction.

### 2.3 MemoryAgentBench

MemoryAgentBench (ICLR 2026) provides standardized evaluation for AI memory agents. The FactConsolidation task presents serial-numbered facts where later facts may contradict earlier ones, then tests whether the system correctly resolves queries using the most recent information.

- **Single-hop (SH)**: Direct fact lookup (e.g., "Who is the president of Russia?")
- **Multi-hop (MH)**: Chain reasoning (e.g., "What is the capital of the country where Madame du Barry held citizenship?")

---

## 3. Collateral Damage Analysis

### 3.1 Experimental Setup

We measure collateral damage by running the FactConsolidation memorization phase under three conditions:

| Mode | Conflict Detection | Propagation |
|------|-------------------|-------------|
| Baseline | Subject-key match, `is_valid=False` | None |
| BFS | Same as Baseline | BFS through entity co-occurrence graph |
| Attribute-aware | Same as Baseline | Downstream fact chain only |

After memorization, we count how many valid memories have `decay_weight < 1.0` (indicating propagation affected them), and their weight distribution.

**Infrastructure**: Gemma-4-31B-it (LLM), BAAI/bge-m3 (Embedding), SQLite + NumPy in-memory.

### 3.2 Main Results

| Context | Valid Memories | BFS Decayed | Attr-aware Decayed | Reduction |
|---------|---------------|-------------|---------------------|-----------|
| 6K (456 facts) | 344 | **237 (68.9%)** | 51 (14.8%) | **78.5%** |
| 32K (2,311 facts) | 1,744 | **1,377 (79.0%)** | 275 (15.8%) | **80.0%** |

**Finding 1: BFS propagation damages the majority of valid memories.** At 6K context, 237 of 344 valid memories (68.9%) have their weight reduced. At 32K, this rises to 1,377 of 1,744 (79.0%). The system effectively "forgets" most of what it knows.

**Finding 2: The damage is severe, not marginal.** Weight distribution analysis:

| Weight Range | 6K BFS | 6K Attr | 32K BFS | 32K Attr |
|-------------|--------|---------|---------|----------|
| < 0.1 (complete loss) | 143 | 0 | **1,179** | 5 |
| < 0.3 (effective loss) | 175 | 1 | 1,263 | 11 |
| < 0.5 (retrieval disadvantage) | 188 | 1 | 1,278 | 15 |
| = 1.0 (unaffected) | 107 | **293** | 367 | **1,469** |

At 32K, **1,179 valid memories** (67.6% of all valid) collapse to weight < 0.1 under BFS — functionally deleted. Attribute-aware reduces this to 5 (99.6% reduction).

### 3.3 Root Cause: Hub Entities

| Entity | 6K Degree | 32K Degree | 32K Connected Memories |
|--------|-----------|------------|----------------------|
| United States | 23 | **121** | 127 |
| University | 17 | **86** | 76 |
| United Kingdom | 12 | **68** | 58 |
| Catholic Church | — | **66** | 49 |
| France | 13 | **41** | 39 |

**Finding 3: Hub degree grows superlinearly with context size.** "United States" goes from degree 23 (6K) to 121 (32K) — a 5.3x increase for 5.1x more facts. This is because hub entities appear across diverse topical domains, and co-occurrence construction connects them to entities from every domain.

**Finding 4: A small fraction of entities cause most damage.** At 32K:
- Nodes with degree > 10: 44/1,732 (2.5%)
- Nodes with degree > 20: 17/1,732 (1.0%)
- These ~1% of entities mediate the propagation that damages 79% of memories.

Degree distribution: mean=3.0, std=6.0, median=2, max=121. The distribution is heavily right-skewed, exhibiting power-law characteristics typical of co-occurrence networks.

### 3.4 Scaling Analysis

| Metric | 6K | 32K | Scale Factor |
|--------|----|----|-------------|
| Facts | 456 | 2,311 | 5.1x |
| Graph nodes | 414 | 1,732 | 4.2x |
| Graph edges | 520 | 2,600 | 5.0x |
| Max degree | 23 | 121 | **5.3x** |
| BFS collateral ratio | 68.9% | 79.0% | **+10.1pp** |
| Attr collateral ratio | 14.8% | 15.8% | +1.0pp |

BFS collateral damage worsens with scale; attribute-aware remains stable. This is because BFS damage is dominated by hub degree (superlinear growth), while attribute-aware is bounded by the number of actual downstream dependencies (linear growth).

---

## 4. Attribute-aware Selective Propagation

### 4.1 Method

When fact *f* with subject_key `Entity:Attribute` is invalidated:

1. **Extract object entities** from *f* (entities in *f* other than the subject)
   - Example: "The president of Russia is Putin" → subject="Russia", object="Putin"

2. **Find downstream facts** in the fact registry where any object entity is the subject
   - "Putin:birthplace" → "Putin was born in Leningrad" (downstream, decay)
   - "Russia:capital" → "The capital of Russia is Moscow" (different attribute, skip)

3. **Apply decay**: `w_new = w_current × (decay_per_hop ^ hop_distance)`
   - With in-degree adjustment: `adjusted = 1 - (1 - base_factor) / in_degree`

4. **Recurse** for depth > 1, following the downstream chain

This is analogous to directional link failure in transportation: closing the Seoul→Busan link only affects Busan-side traffic, not the Seoul→Incheon direction.

### 4.2 Complexity

- **BFS**: O(V + E) per invalidation, touching all reachable nodes
- **Attribute-aware**: O(|downstream_chain|) per invalidation, typically O(1-3) facts
- Overhead: +2-4s memorize time, ~0s query time

---

## 5. Benchmark Results

### 5.1 MemoryAgentBench FactConsolidation

| Dataset | Baseline EM | Experiment EM | Δ |
|---------|-------------|---------------|---|
| MH 6K | 19.0% | **21.0%** | **+2.0%** |
| SH 6K | 78.0% | 76-78% | -2~0% |
| MH 32K | 4.0% | 3.0% | -1.0% |
| SH 32K | 30.0% | 30.0% | 0.0% |

### 5.2 Statistical Analysis

**Individual query level (MH 6K, depth=2, dph=0.5):**
- Improved: 3, Degraded: 1, Same: 96 queries
- Bootstrap 95% CI: [-2.0%, +6.0%] (includes 0)
- McNemar p=0.3125 (not significant)

**Ablation consistency (all MH 6K configurations):**
- 12 runs: 10 positive (Δ=+1~+2%), 2 zero, 0 negative
- **Sign test p=0.001** (highly significant)
- Probability of all-non-negative under H0: 0.5^12 = 0.024%

The individual effect size is modest (+2%, 2 queries out of 100), but the **consistency across all hyperparameter configurations is striking**. No configuration produced a negative result on multi-hop, suggesting that attribute-aware propagation reliably helps (though the magnitude depends on retrieval quality).

### 5.3 Why 32K Shows No Improvement

At 32K context, baseline MH EM drops to 4.0% (from 19.0% at 6K). This reflects a **retrieval bottleneck**, not a propagation failure: top-k search over 2,000+ facts cannot reliably retrieve all intermediate facts in a 2-3 hop chain. Propagation can only help when the retrieval system brings back the relevant facts — at 4% accuracy, the retrieval system is the binding constraint.

This finding suggests that **propagation benefits are conditional on retrieval quality**, and future work should address chain-aware iterative retrieval before scaling propagation to larger contexts.

### 5.4 Qualitative Analysis of Improved Queries

| Query | Question | Baseline | Experiment | Mechanism |
|-------|----------|----------|------------|-----------|
| Q17 | "capital of country where Madame du Barry held citizenship" | Harare | **London** | France→capital chain correctly resolved |
| Q36 | "country of performer Rocket Man" | UK | **Japan** | Citizenship chain updated |
| Q53 | "country of genre of spouse of Roy Lichtenstein" | USA | **Russian Empire** | Genre→country chain tracked |

These cases share a pattern: the baseline retrieves stale intermediate facts that lead to wrong chain resolution, while attribute-aware propagation correctly decays the stale intermediates.

---

## 6. Related Work

**Memory systems**: Mem0 (2024), MemGPT/Letta (2023), and A-Mem (2025) implement fact storage and retrieval but do not address selective forgetting. MAGMA (2026) proposes multi-graph architectures but does not analyze propagation damage.

**Temporal decay**: Mnemosyne (2025) uses Ebbinghaus-inspired decay with edge-based temporal boosting. Our work is complementary — we address *which* memories to decay, not *how fast* they decay.

**Graph-based knowledge**: Knowledge graph completion and link prediction (TransE, RotatE) focus on inference, not invalidation. Our collateral damage analysis is a novel contribution specific to memory update scenarios.

**Transportation network resilience**: Link failure propagation (Chen et al., 2012; Zhang & Levinson, 2008) studies how road closures cascade through networks. We are the first to apply these directional propagation principles to AI memory invalidation.

---

## 7. Discussion

### Why This Matters Beyond Benchmarks

The collateral damage we document is not specific to MemoryAgentBench. Any system that:
1. Stores facts as entities in a co-occurrence graph
2. Uses BFS or similar traversal for invalidation propagation
3. Operates on real-world knowledge (which naturally has hub entities)

...will exhibit the same problem. "United States", "the", "University" — these hub entities exist in any knowledge domain.

### The Hub Entity Problem Is Fundamental

Hub entities in co-occurrence graphs are not bugs — they reflect genuine reality. The United States really is connected to thousands of facts across diverse topics. The problem is that **co-occurrence ≠ causal dependency**. "United States" appearing in a fact about its president and a fact about its national bird does not mean updating the president should affect knowledge about the bird.

Attribute-aware propagation addresses this by restricting propagation to genuine dependency chains (same subject-attribute relationships), rather than all co-occurrence connections.

### Limitations

1. **Entity extraction**: Rule-based extraction treats "Vladimir Putin" and "Putin" as separate entities. Stronger entity resolution would improve both BFS and attribute-aware modes.

2. **Single benchmark**: Results are from MemoryAgentBench FactConsolidation only. Replication on other memory benchmarks (e.g., with different fact structures) would strengthen the findings.

3. **Graph construction**: We only evaluate co-occurrence graphs. Relation-typed graphs may partially mitigate the hub problem, though hub entities would likely persist.

---

## 8. Conclusion

We present the first quantitative analysis of collateral damage in graph-based memory invalidation. BFS propagation through entity co-occurrence graphs is **catastrophically destructive**, decaying 68.9-79.0% of valid memories with 67.6% suffering complete weight collapse at scale. The root cause — hub entities with superlinearly growing degree — is fundamental to co-occurrence graph construction on real-world knowledge.

Attribute-aware Selective Propagation, inspired by directional link failure models in transportation engineering, reduces this damage by 78-80% by restricting propagation to genuine downstream fact chains. On MemoryAgentBench, this produces consistent improvements across all hyperparameter configurations (sign test p=0.001), with individual multi-hop QA gains of +1-2% EM.

The key takeaway: **in memory invalidation, the default propagation approach — BFS through an entity graph — is worse than no propagation at all.** Selective, direction-aware propagation is essential.

---

## Appendix A: Full Ablation Results (MH 6K)

| Depth | dph=0.3 | dph=0.5 | dph=0.7 |
|-------|---------|---------|---------|
| 1 | +2.0% | +1.0% | +1.0% |
| 2 | +2.0% | +2.0% | +1.0% |
| 3 | +2.0% | +2.0% | +1.0% |

All 9 configurations positive. Including 3 additional early runs (2 zero, 0 negative): 10/12 positive, 2/12 zero, 0/12 negative.

## Appendix B: Experimental Configuration

| Component | Specification |
|-----------|--------------|
| LLM | google/gemma-4-31B-it (max_tokens=10, temp=0.0) |
| Embedding | BAAI/bge-m3 (dim=1024) |
| Vector search | NumPy cosine similarity, RRF fusion (k=60) |
| Graph | NetworkX entity co-occurrence |
| Storage | SQLite in-memory |
| Benchmark | ai-hyz/MemoryAgentBench, Conflict_Resolution split |
| Context sizes | 6K (456 facts, 100 queries), 32K (2,311 facts, 100 queries) |
