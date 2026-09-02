from __future__ import annotations

from dataclasses import replace
import runpy


def build_scenario():
    scenario = runpy.run_path(
        "tests/ausi/fixtures/ai_daily_fetched_source_scenario.py"
    )["build_scenario"]()
    pages = list(scenario.fetched_pages)
    media_a = pages[2]
    pages[2] = replace(
        media_a,
        html=(
            '<link rel="canonical" href="https://media.example/a">'
            '<link rel="original-source" href="https://official.example/model-x">'
            '<p>According to <a href="https://official.example/model-x">Official Lab</a>, '
            'the release is official.</p>'
            '<blockquote>Model X is available today from the official release.</blockquote>'
        ),
    )
    return replace(scenario, fetched_pages=tuple(pages))
