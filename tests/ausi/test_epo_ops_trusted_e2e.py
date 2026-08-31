import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, RiskClass, SearchAction, VersionRef
from ai_web_research.domains.patents.methods import register_patent_methods
from ai_web_research.execution.models import ExecutionContext
from ai_web_research.execution.registry import AdapterRegistry
from ai_web_research.execution.runtime import ExecutionRuntime
from ai_web_research.execution.trusted import TrustedExecutionRuntime
from ai_web_research.experience.receipt import SearchReceiptRecorder, SearchReceiptStatus
from ai_web_research.experience.sqlite import SearchReceiptStore
from ai_web_research.methods.builtin import register_builtin_methods
from ai_web_research.methods.registry import SearchMethodRegistry
from ai_web_research.policy.evaluator import DeterministicPolicyEvaluator
from ai_web_research.policy.models import AcquisitionAction, PolicyContext
from ai_web_research.policy.registry import SourcePolicyRegistry
from ai_web_research.providers.patents.epo_ops import EpoOpsAdapter, epo_ops_policy_profile, register_epo_ops_provider
from ai_web_research.providers.registry import ProviderRegistry
from ai_web_research.storage.trusted_sqlite import TrustedDataStore

OPS_XML='''<?xml version="1.0" encoding="UTF-8"?><ops:world-patent-data xmlns:ops="http://ops.epo.org" xmlns:exchange="http://www.epo.org/exchange"><ops:biblio-search total-result-count="1"><ops:search-result><exchange:exchange-documents><exchange:exchange-document country="EP" doc-number="1234567" kind="A1"><exchange:bibliographic-data><exchange:publication-reference><exchange:document-id document-id-type="docdb"><exchange:country>EP</exchange:country><exchange:doc-number>1234567</exchange:doc-number><exchange:kind>A1</exchange:kind><exchange:date>20260115</exchange:date></exchange:document-id></exchange:publication-reference><exchange:invention-title lang="en">Autonomous patent search</exchange:invention-title><exchange:classifications-cpc><exchange:classification-cpc><exchange:text>G06F16/24578</exchange:text></exchange:classification-cpc></exchange:classifications-cpc></exchange:bibliographic-data></exchange:exchange-document></exchange:exchange-documents></ops:search-result></ops:biblio-search></ops:world-patent-data>'''
class FakeResponse:
    def __init__(self,text=OPS_XML): self.text=text; self.status_code=200; self.headers={}
    def raise_for_status(self): return None
class FakeClient:
    def __init__(self,response=None): self.response=response or FakeResponse(); self.calls=[]
    async def get(self,url,*,params=None,headers=None): self.calls.append((url,params or {},headers or {})); return self.response

def build(tmp_path):
    methods=SearchMethodRegistry(); register_builtin_methods(methods); register_patent_methods(methods)
    providers=ProviderRegistry(); register_epo_ops_provider(providers,methods.snapshot()); provider_snapshot=providers.snapshot()
    adapters=AdapterRegistry(); adapters.register(EpoOpsAdapter()); execution=ExecutionRuntime(adapters,provider_snapshot)
    policies=SourcePolicyRegistry(); policies.register(epo_ops_policy_profile())
    trusted_store=TrustedDataStore(tmp_path/"trusted.db"); receipt_store=SearchReceiptStore(tmp_path/"receipts.db"); recorder=SearchReceiptRecorder(receipt_store)
    trusted=TrustedExecutionRuntime(execution=execution,providers=provider_snapshot,policies=policies.snapshot(),evaluator=DeterministicPolicyEvaluator(),store=trusted_store,receipt_recorder=recorder)
    return trusted,recorder,trusted_store,receipt_store

def action():
    return SearchAction("epo-e2e-1","patent-task-1","patent-epoch-1",VersionRef("method.patent.classification_search","1.0.0"),VersionRef("provider.epo_ops","1.0.0"),"surface.epo_ops.rest","binding.patent_classification.epo_ops.v1",ActionKind.SEARCH,(ArtifactRef(ArtifactKind.QUERY,"classification:G06F16/00"),),{"classification":"G06F16/00","scheme":"cpc","range":"1-10"},(),("candidate_set_created",),"planner.rule.v0","2026-08-31T12:00:00+00:00")

@pytest.mark.asyncio
async def test_epo_ops_runs_through_common_policy_trusted_asset_and_receipt_runtime(tmp_path):
    trusted,recorder,trusted_store,receipt_store=build(tmp_path)
    try:
        result=await trusted.execute(action(),ExecutionContext("patent-task-1","patent-epoch-1","patent-registry-1",{"epo_ops_http_client":FakeClient(FakeResponse(OPS_XML)),"epo_ops_access_token":"token","clock":"2026-08-31T12:00:01+00:00"},{}),PolicyContext("patent-task-1","research",None,RiskClass.HIGH,("EP",),(AcquisitionAction.AUTOMATED_QUERY,),"2026-08-31T12:00:00+00:00"),credential_profile_id="credential.epo_ops")
        assert result.observation.result_count==1; assert result.observation.artifacts[0].id=="epo:publication:EP1234567A1"; assert len(result.materialized_assets)==1
        envelope=result.materialized_assets[0].usage_envelope; assert AcquisitionAction.AUTOMATED_QUERY in envelope.permissions; assert AcquisitionAction.INTERNAL_USE in envelope.permissions; assert AcquisitionAction.DISTRIBUTE_DERIVED in envelope.permissions; assert AcquisitionAction.REDISTRIBUTE_RAW in envelope.prohibitions
        action_receipts=receipt_store.list_search_action_receipts("patent-epoch-1"); assert len(action_receipts)==1; assert action_receipts[0].provider_ref.id=="provider.epo_ops"; assert action_receipts[0].result_count==1; assert action_receipts[0].artifact_refs==("epo:publication:EP1234567A1",)
        final=recorder.finalize(receipt_id="patent-receipt-1",task_id="patent-task-1",epoch_id="patent-epoch-1",registry_snapshot_id="patent-registry-1",planner_id="planner.rule",planner_version="0.1.0",stop_reason="FIRST_PATENT_PROVIDER_SLICE_COMPLETE",status=SearchReceiptStatus.PARTIAL,created_at="2026-08-31T12:00:02+00:00",metadata={"declared_scope":"EPO OPS bibliographic/classification"}); assert final.actions==action_receipts
    finally:
        trusted_store.close(); receipt_store.close()
