import pytest

from ai_web_research.domains.patents.methods import register_patent_methods
from ai_web_research.domains.patents.models import InventionFeature, PatentConcept
from ai_web_research.domains.patents.prior_art_methods import register_prior_art_methods
from ai_web_research.domains.patents.workflow import SoftwarePriorArtDiscoveryRequest, SoftwarePriorArtDiscoveryWorkflow
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.execution.registry import AdapterRegistry
from ai_web_research.execution.runtime import ExecutionRuntime
from ai_web_research.execution.trusted import TrustedExecutionRuntime
from ai_web_research.experience.receipt import SearchReceiptRecorder
from ai_web_research.experience.sqlite import SearchReceiptStore
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.crossref import CrossrefAdapter, crossref_policy_profile, register_crossref_provider
from ai_web_research.providers.patents.epo_ops import epo_ops_policy_profile
from ai_web_research.providers.patents.epo_ops_prior_art import EpoOpsPriorArtAdapter, register_epo_ops_prior_art_provider
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.storage.trusted_sqlite import TrustedDataStore


SEARCH_XML = """<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:e="http://www.epo.org/exchange">
<ops:biblio-search><ops:search-result><e:exchange-documents>
<e:exchange-document family-id="42" country="EP" doc-number="1" kind="A1"><e:bibliographic-data>
<e:publication-reference><e:document-id document-id-type="docdb"><e:country>EP</e:country><e:doc-number>1</e:doc-number><e:kind>A1</e:kind><e:date>20260101</e:date></e:document-id></e:publication-reference>
<e:priority-claims><e:priority-claim><e:document-id><e:date>20240101</e:date></e:document-id></e:priority-claim></e:priority-claims>
<e:invention-title lang="en">Autonomous patent search</e:invention-title>
<e:classifications-cpc><e:classification-cpc><e:text>G06F16/00</e:text></e:classification-cpc></e:classifications-cpc>
</e:bibliographic-data></e:exchange-document>
</e:exchange-documents></ops:search-result></ops:biblio-search></ops:world-patent-data>"""

FAMILY_XML = """<ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:e="http://www.epo.org/exchange">
<ops:patent-family family-id="42"><ops:family-member>
<e:publication-reference><e:document-id document-id-type="docdb"><e:country>EP</e:country><e:doc-number>1</e:doc-number><e:kind>A1</e:kind></e:document-id></e:publication-reference>
</ops:family-member></ops:patent-family></ops:world-patent-data>"""

CLAIMS_XML = """<f:fulltext-document xmlns:f="http://www.epo.org/fulltext">
<f:claims lang="EN"><f:claim num="1"><f:claim-text>1. A search planner.</f:claim-text></f:claim></f:claims>
</f:fulltext-document>"""


class EpoResponse:
    def __init__(self, text):
        self.text = text
        self.headers = {}

    def raise_for_status(self):
        return None


class EpoClient:
    async def get(self, url, *, params=None, headers=None):
        if "/family/" in url:
            return EpoResponse(FAMILY_XML)
        if url.endswith("/claims"):
            return EpoResponse(CLAIMS_XML)
        return EpoResponse(SEARCH_XML)


class CrossrefResponse:
    headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "status": "ok",
            "message": {
                "items": [
                    {
                        "DOI": "10.1/npl",
                        "title": ["Relevant NPL"],
                        "publisher": "Example Publisher",
                        "published": {"date-parts": [[2023, 1, 1]]},
                    }
                ]
            },
        }


class CrossrefClient:
    async def get(self, url, *, params=None, headers=None):
        return CrossrefResponse()


@pytest.mark.asyncio
async def test_software_prior_art_workflow_closes_search_branches_but_keeps_legal_manifestation_gap(tmp_path):
    methods = SearchMethodRegistry()
    register_builtin_methods(methods)
    register_patent_methods(methods)
    register_prior_art_methods(methods)

    providers = ProviderRegistry()
    register_epo_ops_prior_art_provider(providers, methods.snapshot())
    register_crossref_provider(providers, methods.snapshot())
    provider_snapshot = providers.snapshot()

    adapters = AdapterRegistry()
    adapters.register(EpoOpsPriorArtAdapter())
    adapters.register(CrossrefAdapter())

    policies = SourcePolicyRegistry()
    policies.register(epo_ops_policy_profile())
    policies.register(crossref_policy_profile())

    trusted_store = TrustedDataStore(tmp_path / "trusted.db")
    receipt_store = SearchReceiptStore(tmp_path / "receipts.db")
    recorder = SearchReceiptRecorder(receipt_store)
    runtime = TrustedExecutionRuntime(
        execution=ExecutionRuntime(adapters, provider_snapshot),
        providers=provider_snapshot,
        policies=policies.snapshot(),
        evaluator=DeterministicPolicyEvaluator(),
        store=trusted_store,
        receipt_recorder=recorder,
    )
    context = ExecutionContext(
        task_id="task-1",
        epoch_id="epoch-1",
        registry_snapshot_id="registry-1",
        services={
            "epo_ops_http_client": EpoClient(),
            "epo_ops_access_token": "token",
            "crossref_http_client": CrossrefClient(),
            "clock": "2026-08-31T12:00:01+00:00",
        },
        runtime_limits={},
    )
    feature = InventionFeature(
        feature_id="feature.1",
        description="Generate diversified search branches for autonomous research.",
        function="query diversification",
        mechanism="model-generated branches",
        input_state=None,
        output_state=None,
        constraints=(),
        dependencies=(),
        importance=1.0,
        novelty_hypothesis=None,
        metadata={},
    )
    concept = PatentConcept(
        concept_id="concept.1",
        feature_refs=("feature.1",),
        functional_terms=("query diversification",),
        structural_terms=(),
        mechanism_terms=(),
        patent_style_terms=("generating a plurality of search queries",),
        historical_terms=(),
        synonyms=(),
        broader_terms=(),
        narrower_terms=(),
        translations={},
        classification_hints=("G06F16/00",),
        metadata={},
    )
    request = SoftwarePriorArtDiscoveryRequest(
        task_id="task-1",
        epoch_id="epoch-1",
        feature=feature,
        concept=concept,
        classifications=("G06F16/00",),
        classification_scheme="cpc",
        jurisdictions=("EP",),
        languages=("en",),
        cutoff="2025-01-01",
        include_npl=True,
        include_backward_citation=False,
        max_deep_candidates=1,
        max_results_per_branch=5,
    )

    try:
        result = await SoftwarePriorArtDiscoveryWorkflow(runtime, context).run(request)
        assert len(result.patent_candidates) == 1
        assert result.patent_candidates[0].family_id == "epo:family-id:42"
        assert result.chronologies[0].priority_class.value == "before_cutoff"
        assert result.chronologies[0].publication_class.value == "after_cutoff"
        assert len(result.claims) == 1
        assert result.claims[0].publication_number == "EP1A1"
        assert result.claims[0].is_legally_authoritative is False
        assert len(result.npl_candidates) == 1
        assert result.npl_candidates[0].persistent_id == "doi:10.1/npl"
        assert {gap.value for gap in result.coverage.gaps} == {"legal_manifestation_not_verified"}
        assert result.status == "PARTIAL"
        assert result.stop_reason == "MANDATORY_GAPS_REMAIN"
        assert result.search_receipt is not None
        assert len(result.search_receipt.actions) == 5
    finally:
        trusted_store.close()
        receipt_store.close()
