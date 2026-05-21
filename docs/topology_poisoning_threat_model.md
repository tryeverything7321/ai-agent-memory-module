# Topology Poisoning Threat Model

## Definition

Topology poisoning is an attack on graph-memory construction in which repeated
generic or template-like phrases are extracted as entities and become
high-degree graph hubs. Later maintenance operations such as invalidation or
forgetting propagation can traverse these fabricated hubs.

## Difference From Content-Hub Attack

Content-hub attack targets an existing high-degree content entity such as a
person, location, or organization.

Topology poisoning fabricates the hub itself by repeatedly introducing phrases
such as `Project Note`, `Current Context`, `Important Reminder`, or `Chat Time`.

## Attacker Capability

The attacker can write memories or messages that are stored by the memory system.
The attacker does not need direct graph access. The attacker may not know the
current graph topology.

## Current Evidence

LongMemEval dry checks show that repeated template phrases such as `Chat Time`,
`Here`, `Use`, `Make`, and `Can` can dominate naive hub rankings. This is not yet
an attack result; it is evidence that naive graph construction can form
non-semantic hubs.

## Required Experiment

Inject repeated generic phrases into otherwise clean memory streams and measure:

1. whether the phrase becomes a top-k hub;
2. whether propagation from that hub creates increased blast radius;
3. whether filtering or typed extraction prevents hub fabrication.
