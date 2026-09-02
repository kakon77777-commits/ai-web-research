from dataclasses import replace
import runpy

from ai_web_research.source_graph.models import SourceNode


def build_scenario():
    base = runpy.run_path("tests/ausi/fixtures/ai_daily_fetched_source_scenario.py")["build_scenario"]()
    phrase = "Model X is available today with a new reasoning mode."
    html_by_url = {
        "https://official.example/model-x": f'<link rel="canonical" href="https://official.example/model-x"><meta property="og:site_name" content="Official Example"><p>{phrase}</p>',
        "https://repo.example/model-x": '<link rel="canonical" href="https://repo.example/model-x"><meta property="og:site_name" content="Official Example"><p>Repository metadata only.</p>',
        "https://media.example/a": f'<link rel="canonical" href="https://media.example/a"><p>According to <a href="https://official.example/about">Official Example</a>:</p><q>{phrase}</q>',
        "https://media.example/b": '<link rel="canonical" href="https://media.example/b"><link rel="syndication-source" href="https://media.example/a"><p>Syndicated report.</p>',
    }
    pages = tuple(replace(page, html=html_by_url[page.url], content_hash="verify-" + str(i)) for i, page in enumerate(base.fetched_pages))
    nodes = tuple(SourceNode(page.source_id,page.url,page.canonical_url,page.published_at,page.observed_at,None,page.content_hash,{}) for page in pages)
    return replace(base, fetched_pages=pages, source_nodes=nodes)
