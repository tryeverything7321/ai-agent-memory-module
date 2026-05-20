# Graph Construction Variant Design

## Purpose

The paper must show that the blast-radius result is not only an artifact of one
rule-based extraction pipeline.

## Variants

1. `raw_rule_based`: current graph construction.
2. `stopword_pronoun_filtered`: remove function-word and pronoun entity nodes.
3. `named_entity_actionable`: current headline hub selection; graph unchanged.
4. `typed_relation_only`: propagate only over facts with explicit subject:attribute keys.

## Minimum Acceptance Criterion

The qualitative BFS > ATTR-AWARE blast-radius gap should survive at least
`raw_rule_based`, `stopword_pronoun_filtered`, and `typed_relation_only`.

## Paper Use

If graph variants reduce absolute blast radius but preserve ordering, the paper
can claim the failure mode is not solely caused by extraction artifacts.
