"""
C-1.6 — evaluation_rubric resolver.

Source of Truth 우선순위 (b8.md / c-1.6 발주문):
  1. announcement_signals.criteria 있음 → source="announcement"
  2. criteria 없음 + 사업 유형 감지 → source="default_template", template_type=<유형>
  3. 유형 불명확 → source="general", template_type="general"

axis-level weight_source enum (사용자 확정안):
  - announcement_explicit          : 공고문 weight 명시 → rescale to 100
  - announcement_equal_distribution: criteria 있으나 모두 weight 없음 → 균등 분배
  - missing_in_announcement        : mixed에서 일부 누락 (weight=0, is_scored=false)
  - default_template               : default template 사용 시

axes 구조 (발주문 5필드 + 사용자 확정 2필드):
  axis_id, name, weight, description, checklist + is_scored, weight_source
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


# ─── 사업 유형 분류 키워드 ───────────────────────────────────────────
_BUSINESS_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "R&D": ["R&D", "연구개발", "기술개발", "연구", "기술 개발"],
    "startup": ["창업", "예비창업", "초기창업", "스타트업"],
    "commercialization": ["사업화", "제품화", "실증", "양산", "상용화"],
    "marketing": ["마케팅", "판로", "수출", "홍보", "브랜딩"],
}


# ─── default rubric template 5종 (Q2 사용자 확정안) ───────────────────
# 각 template은 5축, weight=20 (5×20=100)
_DEFAULT_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "R&D": [
        {"axis_id": "rd_tech_diff", "name": "기술 차별성"},
        {"axis_id": "rd_goal_clarity", "name": "연구 목표 명확성"},
        {"axis_id": "rd_execution", "name": "실행 역량"},
        {"axis_id": "rd_collaboration", "name": "산학연 협력"},
        {"axis_id": "rd_commercialize", "name": "사업화 가능성"},
    ],
    "startup": [
        {"axis_id": "su_problem", "name": "시장 문제 정의"},
        {"axis_id": "su_solution", "name": "솔루션 차별성"},
        {"axis_id": "su_team", "name": "창업팀 역량"},
        {"axis_id": "su_market_entry", "name": "시장 진입 전략"},
        {"axis_id": "su_revenue", "name": "수익 모델"},
    ],
    "commercialization": [
        {"axis_id": "cm_product_maturity", "name": "제품 성숙도"},
        {"axis_id": "cm_production", "name": "양산 역량"},
        {"axis_id": "cm_channel", "name": "판로"},
        {"axis_id": "cm_profitability", "name": "수익성"},
        {"axis_id": "cm_risk", "name": "리스크 관리"},
    ],
    "marketing": [
        {"axis_id": "mk_target", "name": "타겟 정의"},
        {"axis_id": "mk_messaging", "name": "차별화 메시지"},
        {"axis_id": "mk_channel", "name": "채널 전략"},
        {"axis_id": "mk_metric", "name": "측정 지표"},
        {"axis_id": "mk_roi", "name": "ROI"},
    ],
    "general": [
        {"axis_id": "gn_problem_clarity", "name": "문제 정의의 명확성"},
        {"axis_id": "gn_solution_diff", "name": "솔루션의 차별성"},
        {"axis_id": "gn_market", "name": "시장성"},
        {"axis_id": "gn_execution", "name": "실행 가능성"},
        {"axis_id": "gn_measurability", "name": "성과 측정 가능성"},
    ],
}


# ────────────────────────────────────────────────────────────────────
# business_type 감지
# ────────────────────────────────────────────────────────────────────

def detect_business_type(
    notice_schema: Optional[Dict[str, Any]],
    confirmed_schema: Optional[Dict[str, Any]],
    announcement_signals: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """3개 소스에서 키워드 매칭으로 사업 유형 감지.

    Returns:
        {
            "method": "keyword_match" | "default_general",
            "matched_keywords": [{"keyword", "source", "matched_type"}],
            "scores": {type: count},
            "selected_type": "R&D" | "startup" | ... | "general",
            "confidence": float,
        }
    """
    sources = _collect_text_sources(notice_schema, confirmed_schema, announcement_signals)
    matched: List[Dict[str, str]] = []
    scores: Dict[str, int] = {t: 0 for t in _BUSINESS_TYPE_KEYWORDS.keys()}

    for source_name, text in sources:
        if not text:
            continue
        for btype, keywords in _BUSINESS_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw and kw in text:
                    matched.append({
                        "keyword": kw,
                        "source": source_name,
                        "matched_type": btype,
                    })
                    scores[btype] += 1

    if not matched:
        return {
            "method": "default_general",
            "matched_keywords": [],
            "scores": scores,
            "selected_type": "general",
            "confidence": 0.0,
        }

    # 최고 점수 유형 선택
    selected_type = max(scores.items(), key=lambda x: x[1])[0]
    top_score = scores[selected_type]
    total = sum(scores.values())
    confidence = top_score / total if total > 0 else 0.0

    return {
        "method": "keyword_match",
        "matched_keywords": matched,
        "scores": scores,
        "selected_type": selected_type if top_score > 0 else "general",
        "confidence": round(confidence, 3),
    }


def _collect_text_sources(
    notice_schema: Optional[Dict[str, Any]],
    confirmed_schema: Optional[Dict[str, Any]],
    announcement_signals: Optional[Dict[str, Any]],
) -> List[tuple]:
    """3개 소스에서 키워드 매칭용 텍스트를 (source_name, text) 튜플로 수집."""
    out: List[tuple] = []

    # 1. notice_schema
    if isinstance(notice_schema, dict):
        for key in ("target", "benefit", "submission_system"):
            v = notice_schema.get(key)
            if isinstance(v, str):
                out.append((f"notice.{key}", v))
        # important_keywords
        kws = notice_schema.get("important_keywords") or []
        if isinstance(kws, list):
            out.append(("notice.important_keywords", " ".join(str(k) for k in kws)))
        # ai_interpretation 모든 문자열 모음
        ai = notice_schema.get("ai_interpretation") or {}
        if isinstance(ai, dict):
            chunks = []
            for v in ai.values():
                if isinstance(v, list):
                    chunks.extend(str(x) for x in v)
                elif isinstance(v, str):
                    chunks.append(v)
            out.append(("notice.ai_interpretation", " ".join(chunks)))

    # 2. confirmed_schema (form)
    if isinstance(confirmed_schema, dict):
        form_name = confirmed_schema.get("form_name") or ""
        out.append(("form.form_name", form_name))
        sections = confirmed_schema.get("sections") or []
        if isinstance(sections, list):
            titles = []
            for s in sections:
                if isinstance(s, dict):
                    titles.append(str(s.get("title") or ""))
                    for q in (s.get("questions") or []):
                        if isinstance(q, dict):
                            titles.append(str(q.get("title") or ""))
            out.append(("form.titles", " ".join(titles)))

    # 3. announcement_signals
    if isinstance(announcement_signals, dict):
        # criteria/preferences/eligibility name/value 모음
        chunks = []
        for slot_key in ("criteria", "preferences", "eligibility", "emphasis_keywords"):
            for item in (announcement_signals.get(slot_key) or []):
                if not isinstance(item, dict):
                    continue
                for k in ("name", "value", "keyword"):
                    v = item.get(k)
                    if isinstance(v, str):
                        chunks.append(v)
                    elif isinstance(v, list):
                        chunks.extend(str(x) for x in v)
        out.append(("announcement_signals", " ".join(chunks)))

    return out


# ────────────────────────────────────────────────────────────────────
# axes weight 정규화 (사용자 Q6 확정안)
# ────────────────────────────────────────────────────────────────────

def _normalize_announcement_axes(criteria: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """announcement_signals.criteria → axes (Q6 사용자 확정안).

    3-case:
      - case 1 (모두 positive): rescale to 100, weight_source=announcement_explicit
      - case 2 (모두 0/없음): 균등 분배, weight_source=announcement_equal_distribution
      - case 3 (mixed): positive만 100 normalize, 누락은 weight=0 + is_scored=false
        + weight_source=missing_in_announcement / announcement_explicit
    """
    if not criteria:
        return []

    axes: List[Dict[str, Any]] = []
    positive_indices: List[int] = []
    none_or_zero_indices: List[int] = []

    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            continue
        w = c.get("weight") or 0
        if w > 0:
            positive_indices.append(i)
        else:
            none_or_zero_indices.append(i)
        axes.append({
            "axis_id": f"axis_{len(axes) + 1:02d}",
            "name": c.get("name") or f"axis_{len(axes) + 1}",
            "weight": 0.0,  # 아래에서 결정
            "description": "",
            "checklist": [],
            "is_scored": False,  # 아래에서 결정
            "weight_source": "missing_in_announcement",  # 아래에서 결정
            "_raw_weight": w,
        })

    if not axes:
        return []

    # case 2: 모두 0/없음 → 균등 분배
    if not positive_indices:
        n = len(axes)
        each = 100.0 / n
        for ax in axes:
            ax["weight"] = each
            ax["is_scored"] = True
            ax["weight_source"] = "announcement_equal_distribution"
        _apply_residual_correction(axes)
        _strip_internal_fields(axes)
        return axes

    # case 1 또는 case 3: positive만 100으로 normalize
    total_positive = sum(criteria[i].get("weight") or 0 for i in positive_indices)
    for i, ax in enumerate(axes):
        raw_w = ax["_raw_weight"]
        if raw_w > 0:
            ax["weight"] = raw_w * (100.0 / total_positive)
            ax["is_scored"] = True
            ax["weight_source"] = "announcement_explicit"
        else:
            ax["weight"] = 0.0
            ax["is_scored"] = False
            ax["weight_source"] = "missing_in_announcement"

    _apply_residual_correction(axes)
    _strip_internal_fields(axes)
    return axes


def _apply_residual_correction(axes: List[Dict[str, Any]]) -> None:
    """마지막 scored axis에서 rounding 잔차 보정 (sum=100 보장)."""
    scored = [a for a in axes if a.get("is_scored")]
    if not scored:
        return
    current_sum = sum(a["weight"] for a in scored)
    residual = 100.0 - current_sum
    if abs(residual) > 1e-9:
        scored[-1]["weight"] = round(scored[-1]["weight"] + residual, 10)


def _strip_internal_fields(axes: List[Dict[str, Any]]) -> None:
    """내부 계산용 필드 제거 (_raw_weight 등)."""
    for ax in axes:
        ax.pop("_raw_weight", None)


# ────────────────────────────────────────────────────────────────────
# default template axes 생성
# ────────────────────────────────────────────────────────────────────

def _template_axes(template_type: str) -> List[Dict[str, Any]]:
    """default template 5축 (각 weight=20).

    weight_source = "default_template", is_scored=True.
    """
    template = _DEFAULT_TEMPLATES.get(template_type, _DEFAULT_TEMPLATES["general"])
    return [
        {
            "axis_id": ax["axis_id"],
            "name": ax["name"],
            "weight": 20.0,
            "description": "",
            "checklist": [],
            "is_scored": True,
            "weight_source": "default_template",
        }
        for ax in template
    ]


# ────────────────────────────────────────────────────────────────────
# Public API — resolve_evaluation_rubric
# ────────────────────────────────────────────────────────────────────

def resolve_evaluation_rubric(
    notice_schema: Optional[Dict[str, Any]],
    confirmed_schema: Optional[Dict[str, Any]],
    announcement_signals: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """C-1.6 main resolver.

    Source of Truth 우선순위:
      1. announcement_signals.criteria 있음 → source="announcement"
      2. criteria 없음 + 사업 유형 감지 → source="default_template", template_type
      3. 유형 불명확 → source="general", template_type="general"

    Returns: evaluation_rubric dict (저장 구조)
    """
    # business_type 항상 감지 (Q9 — announcement source여도 참고)
    detection = detect_business_type(notice_schema, confirmed_schema, announcement_signals)

    criteria_list = []
    if isinstance(announcement_signals, dict):
        c = announcement_signals.get("criteria") or []
        if isinstance(c, list):
            criteria_list = c

    if criteria_list:
        # source=announcement (case 1/2/3)
        axes = _normalize_announcement_axes(criteria_list)
        source = "announcement"
        template_type = detection.get("selected_type") or "general"
    else:
        # default_template 분기 (announcement criteria 빈)
        selected = detection.get("selected_type") or "general"
        template_type = selected
        axes = _template_axes(template_type)
        source = "general" if selected == "general" else "default_template"

    return {
        "source": source,
        "template_type": template_type,
        "axes": axes,
        "business_type_detection": detection,
        "user_confirmed": False,
        "user_modified": False,
        # resolved_at은 호출자가 채움 (datetime import 분리)
    }
