from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.execution.models import ObservationStatus, ProviderObservation
from ai_web_research.discovery.normalize import normalize_discovery_observation


def observation():
    return ProviderObservation(
        observation_id='obs1', action_id='a1', provider_id='provider.brave_search', surface_id='surface.brave_search.web',
        status=ObservationStatus.SUCCEEDED,
        artifacts=(
            ArtifactRef(ArtifactKind.CANDIDATE,'a',metadata={'url':'HTTPS://Example.com/path#frag','title':'First','description':'snippet one','provider_rank':1,'evidence_role':'discovery_only'}),
            ArtifactRef(ArtifactKind.CANDIDATE,'b',metadata={'url':'https://example.com/path','title':'Duplicate','description':'snippet two','provider_rank':2,'evidence_role':'discovery_only'}),
            ArtifactRef(ArtifactKind.DOCUMENT,'ignored',metadata={'url':'https://ignored.example/'}),
        ), raw_ref=None, result_count=3, cost={}, latency_ms=None, continuation={}, diagnostics=(),
        occurred_at='2026-08-31T15:10:00+00:00', metadata={'query':'Model X release'},
    )


def test_normalizes_and_folds_duplicate_urls_without_creating_evidence():
    batch=normalize_discovery_observation(observation())
    assert batch.query == 'Model X release'
    assert len(batch.candidates) == 1
    c=batch.candidates[0]
    assert c.url == 'https://example.com/path'
    assert c.provider_rank == 1
    assert c.artifact_ids == ('a','b')
    assert c.title == 'First'
    assert c.snippet == 'snippet one'
    assert c.metadata['evidence_role'] == 'discovery_only'


def test_candidate_id_is_stable_for_same_provider_and_normalized_url():
    a=normalize_discovery_observation(observation()).candidates[0]
    b=normalize_discovery_observation(observation()).candidates[0]
    assert a.candidate_id == b.candidate_id


def test_candidate_requires_url():
    obs=observation()
    bad=ProviderObservation(**{**obs.__dict__, 'artifacts': (ArtifactRef(ArtifactKind.CANDIDATE,'x',metadata={'provider_rank':1}),)})
    batch=normalize_discovery_observation(bad)
    assert batch.candidates == ()
