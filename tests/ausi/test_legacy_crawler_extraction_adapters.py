from dataclasses import dataclass, field

import pytest

from ai_web_research.core.types import ActionKind, ArtifactKind, ArtifactRef, SearchAction, VersionRef
from ai_web_research.execution.models import AuthorizationResult, AuthorizedAction, ExecutionContext, PolicyDecision
from ai_web_research.providers.legacy.crawler import LegacyCrawlAdapter, LegacyFetchAdapter
from ai_web_research.providers.legacy.extraction import LegacySemanticExtractionAdapter


@dataclass
class FakeCrawlerCfg:
    max_depth: int = 3
    max_pages_per_domain: int = 50


@dataclass
class FakeAppConfig:
    crawler: FakeCrawlerCfg = field(default_factory=FakeCrawlerCfg)


@dataclass
class FakeStats:
    fetched: int = 1
    skipped_robots: int = 0
    skipped_ssrf: int = 0
    unchanged: int = 0
    failed: int = 0


class FakeStore:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def all_pages(self):
        return list(self.rows)


@dataclass
class FakeField:
    value: object
    source_quote: str | None
    confidence: float | None
    quote_verified: bool


@dataclass
class FakeExtractionResult:
    url: str
    extractor_version: str
    provider: str
    model: str
    fields: dict
    validation_errors: list[str]


def auth_action(method_id, binding_id, kind, *, params=None, inputs=()):
    return AuthorizedAction(
        SearchAction(
            action_id=f"a:{method_id}",
            task_id="t1",
            epoch_id="e1",
            method_ref=VersionRef(method_id, "1.0.0"),
            provider_ref=VersionRef(
                "provider.crawler" if "crawl" in method_id or "fetch" in method_id else "provider.llm_recall",
                "1.0.0",
            ),
            surface_id="surface.crawler.browser" if "crawl" in method_id or "fetch" in method_id else "surface.llm.vertex",
            binding_id=binding_id,
            action_kind=kind,
            inputs=tuple(inputs),
            parameters=dict(params or {}),
            guards=(),
            expected_effects=(),
            created_by="test",
            created_at="2026-08-31T09:00:00+00:00",
        ),
        AuthorizationResult(PolicyDecision.ALLOW),
    )


def context(**services):
    return ExecutionContext("t1", "e1", "snap", services=services)


@pytest.mark.asyncio
async def test_crawl_adapter_returns_candidate_set_summary_not_evidence():
    seen = {}

    async def fake_crawl(seed_url, config, fresh=False):
        seen.update(seed_url=seed_url, depth=config.crawler.max_depth, fresh=fresh)
        return FakeStats(fetched=2)

    adapter = LegacyCrawlAdapter(crawl_fn=fake_crawl)
    obs = await adapter.execute(
        auth_action(
            "method.crawl_discovery",
            "binding.crawl_discovery.crawler.v1",
            ActionKind.CRAWL,
            params={"url": "https://example.com", "max_depth": 2},
        ),
        context(app_config=FakeAppConfig()),
    )
    assert seen == {"seed_url": "https://example.com", "depth": 2, "fresh": False}
    assert obs.artifacts[0].kind is ArtifactKind.CANDIDATE_SET
    assert obs.artifacts[0].metadata["stats"]["fetched"] == 2
    assert all(a.kind is not ArtifactKind.VERIFIED_EVIDENCE for a in obs.artifacts)


@pytest.mark.asyncio
async def test_fetch_adapter_uses_existing_page_without_recrawling():
    url = "https://example.com/doc"
    row = {
        "document_id": "doc-existing",
        "url": url,
        "canonical_url": url,
        "markdown_path": "/tmp/doc.md",
        "raw_path": "/tmp/doc.html",
        "content_hash": "abc",
        "fetched_at": "2026-08-31T08:00:00+00:00",
    }

    async def fail_crawl(*args, **kwargs):
        raise AssertionError("crawl should not run for an already stored document")

    adapter = LegacyFetchAdapter(crawl_fn=fail_crawl, document_id_fn=lambda value: "doc-existing")
    obs = await adapter.execute(
        auth_action(
            "method.fetch_document",
            "binding.fetch_document.crawler.v1",
            ActionKind.FETCH,
            params={"url": url},
        ),
        context(app_config=FakeAppConfig(), page_store=FakeStore([row])),
    )
    artifact = obs.artifacts[0]
    assert artifact.kind is ArtifactKind.DOCUMENT
    assert artifact.id == "doc-existing"
    assert artifact.metadata["content_hash"] == "abc"
    assert artifact.metadata["markdown_path"] == "/tmp/doc.md"


@pytest.mark.asyncio
async def test_fetch_adapter_crawls_with_depth_zero_copy_when_document_missing():
    url = "https://example.com/new"
    store = FakeStore()
    seen = {}

    async def fake_crawl(seed_url, config, fresh=False):
        seen["depth"] = config.crawler.max_depth
        store.rows.append({
            "document_id": "doc-new", "url": url, "canonical_url": url,
            "markdown_path": "/tmp/new.md", "raw_path": None,
            "content_hash": "newhash", "fetched_at": "2026-08-31T09:00:00+00:00",
        })
        return FakeStats(fetched=1)

    adapter = LegacyFetchAdapter(crawl_fn=fake_crawl, document_id_fn=lambda value: "doc-new")
    obs = await adapter.execute(
        auth_action(
            "method.fetch_document",
            "binding.fetch_document.crawler.v1",
            ActionKind.FETCH,
            params={"url": url},
        ),
        context(app_config=FakeAppConfig(), page_store=store),
    )
    assert seen["depth"] == 0
    assert obs.artifacts[0].id == "doc-new"


@pytest.mark.asyncio
async def test_semantic_extraction_adapter_produces_candidate_evidence_with_quote_state():
    async def fake_extract(markdown, schema, llm_config, **kwargs):
        assert markdown == "Alpha is supported by source text."
        assert schema["required"] == ["claim"]
        assert llm_config == "LLM"
        return FakeExtractionResult(
            url=kwargs["url"],
            extractor_version="extractor-v1",
            provider="vertex",
            model="gemini-test",
            fields={
                "claim": FakeField(
                    value="Alpha",
                    source_quote="Alpha is supported by source text.",
                    confidence=0.8,
                    quote_verified=True,
                )
            },
            validation_errors=[],
        )

    def loader(ref):
        assert ref.kind is ArtifactKind.DOCUMENT
        return {
            "markdown": "Alpha is supported by source text.",
            "url": "https://example.com/doc",
            "raw_ref": "content:doc-1",
        }

    adapter = LegacySemanticExtractionAdapter(extract_fn=fake_extract)
    obs = await adapter.execute(
        auth_action(
            "method.extract_candidate_evidence",
            "binding.extract_candidate_evidence.llm.v1",
            ActionKind.EXTRACT,
            params={"schema": {"type": "object", "properties": {"claim": {"type": "string"}}, "required": ["claim"]}},
            inputs=(ArtifactRef(ArtifactKind.DOCUMENT, "doc-1"),),
        ),
        context(document_loader=loader, llm_config="LLM"),
    )
    artifact = obs.artifacts[0]
    assert artifact.kind is ArtifactKind.EVIDENCE_CANDIDATE
    assert artifact.metadata["fields"]["claim"]["quote_verified"] is True
    assert artifact.metadata["fields"]["claim"]["value"] == "Alpha"
    assert artifact.metadata["verification_scope"] == "anchor_only"
    assert artifact.metadata["semantic_support_verified"] is False
