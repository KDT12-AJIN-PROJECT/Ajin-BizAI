"""E-2 Phase 4 — evidence_store.

chromadb 영속 vector store 래퍼.
세션별 collection 분리 (multi-tenancy 격리).

특징:
  - PersistentClient (backend/chroma_data/ 디스크 저장)
  - cosine similarity (hnsw:space=cosine)
  - session_id별 collection — 사용자 자료 격리
  - upsert 지원 (자료 재업로드 시 chunk_id로 덮어쓰기)

발주 e-2: 외부 검색 금지, 사용자 자료만, citation 가능해야 함.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 기본 영속 경로 (backend/chroma_data)
_DEFAULT_PATH = str(
    Path(__file__).resolve().parent.parent / "chroma_data"
)
CHROMA_DATA_PATH = os.getenv("CHROMA_DATA_PATH", _DEFAULT_PATH)


class EvidenceStore:
    """chromadb 영속 store wrapper — 세션별 collection 격리.

    사용:
        store = EvidenceStore()
        store.upsert(session_id, chunks, vectors)
        result = store.search(session_id, query_vector, top_k=5)
        store.count(session_id)  # collection size
        store.delete_session(session_id)  # 세션 전체 제거
    """

    def __init__(self, persist_path: Optional[str] = None):
        import chromadb
        from chromadb.config import Settings

        self._path = persist_path or CHROMA_DATA_PATH
        Path(self._path).mkdir(parents=True, exist_ok=True)

        # PersistentClient — 자동 디스크 저장
        # anonymized_telemetry=False — 외부 통신 차단 (발주 e-2 외부 검색 금지)
        self._client = chromadb.PersistentClient(
            path=self._path,
            settings=Settings(anonymized_telemetry=False, allow_reset=False),
        )

    def _collection_name(self, session_id: str) -> str:
        """session_id → safe collection name (chromadb는 [a-zA-Z0-9_-] 만 허용)."""
        if not session_id:
            return "session_default"
        # session_id는 이미 hex string이지만 safety로 sanitize
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in session_id)
        return f"sess_{safe}"

    def _get_collection(self, session_id: str):
        return self._client.get_or_create_collection(
            name=self._collection_name(session_id),
            metadata={"hnsw:space": "cosine"},  # cosine similarity (1 - cosine_distance)
        )

    def upsert(
        self,
        session_id: str,
        chunks: List[Dict[str, Any]],
        vectors: List[List[float]],
    ) -> int:
        """chunks + vectors를 collection에 추가/갱신.

        chunk_id 기준 upsert — 같은 ID 존재 시 덮어쓰기.
        Returns: 추가/갱신된 row 수.
        """
        if not chunks or not vectors:
            return 0
        if len(chunks) != len(vectors):
            raise ValueError(
                f"chunks/vectors length mismatch: {len(chunks)} vs {len(vectors)}"
            )

        collection = self._get_collection(session_id)

        ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        documents: List[str] = []
        embeddings: List[List[float]] = []

        for c, vec in zip(chunks, vectors):
            cid = c.get("chunk_id")
            content = c.get("content") or ""
            if not cid or not content:
                continue
            ids.append(cid)
            documents.append(content)
            embeddings.append(vec)
            # chromadb metadata는 scalar만 허용 (str/int/float/bool). None은 제거.
            meta_raw = {
                "source_file": c.get("source_file") or "",
                "page": c.get("page") if c.get("page") is not None else -1,
                "start_char": c.get("start_char") or 0,
                "end_char": c.get("end_char") or 0,
                "content_chars": c.get("content_chars") or len(content),
            }
            metadatas.append({k: v for k, v in meta_raw.items() if v is not None})

        if not ids:
            return 0

        try:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents,
            )
        except Exception as e:
            logger.exception("[evidence_store] upsert 실패 session=%s: %s", session_id, e)
            raise
        return len(ids)

    def search(
        self,
        session_id: str,
        query_vector: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """query_vector와 가장 유사한 top_k chunks 반환.

        Returns:
            [{chunk_id, source_file, page, content, similarity, distance}, ...]
            similarity = 1 - cosine_distance (0~1, 1이 가장 유사)
        """
        if not query_vector:
            return []
        collection = self._get_collection(session_id)
        if collection.count() == 0:
            return []

        try:
            res = collection.query(
                query_embeddings=[query_vector],
                n_results=min(top_k, collection.count()),
                include=["metadatas", "documents", "distances"],
            )
        except Exception as e:
            logger.exception("[evidence_store] search 실패 session=%s: %s", session_id, e)
            raise

        out: List[Dict[str, Any]] = []
        ids = (res.get("ids") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]

        for cid, meta, doc, dist in zip(ids, metas, docs, dists):
            similarity = 1.0 - float(dist) if dist is not None else 0.0
            out.append({
                "chunk_id": cid,
                "source_file": (meta or {}).get("source_file", ""),
                "page": (meta or {}).get("page", -1),
                "content": doc or "",
                "similarity": round(similarity, 4),
                "distance": round(float(dist), 4) if dist is not None else None,
            })
        return out

    def count(self, session_id: str) -> int:
        """session collection 안의 chunk 수."""
        try:
            return self._get_collection(session_id).count()
        except Exception:
            return 0

    def delete_session(self, session_id: str) -> bool:
        """session collection 전체 삭제."""
        try:
            self._client.delete_collection(self._collection_name(session_id))
            return True
        except Exception as e:
            logger.warning("[evidence_store] delete_session 실패 session=%s: %s", session_id, e)
            return False

    def list_sessions(self) -> List[str]:
        """전체 collection 이름 리스트 (디버그용)."""
        try:
            return [c.name for c in self._client.list_collections()]
        except Exception:
            return []


# ─── singleton (process 1회) ─────────────────────────────────

_cached_store: Optional[EvidenceStore] = None


def get_store() -> EvidenceStore:
    """process 동안 단일 EvidenceStore 인스턴스 반환."""
    global _cached_store
    if _cached_store is None:
        _cached_store = EvidenceStore()
        logger.info("[evidence_store] initialized at %s", _cached_store._path)
    return _cached_store
