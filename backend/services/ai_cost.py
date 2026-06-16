"""
NOAPI-P3 — AI 호출 비용 산출 utility.

정책 (NOAPI-P1 §7 / NOAPI-P3 D4):
  - pricing_table은 null placeholder. 실 단가는 운영 적용 직전 별도 작업.
  - pricing 미입력 시 cost_estimate_krw=None 허용.
  - 비용 산출 실패가 main flow를 중단하면 안 됨 (호출자가 try/except로 격리).
  - DB migration 없음. 기존 AICallLog.cost_estimate_krw 컬럼만 사용.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ─── pricing schema (P3는 null placeholder만) ────────────────────────
# 실 단가는 별도 작업에서 입력 (운영 적용 직전).
# 단가 출처는 OpenAI 공식 pricing page로 고정.

DEFAULT_PRICING_TABLE: Dict[str, Dict[str, Any]] = {
    "gpt-4o-mini": {
        "input_per_1m_tokens_usd": None,
        "output_per_1m_tokens_usd": None,
        "usd_to_krw_rate": None,
        "verified_at": None,
        "source": "OpenAI official pricing",
    },
    "gpt-4o": {
        "input_per_1m_tokens_usd": None,
        "output_per_1m_tokens_usd": None,
        "usd_to_krw_rate": None,
        "verified_at": None,
        "source": "OpenAI official pricing",
    },
}


_PRICING_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def load_pricing_table(path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """OPENAI_PRICING_PATH env 또는 default null placeholder 로드.

    cached. 미존재/parse 실패 시 DEFAULT_PRICING_TABLE 사용.
    """
    global _PRICING_CACHE
    if _PRICING_CACHE is not None:
        return _PRICING_CACHE

    resolved_path = path or os.getenv("OPENAI_PRICING_PATH", "")
    if resolved_path and os.path.isfile(resolved_path):
        try:
            with open(resolved_path, encoding="utf-8") as f:
                table = json.load(f)
            if isinstance(table, dict):
                _PRICING_CACHE = table
                return _PRICING_CACHE
        except Exception as e:
            logger.warning("[ai_cost] pricing table load 실패: %s — default 사용", e)

    _PRICING_CACHE = dict(DEFAULT_PRICING_TABLE)
    return _PRICING_CACHE


def reset_pricing_cache() -> None:
    """테스트용 — 캐시 reset."""
    global _PRICING_CACHE
    _PRICING_CACHE = None


def estimate_ai_cost_krw(
    model: Optional[str],
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    pricing_table: Optional[Dict[str, Dict[str, Any]]] = None,
    usd_to_krw_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """모델 + token 사용량 → 추정 비용 (KRW).

    Args:
        model: provider.model_name (예: "gpt-4o-mini"). None이면 pricing_found=False.
        input_tokens / output_tokens: prompt_tokens / completion_tokens (None 허용).
        pricing_table: 단가 dict. None이면 load_pricing_table().
        usd_to_krw_rate: 명시 환율. None이면 pricing_table[model]["usd_to_krw_rate"].

    Returns:
        {
          "cost_estimate_krw": float | None,
          "currency": "KRW",
          "pricing_found": bool,
          "warnings": List[str],   # 예: ["unknown_pricing", "rate_missing"]
        }

    정책:
      - pricing 미확인 / token None / rate None → cost=None + warnings
      - 비용 산출 실패가 main flow를 중단하지 않도록 호출자가 try/except 격리 권장
    """
    warnings: list[str] = []
    if pricing_table is None:
        pricing_table = load_pricing_table()

    if not model or model not in pricing_table:
        return {
            "cost_estimate_krw": None,
            "currency": "KRW",
            "pricing_found": False,
            "warnings": ["unknown_model" if model else "model_missing"],
        }

    p = pricing_table[model]
    in_rate = p.get("input_per_1m_tokens_usd")
    out_rate = p.get("output_per_1m_tokens_usd")
    krw_rate = usd_to_krw_rate if usd_to_krw_rate is not None else p.get("usd_to_krw_rate")

    if in_rate is None or out_rate is None:
        warnings.append("unknown_pricing")
    if krw_rate is None:
        warnings.append("rate_missing")
    if input_tokens is None and output_tokens is None:
        warnings.append("tokens_missing")

    if warnings:
        return {
            "cost_estimate_krw": None,
            "currency": "KRW",
            "pricing_found": (in_rate is not None and out_rate is not None),
            "warnings": warnings,
        }

    in_t = int(input_tokens or 0)
    out_t = int(output_tokens or 0)
    cost_usd = (in_t * in_rate + out_t * out_rate) / 1_000_000.0
    cost_krw = round(cost_usd * float(krw_rate), 4)

    return {
        "cost_estimate_krw": cost_krw,
        "currency": "KRW",
        "pricing_found": True,
        "warnings": [],
    }
