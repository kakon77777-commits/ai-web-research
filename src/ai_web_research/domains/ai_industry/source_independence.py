from __future__ import annotations

from dataclasses import replace

from ai_web_research.source_graph.models import SourceFamilyResolution

from .models import ClaimDraft


def attach_independent_root_count(
    draft: ClaimDraft,
    evidence_source_ids: tuple[str, ...],
    family_resolution: SourceFamilyResolution,
) -> ClaimDraft:
    return replace(
        draft,
        independent_root_count=family_resolution.independent_root_count(evidence_source_ids),
    )
