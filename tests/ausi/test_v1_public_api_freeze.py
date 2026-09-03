import json
from pathlib import Path
import omphalos
from omphalos.api import PUBLIC_EXPORTS, build_public_api_manifest

MANIFEST = Path('release/omphalos-v1.0.0rc1-public-api.json')


def test_v1_public_facade_and_manifest_are_frozen():
    assert omphalos.__version__ == '1.0.0rc1'
    assert omphalos.PUBLIC_API_VERSION == '1.0'
    required = {
        'SearchTask', 'SearchState', 'SearchAction', 'SearchMethodSpec',
        'ProviderSpec', 'ProviderState', 'MethodBinding', 'SearchPlan',
        'AuthorizedAction', 'ProviderObservation', 'CandidateEvidence',
        'VerifiedEvidence', 'EvidenceProvenance', 'GapProjection',
        'SearchReceipt', 'SearchActionReceipt', 'OmphalosErrorCode',
        'ErrorDescriptor', 'OmphalosError',
    }
    assert required <= set(PUBLIC_EXPORTS)
    assert all(getattr(omphalos, name) is PUBLIC_EXPORTS[name] for name in required)
    generated = build_public_api_manifest()
    assert generated == json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert generated['public_api_version'] == '1.0'
    assert generated['package_version'] == '1.0.0rc1'


def test_manifest_freezes_representative_fields_and_enum_values():
    contracts = build_public_api_manifest()['contracts']
    assert contracts['SearchTask']['fields'][:4] == ['task_id', 'raw_request', 'intent', 'domain']
    assert contracts['ProviderState']['fields'][:4] == ['provider_ref', 'surface_id', 'availability', 'healthy']
    assert contracts['SearchPlan']['fields'] == ['plan_id', 'task_id', 'epoch_id', 'nodes', 'edges', 'entry_node_ids', 'metadata']
    assert contracts['PolicyDecision']['values'] == ['allow', 'allow_with_obligations', 'deny', 'unknown', 'review']
