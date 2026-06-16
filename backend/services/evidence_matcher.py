"""E-2 Phase 6 — evidence_matcher.

semantic search + 4-feature scoring으로 form_questions ↔ chunks 매칭.

E-2 발주 공식:
  final_score = semantic_similarity * 0.55
              + evidence_type_match   * 0.20
              + ontology_signal_strength * 0.15
              + section_question_fit  * 0.10

threshold:
  >= 0.70 → auto_confirmed
  0.50~0.70 → awaiting_user_confirm
  < 0.50 → no_match

Phase 6 (현재):
  - semantic_similarity: chromadb cosine 그대로 (진짜)
  - evidence_type_match: keyword 기반 단순 매칭 (Phase 6 단순화)
  - ontology_signal_strength: announcement_signals 가중치 (Phase 7 신호 router 통합 후 완성)
  - section_question_fit: source_file/section vs question section 단순 매칭

Phase 7에서 위 3개를 정교화.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from services.evidence_embedder import EmbedderBase, get_embedder
from services.evidence_store import EvidenceStore, get_store
from services.item_query_builder import build_queries

logger = logging.getLogger(__name__)

# E-2 발주 weights
WEIGHT_SEMANTIC = 0.55
WEIGHT_TYPE = 0.20
WEIGHT_SIGNAL = 0.15
WEIGHT_FIT = 0.10

# threshold (Phase 9-B 2026-05-18: 상향 — 노이즈 매핑 차단)
THRESHOLD_AUTO = 0.75
THRESHOLD_REVIEW = 0.60


# ─── feature scorers ─────────────────────────────────────────

def _score_type_match(
    question: Dict[str, Any],
    chunk_meta: Dict[str, Any],
    chunk_content: str,
) -> float:
    """evidence_type_match (0~1).

    Phase 6 단순화:
      - question.required_evidence_types가 비었으면 1.0 (제약 없음)
      - 있으면 chunk content에 type 키워드가 등장하면 1.0, 아니면 0.5

    Phase 7에서 chunk type 명시 분류 후 정확한 매칭으로 개선.
    """
    req_types = question.get("required_evidence_types") or question.get("required_evidence_type") or []
    if not isinstance(req_types, list) or not req_types:
        return 1.0

    content_lower = (chunk_content or "").lower()
    type_keywords = {
        "정량": ["매출", "실적", "%", "억", "건", "명", "년"],
        "재무": ["매출", "이익", "자산", "부채", "현금"],
        "시장": ["시장", "고객", "수출", "점유"],
        "기술": ["특허", "기술", "개발", "R&D", "rnd"],
        "인증": ["인증", "ISO", "iso", "수상", "인정"],
        "고용": ["고용", "직원", "채용", "인력"],
    }
    matched = 0
    for rt in req_types:
        rt_str = str(rt).lower()
        # 직접 매칭
        if any(rt_str in content_lower for _ in [True]):
            matched += 1
            continue
        # 키워드 매칭
        for cat, kws in type_keywords.items():
            if cat in rt_str:
                if any(kw.lower() in content_lower for kw in kws):
                    matched += 0.5
                    break
    return min(1.0, matched / max(1, len(req_types)))


def _score_signal_strength(
    question: Dict[str, Any],
    chunk_meta: Dict[str, Any],
    announcement_signals: Optional[Dict[str, Any]] = None,
) -> float:
    """ontology_signal_strength (0~1).

    Phase 6: 단순 — question.is_required True면 0.8, 아니면 0.5
    Phase 7에서 announcement_signal_router 통합 후 진짜 ontology score.
    """
    if not announcement_signals:
        # 공고 신호 없음 → required 여부만으로 추정
        return 0.8 if question.get("is_required") else 0.5

    # announcement_signals 활용 (Phase 7 완성)
    # 예: signals에 question_id별 가중치 또는 evaluation_criteria 매칭
    return 0.7  # placeholder


def _score_section_fit(
    question: Dict[str, Any],
    chunk_meta: Dict[str, Any],
    chunk_content: str = "",
) -> float:
    """section_question_fit (0~1).

    Phase 9-B 정교화: section_title + question_title의 핵심 단어가
    chunk content에 얼마나 등장하는지 측정.

    예: section_title="1. 스마트공장 구축 개요" + question_title="구축 목표"
        → keywords: [스마트공장, 구축, 개요, 목표]
        chunk content에 이 단어들 몇 개 등장하는가
    """
    sec_title = question.get("section_title") or ""
    q_title = question.get("title") or ""

    # 핵심 단어 추출 (한국어 2자+ 명사 위주 — 간단한 split)
    import re
    HANGUL_WORD = re.compile(r"[가-힣]{2,}")
    sec_words = set(HANGUL_WORD.findall(sec_title))
    q_words = set(HANGUL_WORD.findall(q_title))
    all_keywords = (sec_words | q_words) - {
        # 너무 흔한 단어 제거 (도메인 stop words)
        "사업", "내용", "계획", "방법", "기준", "현황", "구분", "기타", "관련",
    }

    if not all_keywords:
        return 0.6  # keyword 없으면 중립

    content_lower = (chunk_content or "").lower()
    hits = sum(1 for kw in all_keywords if kw.lower() in content_lower)
    fit = hits / max(1, len(all_keywords))

    # 0.0~1.0 정규화 + 최소값 보장 (semantic이 이미 잡았다면 너무 0으로 떨어지지 않음)
    return max(0.3, min(1.0, fit + 0.3))


# ─── main matcher ────────────────────────────────────────────

async def match_questions(
    session_id: str,
    form_questions: List[Dict[str, Any]],
    *,
    store: Optional[EvidenceStore] = None,
    embedder: Optional[EmbedderBase] = None,
    announcement_signals: Optional[Dict[str, Any]] = None,
    top_k: int = 5,
    threshold: float = THRESHOLD_REVIEW,
) -> Dict[str, Any]:
    """form questions → 4-feature scoring으로 매칭.

    Args:
        session_id: 검색할 evidence collection 식별자
        form_questions: flatten된 question list (section_title 포함이면 더 정확)
        store: EvidenceStore (None이면 singleton)
        embedder: EmbedderBase (None이면 singleton)
        announcement_signals: Phase 7 통합 시 사용 (None OK)
        top_k: 각 question당 top-k chunks 검색
        threshold: 최소 final_score (이하는 no_match)

    Returns:
        {
          session_id, question_mappings, overall_missing_count, coverage_rate,
          stats: {avg_score, matched_count, ...}
        }
    """
    store = store or get_store()
    embedder = embedder or get_embedder()

    if not form_questions:
        return {
            "session_id": session_id,
            "question_mappings": [],
            "overall_missing_count": 0,
            "coverage_rate": 0.0,
            "stats": {},
        }

    # collection 비어있으면 모든 question no_match
    chunk_total = store.count(session_id)
    if chunk_total == 0:
        return {
            "session_id": session_id,
            "question_mappings": [
                {
                    "question_id": q.get("question_id"),
                    "matched_evidence_ids": [],
                    "matched_evidence": [],
                    "confidence_score": 0.0,
                    "match_status": "no_match",
                }
                for q in form_questions if q.get("question_id")
            ],
            "overall_missing_count": len(form_questions),
            "coverage_rate": 0.0,
            "stats": {"chunk_total": 0, "reason": "no chunks in store"},
        }

    # 1. queries 생성 + embedding
    queries_map = build_queries(form_questions)
    qids = list(queries_map.keys())
    queries = [queries_map[qid] for qid in qids]

    logger.info("[matcher] embedding %d queries for session=%s (chunks_in_store=%d)",
                len(qids), session_id, chunk_total)
    query_vecs = await embedder.embed(queries)

    # 2. 각 question당 search + 4-feature scoring
    question_by_id = {q.get("question_id"): q for q in form_questions if q.get("question_id")}
    mappings: List[Dict[str, Any]] = []

    for qid, qvec in zip(qids, query_vecs):
        question = question_by_id.get(qid, {})

        hits = store.search(session_id, qvec, top_k=top_k)

        scored_hits: List[Dict[str, Any]] = []
        for hit in hits:
            meta = {
                "source_file": hit.get("source_file"),
                "page": hit.get("page"),
            }
            content = hit.get("content", "")
            sem = float(hit.get("similarity") or 0.0)
            type_score = _score_type_match(question, meta, content)
            signal_score = _score_signal_strength(question, meta, announcement_signals)
            fit_score = _score_section_fit(question, meta, content)

            final = (
                sem * WEIGHT_SEMANTIC
                + type_score * WEIGHT_TYPE
                + signal_score * WEIGHT_SIGNAL
                + fit_score * WEIGHT_FIT
            )

            scored_hits.append({
                "chunk_id": hit["chunk_id"],
                "source_file": meta["source_file"],
                "page": meta["page"],
                "content": content[:500],  # head 500자만 (응답 크기 관리)
                "score_semantic": round(sem, 4),
                "score_type": round(type_score, 4),
                "score_signal": round(signal_score, 4),
                "score_fit": round(fit_score, 4),
                "final_score": round(final, 4),
            })

        # threshold filter — final_score 기준
        passed = [h for h in scored_hits if h["final_score"] >= threshold]
        passed.sort(key=lambda h: h["final_score"], reverse=True)
        max_score = passed[0]["final_score"] if passed else 0.0

        if not passed:
            match_status = "no_match"
        elif max_score >= THRESHOLD_AUTO:
            match_status = "auto_confirmed"
        else:
            match_status = "awaiting_user_confirm"

        mappings.append({
            "question_id": qid,
            "matched_evidence_ids": [h["chunk_id"] for h in passed],
            "matched_evidence": passed,
            "used_evidence_ids": [h["chunk_id"] for h in passed],  # default — draft_writer가 그대로 사용
            "confidence_score": round(max_score, 4),
            "match_status": match_status,
            "missing_evidence_types": [] if passed else (
                question.get("required_evidence_types") or []
            ),
        })

    # ── Phase 9-C: chunk 다양성 페널티 ─────────────────────────
    # 같은 chunk가 너무 많은 question의 top-1로 사용되면 신뢰 ↓
    # (회사 자료의 일부 chunk가 모든 query에 우연 매칭되는 노이즈 차단)
    chunk_top1_count: Dict[str, int] = {}
    for m in mappings:
        if m["matched_evidence_ids"]:
            top_chunk = m["matched_evidence_ids"][0]
            chunk_top1_count[top_chunk] = chunk_top1_count.get(top_chunk, 0) + 1

    # 한 chunk가 3+ question에 top-1이면 confidence penalty
    PENALTY_PER_EXTRA_USE = 0.08  # 4번째 사용부터 -0.08, 5번째 -0.16, ...
    PENALTY_THRESHOLD = 3
    diversity_adjusted = 0
    for m in mappings:
        if not m["matched_evidence_ids"]:
            continue
        top_chunk = m["matched_evidence_ids"][0]
        usage = chunk_top1_count.get(top_chunk, 1)
        if usage > PENALTY_THRESHOLD:
            extra = usage - PENALTY_THRESHOLD
            penalty = min(0.4, extra * PENALTY_PER_EXTRA_USE)
            old_score = m["confidence_score"]
            new_score = max(0.0, old_score - penalty)
            m["confidence_score"] = round(new_score, 4)
            m["diversity_penalty"] = round(penalty, 4)
            # threshold 재평가
            if new_score < threshold:
                m["match_status"] = "no_match"
                m["matched_evidence_ids"] = []
                m["used_evidence_ids"] = []
                m["matched_evidence"] = []
            elif new_score < THRESHOLD_AUTO:
                m["match_status"] = "awaiting_user_confirm"
            diversity_adjusted += 1

    matched_count = sum(1 for m in mappings if m["matched_evidence_ids"])
    avg_score = sum(m["confidence_score"] for m in mappings) / max(1, len(mappings))
    coverage = matched_count / max(1, len(mappings))

    return {
        "session_id": session_id,
        "question_mappings": mappings,
        "overall_missing_count": len(mappings) - matched_count,
        "coverage_rate": round(coverage, 4),
        "stats": {
            "chunk_total": chunk_total,
            "question_total": len(mappings),
            "matched_count": matched_count,
            "avg_confidence": round(avg_score, 4),
            "diversity_adjusted_count": diversity_adjusted,
            "thresholds": {"auto": THRESHOLD_AUTO, "review": THRESHOLD_REVIEW},
            "weights": {
                "semantic": WEIGHT_SEMANTIC, "type": WEIGHT_TYPE,
                "signal": WEIGHT_SIGNAL, "fit": WEIGHT_FIT,
            },
        },
    }
