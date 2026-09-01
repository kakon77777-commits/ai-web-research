from .common import LegacyAdapterError
from .crawler import LegacyCrawlAdapter, LegacyFetchAdapter
from .extraction import LegacySemanticExtractionAdapter
from .llm import LegacyDivergenceAdapter, LegacyLlmRecallAdapter
from .local import LegacyIdentitySearchAdapter, LegacyLexicalSearchAdapter
from .register import register_legacy_adapters

__all__ = [
    "LegacyAdapterError",
    "LegacyCrawlAdapter",
    "LegacyFetchAdapter",
    "LegacySemanticExtractionAdapter",
    "LegacyDivergenceAdapter",
    "LegacyLlmRecallAdapter",
    "LegacyIdentitySearchAdapter",
    "LegacyLexicalSearchAdapter",
    "register_legacy_adapters",
]
