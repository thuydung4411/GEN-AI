import io
import pandas as pd
from docx import Document
import pymupdf

from worker.app.services.models import ExtractedDataset


def parse_pdf(content: bytes) -> ExtractedDataset:
    doc = pymupdf.open(stream=content, filetype="pdf")
    text_blocks = []
    
    if len(doc) == 0:
        raise ValueError("Cannot parse empty PDF dataset")

    for index, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            text_blocks.append(f"--- Page {index + 1} ---\n{text}")

    full_text = "\n\n".join(text_blocks)
    if not full_text.strip():
        raise ValueError("PDF dataset extracted NO text output (possibly scanned image without OCR)")

    return ExtractedDataset(
        content=full_text,
        metadata={"parser": "pymupdf_pdf_parser"}
    )


def parse_docx(content: bytes) -> ExtractedDataset:
    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n\n".join(paragraphs)
    
    if not full_text.strip():
        raise ValueError("DOCX dataset extracted NO text output")

    return ExtractedDataset(
        content=full_text,
        metadata={"parser": "python_docx_parser"}
    )


def parse_text(content: bytes) -> ExtractedDataset:
    text = content.decode("utf-8", errors="replace")
    if not text.strip():
        raise ValueError("TXT/MD dataset extracted NO text output")
        
    return ExtractedDataset(
        content=text,
        metadata={"parser": "raw_text_parser"}
    )


def parse_excel(content: bytes, mime_type: str) -> ExtractedDataset:
    try:
        if mime_type == "text/csv":
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise ValueError(f"Failed to parse Excel/CSV dataset: {e}")
        
    text = df.to_csv(index=False, sep="\t")
    if not text or not text.strip() or df.empty:
        raise ValueError("Excel/CSV dataset extracted NO text output")
        
    return ExtractedDataset(
        content=text,
        metadata={"parser": "pandas_excel_parser"}
    )


class DatasetParser:
    def parse(self, mime_type: str, content: bytes) -> ExtractedDataset:
        if mime_type == "application/pdf":
            return parse_pdf(content)
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return parse_docx(content)
        elif mime_type in ("text/plain", "text/markdown"):
            return parse_text(content)
        elif mime_type in (
            "text/csv", 
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            "application/vnd.ms-excel"
        ):
            return parse_excel(content, mime_type)
        else:
            raise ValueError(f"Unsupported mime type for parsing: {mime_type}")
