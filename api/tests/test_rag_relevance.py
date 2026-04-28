from uuid import uuid4

import pytest

from api.app.core.config import Settings
from api.app.services.rag import RAGService, RetrievedContext


def make_context(
    *,
    content: str,
    asset_id=None,
    filename: str = "Document 1.docx",
    distance: float = 0.2,
) -> RetrievedContext:
    resolved_asset_id = asset_id or uuid4()
    return RetrievedContext(
        chunk_id=uuid4(),
        content=content,
        asset_id=resolved_asset_id,
        asset_title=filename.removesuffix(".docx"),
        original_filename=filename,
        distance=distance,
        source_page=None,
        section_title=None,
    )


def test_select_relevant_contexts_prefers_lexical_match():
    service = RAGService(Settings(auto_create_schema=False), embedder=None, session=None)

    relevant = make_context(
        content="1. Thoi gian lam viec\nSang tu 08h00-11h45; chieu tu 13h00-17h15.",
        filename="Document 1.docx",
        distance=0.22,
    )
    noisy = make_context(
        content="Bao cao kiem thu chuc nang cap chung chi nghiep vu dau thau.",
        filename="BAO CAO KIEM THU.docx",
        distance=0.18,
    )

    selected = service._select_relevant_contexts(
        "thoi gian lam viec cua cong ty",
        [noisy, relevant],
    )

    assert selected == [relevant]


def test_build_citations_deduplicates_by_asset():
    service = RAGService(Settings(auto_create_schema=False), embedder=None, session=None)
    asset_id = uuid4()
    first = make_context(content="first chunk", asset_id=asset_id, distance=0.1)
    second = make_context(content="second chunk", asset_id=asset_id, distance=0.2)
    other = make_context(content="other file", filename="Other.docx", distance=0.3)

    citations = service._build_citations([first, second, other])

    assert [citation["original_filename"] for citation in citations] == [
        "Document 1.docx",
        "Other.docx",
    ]


@pytest.mark.asyncio
async def test_stream_generation_surfaces_provider_error(monkeypatch):
    service = RAGService(Settings(auto_create_schema=False), embedder=None, session=None)
    context = make_context(content="1. Thoi gian lam viec\nSang tu 08h00-11h45.")

    async def failing_stream(*args, **kwargs):
        if False:
            yield ""
        raise RuntimeError("API key must be set when using the Google AI API.")

    monkeypatch.setattr(service, "_stream_gemini", failing_stream)

    events = [
        event
        async for event in service.stream_generation(
            model_name="gemini-2.5-flash",
            query="thoi gian lam viec",
            contexts=[context],
            history=[],
        )
    ]

    assert events[0][0].startswith("Lỗi khi gọi model gemini-2.5-flash")
    assert events[-1][1]["error"] == "API key must be set when using the Google AI API."
