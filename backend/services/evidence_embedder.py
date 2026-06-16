"""E-2 Phase 3 — evidence_embedder.

텍스트 → vector 변환을 추상화한 Strategy 패턴.
환경변수 EMBEDDER로 백엔드 교체.

지원:
  - openai (활성, 기본): OpenAI text-embedding-3-small (1536차원)
  - bge-m3-ko (placeholder): 로컬 BAAI/bge-m3-ko (1024차원, GPU 권장)

추가 백엔드는 EmbedderBase를 상속하고 get_embedder()의 분기에 등록.

비용 (OpenAI text-embedding-3-small):
  $0.02 / 1M tokens
  300페이지 ≈ 500K tokens ≈ $0.01 (~15원)
  60 question queries ≈ 5K tokens ≈ $0.0001 (무시)
"""
from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Optional

logger = logging.getLogger(__name__)


# ─── 추상 베이스 ─────────────────────────────────────────────

class EmbedderBase(ABC):
    """Embedding 모델 추상화.

    구현체는 embed/embed_one/dim/name 4개 필수 + close (optional).
    """

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배열 → 벡터 배열 (각 1536/1024 차원 등)."""
        ...

    async def embed_one(self, text: str) -> List[float]:
        """단일 텍스트 편의 메서드."""
        result = await self.embed([text])
        return result[0] if result else []

    @property
    @abstractmethod
    def dim(self) -> int:
        """벡터 차원."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """식별자 (예: 'openai/text-embedding-3-small')."""
        ...

    def close(self) -> None:
        """리소스 정리 (필요 시 override)."""
        pass


# ─── OpenAI 구현 ─────────────────────────────────────────────

class OpenAIEmbedder(EmbedderBase):
    """OpenAI text-embedding-3-small (기본 1536차원).

    환경변수:
      OPENAI_EMBED_MODEL (default: text-embedding-3-small)
      OPENAI_API_KEY (필수)
      OPENAI_EMBED_BATCH (default: 100 — 1 요청당 텍스트 수)
    """

    def __init__(self, model: Optional[str] = None):
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 미설정 — embedder 사용 불가")

        self._model = model or os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
        self._batch = int(os.getenv("OPENAI_EMBED_BATCH", "100"))
        self._client = AsyncOpenAI(api_key=api_key)

        # 모델별 차원 (text-embedding-3-small=1536, large=3072)
        if "large" in self._model:
            self._dim = 3072
        else:
            self._dim = 1536

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # 빈 문자열 처리 — OpenAI는 빈 input rejects. 임시 ' '로 치환 후 결과는 0벡터로 대체할 수도 있으나 단순화: 호출자가 보장.
        # 여기서는 None/빈 입력은 0벡터 반환.
        clean: List[tuple] = []  # (idx, text)
        for i, t in enumerate(texts):
            if isinstance(t, str) and t.strip():
                clean.append((i, t))

        if not clean:
            return [[0.0] * self._dim for _ in texts]

        # 배치 분할 호출
        out: List[List[float]] = [None] * len(texts)  # type: ignore
        for start in range(0, len(clean), self._batch):
            batch_pairs = clean[start:start + self._batch]
            batch_texts = [t for _, t in batch_pairs]
            try:
                resp = await self._client.embeddings.create(
                    model=self._model,
                    input=batch_texts,
                )
            except Exception as e:
                logger.exception("[OpenAIEmbedder] embeddings.create 실패: %s", e)
                raise
            for (orig_idx, _), datum in zip(batch_pairs, resp.data):
                out[orig_idx] = list(datum.embedding)

        # 빈 입력 자리는 0벡터로
        for i, v in enumerate(out):
            if v is None:
                out[i] = [0.0] * self._dim

        return out

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return f"openai/{self._model}"


# ─── bge-m3-ko 구현 (placeholder) ─────────────────────────────

class BgeM3KoEmbedder(EmbedderBase):
    """로컬 BAAI/bge-m3-ko (1024차원, GPU 권장).

    placeholder — 사용자가 sentence-transformers + torch 설치 후
    아래 NotImplementedError 부분을 실제 호출로 교체.

    설치:
      pip install sentence-transformers torch
      (RTX 5060 등 CUDA GPU가 있으면 GPU 자동 사용)

    참고:
      모델 다운로드 ~2GB (HuggingFace)
      첫 호출 시 모델 로드 ~10초 (이후 캐시)
      RTX 5060 기준 300페이지 ≈ 1-3분
    """

    def __init__(self):
        self._dim = 1024
        # 실제 사용 시 아래 활성:
        # from sentence_transformers import SentenceTransformer
        # self._model = SentenceTransformer("BAAI/bge-m3", device="cuda")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError(
            "BgeM3KoEmbedder placeholder — 실제 구현은 sentence-transformers 설치 후 활성. "
            "EMBEDDER=openai 로 유지하거나 sentence-transformers + torch 설치 후 본 메서드 구현."
        )
        # 실제 구현 예 (참고):
        # loop = asyncio.get_event_loop()
        # vectors = await loop.run_in_executor(
        #     None,
        #     lambda: self._model.encode(texts, batch_size=32, show_progress_bar=False),
        # )
        # return [v.tolist() for v in vectors]

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def name(self) -> str:
        return "bge-m3-ko/local"


# ─── factory ─────────────────────────────────────────────────

_cached_embedder: Optional[EmbedderBase] = None


def get_embedder(force_new: bool = False) -> EmbedderBase:
    """환경변수 EMBEDDER 값에 따라 embedder 인스턴스 반환.

    값:
      "openai" (기본): OpenAIEmbedder
      "bge-m3-ko": BgeM3KoEmbedder

    Process 동안 1회만 초기화 (singleton). force_new=True 시 재생성.
    """
    global _cached_embedder
    if _cached_embedder is not None and not force_new:
        return _cached_embedder

    name = os.getenv("EMBEDDER", "openai").lower()
    if name == "openai":
        _cached_embedder = OpenAIEmbedder()
    elif name in ("bge-m3-ko", "bge", "bge-m3"):
        _cached_embedder = BgeM3KoEmbedder()
    else:
        raise ValueError(
            f"unknown EMBEDDER='{name}'. 지원: 'openai' | 'bge-m3-ko'"
        )

    logger.info("[evidence_embedder] selected: %s (dim=%d)",
                _cached_embedder.name, _cached_embedder.dim)
    return _cached_embedder
