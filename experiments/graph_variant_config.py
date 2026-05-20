GRAPH_VARIANTS = {
    "raw_rule_based": {
        "description": "Current graph construction without additional filtering.",
        "filter_entities": False,
        "typed_edges_only": False,
    },
    "stopword_pronoun_filtered": {
        "description": "Remove function-word/pronoun entity nodes before analysis.",
        "filter_entities": True,
        "typed_edges_only": False,
    },
    "typed_relation_only": {
        "description": "Restrict propagation analysis to subject:attribute-style facts.",
        "filter_entities": True,
        "typed_edges_only": True,
    },
}


def validate_variant(name: str) -> dict:
    if name not in GRAPH_VARIANTS:
        raise ValueError(f"Unknown graph variant: {name}")
    return GRAPH_VARIANTS[name]
