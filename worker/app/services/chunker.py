import hashlib
from typing import Iterator
from langchain_text_splitters import RecursiveCharacterTextSplitter

from worker.app.services.models import ExtractedDataset, ChunkEntity


class DatasetChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )

    def chunk(self, doc: ExtractedDataset) -> Iterator[ChunkEntity]:
        texts = self.splitter.split_text(doc.content)
        
        for index, text in enumerate(texts):
            text_strip = text.strip()
            if not text_strip:
                continue
                
            content_hash = hashlib.sha256(text_strip.encode("utf-8")).hexdigest()
            
            # Simple heuristic for page number if available
            source_page = None
            if "--- Page" in text_strip:
                try:
                    # just extract the first page number mentioned
                    page_str = text_strip.split("--- Page")[1].split("---")[0].strip()
                    source_page = int(page_str)
                except Exception:
                    pass
            
            yield ChunkEntity(
                chunk_index=index,
                content=text_strip,
                metadata={
                    "parser": doc.metadata.get("parser", "unknown"),
                    "chunk_size": len(text_strip)
                },
                source_page=source_page,
                section_title=None,
                content_hash=content_hash
            )
