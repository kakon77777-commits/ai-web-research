from __future__ import annotations
from hashlib import sha256
from .models import SourceFamily, SourceFamilyResolution, SourceNode, SourceRelation, SourceRelationType

_COLLAPSING = {
    SourceRelationType.SYNDICATED_FROM,
    SourceRelationType.MIRRORS,
    SourceRelationType.DERIVED_FROM,
    SourceRelationType.TRANSLATED_FROM,
    SourceRelationType.SAME_ORIGIN_FAMILY,
}
_DIRECTIONAL = _COLLAPSING - {SourceRelationType.SAME_ORIGIN_FAMILY}


def _family_id(members: tuple[str, ...]) -> str:
    digest = sha256('|'.join(members).encode('utf-8')).hexdigest()[:20]
    return f'source-family:{digest}'


def _has_cycle(members: set[str], edges: dict[str, set[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in edges.get(node, ()):
            if nxt in members and visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False
    return any(visit(node) for node in sorted(members))


def resolve_source_families(nodes: tuple[SourceNode, ...], relations: tuple[SourceRelation, ...]) -> SourceFamilyResolution:
    node_by_id = {node.source_id: node for node in nodes}
    parent = {source_id: source_id for source_id in node_by_id}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        lo, hi = sorted((ra, rb))
        parent[hi] = lo

    directed: dict[str, set[str]] = {}
    for relation in relations:
        if relation.from_source_id not in node_by_id or relation.to_source_id not in node_by_id:
            continue
        if relation.relation_type in _COLLAPSING:
            union(relation.from_source_id, relation.to_source_id)
        if relation.relation_type in _DIRECTIONAL:
            directed.setdefault(relation.from_source_id, set()).add(relation.to_source_id)

    components: dict[str, set[str]] = {}
    for source_id in node_by_id:
        components.setdefault(find(source_id), set()).add(source_id)

    source_to_family: dict[str, str] = {}
    families: dict[str, SourceFamily] = {}
    for members_set in components.values():
        members = tuple(sorted(members_set))
        family_id = _family_id(members)
        cycle = _has_cycle(members_set, directed)
        root_candidates = [source_id for source_id in members if not (directed.get(source_id, set()) & members_set)]
        if not root_candidates:
            root = members[0]
            resolved = False
        else:
            root = min(root_candidates, key=lambda sid: (node_by_id[sid].published_at is None, node_by_id[sid].published_at or '', sid))
            resolved = (not cycle) and (len(members) == 1 or len(root_candidates) == 1)
        family = SourceFamily(family_id, members, root, resolved, cycle)
        families[family_id] = family
        for source_id in members:
            source_to_family[source_id] = family_id
    return SourceFamilyResolution(source_to_family=source_to_family, families=families)
