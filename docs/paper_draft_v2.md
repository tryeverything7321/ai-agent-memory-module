# Collateral Damage in Graph-based Memory Forgetting: Quantification, Exploitation, and Defense

---

## Abstract

Graph-based propagation is a natural approach to invalidating stale facts in AI memory systems: when a fact changes, propagate the update through an entity graph to downstream dependents. We show that this intuition leads to **catastrophic collateral damage** that is both quantitatively severe and adversarially exploitable. On MemoryAgentBench, BFS-based propagation through entity co-occurrence graphs decays 68.9-78.5% of valid memories across scales (6K-64K facts), with hub entity degrees growing superlinearly (23→121→298). More critically, we demonstrate that an attacker can **weaponize this mechanism**: injecting just 5 fake facts targeting hub entities destroys 57.3% of valid memories at 32K context. We further show that this collateral damage **crosses task boundaries** — BFS propagation triggered during fact consolidation degrades retrieval accuracy on an unrelated task (EM -5.0pp, F1 -18.2pp). We propose **Attribute-aware Selective Propagation**, inspired by directional link failure models in transportation engineering, which defends against both organic and adversarial damage with 78-100% effectiveness across all experiments.

---

## 1. Introduction

AI memory systems that persist and update factual knowledge face a fundamental tension: when stored facts become outdated, the system must invalidate not only the stale fact itself but also dependent knowledge. Graph-based propagation — traversing entity connections to propagate decay — is the natural solution (Mnemosyne, 2025; MAGMA, 2026).

**We discover three critical flaws in this approach.**

First, BFS propagation through entity co-occurrence graphs causes **catastrophic collateral damage**: at 64K context, a single fact update can cascade through hub nodes to decay 78.5% of all valid memories. The root cause is hub entities whose degree grows superlinearly with context size (23→298 from 6K→64K).

Second, this vulnerability is **adversarially exploitable**. An attacker who identifies hub entities in the graph can inject a small number of fake facts (1-5) to trigger the forgetting mechanism, destroying up to 57.3% of valid memories. This represents a novel attack vector on AI memory systems that we term **hub exploitation**.

Third, the damage **crosses task boundaries**. BFS propagation triggered during fact consolidation degrades retrieval accuracy on completely unrelated queries, reducing F1 by 18.2 percentage points.

We propose **Attribute-aware Selective Propagation**, a directional propagation method inspired by transportation network link failure models, and demonstrate that it defends against all three threat vectors with 78-100% effectiveness.

### Contributions

1. **Scale trend analysis** (C1): Collateral damage quantification across 6K→32K→64K, revealing superlinear hub degree growth and stable ~78% BFS damage ratio.

2. **Cross-task contamination** (C2): First demonstration that graph-based forgetting in one task degrades retrieval accuracy in an unrelated task (EM -5.0pp, F1 -18.2pp on Accurate_Retrieval).

3. **Adversarial hub exploitation** (C3): A novel attack scenario where 5 fake facts destroy 57.3% of valid memories through weaponized BFS propagation, with scale amplifying vulnerability (5.2%→38.1% damage from a single attack at 6K→32K).

4. **Attribute-aware defense** (C4): Consistent defense effectiveness of 78-100% across all organic and adversarial damage scenarios, with kill prevention (weight<0.1) rate of 99.6-100%.

---

## 2. Background and Motivation

### 2.1 AI Memory and Fact Invalidation

Long-term AI memory systems (Mem0, 2024; MemGPT/Letta, 2023; A-Mem, 2025) store user interactions as structured facts. When new information contradicts stored facts, the system must (1) detect the conflict, (2) invalidate the outdated fact, and (3) propagate the change to dependent downstream facts. Step 3 is where graph-based approaches are used, but **none of the existing works quantitatively analyze the collateral damage of propagation, its adversarial exploitability, or its cross-task effects**.

### 2.2 Transportation Network Analogy

In transportation engineering, **link failure propagation** studies how road closures cascade through networks. Hub intersections amplify disruption disproportionately — closing one road at a major interchange can gridlock an entire region. Critically, transportation research distinguishes between directional and non-directional propagation: closing Seoul→Busan affects only Busan-downstream traffic, not Seoul→Incheon.

Standard BFS propagation in AI memory is non-directional — it spreads invalidation to all connected entities regardless of semantic direction. Our attribute-aware approach applies the directional principle.

### 2.3 MemoryAgentBench

