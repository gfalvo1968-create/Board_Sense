"""SPIKE Web Scout.

Web evidence is advisory. SPIKE remains final authority because the physical
board may be modified, incomplete, damaged, or merely resemble a web listing.
A search provider can populate `matches`; this module scores those matches
without allowing them to overwrite structural evidence.
"""

from urllib.parse import quote_plus


def build_search_queries(board_type, identifiers=None, structural_anchors=None):
    identifiers = [str(x).strip() for x in (identifiers or []) if str(x).strip()]
    anchors = [str(x).strip() for x in (structural_anchors or []) if str(x).strip()]
    queries = []
    for ident in identifiers[:5]:
        queries.append(f'"{ident}" circuit board PCB')
    if board_type:
        detail = " ".join(anchors[:4])
        queries.append(f'{board_type} PCB {detail}'.strip())
    return queries[:6]


def search_links(queries):
    """Return provider-neutral search launch links until an API is configured."""
    return [
        {"query": q, "search_url": f"https://www.google.com/search?q={quote_plus(q)}"}
        for q in queries
    ]


def evaluate_matches(spike_family, matches=None):
    """Classify supplied web matches as support/conflict/neutral, never authority."""
    matches = matches or []
    evaluated = []
    support = conflict = 0
    target = str(spike_family or "").lower()
    for item in matches[:10]:
        title = str(item.get("title", ""))
        snippet = str(item.get("snippet", ""))
        text = f"{title} {snippet}".lower()
        relation = "neutral"
        if target and any(word in text for word in target.replace("/", " ").split() if len(word) > 4):
            relation = "supports"
            support += 1
        elif item.get("claimed_family"):
            relation = "conflicts"
            conflict += 1
        evaluated.append({**item, "relation_to_spike": relation})
    return {
        "authority": "advisory_only",
        "spike_has_final_decision": True,
        "supporting_matches": support,
        "conflicting_matches": conflict,
        "matches": evaluated,
        "rule": "Web identity is evidence about origin; SPIKE classifies the physical board as it exists now.",
    }


def web_scout_packet(board_type, identifiers=None, structural_anchors=None, matches=None):
    queries = build_search_queries(board_type, identifiers, structural_anchors)
    return {
        "status": "provider_ready" if matches else "search_provider_not_configured",
        "queries": queries,
        "search_launchers": search_links(queries),
        "evaluation": evaluate_matches(board_type, matches),
        "decision_authority": "SPIKE",
    }
