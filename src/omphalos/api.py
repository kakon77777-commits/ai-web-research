from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import EnumMeta

from ai_web_research.core.types import (
    ArtifactKind,
    RiskClass,
    SearchAction,
    SearchIntent,
    SearchState,
    SearchTask,
    VersionRef,
)
from ai_web_research.evidence.models import (
    CandidateEvidence,
    EvidenceProvenance,
    EvidenceStatus,
    VerifiedEvidence,
)
from ai_web_research.execution.models import (
    AuthorizedAction,
    PolicyDecision,
    ProviderObservation,
)
from ai_web_research.experience.receipt import (
    SearchActionReceipt,
    SearchReceipt,
    SearchReceiptStatus,
)
from ai_web_research.gaps.projection import EvidenceGapType, GapProjection
from ai_web_research.methods.spec import SearchMethodSpec
from ai_web_research.planning.graph import SearchPlan
from ai_web_research.providers.spec import (
    MethodBinding,
    ProviderSpec,
    ProviderTopology,
)
from ai_web_research.routing.models import (
    PolicyFreshness,
    ProviderAvailability,
    ProviderState,
)

from .errors import ErrorDescriptor, OmphalosError, OmphalosErrorCode
from .version import PACKAGE_VERSION, PUBLIC_API_VERSION


PUBLIC_EXPORTS = {
    "OmphalosError": OmphalosError,
    "OmphalosErrorCode": OmphalosErrorCode,
    "ErrorDescriptor": ErrorDescriptor,
    "VersionRef": VersionRef,
    "ArtifactKind": ArtifactKind,
    "SearchIntent": SearchIntent,
    "RiskClass": RiskClass,
    "SearchTask": SearchTask,
    "SearchState": SearchState,
    "SearchAction": SearchAction,
    "SearchMethodSpec": SearchMethodSpec,
    "ProviderSpec": ProviderSpec,
    "ProviderTopology": ProviderTopology,
    "ProviderState": ProviderState,
    "ProviderAvailability": ProviderAvailability,
    "PolicyFreshness": PolicyFreshness,
    "MethodBinding": MethodBinding,
    "SearchPlan": SearchPlan,
    "AuthorizedAction": AuthorizedAction,
    "ProviderObservation": ProviderObservation,
    "PolicyDecision": PolicyDecision,
    "CandidateEvidence": CandidateEvidence,
    "VerifiedEvidence": VerifiedEvidence,
    "EvidenceProvenance": EvidenceProvenance,
    "EvidenceStatus": EvidenceStatus,
    "EvidenceGapType": EvidenceGapType,
    "GapProjection": GapProjection,
    "SearchActionReceipt": SearchActionReceipt,
    "SearchReceipt": SearchReceipt,
    "SearchReceiptStatus": SearchReceiptStatus,
}


def _contract_descriptor(obj) -> dict:
    descriptor = {
        "source": f"{obj.__module__}.{obj.__qualname__}",
    }
    if is_dataclass(obj):
        descriptor["kind"] = "dataclass"
        descriptor["fields"] = [field.name for field in fields(obj)]
        descriptor["frozen"] = bool(
            getattr(getattr(obj, "__dataclass_params__", None), "frozen", False)
        )
        return descriptor
    if isinstance(obj, EnumMeta):
        descriptor["kind"] = "enum"
        descriptor["values"] = [member.value for member in obj]
        return descriptor
    descriptor["kind"] = "class"
    return descriptor


def build_public_api_manifest() -> dict:
    return {
        "package_name": "ai-web-research",
        "facade_package": "omphalos",
        "package_version": PACKAGE_VERSION,
        "public_api_version": PUBLIC_API_VERSION,
        "contracts": {
            name: _contract_descriptor(PUBLIC_EXPORTS[name])
            for name in sorted(PUBLIC_EXPORTS)
        },
    }
