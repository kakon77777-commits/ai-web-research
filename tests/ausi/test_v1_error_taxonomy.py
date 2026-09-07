import pytest
from ai_web_research.execution.models import ErrorCategory
from omphalos.errors import ERROR_CATALOG, OmphalosError, OmphalosErrorCode


def test_public_error_catalog_is_complete_and_stable():
    assert set(ERROR_CATALOG) == set(OmphalosErrorCode)
    assert ERROR_CATALOG[OmphalosErrorCode.POLICY_BLOCKED].category is ErrorCategory.POLICY
    assert ERROR_CATALOG[OmphalosErrorCode.PROVIDER_UNAVAILABLE].recoverable is True
    assert ERROR_CATALOG[OmphalosErrorCode.REPLAY_MISMATCH].recoverable is False


def test_public_error_converts_to_runtime_record_without_secret_metadata():
    err = OmphalosError(OmphalosErrorCode.TIMEOUT, 'timed out', metadata={'attempt': 2})
    record = err.to_runtime_record(action_id='a1', provider_id='p1')
    assert record.code == 'TIMEOUT'
    assert record.category is ErrorCategory.TIMEOUT
    assert record.metadata == {'attempt': 2}
    with pytest.raises(ValueError):
        OmphalosError(OmphalosErrorCode.AUTH_REQUIRED, 'auth', metadata={'nested': {'api_key': 'x'}})
