from pathlib import Path

DOCS = {
    'quick': Path('docs/QUICKSTART.md'),
    'api': Path('docs/release/API_STABILITY_AND_MIGRATION_v1.md'),
    'security': Path('docs/release/SECURITY_AND_CREDENTIALS_v1.md'),
    'workflows': Path('docs/release/REFERENCE_WORKFLOWS_v1.md'),
    'rc': Path('docs/release/RELEASE_CANDIDATE_v1.0.0rc1.md'),
}


def test_required_release_docs_exist_and_lock_core_boundaries():
    text = {name: path.read_text(encoding='utf-8') for name, path in DOCS.items()}
    assert all(path.is_file() for path in DOCS.values())
    assert 'import omphalos' in text['quick'] and '1.0.0rc1' in text['quick']
    assert 'Public API Version: `1.0`' in text['api'] and 'Semantic Versioning' in text['api']
    for invariant in ['UNKNOWN != ALLOW', 'Planning != Authorization', 'Learning != SelfAuthorization', 'SearchReceipt != ChainOfThought']:
        assert invariant in text['security'] or invariant in text['api']
    for heading in ['General Web Research', 'X / Current Discourse Research', 'Academic / NPL Research', 'Patent Prior-Art Research']:
        assert heading in text['workflows']
    assert 'not the final v1.0 release' in text['rc']
    assert 'synthetic' in text['rc'].lower() and 'live Provider' in text['rc']
