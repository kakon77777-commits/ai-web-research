from ai_web_research.domains.ai_industry.live_discovery import FetchedSourcePageResult
from ai_web_research.source_graph.candidate_verification import CandidateFetchExecution,CandidateFetchStatus
from ai_web_research.source_graph.predecessor_verification import PredecessorVerificationStatus,verify_predecessor_candidate
from ai_web_research.source_graph.fetched_page import FetchedPage
from ai_web_research.source_graph.html_extract import extract_page_source_signals
from ai_web_research.source_graph.signal_compile import compile_page_source_signals
from ai_web_research.source_graph.models import RelationInferenceType,SourceRelationType

def _page(url,html): return FetchedPage(f"source:{url}",url,None,html,"2026-09-02T00:00:00Z",None,None,None,None,"fixture",False)
def _source_result(url,html):
    page=_page(url,html); extraction=extract_page_source_signals(page); compiled=compile_page_source_signals(page,extraction,claim_keywords=("Model X",)); return FetchedSourcePageResult(page,extraction,compiled)
def _fetch(page,candidate_id="candidate:1"): return CandidateFetchExecution("source:https://media.example/story","trace:1",candidate_id,"fetch:1","provider.fetch","binding.fetch",CandidateFetchStatus.FETCHED,page,"obs:1",None)

def test_explicit_attributed_url_plus_successful_fetch_verifies_explicit_predecessor():
    source=_source_result("https://media.example/story",'<p>According to <a href="https://official.example/model-x">Official Example</a>, Model X launched.</p>'); candidate=_page("https://official.example/model-x",'<meta property="og:site_name" content="Official Example"><p>Model X launched.</p>'); result=verify_predecessor_candidate(source,_fetch(candidate)); assert result.status is PredecessorVerificationStatus.VERIFIED_EXPLICIT; assert result.explicit_url_match is True; assert result.relation.relation_type is SourceRelationType.DERIVED_FROM; assert result.relation.inference_type is RelationInferenceType.EXPLICIT; assert result.relation.confidence==1.0

def test_exact_quote_only_is_related_not_predecessor():
    phrase="Model X is available today with a new reasoning mode."; source=_source_result("https://media.example/story",f"<blockquote>{phrase}</blockquote>"); candidate=_page("https://random.example/post",f"<p>{phrase}</p>"); result=verify_predecessor_candidate(source,_fetch(candidate)); assert result.quote_match is True; assert result.owner_match is False; assert result.status is PredecessorVerificationStatus.RELATED_ONLY; assert result.relation is None

def test_owner_match_only_is_related_not_predecessor():
    source=_source_result("https://media.example/story",'<p>According to <a href="https://official.example/about">Official Example</a>, an update is coming.</p>'); candidate=_page("https://repo.example/model-x",'<meta property="og:site_name" content="Official Example"><p>Different content.</p>'); result=verify_predecessor_candidate(source,_fetch(candidate)); assert result.explicit_url_match is False; assert result.owner_match is True; assert result.quote_match is False; assert result.status is PredecessorVerificationStatus.RELATED_ONLY; assert result.relation is None

def test_quote_plus_attribution_entity_owner_match_verifies_inferred_predecessor():
    phrase="Model X is available today with a new reasoning mode."; source=_source_result("https://media.example/story",f'<p>According to <a href="https://official.example/about">Official Example</a>:</p><blockquote>{phrase}</blockquote>'); candidate=_page("https://official.example/model-x",f'<meta property="og:site_name" content="Official Example"><p>{phrase}</p>'); result=verify_predecessor_candidate(source,_fetch(candidate)); assert result.status is PredecessorVerificationStatus.VERIFIED_INFERRED; assert result.relation.inference_type is RelationInferenceType.INFERRED; assert result.relation.confidence==0.95; assert all("rank" not in s and "snippet" not in s and "title" not in s for s in result.relation.signals)

def test_entity_and_quote_normalization_is_case_and_whitespace_stable():
    source=_source_result("https://media.example/story",'<p>According to <a href="https://official.example/about">OFFICIAL   Example!</a>:</p><q>A   Distinctive QUOTE about Model X.</q>'); candidate=_page("https://official.example/model-x",'<meta property="og:site_name" content="official example"><p>a distinctive quote about model x.</p>'); assert verify_predecessor_candidate(source,_fetch(candidate)).status is PredecessorVerificationStatus.VERIFIED_INFERRED
