from __future__ import annotations

from dataclasses import replace
from typing import Awaitable, Callable

from ai_web_research.core.types import ArtifactKind, ArtifactRef
from ai_web_research.execution.models import AuthorizedAction, ExecutionContext, ObservationStatus, ProviderObservation

from .common import LegacyAdapterError, jsonable, occurred_at, require_service, validate_action


CrawlFn = Callable[..., Awaitable[object]]
DocumentIdFn = Callable[[str], str]


def _page_value(row, key: str, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _find_page(store, document_id: str):
    for row in store.all_pages():
        if _page_value(row, "document_id") == document_id:
            return row
    return None


def _page_metadata(row) -> dict:
    keys = (
        "url",
        "canonical_url",
        "markdown_path",
        "raw_path",
        "content_hash",
        "fetched_at",
        "published_at",
        "content_type",
        "language",
        "title",
        "author",
        "robots_allowed",
    )
    return {key: _page_value(row, key) for key in keys if _page_value(row, key) is not None}


class _CrawlerBase:
    adapter_version = "legacy-ca57faf6"
    provider_id = "provider.crawler"
    surface_id = "surface.crawler.browser"

    def __init__(self, crawl_fn: CrawlFn | None = None) -> None:
        self._crawl_fn = crawl_fn

    def _legacy_crawl(self) -> CrawlFn:
        if self._crawl_fn is not None:
            return self._crawl_fn
        from crawler.run import crawl_site
        return crawl_site

    @staticmethod
    def _url(action) -> str:
        value = action.parameters.get("url") or action.parameters.get("seed_url")
        if value:
            return str(value)
        for artifact in action.inputs:
            meta_url = artifact.metadata.get("url")
            if meta_url:
                return str(meta_url)
            if artifact.id.startswith(("http://", "https://")):
                return artifact.id
        raise LegacyAdapterError("crawler action requires a URL")


class LegacyCrawlAdapter(_CrawlerBase):
    adapter_id = "legacy.crawl_site"

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw_action = action.action
        validate_action(
            raw_action,
            method_id="method.crawl_discovery",
            provider_id=self.provider_id,
            surface_id=self.surface_id,
            binding_id="binding.crawl_discovery.crawler.v1",
        )
        url = self._url(raw_action)
        config = require_service(context, "app_config")
        crawler_cfg = config.crawler
        if "max_depth" in raw_action.parameters:
            crawler_cfg = replace(crawler_cfg, max_depth=int(raw_action.parameters["max_depth"]))
        if "max_pages" in raw_action.parameters:
            crawler_cfg = replace(crawler_cfg, max_pages_per_domain=int(raw_action.parameters["max_pages"]))
        if crawler_cfg is not config.crawler:
            config = replace(config, crawler=crawler_cfg)
        fresh = bool(raw_action.parameters.get("fresh", False))
        stats = await self._legacy_crawl()(url, config, fresh=fresh)
        stats_payload = jsonable(stats)
        artifact = ArtifactRef(
            ArtifactKind.CANDIDATE_SET,
            f"{raw_action.action_id}:crawl-summary",
            metadata={
                "seed_url": url,
                "stats": stats_payload,
                "source_type": "web_crawled",
                "evidence_state": "not_verified",
            },
        )
        result_count = int(getattr(stats, "fetched", 0)) + int(getattr(stats, "unchanged", 0))
        return ProviderObservation(
            observation_id=f"{raw_action.action_id}:observation:1",
            action_id=raw_action.action_id,
            provider_id=raw_action.provider_ref.id,
            surface_id=raw_action.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=(artifact,),
            raw_ref=None,
            result_count=result_count,
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=occurred_at(context),
            metadata={"stats": stats_payload},
        )


class LegacyFetchAdapter(_CrawlerBase):
    adapter_id = "legacy.fetch_document"

    def __init__(
        self,
        crawl_fn: CrawlFn | None = None,
        document_id_fn: DocumentIdFn | None = None,
    ) -> None:
        super().__init__(crawl_fn=crawl_fn)
        self._document_id_fn = document_id_fn

    def _document_id(self, url: str) -> str:
        if self._document_id_fn is not None:
            return self._document_id_fn(url)
        from crawler.store import document_id_for
        return document_id_for(url)

    async def execute(self, action: AuthorizedAction, context: ExecutionContext) -> ProviderObservation:
        raw_action = action.action
        validate_action(
            raw_action,
            method_id="method.fetch_document",
            provider_id=self.provider_id,
            surface_id=self.surface_id,
            binding_id="binding.fetch_document.crawler.v1",
        )
        url = self._url(raw_action)
        store = require_service(context, "page_store")
        document_id = self._document_id(url)
        row = _find_page(store, document_id)
        crawl_stats = None
        if row is None:
            config = require_service(context, "app_config")
            single_page_config = replace(config, crawler=replace(config.crawler, max_depth=0))
            crawl_stats = await self._legacy_crawl()(url, single_page_config, fresh=False)
            row = _find_page(store, document_id)
        if row is None:
            raise LegacyAdapterError(
                f"fetch completed without a persisted PageRecord for {url} ({document_id})"
            )

        metadata = _page_metadata(row)
        metadata.update({
            "source_type": "web_crawled",
            "evidence_state": "not_verified",
        })
        if crawl_stats is not None:
            metadata["crawl_stats"] = jsonable(crawl_stats)
        artifact = ArtifactRef(ArtifactKind.DOCUMENT, document_id, metadata=metadata)
        return ProviderObservation(
            observation_id=f"{raw_action.action_id}:observation:1",
            action_id=raw_action.action_id,
            provider_id=raw_action.provider_ref.id,
            surface_id=raw_action.surface_id,
            status=ObservationStatus.SUCCEEDED,
            artifacts=(artifact,),
            raw_ref=_page_value(row, "raw_path"),
            result_count=1,
            cost={},
            latency_ms=None,
            continuation={},
            diagnostics=(),
            occurred_at=occurred_at(context),
            metadata={"document_id": document_id},
        )
