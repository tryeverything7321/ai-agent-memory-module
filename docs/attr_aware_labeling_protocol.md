# ATTR-AWARE Dependency Labeling Protocol

## Labels

`SHOULD_PROPAGATE`: the target memory depends on the invalidated fact; failing
to propagate would leave stale or contradictory memory.

`SHOULD_NOT_PROPAGATE`: the target memory only co-occurs with the invalidated
fact or shares an entity without depending on it.

`BORDERLINE`: dependency cannot be determined from the stored memory text alone.

## Decision Rules

Label `SHOULD_PROPAGATE` when the target memory states an attribute, event, or
relationship whose truth would change if the source fact is invalidated.

Label `SHOULD_NOT_PROPAGATE` when the target memory mentions the same entity but
describes an independent fact, unrelated event, or different relationship.

Label `BORDERLINE` when the target memory could depend on the source fact but
the dependency requires unstated background knowledge.
