"""
NOAPI-P2 R1 — Context size guard for LLM calls.

목표:
  - Sonnet/Haiku/Opus context window (200K tokens) overflow 방지
  - evidence_list / ref_text / form_text 등 큰 텍스트를 LLM 호출 전에 추정/조정
  - Offline (외부 API 호출 없음, anthropic.count_tokens 사용 안 함)

정밀도 정책:
  - estimate_tokens: 단순 char/4 휴리스틱 (Anthropic/OpenAI 권장 근사)
  - 한국어는 1 char ≈ 1.5 token이므로 보수적으로 잡음 (char*0.6)
  - 정밀 카운트가 필요하면 tiktoken / anthropic.count_tokens 사용 (별도 작업)

용도:
  - AnthropicProvider._chat() 호출 전 budget 확인
  - 초과 시: truncate (잘림 안내) 또는 raise (호출자가 분할)
"""
from typing import List, Optional


# ─── 상수 ─────────────────────────────────────────────────────────

# Claude 4 family default context window
DEFAULT_CONTEXT_TOKENS = 200_000

# 안전 마진 (응답 max_tokens 4096 + system overhead 등)
DEFAULT_SAFETY_MARGIN_TOKENS = 8_192

# 한국어 + 영문 혼합 추정 계수 (char × COEF = approx tokens)
# 영문: char/4 (계수 0.25), 한국어: char × 1.5 (계수 1.5)
# 한국어 중심 코퍼스 가정 → 0.6 (안전 측면 over-estimate)
KOREAN_CHAR_TO_TOKEN_COEF = 0.6
ASCII_CHAR_TO_TOKEN_COEF = 0.25


# ─── 추정 ─────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """텍스트 → 추정 토큰 수 (offline, 보수적 over-estimate).

    영문/한국어 비율 기반 가중 평균. 정밀하지 않으나 budget guard 용도로 충분.
    빈 문자열 → 0.
    """
    if not text:
        return 0
    text_str = str(text)
    total = len(text_str)
    if total == 0:
        return 0

    # ASCII vs 비ASCII 분리
    ascii_count = sum(1 for ch in text_str if ord(ch) < 128)
    non_ascii_count = total - ascii_count

    tokens = (
        ascii_count * ASCII_CHAR_TO_TOKEN_COEF
        + non_ascii_count * KOREAN_CHAR_TO_TOKEN_COEF
    )
    # 보수: 최소 1 token + ceiling
    return max(1, int(tokens) + 1)


def estimate_messages_tokens(system: str, user: str) -> int:
    """system + user prompt 합산 토큰 추정.

    Anthropic messages API의 wrapping overhead (~50 tokens) 포함.
    """
    return estimate_tokens(system) + estimate_tokens(user) + 50


# ─── budget guard ─────────────────────────────────────────────────

class TokenBudgetExceeded(Exception):
    """입력이 context budget을 초과."""


def check_budget(
    system: str,
    user: str,
    *,
    max_response_tokens: int = 4096,
    context_limit: int = DEFAULT_CONTEXT_TOKENS,
    safety_margin: int = DEFAULT_SAFETY_MARGIN_TOKENS,
) -> dict:
    """입력 토큰 추정 + budget 검사. 결과 dict 반환.

    초과 시 raise X — 호출자가 truncate/분할 결정.

    반환:
      {
        "input_tokens": int,
        "max_response_tokens": int,
        "total_budget": int,
        "context_limit": int,
        "available_after_response": int,
        "over_budget": bool,
        "over_by": int (>=0)
      }
    """
    input_tokens = estimate_messages_tokens(system, user)
    total_budget = input_tokens + max_response_tokens + safety_margin
    over_by = max(0, total_budget - context_limit)
    return {
        "input_tokens": input_tokens,
        "max_response_tokens": max_response_tokens,
        "total_budget": total_budget,
        "context_limit": context_limit,
        "available_after_response": context_limit - total_budget,
        "over_budget": over_by > 0,
        "over_by": over_by,
    }


def assert_budget(
    system: str,
    user: str,
    *,
    max_response_tokens: int = 4096,
    context_limit: int = DEFAULT_CONTEXT_TOKENS,
    safety_margin: int = DEFAULT_SAFETY_MARGIN_TOKENS,
) -> None:
    """budget 초과 시 TokenBudgetExceeded raise."""
    result = check_budget(
        system, user,
        max_response_tokens=max_response_tokens,
        context_limit=context_limit,
        safety_margin=safety_margin,
    )
    if result["over_budget"]:
        raise TokenBudgetExceeded(
            f"입력 {result['input_tokens']} + 응답 {max_response_tokens} + margin {safety_margin} "
            f"= {result['total_budget']} > context {context_limit} "
            f"(초과 {result['over_by']} tokens)"
        )


# ─── truncation ───────────────────────────────────────────────────

def truncate_to_token_budget(
    text: str,
    max_tokens: int,
    *,
    suffix: str = "\n[... 이하 생략, 토큰 한도 초과 ...]",
) -> str:
    """text를 max_tokens 이내로 자름. suffix 포함.

    추정 기반이므로 실제 토큰은 max_tokens보다 약간 적을 수 있음.
    over-estimate 정책 (안전 측면).
    """
    if max_tokens <= 0:
        return ""
    current = estimate_tokens(text)
    if current <= max_tokens:
        return text

    suffix_tokens = estimate_tokens(suffix)
    target_text_tokens = max_tokens - suffix_tokens
    if target_text_tokens <= 0:
        return suffix[:100]

    # 비례 단축 (조금 더 여유)
    target_char_count = int(len(text) * (target_text_tokens / current) * 0.95)
    if target_char_count <= 0:
        return suffix

    return text[:target_char_count].rstrip() + suffix


def truncate_items_to_budget(
    items: List[dict],
    text_key: str,
    max_total_tokens: int,
) -> List[dict]:
    """item 배열을 합산 토큰이 budget 이내로 자름.

    각 item의 `text_key` 필드 텍스트를 측정. 누적 초과 시 그 시점에서 잘림.
    item 자체는 자르지 않음 (전체 포함 또는 전체 제외).

    용도: evidence_list, ref_text chunks 등.
    """
    out = []
    used_tokens = 0
    for item in items:
        text = item.get(text_key, "") if isinstance(item, dict) else ""
        item_tokens = estimate_tokens(text)
        if used_tokens + item_tokens > max_total_tokens:
            break
        out.append(item)
        used_tokens += item_tokens
    return out
