from ai_web_research.core.types import ActionKind, ArtifactKind, VersionRef
from ai_web_research.discovery.models import DiscoveryCandidate
from ai_web_research.providers.registry import ProviderRegistrySnapshot
from ai_web_research.providers.spec import MethodBinding, ProviderKind, ProviderSpec, ProviderSurface, SurfaceKind
from ai_web_research.source_graph.candidate_verification import FETCH_METHOD, CandidateFetchUnavailable, compile_candidate_fetch_action, select_fetch_binding


def _candidate(url="https://official.example/model-x"):
    return DiscoveryCandidate("candidate:1", url, "Official result", "snippet only", "provider.search", "surface.search", 1, ("artifact:1",), {"evidence_role":"discovery_only"})


def _provider(provider_id, surface_id, capability):
    return ProviderSpec(provider_id,"1.0.0",ProviderKind.CRAWLER,provider_id,(),(),(),(ProviderSurface(surface_id,SurfaceKind.PUBLIC_API,None,frozenset({capability}),None,(),{},{}),),{})


def _binding(binding_id, provider_id, surface_id, *, enabled=True):
    return MethodBinding(binding_id,FETCH_METHOD,VersionRef(provider_id,"1.0.0"),surface_id,f"adapter.{provider_id}","1.0.0",enabled,{}, {})


def test_candidate_compiles_to_existing_fetch_document_action():
    binding=_binding("binding.fetch.a","provider.a","surface.a")
    compiled=compile_candidate_fetch_action(source_id="source:https://media.example/story",trace_action_id="trace-action:1",candidate=_candidate(),binding=binding,task_id="task:1",epoch_id="epoch:1",created_at="2026-09-02T00:00:00Z")
    action=compiled.fetch_action
    assert action.method_ref==VersionRef("method.fetch_document","1.0.0")
    assert action.action_kind is ActionKind.FETCH
    assert action.inputs[0].kind is ArtifactKind.CANDIDATE
    assert action.inputs[0].metadata["url"]=="https://official.example/model-x"
    assert action.parameters["url"]=="https://official.example/model-x"
    assert compiled.search_candidate_id=="candidate:1"


def test_fetch_binding_selection_honors_provider_preference():
    b1=_binding("binding.fetch.a","provider.a","surface.a"); b2=_binding("binding.fetch.b","provider.b","surface.b")
    providers=ProviderRegistrySnapshot("snap",(_provider("provider.a","surface.a","capability.fetch_url"),_provider("provider.b","surface.b","capability.fetch_url")),(b1,b2))
    assert select_fetch_binding(providers,("provider.b","provider.a"))==b2


def test_fetch_binding_selection_is_deterministic_without_preference():
    b2=_binding("binding.fetch.z","provider.z","surface.z"); b1=_binding("binding.fetch.a","provider.a","surface.a")
    providers=ProviderRegistrySnapshot("snap",(_provider("provider.z","surface.z","capability.fetch_url"),_provider("provider.a","surface.a","capability.fetch_url")),(b2,b1))
    assert select_fetch_binding(providers)==b1


def test_disabled_or_non_fetch_bindings_are_ignored_and_missing_fetch_fails_closed():
    disabled=_binding("binding.fetch.a","provider.a","surface.a",enabled=False)
    wrong=MethodBinding("binding.search.a",VersionRef("method.lexical_search","1.0.0"),VersionRef("provider.a","1.0.0"),"surface.a","adapter.a","1.0.0",True,{}, {})
    providers=ProviderRegistrySnapshot("snap",(_provider("provider.a","surface.a","capability.fetch_url"),),(disabled,wrong))
    try: select_fetch_binding(providers)
    except CandidateFetchUnavailable: pass
    else: raise AssertionError("expected CandidateFetchUnavailable")
