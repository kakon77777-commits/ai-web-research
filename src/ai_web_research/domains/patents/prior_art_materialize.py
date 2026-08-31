from __future__ import annotations

from dataclasses import replace

from ai_web_research.core.types import ArtifactKind, ArtifactRef

from .models import PatentCandidate, PatentFamilyIdentity
from .prior_art_models import (
    ChronologyClass,
    NPLCandidate,
    PatentClaim,
    PatentFamilyFold,
    PatentLegalValueClass,
    PatentPriorityChronology,
)


def _strings(value) -> tuple[str, ...]:
    return tuple(str(v) for v in value) if isinstance(value, (list, tuple)) else ()


def patent_candidate(artifact: ArtifactRef) -> PatentCandidate:
    m = artifact.metadata
    if artifact.kind is not ArtifactKind.CANDIDATE or m.get("source_type") != "epo_ops_bibliographic":
        raise ValueError("unsupported patent candidate")
    return PatentCandidate(
        candidate_id=artifact.id,
        publication_number=m.get("publication_number"),
        application_number=m.get("application_number"),
        family_id=m.get("family_id"),
        title=m.get("title"),
        abstract=m.get("abstract"),
        classifications=tuple(dict.fromkeys((*_strings(m.get("cpc")), *_strings(m.get("ipc"))))),
        priority_dates=_strings(m.get("priority_dates")),
        publication_date=m.get("publication_date"),
        applicant_refs=_strings(m.get("applicants")),
        inventor_refs=_strings(m.get("inventors")),
        retrieval_score=None,
        score_semantics=str(m.get("score_semantics") or "unknown"),
        provider_refs=("provider.epo_ops",),
        metadata={
            "docdb_publication": m.get("docdb_publication"),
            "epodoc_publication": m.get("epodoc_publication"),
        },
    )


def patent_family(artifact: ArtifactRef) -> PatentFamilyIdentity:
    m = artifact.metadata
    return PatentFamilyIdentity(
        artifact.id,
        str(m.get("family_type") or "PROVIDER_DEFINED"),
        str(m.get("provider") or "unknown"),
        m.get("definition_version"),
        _strings(m.get("member_publications")),
        _strings(m.get("priority_refs")),
    )


def apply_families(candidates, families):
    lookup = {publication: family.family_id for family in families for publication in family.member_publications}
    return tuple(
        replace(candidate, family_id=lookup.get(candidate.publication_number or "") or candidate.family_id)
        for candidate in candidates
    )


def fold_families(candidates):
    groups = {}
    order = []
    for candidate in candidates:
        key = candidate.family_id or f"publication:{candidate.publication_number or candidate.candidate_id}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(candidate)
    folds = []
    for key in order:
        members = groups[key]
        folds.append(PatentFamilyFold(
            fold_id=f"fold:{key}",
            family_id=members[0].family_id,
            publication_numbers=tuple(c.publication_number for c in members if c.publication_number),
            candidate_refs=tuple(c.candidate_id for c in members),
            representative_candidate_ref=members[0].candidate_id,
        ))
    return tuple(folds)


def _chronology_class(value, cutoff):
    if not value or not cutoff:
        return ChronologyClass.UNKNOWN
    if value < cutoff:
        return ChronologyClass.BEFORE_CUTOFF
    if value > cutoff:
        return ChronologyClass.AFTER_CUTOFF
    return ChronologyClass.ON_CUTOFF


def chronology(candidate, cutoff):
    earliest = min(candidate.priority_dates) if candidate.priority_dates else None
    return PatentPriorityChronology(
        candidate.candidate_id,
        earliest,
        candidate.publication_date,
        cutoff,
        _chronology_class(earliest, cutoff),
        _chronology_class(candidate.publication_date, cutoff),
    )


def patent_claims(artifact: ArtifactRef):
    m = artifact.metadata
    legal_class = PatentLegalValueClass(str(m.get("legal_value_class") or "unknown"))
    authoritative = legal_class is PatentLegalValueClass.OFFICIAL_LEGAL_TEXT
    out = []
    for index, raw in enumerate(m.get("claims") or [], 1):
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        claim_number = int(raw.get("claim_number", index))
        out.append(PatentClaim(
            patent_claim_id=f"patent-claim:{m.get('publication_number')}:{claim_number}",
            publication_number=str(m.get("publication_number")),
            claim_number=claim_number,
            text=text,
            language=m.get("language"),
            legal_value_class=legal_class,
            is_legally_authoritative=authoritative,
            metadata={"manifestation_verification_required": bool(m.get("manifestation_verification_required"))},
        ))
    return tuple(out)


def npl_candidate(artifact: ArtifactRef):
    m = artifact.metadata
    if m.get("source_type") != "crossref_metadata":
        raise ValueError("not Crossref NPL")
    doi = m.get("doi")
    return NPLCandidate(
        candidate_id=artifact.id,
        persistent_id=f"doi:{doi}" if doi else None,
        title=m.get("title"),
        publication_date=m.get("published"),
        publisher=m.get("publisher"),
        authors=_strings(m.get("authors")),
        provider_ref="provider.crossref",
        source_type="crossref_metadata",
        metadata={"url": m.get("url")},
    )
