"""
LM Studio 클라이언트 (DetailPage AI 본문 분석용, 2026-05-25 C 그룹).

특이사항 — gemma-4-e4b reasoning 모델:
  - 응답이 reasoning_content (추론) + content (최종 답) 두 부분으로 나뉨
  - max_tokens가 짧으면 reasoning에서 다 소진되어 content가 빈 문자열로 끝남
  - → max_tokens 4096+ 권장
"""
import json
import os
from typing import Any, Optional

import httpx


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


async def call_lm_studio(
    system: str,
    user: str,
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    timeout: float = 120.0,
) -> str:
    """LM Studio chat completion 호출 → content 문자열 반환.

    reasoning 모델 대응: max_tokens 충분히 + content 빈 문자열이면 명확한 에러 raise.
    """
    url = _env("LM_STUDIO_URL", "http://127.0.0.1:1234").rstrip("/")
    model = _env("LM_STUDIO_MODEL", "google/gemma-4-e4b")
    token = _env("LM_STUDIO_TOKEN")

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{url}/v1/chat/completions", headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"LM Studio HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()

    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = (msg.get("content") or "").strip()
    finish = choice.get("finish_reason", "")

    if not content:
        reasoning_preview = (msg.get("reasoning_content") or "")[:100]
        raise RuntimeError(
            f"LM Studio 응답이 비어있습니다 (finish_reason={finish}). "
            f"max_tokens를 늘리거나 reasoning mode를 끄세요. "
            f"reasoning 미리보기: {reasoning_preview!r}"
        )
    return content


def try_parse_json(text: str) -> Optional[dict]:
    """LLM 출력에서 JSON 블록을 안전하게 추출."""
    text = text.strip()
    # 코드펜스 제거
    if text.startswith("```"):
        lines = text.split("\n")
        # 첫 줄(```json), 마지막 줄(```) 제거
        text = "\n".join(lines[1:-1]) if len(lines) >= 3 else text
    # 첫 { ~ 마지막 } 추출
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
