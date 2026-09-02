from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectIdentity:
    codename: str
    technical_name: str
    full_technical_name: str
    core_identity: str
    legacy_repository_name: str


PROJECT_IDENTITY = ProjectIdentity(
    codename="Omphalos",
    technical_name="AUSI Runtime",
    full_technical_name="AI-Native Unified Search Intelligence Runtime",
    core_identity="AI-native Search Method Runtime",
    legacy_repository_name="ai-web-research",
)
