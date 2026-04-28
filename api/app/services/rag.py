import json
import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx
from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.app.core.config import Settings
from api.app.models.entities import KnowledgeAsset, KnowledgeChunk, KnowledgeVersion
from api.app.services.embedder import QueryEmbedder


logger = logging.getLogger(__name__)


@dataclass
class RetrievedContext:
    chunk_id: uuid.UUID
    content: str
    asset_id: uuid.UUID
    asset_title: str
    original_filename: str
    distance: float
    source_page: int | None
    section_title: str | None


class RAGService:
    def __init__(self, settings: Settings, embedder: QueryEmbedder, session: AsyncSession):
        self._settings = settings
        self._embedder = embedder
        self._session = session

    def _normalize_for_matching(self, value: str) -> str:
        normalized = unicodedata.normalize("NFD", value.casefold())
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        return normalized.replace("đ", "d")

    async def retrieve_context(self, workspace_id: uuid.UUID, query: str) -> list[RetrievedContext]:
        query_embedding = await self._embedder.embed_query(query)

        statement = (
            select(
                KnowledgeChunk,
                KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(KnowledgeChunk.knowledge_version)
            .join(KnowledgeVersion.knowledge_asset)
            .where(KnowledgeAsset.workspace_id == workspace_id)
            .where(KnowledgeChunk.embedding.isnot(None))
            .options(
                selectinload(KnowledgeChunk.knowledge_version).selectinload(
                    KnowledgeVersion.knowledge_asset
                )
            )
            .order_by(KnowledgeChunk.embedding.cosine_distance(query_embedding))
            .limit(self._settings.rag_candidate_k)
        )

        results = await self._session.execute(statement)

        candidates: list[RetrievedContext] = []
        for chunk, distance in results:
            if distance > self._settings.rag_max_distance:
                continue

            asset = chunk.knowledge_version.knowledge_asset
            metadata = chunk.metadata_json or {}
            source_page = metadata.get("source_page") or metadata.get("page")
            section_title = metadata.get("section_title")

            candidates.append(
                RetrievedContext(
                    chunk_id=chunk.id,
                    content=chunk.content,
                    asset_id=asset.id,
                    asset_title=asset.title,
                    original_filename=asset.original_filename,
                    distance=distance,
                    source_page=source_page if isinstance(source_page, int) else None,
                    section_title=section_title if isinstance(section_title, str) else None,
                )
            )

        return self._select_relevant_contexts(query, candidates)

    def _query_terms(self, query: str) -> set[str]:
        normalized = self._normalize_for_matching(query)
        terms = {
            term
            for term in re.findall(r"[\w]+", normalized, flags=re.UNICODE)
            if len(term) >= 4
        }
        return terms

    def _lexical_score(self, query: str, context: RetrievedContext) -> float:
        terms = self._query_terms(query)
        if not terms:
            return 0.0

        haystack = " ".join(
            [
                context.content,
                context.asset_title,
                context.original_filename,
            ]
        )
        haystack = self._normalize_for_matching(haystack)
        matches = sum(1 for term in terms if term in haystack)
        return matches / len(terms)

    def _select_relevant_contexts(
        self,
        query: str,
        contexts: list[RetrievedContext],
    ) -> list[RetrievedContext]:
        if not contexts:
            return []

        scored = [
            (self._lexical_score(query, context), context)
            for context in sorted(contexts, key=lambda item: item.distance)
        ]
        lexical_matches = [(score, context) for score, context in scored if score > 0]

        if lexical_matches:
            lexical_matches.sort(key=lambda item: (-item[0], item[1].distance))
            pool = [context for _, context in lexical_matches]
        else:
            best_distance = min(context.distance for context in contexts)
            max_distance = min(
                self._settings.rag_max_distance,
                best_distance + self._settings.rag_distance_margin,
            )
            pool = [context for context in contexts if context.distance <= max_distance]
            pool.sort(key=lambda item: item.distance)

        selected: list[RetrievedContext] = []
        selected_assets: set[uuid.UUID] = set()

        for context in pool:
            if (
                context.asset_id not in selected_assets
                and len(selected_assets) >= self._settings.rag_max_citation_assets
            ):
                continue

            selected.append(context)
            selected_assets.add(context.asset_id)

            if len(selected) >= self._settings.rag_top_k:
                break

        return selected

    def _build_citations(self, contexts: list[RetrievedContext]) -> list[dict]:
        citations: list[dict] = []
        seen_assets: set[uuid.UUID] = set()

        for ctx in contexts:
            if ctx.asset_id in seen_assets:
                continue
            seen_assets.add(ctx.asset_id)
            citations.append(
                {
                    "asset_id": str(ctx.asset_id),
                    "original_filename": ctx.original_filename,
                    "chunk_id": str(ctx.chunk_id),
                    "source_page": ctx.source_page,
                    "quote": ctx.content[:200] + "...",
                    "distance": ctx.distance,
                }
            )

        return citations

    def build_grounded_prompt(self, query: str, contexts: list[RetrievedContext]) -> str:
        context_parts = []
        for ctx in contexts:
            page_info = f" (Page {ctx.source_page})" if ctx.source_page else ""
            context_parts.append(f"--- Document: {ctx.original_filename}{page_info} ---\n{ctx.content}")

        context_blocks = "\n\n".join(context_parts)

        return f"""Bạn là một AI RAG hỗ trợ hỏi đáp trên tài liệu đã tải lên.
Chỉ được trả lời dựa trên ngữ cảnh bên dưới.
Nếu thông tin không có trong ngữ cảnh, hãy trả lời đúng câu:
"Tôi không tìm thấy thông tin phù hợp trong tài liệu của bạn để trả lời câu hỏi này."
Tuyệt đối không bịa thêm.

=== NGỮ CẢNH ===
{context_blocks}
================

CÂU HỎI CỦA NGƯỜI DÙNG:
{query}
"""

    async def stream_generation(
        self,
        model_name: str,
        query: str,
        contexts: list[RetrievedContext],
        history: list[dict],
    ) -> AsyncGenerator[tuple[str, dict | None], None]:
        if not contexts:
            yield "Tôi không tìm thấy thông tin phù hợp trong tài liệu của bạn để trả lời câu hỏi này.", None

            citation_payload = {
                "citations": [],
                "retrieval": {
                    "top_k": self._settings.rag_top_k,
                    "distance_threshold": self._settings.rag_max_distance,
                },
                "provider": {"name": "guardrail", "model": "none"},
                "error": None,
            }
            yield "", citation_payload
            return

        prompt = self.build_grounded_prompt(query, contexts)

        citations = self._build_citations(contexts)

        messages = history + [{"role": "user", "content": prompt}]
        emitted_token = False

        try:
            if model_name.startswith("gemini"):
                async for token in self._stream_gemini(model_name, messages):
                    emitted_token = True
                    yield token, None
                provider = {"name": "gemini", "model": model_name}

            elif model_name.startswith("llama") or model_name.startswith("gemma"):
                async for token in self._stream_ollama(model_name, messages, self._settings.ollama_url):
                    emitted_token = True
                    yield token, None
                provider = {"name": "ollama", "model": model_name}

            else:
                raise ValueError(f"Unknown model identifier: {model_name}")

            citation_payload = {
                "citations": citations,
                "retrieval": {
                    "top_k": self._settings.rag_top_k,
                    "distance_threshold": self._settings.rag_max_distance,
                },
                "provider": provider,
                "error": None,
            }
            yield "", citation_payload

        except Exception as exc:
            logger.exception("Generation provider failed for model %s", model_name)
            if not emitted_token:
                yield f"Lỗi khi gọi model {model_name}: {exc}", None

            yield "", {
                "citations": citations,
                "retrieval": {
                    "top_k": self._settings.rag_top_k,
                    "distance_threshold": self._settings.rag_max_distance,
                },
                "provider": {"name": "unknown", "model": model_name},
                "error": str(exc),
            }

    async def _stream_gemini(self, model_name: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        client = genai.Client(api_key=self._settings.gemini_api_key)

        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = await client.aio.models.generate_content_stream(
            model=model_name,
            contents=gemini_messages,
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_ollama(
        self, model_name: str, messages: list[dict], url: str
    ) -> AsyncGenerator[str, None]:
        payload = {"model": model_name, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if "message" in chunk and "content" in chunk["message"]:
                        yield chunk["message"]["content"]