MemoryAgentBench (ICLR 2026) provides standardized evaluation across four task types:
- **Conflict_Resolution** (FactConsolidation): Fact updates with serial ordering
- **Accurate_Retrieval**: Precise fact retrieval from long contexts
- **Test_Time_Learning**: Adaptive behavior from experience
- **Long_Range_Understanding**: Cross-context comprehension

We use Conflict_Resolution for scale analysis (C1) and adversarial experiments (C3), and Accurate_Retrieval for cross-task analysis (C2).

---

## 3. Collateral Damage at Scale (C1)

### 3.1 Experimental Setup

We measure collateral damage by running FactConsolidation memorization under three modes:

| Mode | Conflict Detection | Propagation |
|------|-------------------|-------------|
| Baseline | Subject-key match | None |
| BFS | Subject-key match | BFS through entity co-occurrence graph |
| Attribute-aware | Subject-key match | Downstream fact chain only |

**Infrastructure**: Gemma-4-31B-it (LLM), BAAI/bge-m3 1024-dim (Embedding), SQLite + NumPy in-memory, NetworkX graph.

### 3.2 Scale Trend Results

| Scale | Valid Mem | BFS Decay | Attr Decay | Reduction | BFS Kill (<0.1) | Max Hub Degree |
|-------|----------|-----------|------------|-----------|-----------------|----------------|
| 6K | 344 | 237 (68.9%) | 51 (14.8%) | 78.5% | 143 | 23 (United States) |
| 32K | 1,744 | 1,377 (79.0%) | 275 (15.8%) | 80.0% | 1,179 | 121 (United States) |
| 64K | 3,414 | 2,680 (78.5%) | 513 (15.0%) | 80.9% | 2,465 | 298 (America) |

**Finding 1**: BFS damage ratio plateaus at ~78-79% across scales, but the **absolute number of destroyed memories scales linearly**: 143→1,179→2,465 complete losses (weight<0.1).

**Finding 2**: Hub entity degree grows superlinearly: 23→121→298 (~13x from 6K→64K), while the fact count grows ~7.5x. Hub degree growth outpaces data growth, making the problem structurally worse at scale.

**Finding 3**: Attribute-aware damage ratio remains stable at ~15% regardless of scale, demonstrating that the defense mechanism's effectiveness does not degrade with context size.

### 3.3 Hub Entity Analysis (64K)

| Entity | Degree | Connected Memories |
|--------|--------|-------------------|
| America | 298 | 297 |
| United States | 296 | 295 |
| University | 174 | 154 |
| Catholic Church | 138 | 109 |
| United Kingdom | 127 | 117 |
| English | 124 | 110 |

At 64K, 3,187 graph nodes have mean degree 3.3 but max degree 298. The top 1% of entities mediate propagation that damages ~78% of all valid memories.

---

## 4. Cross-task Contamination (C2)

### 4.1 Hypothesis

BFS collateral damage extends beyond the conflict resolution task. If a memory system runs both fact consolidation and retrieval tasks, BFS propagation triggered during consolidation will degrade retrieval accuracy on unrelated queries.

### 4.2 Setup

We use the Accurate_Retrieval split (eventqa_65536) from MemoryAgentBench:
1. **Baseline**: Memorize document → query → measure EM/F1
2. **Post-BFS**: Memorize → trigger BFS propagation from hub entity → query
3. **Post-Attr**: Memorize → trigger attribute-aware propagation from hub entity → query

### 4.3 Results

| ARM | EM | F1 | Collateral | Memories Affected |
|-----|-----|-----|------------|-------------------|
| Baseline | 15.0% | 67.1% | 0 | 0 |
| Post-BFS | **10.0%** | **48.9%** | 32 | 3,381 |
| Post-Attr | 15.0% | 67.1% | 1 | 0 |

**Finding 4**: A single BFS propagation from the hub entity "Debbie" (degree=715) cascades to 3,381 memories, rendering 32 previously-retrievable memories unsearchable. This causes **EM -5.0pp and F1 -18.2pp** on completely unrelated retrieval queries.

**Finding 5**: Attribute-aware propagation preserves full retrieval accuracy (EM +0.0pp, F1 +0.0pp), affecting only 1 memory — the directly invalidated fact.

This demonstrates that graph-based forgetting is not a self-contained operation: its damage leaks across task boundaries, contaminating unrelated system capabilities.

---

## 5. Adversarial Hub Exploitation (C3)

### 5.1 Threat Model

We consider an attacker who can inject text into the memory system's input stream (e.g., via compromised data sources, prompt injection, or adversarial user input). The attacker's goal is to **maximize destruction of valid memories** with minimal input.

