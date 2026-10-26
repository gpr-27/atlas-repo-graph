"""Cross-repo linker: produces CALLS and CONSUMES edges (architecture §5.5)."""
import re
from collections import defaultdict

from atlas.models import Edge, Evidence, Node


def link(nodes: list[Node], snippets: dict[str, str]) -> list[Edge]:
    """nodes: all nodes from all repos. snippets: node.key -> source line text.
    Returns CALLS + CONSUMES edges (never within the same repo)."""
    edges: list[Edge] = []

    endpoints: list[Node] = [n for n in nodes if n.kind == "endpoint"]
    fields_by_name: dict[str, list[Node]] = defaultdict(list)
    for n in nodes:
        if n.kind == "field":
            fields_by_name[n.name].append(n)
    http_calls: list[Node] = [n for n in nodes if n.kind == "http_call"]
    field_refs: list[Node] = [n for n in nodes if n.kind == "field_ref"]

    # CALLS: http_call → endpoint (cross-repo, method+pattern match)
    calls_edges: list[Edge] = []
    # index: (call_repo, call_file) → list of endpoint names this file calls
    file_calls_endpoints: dict[tuple[str, str], list[str]] = defaultdict(list)

    for call in http_calls:
        call_path = call.meta.get("path", "")
        call_method = call.meta.get("method", "")
        # substitute {} → "x" to match endpoint patterns
        test_path = call_path.replace("{}", "x")
        for ep in endpoints:
            if ep.repo == call.repo:
                continue
            if ep.meta.get("method") != call_method:
                continue
            pattern = ep.meta.get("pattern", "")
            if pattern and re.fullmatch(pattern, test_path):
                snip = snippets.get(call.key, "")
                e = Edge(
                    call.key, ep.key, "CALLS", "exact",
                    Evidence(call.file, call.line, snip, "link",
                             f"{call.name} matches {ep.name}"),
                )
                calls_edges.append(e)
                file_calls_endpoints[(call.repo, call.file)].append(ep.name)

    edges.extend(calls_edges)

    # Build set of endpoint names reachable from each (repo, file) via CALLS
    # endpoint name → set of field nodes it exposes
    ep_name_to_fields: dict[str, list[Node]] = defaultdict(list)
    for f in nodes:
        if f.kind == "field":
            ep_name_to_fields[f.meta.get("endpoint", "")].append(f)

    # CONSUMES: field_ref → field
    for ref in field_refs:
        candidates = [f for f in fields_by_name.get(ref.name, []) if f.repo != ref.repo]
        if not candidates:
            continue

        snip = snippets.get(ref.key, "")
        # Check if this file has a CALLS edge to an endpoint that exposes the field
        reachable_ep_names = file_calls_endpoints.get((ref.repo, ref.file), [])

        exact_added = set()
        inferred_candidates = []

        for field in candidates:
            ep_name = field.meta.get("endpoint", "")
            if ep_name and ep_name in reachable_ep_names:
                if field.key not in exact_added:
                    edges.append(Edge(
                        ref.key, field.key, "CONSUMES", "exact",
                        Evidence(ref.file, ref.line, snip, "link",
                                 f"same file calls {ep_name}"),
                    ))
                    exact_added.add(field.key)
            else:
                inferred_candidates.append(field)

        # Add inferred only for candidates that weren't already linked exactly
        for field in inferred_candidates:
            if field.key not in exact_added:
                edges.append(Edge(
                    ref.key, field.key, "CONSUMES", "inferred",
                    Evidence(ref.file, ref.line, snip, "link", "name match only"),
                ))

    return edges
