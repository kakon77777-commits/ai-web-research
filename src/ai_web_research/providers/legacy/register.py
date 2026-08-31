from __future__ import annotations

from ai_web_research.execution.registry import AdapterRegistry

from .crawler import LegacyCrawlAdapter, LegacyFetchAdapter
from .extraction import LegacySemanticExtractionAdapter
from .llm import LegacyDivergenceAdapter, LegacyLlmRecallAdapter
from .local import LegacyIdentitySearchAdapter, LegacyLexicalSearchAdapter


def register_legacy_adapters(registry: AdapterRegistry) -> None:
    for adapter in (
        LegacyIdentitySearchAdapter(),
        LegacyLexicalSearchAdapter(),
        LegacyDivergenceAdapter(),
        LegacyLlmRecallAdapter(),
        LegacyCrawlAdapter(),
        LegacyFetchAdapter(),
        LegacySemanticExtractionAdapter(),
    ):
        registry.register(adapter)