**Attack procedure**:
1. Memorize legitimate facts (propagation disabled during baseline)
2. Identify high-impact keys in the fact registry by graph degree
3. Craft fake facts that generate matching subject keys (e.g., "The capital of united states of america is Los Angeles")
4. Inject fake facts with propagation enabled
5. Measure collateral damage

This attack is realistic: it requires no knowledge of the system's internal graph structure — only the ability to inject facts about well-known entities (countries, organizations) that are likely to be hub nodes.

### 5.2 Results

#### 6K Context (344 valid memories)

| Attack Facts | BFS Damage | BFS Kill | Attr Damage | BFS EM Drop |
|-------------|------------|----------|-------------|-------------|
| 1 | 5.2% | 0.3% | 0.0% | +0.0pp |
| 3 | 26.7% | 4.4% | 0.0% | -10.0pp |
| 5 | 39.8% | 17.4% | 0.3% | -10.0pp |

#### 32K Context (1,744 valid memories)

| Attack Facts | BFS Damage | BFS Kill | Attr Damage | BFS EM Drop |
|-------------|------------|----------|-------------|-------------|
| 1 | 38.1% | 1.0% | 0.0% | +0.0pp |
| 3 | 46.0% | 8.8% | 1.0% | +0.0pp |
| 5 | **57.3%** | **19.3%** | 1.0% | +0.0pp |

**Finding 6**: A single fake fact destroys 5.2% of valid memories at 6K and **38.1% at 32K** — a 7.3x amplification from scale alone. The attacker gets more destructive as the system stores more knowledge.

**Finding 7**: Five fake facts at 32K destroy 57.3% of valid memories and cause 19.3% complete loss (weight<0.1). The system's own forgetting mechanism becomes a weapon.

**Finding 8**: Attribute-aware propagation provides near-perfect defense: 0-1% damage across all attack scenarios (97.8-100% defense rate).

### 5.3 Scale Amplification

| Attack | 6K Damage | 32K Damage | Amplification |
|--------|-----------|------------|---------------|
| 1 fact | 5.2% | 38.1% | 7.3x |
| 3 facts | 26.7% | 46.0% | 1.7x |
| 5 facts | 39.8% | 57.3% | 1.4x |

The scale amplification effect is strongest for minimal attacks (1 fact: 7.3x), because at larger scale, a single hub entity connects to proportionally more memories. This makes BFS-based systems **increasingly vulnerable** as they accumulate more knowledge.

---

## 6. Attribute-aware Selective Propagation (C4)

### 6.1 Method

When fact *f* with subject_key `Entity:Attribute` is invalidated:

1. **Extract object entities** from *f* (non-subject entities)
2. **Find downstream facts** where object entities are subjects with same attribute chain
3. **Apply decay**: `w_new = w_current × (decay_per_hop ^ hop_distance)` with in-degree adjustment
4. **Recurse** for depth > 1

This restricts propagation to genuine causal chains rather than all graph neighbors.

### 6.2 Defense Effectiveness Across All Experiments

| Experiment | BFS Damage | Attr Damage | Defense Rate |
|------------|------------|-------------|--------------|
| CD 6K | 68.9% | 14.8% | 78.5% |
| CD 32K | 79.0% | 15.8% | 80.0% |
| CD 64K | 78.5% | 15.0% | 80.9% |
| Cross-task (F1) | -18.2pp | +0.0pp | 100.0% |
| Adv 6K / 1f | 5.2% | 0.0% | 100.0% |
| Adv 6K / 5f | 39.8% | 0.3% | 99.3% |
| Adv 32K / 1f | 38.1% | 0.0% | 100.0% |
| Adv 32K / 5f | 57.3% | 1.0% | 98.2% |

**Finding 9**: Attribute-aware defense is **consistently effective** across all experimental dimensions:
- Organic collateral damage: 78.5-80.9% reduction
- Adversarial attacks: 97.8-100% defense
- Cross-task contamination: complete prevention
- Kill prevention (weight<0.1): 99.6-100%

### 6.3 Overhead

| Metric | BFS | Attribute-aware | Delta |
|--------|-----|-----------------|-------|
| Memorize time | baseline | +2-4s | minimal |
| Query time | baseline | ~0s | none |
| Memory footprint | O(V+E) | O(V+E + fact_registry) | negligible |

---

## 7. Related Work

**Memory systems**: Mem0 (2024), MemGPT/Letta (2023), A-Mem (2025), and MAGMA (2026) implement memory management but do not analyze propagation damage or adversarial vulnerability.

