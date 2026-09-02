from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ai_web_research.core.types import JsonValue, VersionRef


class ProviderKind(StrEnum):
    CRAWLER = "crawler"
    LOCAL_CORPUS = "local_corpus"
    SEARCH_ENGINE = "search_engine"
    STRUCTURED_API = "structured_api"
    DATABASE = "database"
    ACADEMIC = "academic"
    PATENT = "patent"
    ECONOMIC = "economic"
    METEOROLOGICAL = "meteorological"
    LLM_RECALL = "llm_recall"
    CUSTOM = "custom"


class ProviderTopology(StrEnum):
    UNSPECIFIED = "unspecified"
    MODEL_NATIVE = "model_native"
    PROVIDER_NEUTRAL = "provider_neutral"
    DOMAIN_SPECIFIC = "domain_specific"
    LOCAL_PRIVATE = "local_private"


class SurfaceKind(StrEnum):
    WEB_UI = "web_ui"
    PUBLIC_API = "public_api"
    AUTHENTICATED_API = "authenticated_api"
    BULK_DATA = "bulk_data"
    DOWNLOAD = "download"
    LOCAL_INDEX = "local_index"
    LOCAL_DATABASE = "local_database"
    MODEL = "model"


@dataclass(frozen=True)
class ProviderSurface:
    surface_id: str
    kind: SurfaceKind
    endpoint_ref: str | None
    capabilities: frozenset[str]
    auth_profile: str | None
    policy_profile_refs: tuple[str, ...]
    static_limits: dict[str, JsonValue]
    metadata: dict[str, JsonValue]


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    version: str
    kind: ProviderKind
    display_name: str
    domains: tuple[str, ...]
    languages: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    surfaces: tuple[ProviderSurface, ...]
    metadata: dict[str, JsonValue]
    topology: ProviderTopology = ProviderTopology.UNSPECIFIED


@dataclass(frozen=True)
class MethodBinding:
    binding_id: str
    method_ref: VersionRef
    provider_ref: VersionRef
    surface_id: str
    adapter_id: str
    adapter_version: str
    enabled: bool
    parameter_mapping: dict[str, JsonValue]
    metadata: dict[str, JsonValue]
