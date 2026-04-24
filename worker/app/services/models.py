from dataclasses import dataclass
from typing import Any

@dataclass
class ExtractedDataset:
    content: str
    metadata: dict[str, Any]

@dataclass
class ChunkEntity:
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    source_page: int | None
    section_title: str | None
    content_hash: str