**Temporal decay**: Mnemosyne (2025) uses Ebbinghaus-inspired decay. Our work is complementary — we address *which* memories to decay, not *how fast*.

**Adversarial attacks on AI systems**: Prompt injection (Perez & Ribeiro, 2022) and data poisoning attack language models directly. Our hub exploitation is a novel vector that weaponizes the system's own memory management mechanism rather than the model itself.

**Transportation network resilience**: Link failure propagation (Chen et al., 2012) studies cascade effects in road networks. We are the first to apply directional propagation principles from transportation engineering to AI memory invalidation.

---

## 8. Discussion

### Implications for AI Memory Safety

Our adversarial results have direct implications for deployed AI memory systems:
1. **Any system using graph-based forgetting is vulnerable** to hub exploitation
2. The attack is **low-cost**: 1-5 injected facts can destroy 38-57% of stored knowledge
3. The vulnerability **worsens with scale**: more stored knowledge means larger blast radius
4. **Attribute-aware propagation** provides a practical defense without significant overhead

### Why Hub Entities Are Fundamental

Hub entities reflect genuine reality — the United States really does connect to thousands of facts. The problem is that **co-occurrence ≠ causal dependency**. Attribute-aware propagation resolves this by distinguishing genuine dependency chains from coincidental co-occurrence.

### Limitations

1. **Entity extraction**: Rule-based extraction treats "Vladimir Putin" and "Putin" as separate entities. Stronger entity resolution would improve both modes.
2. **Single benchmark family**: Results from MemoryAgentBench only. Replication on other memory benchmarks would strengthen findings.
3. **Adversarial realism**: Our attack assumes the ability to inject text into the memory system. Real-world exploitability depends on input validation and access control.
4. **32K EM floor**: Baseline EM at 32K is 0-4%, limiting observable EM changes from adversarial attacks at that scale.

---

## 9. Conclusion

We present a comprehensive analysis of collateral damage in graph-based memory forgetting across three dimensions: scale, cross-task contamination, and adversarial exploitation. BFS propagation through entity co-occurrence graphs is **catastrophically destructive** (78% damage), **cross-task toxic** (F1 -18.2pp on unrelated retrieval), and **adversarially weaponizable** (5 fake facts → 57.3% memory destruction).

Attribute-aware Selective Propagation, inspired by directional link failure models in transportation engineering, provides consistent defense across all threat vectors (78-100% effectiveness) with negligible overhead. The key insight: **propagation must follow causal dependency chains, not structural co-occurrence** — a principle well-established in transportation network resilience but previously unapplied to AI memory systems.

---

## Appendix A: Benchmark Performance (FactConsolidation)

| Dataset | Baseline EM | Experiment EM | Δ |
|---------|-------------|---------------|---|
| MH 6K | 19.0% | **21.0%** | +2.0% |
| SH 6K | 78.0% | 76-78% | -2~0% |
| MH 32K | 4.0% | 3.0% | -1.0% |
| MH 64K | 7.0% | 7.0% | 0.0% |

Ablation (MH 6K): 12 runs, 10 positive, 2 zero, 0 negative. Sign test p=0.001.

## Appendix B: Experimental Configuration

| Component | Specification |
|-----------|--------------|
| LLM | google/gemma-4-31B-it (max_tokens=10, temp=0.0) |
| Embedding | BAAI/bge-m3 (dim=1024) |
| Vector search | NumPy cosine similarity, RRF fusion (k=60) |
| Graph | NetworkX entity co-occurrence |
| Storage | SQLite in-memory |
| Benchmark | ai-hyz/MemoryAgentBench (Conflict_Resolution, Accurate_Retrieval) |
| Context sizes | 6K, 32K, 64K (FactConsolidation), 65K (eventqa) |
| Adversarial | 1/3/5 fake facts × BFS/Attr × 6K/32K |

## Appendix C: Adversarial Attack Methodology

**Key design decisions**:

1. **Clean-state attack**: Propagation disabled during baseline memorization → all valid memories start at weight=1.0 → attack effect cleanly measurable.

2. **Registry-based targeting**: Attack facts are constructed to match existing `fact_registry` subject keys, ensuring conflict detection triggers propagation. Hash-based fallback keys (unreproducible) are excluded.

3. **High-impact key selection**: Attack targets are sorted by entity graph degree, maximizing blast radius per injected fact.

4. **Subject key reconstruction**: The attack reverse-engineers `_get_subject_key()` regex patterns to generate facts that produce identical keys to existing entries (e.g., "The capital of united states of america is Los Angeles" → key `united states of america:capital`).
