import json
import uuid
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx
from google import genai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.app.core.config import Settings
from api.app.models.entities import Chunk
from api.app.services.embedder import QueryEmbedder

@dataclass
class RetrievedContext:
    chunk_id: uuid.UUID
    content: str
    dataset_id: uuid.UUID
    dataset_title: str
    original_filename: str
    distance: float
    source_page: int | None
    section_title: str | None


class RAGService:
    def __init__(self, settings: Settings, embedder: QueryEmbedder, session: AsyncSession):
        self._settings = settings
        self._embedder = embedder
        self._session = session

    async def retrieve_context(self, workspace_id: uuid.UUID, query: str) -> list[RetrievedContext]:
        query_embedding = await self._embedder.embed_query(query)

        statement = (
            select(
                Chunk, 
                Chunk.embedding.cosine_distance(query_embedding).label('distance')
            )
            .where(Chunk.workspace_id == workspace_id)
            .options(selectinload(Chunk.dataset))
            .order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(self._settings.rag_top_k)
        )
        
        results = await self._session.execute(statement)
        
        contexts = []
        for chunk, distance in results:
            if distance <= self._settings.rag_max_distance:
                contexts.append(
                    RetrievedContext(
                        chunk_id=chunk.id,
                        content=chunk.content,
                        dataset_id=chunk.dataset.id,
                        dataset_title=chunk.dataset.title,
                        original_filename=chunk.dataset.original_filename,
                        distance=distance,
                        source_page=chunk.source_page,
                        section_title=chunk.section_title
                    )
                )
                
        return contexts

    def build_grounded_prompt(self, query: str, contexts: list[RetrievedContext]) -> str:
        context_parts = []
        for ctx in contexts:
            page_info = f" (Page {ctx.source_page})" if ctx.source_page else ""
            context_parts.append(f"--- Dataset: {ctx.original_filename}{page_info} ---\n{ctx.content}")
            
        context_blocks = "\n\n".join(context_parts)
        
        prompt = f"""Bạn là một AI RAG (Retrieval-Augmented Generation) thông minh. 
Nhiệm vụ của bạn là trả lời câu hỏi DỰA TRÊN NGỮ CẢNH ĐƯỢC CUNG CẤP BÊN DƯỚI.
Nếu thông tin không có trong ngữ cảnh, hãy nói "Tôi không tìm thấy thông tin phù hợp trong tài liệu của bạn để trả lời câu hỏi này." 
TUYỆT ĐỐI KHÔNG bịa đặt thông tin (nghiêm cấm hallucination).

=== NGỮ CẢNH ===
{context_blocks}
================

CÂU HỎI CỦA NGƯỜI DÙNG:
{query}
"""
        return prompt

    async def stream_generation(
        self, 
        model_name: str, 
        query: str, 
        contexts: list[RetrievedContext],
        history: list[dict]
    ) -> AsyncGenerator[tuple[str, dict | None], None]:
        """
        Yields tuples: (text_token, final_metadata)
        Returns the text stream natively so it can be saved in DB before SSE formatting.
        """
        if not contexts:
            # ZERO CONTEXT GUARDRAIL
            yield "Tôi không tìm thấy thông tin phù hợp trong tài liệu của bạn để trả lời câu hỏi này.", None
            
            citation_payload = {
                "citations": [],
                "retrieval": {"top_k": self._settings.rag_top_k, "distance_threshold": self._settings.rag_max_distance},
                "provider": {"name": "guardrail", "model": "none"},
                "error": None
            }
            yield "", citation_payload
            return

        prompt = self.build_grounded_prompt(query, contexts)
        
        citations = [
            {
                "dataset_id": str(ctx.dataset_id),
                "original_filename": ctx.original_filename,
                "chunk_id": str(ctx.chunk_id),
                "source_page": ctx.source_page,
                "quote": ctx.content[:200] + "..."
            }
            for ctx in contexts
        ]
        
        messages = history + [{"role": "user", "content": prompt}]
        
        try:
            if model_name.startswith("gemini"):
                async for token in self._stream_gemini(model_name, messages):
                    yield token, None
                provider = {"name": "gemini", "model": model_name}
                
            elif model_name.startswith("llama") or model_name.startswith("gemma"):
                async for token in self._stream_ollama(model_name, messages, self._settings.ollama_url):
                    yield token, None
                provider = {"name": "ollama", "model": model_name}
                
            else:
                raise ValueError(f"Unknown model identifier: {model_name}")

            citation_payload = {
                "citations": citations,
                "retrieval": {"top_k": self._settings.rag_top_k, "distance_threshold": self._settings.rag_max_distance},
                "provider": provider,
                "error": None
            }
            yield "", citation_payload
            
        except Exception as e:
            yield "", {
                "citations": citations,
                "retrieval": {"top_k": self._settings.rag_top_k, "distance_threshold": self._settings.rag_max_distance},
                "provider": {"name": "unknown", "model": model_name},
                "error": str(e)
            }

    async def _stream_gemini(self, model_name: str, messages: list[dict]) -> AsyncGenerator[str, None]:
        client = genai.Client(api_key=self._settings.gemini_api_key)
        
        # Format history for Gemini
        gemini_messages = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})
            
        response = await client.aio.models.generate_content_stream(
            model=model_name,
            contents=gemini_messages
        )
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def _stream_ollama(self, model_name: str, messages: list[dict], url: str) -> AsyncGenerator[str, None]:
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", f"{url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
