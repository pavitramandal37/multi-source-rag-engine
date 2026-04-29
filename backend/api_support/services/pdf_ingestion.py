from pathlib import Path
from typing import Dict, List, Tuple

from pypdf import PdfReader

from api_support.models import Source
from api_support.services.base_ingestion import BaseIngestionService, IngestionResult

MIN_PAGE_CHARS = 200


class PDFIngestionService(BaseIngestionService):

    def _extract_pages(self, pdf_path: Path) -> List[Tuple[int, str]]:
        """Returns list of (1-indexed page number, extracted text)."""
        reader = PdfReader(str(pdf_path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            pages.append((i + 1, text))
        return pages

    def _merge_short_pages(self, pages: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
        """Merge pages shorter than MIN_PAGE_CHARS into the following page."""
        merged: List[Tuple[int, str]] = []
        buffer_num: int | None = None
        buffer_text = ""

        for page_num, text in pages:
            if buffer_text:
                combined = buffer_text + "\n\n" + text
                if len(combined) >= MIN_PAGE_CHARS:
                    merged.append((buffer_num, combined))
                    buffer_num = None
                    buffer_text = ""
                else:
                    buffer_text = combined
            elif len(text) < MIN_PAGE_CHARS:
                buffer_num = page_num
                buffer_text = text
            else:
                merged.append((page_num, text))

        if buffer_text:
            merged.append((buffer_num, buffer_text))

        return merged

    def ingest_pdf(self, name: str, pdf_path: Path, filename: str) -> IngestionResult:
        source = Source.objects.create(name=name, type=Source.TYPE_PDF, origin=filename)

        pages = self._extract_pages(pdf_path)
        pages = self._merge_short_pages(pages)

        chunks: List[Tuple[str, str, Dict]] = []
        for page_num, text in pages:
            if not text:
                continue
            citation_url = f"/media/uploads/{filename}#page={page_num}"
            meta: Dict = {
                "page_number": page_num,
                "filename": filename,
                "citation_url": citation_url,
            }
            title = f"{name} — Page {page_num}"
            chunks.append((title, text, meta))

        return self._embed_and_store(source, chunks)
