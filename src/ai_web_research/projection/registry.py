from __future__ import annotations

from .models import CorrectionImpact, ProjectionArtifact


class ArtifactRegistry:
    def __init__(self) -> None:
        self._artifacts: dict[str, ProjectionArtifact] = {}
        self._by_claim: dict[str, set[str]] = {}
        self._by_event: dict[str, set[str]] = {}

    def register(self, artifact: ProjectionArtifact) -> None:
        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None and existing != artifact:
            raise ValueError(f"conflicting artifact {artifact.artifact_id}")
        self._artifacts[artifact.artifact_id] = artifact
        for unit in artifact.units:
            for claim_id in unit.claim_ids:
                self._by_claim.setdefault(claim_id, set()).add(artifact.artifact_id)
            for event_id in unit.event_ids:
                self._by_event.setdefault(event_id, set()).add(artifact.artifact_id)

    def get(self, artifact_id: str) -> ProjectionArtifact:
        try:
            return self._artifacts[artifact_id]
        except KeyError:
            raise KeyError(artifact_id) from None

    def affected_by_claim(self, claim_id: str) -> CorrectionImpact:
        return CorrectionImpact(
            claim_id=claim_id,
            artifact_ids=tuple(sorted(self._by_claim.get(claim_id, ()))),
        )

    def artifact_ids_for_event(self, event_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._by_event.get(event_id, ())))
