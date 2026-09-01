from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from .candidate_verification import CandidateFetchExecution, CandidateFetchStatus
from .fetched_page import FetchedPage
from .html_extract import extract_page_source_signals
from .models import RelationInferenceType, SourceRelation, SourceRelationType
from .page_signals import PageSourceSignalKind
from .signal_compile import compile_page_source_signals

class PredecessorVerificationStatus(StrEnum):
    VERIFIED_EXPLICIT="verified_explicit"; VERIFIED_INFERRED="verified_inferred"; RELATED_ONLY="related_only"; REJECTED="rejected"
@dataclass(frozen=True)
class PredecessorVerification:
    verification_id:str; source_id:str; candidate_source_id:str|None; status:PredecessorVerificationStatus
    explicit_url_match:bool; quote_match:bool; owner_match:bool; relation:SourceRelation|None; matched_signal_ids:tuple[str,...]
class _VisibleTextParser(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.parts=[]; self.excluded_depth=0
    def handle_starttag(self,tag,attrs):
        if tag.lower() in {"script","style","noscript"}: self.excluded_depth+=1
    def handle_endtag(self,tag):
        if tag.lower() in {"script","style","noscript"} and self.excluded_depth>0: self.excluded_depth-=1
    def handle_data(self,data):
        if self.excluded_depth==0: self.parts.append(data)
def _normalize_text(value): return " ".join(value.casefold().split())
def _normalize_entity(value): return " ".join(re.sub(r"[^\w]+"," ",value.casefold(),flags=re.UNICODE).split())
def _normalize_url(value):
    parts=urlsplit(value.strip())
    if parts.scheme not in {"http","https"} or not parts.netloc: return None
    path=parts.path or "/"; path=path[:-1] if path!="/" and path.endswith("/") else path
    return urlunsplit((parts.scheme.lower(),parts.netloc.lower(),path,parts.query,""))
def _visible_text(page):
    parser=_VisibleTextParser()
    try: parser.feed(page.html); parser.close()
    except Exception: pass
    return _normalize_text(" ".join(parser.parts))
def _verification_id(source_id,candidate_source_id,status):
    return "predecessor-verification:"+sha256(f"{source_id}|{candidate_source_id}|{status.value}".encode()).hexdigest()[:20]
def _verified_relation(*,source_id,candidate_source_id,inference_type,confidence,signal_ids,verification_id):
    relation_id="source-relation:"+sha256(f"{source_id}|derived_from|{candidate_source_id}|{verification_id}".encode()).hexdigest()[:20]
    return SourceRelation(relation_id,source_id,candidate_source_id,SourceRelationType.DERIVED_FROM,confidence,inference_type,tuple(dict.fromkeys((*signal_ids,verification_id))))
def verify_predecessor_candidate(source_page_result:Any,fetch:CandidateFetchExecution)->PredecessorVerification:
    source_id=source_page_result.page.source_id; candidate_page=fetch.fetched_page
    if fetch.status is not CandidateFetchStatus.FETCHED or candidate_page is None:
        vid=_verification_id(source_id,"unavailable",PredecessorVerificationStatus.REJECTED); return PredecessorVerification(vid,source_id,None,PredecessorVerificationStatus.REJECTED,False,False,False,None,())
    candidate_extraction=extract_page_source_signals(candidate_page); compile_page_source_signals(candidate_page,candidate_extraction)
    candidate_url=_normalize_url(candidate_page.url)
    explicit_ids=[s.signal_id for s in source_page_result.extraction.signals if s.kind is PageSourceSignalKind.ATTRIBUTED_URL and _normalize_url(s.value)==candidate_url]
    candidate_text=_visible_text(candidate_page)
    quote_ids=[s.signal_id for s in source_page_result.extraction.signals if s.kind is PageSourceSignalKind.QUOTED_PHRASE and _normalize_text(s.value) and _normalize_text(s.value) in candidate_text]
    owners={}
    for s in candidate_extraction.signals:
        if s.kind is PageSourceSignalKind.OWNER_HINT:
            norm=_normalize_entity(s.value)
            if norm: owners.setdefault(norm,[]).append(s.signal_id)
    entity_ids=[]; owner_ids=[]
    for s in source_page_result.extraction.signals:
        if s.kind is PageSourceSignalKind.ATTRIBUTION_ENTITY:
            norm=_normalize_entity(s.value)
            if norm and norm in owners: entity_ids.append(s.signal_id); owner_ids.extend(owners[norm])
    explicit=bool(explicit_ids); quote=bool(quote_ids); owner=bool(entity_ids and owner_ids); candidate_source_id=candidate_page.source_id
    if explicit:
        status=PredecessorVerificationStatus.VERIFIED_EXPLICIT; vid=_verification_id(source_id,candidate_source_id,status); matched=tuple(dict.fromkeys(explicit_ids)); rel=_verified_relation(source_id=source_id,candidate_source_id=candidate_source_id,inference_type=RelationInferenceType.EXPLICIT,confidence=1.0,signal_ids=matched,verification_id=vid)
    elif quote and owner:
        status=PredecessorVerificationStatus.VERIFIED_INFERRED; vid=_verification_id(source_id,candidate_source_id,status); matched=tuple(dict.fromkeys((*quote_ids,*entity_ids,*owner_ids))); rel=_verified_relation(source_id=source_id,candidate_source_id=candidate_source_id,inference_type=RelationInferenceType.INFERRED,confidence=0.95,signal_ids=matched,verification_id=vid)
    else:
        status=PredecessorVerificationStatus.RELATED_ONLY; vid=_verification_id(source_id,candidate_source_id,status); matched=tuple(dict.fromkeys((*quote_ids,*entity_ids,*owner_ids))); rel=None
    return PredecessorVerification(vid,source_id,candidate_source_id,status,explicit,quote,owner,rel,matched)
