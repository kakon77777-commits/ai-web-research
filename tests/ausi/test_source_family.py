from ai_web_research.source_graph.family import resolve_source_families
from ai_web_research.source_graph.models import (
    RelationInferenceType, SourceNode, SourceRelation, SourceRelationType,
)


def node(sid, published=None):
    return SourceNode(sid, f'https://{sid}.example/', None, published, '2026-08-31T15:00:00Z', None, None, {})


def rel(rid, child, parent, kind):
    return SourceRelation(rid, child, parent, kind, 1.0, RelationInferenceType.EXPLICIT, ('fixture',))


def test_dependency_chain_collapses_but_independent_repo_remains_separate():
    nodes=(node('official','2026-08-31T10:00:00Z'),node('media_a','2026-08-31T10:10:00Z'),node('media_b','2026-08-31T10:20:00Z'),node('repo','2026-08-31T10:02:00Z'))
    relations=(
        rel('r1','media_a','official',SourceRelationType.DERIVED_FROM),
        rel('r2','media_b','media_a',SourceRelationType.SYNDICATED_FROM),
    )
    result=resolve_source_families(nodes,relations)
    assert result.source_to_family['official'] == result.source_to_family['media_a'] == result.source_to_family['media_b']
    assert result.source_to_family['repo'] != result.source_to_family['official']
    fam=result.families[result.source_to_family['official']]
    assert fam.root_source_id == 'official'
    assert fam.root_resolved is True
    assert result.independent_root_count(('official','media_a','media_b','repo')) == 2


def test_cites_and_links_do_not_collapse_families():
    nodes=(node('a'),node('b'),node('c'))
    relations=(rel('r1','a','b',SourceRelationType.CITES),rel('r2','b','c',SourceRelationType.LINKS_TO))
    result=resolve_source_families(nodes,relations)
    assert result.independent_root_count(('a','b','c')) == 3


def test_mirror_translation_and_same_origin_are_collapsing_relations():
    nodes=(node('root'),node('mirror'),node('translation'),node('alias'))
    relations=(
        rel('r1','mirror','root',SourceRelationType.MIRRORS),
        rel('r2','translation','root',SourceRelationType.TRANSLATED_FROM),
        rel('r3','alias','root',SourceRelationType.SAME_ORIGIN_FAMILY),
    )
    result=resolve_source_families(nodes,relations)
    assert result.independent_root_count(tuple(n.source_id for n in nodes)) == 1


def test_cycle_is_deterministic_but_root_unresolved():
    nodes=(node('a'),node('b'))
    relations=(rel('r1','a','b',SourceRelationType.DERIVED_FROM),rel('r2','b','a',SourceRelationType.DERIVED_FROM))
    one=resolve_source_families(nodes,relations)
    two=resolve_source_families(tuple(reversed(nodes)),tuple(reversed(relations)))
    assert one.source_to_family == two.source_to_family
    fam=one.families[one.source_to_family['a']]
    assert fam.root_resolved is False
    assert fam.cycle_detected is True
    assert fam.root_source_id == 'a'


def test_unknown_source_ids_count_as_distinct_unresolved_roots():
    result=resolve_source_families((node('known'),),())
    assert result.independent_root_count(('known','unknown_1','unknown_2')) == 3
