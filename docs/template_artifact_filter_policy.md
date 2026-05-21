# Template Artifact Filter Policy

Date: 2026-05-21

## Purpose

The graph-memory experiments should not treat chat templates, instruction
phrases, pronouns, titles, or sentence scaffolding as content entities. Earlier
runs surfaced raw hubs such as `And`, `She`, `But`, and LongMemEval surfaced
template hubs such as `Chat Time`, `Here`, `Use`, `Make`, and `Can`.

This policy defines a conservative artifact filter for hub diagnostics. It is
not a replacement for a full NER or typed-entity pipeline.

## Current Filter Classes

1. Function words and pronouns:
   `and`, `but`, `she`, `he`, `it`, `they`, `there`, `this`, `that`, etc.
2. Titles and address forms:
   `mr`, `mrs`, `ms`, `miss`, `monsieur`.
3. Chat-template and instruction artifacts observed in LongMemEval:
   `chat time`, `here`, `use`, `make`, `can`, `remember`, `start`, `tips`,
   `avoid`, `check`.

## How To Use

Use `filter_named_entity_hubs` or `select_actionable_hubs` for headline hub
diagnostics. Raw hubs may still be reported as a diagnostic of graph-construction
failure, but paper claims about content-entity propagation should use filtered
hubs.

## What This Does Not Prove

Passing this filter does not prove that a hub is semantically valid. It only
removes known artifact classes that would otherwise make the graph analysis
obviously brittle. Top-tier evidence still needs:

- typed entity extraction or NER normalization;
- controlled synthetic memory graphs with known dependencies;
- false-negative audits for dependency-aware propagation.

## Paper Framing

The correct framing is:

> We separate raw hub diagnostics from content-entity hub analysis. Raw hubs
> reveal graph-construction brittleness, while filtered hubs are used for
> propagation-risk claims.

Do not claim that the stoplist fully solves artifact risk.
