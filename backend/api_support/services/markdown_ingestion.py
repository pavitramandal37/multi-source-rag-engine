import re
from pathlib import Path
from typing import Dict, List, Tuple

from api_support.models import Source
from api_support.services.base_ingestion import BaseIngestionService, IngestionResult

_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_DEEPER_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)


class MarkdownIngestionService(BaseIngestionService):

    def _slugify(self, heading: str) -> str:
        slug = heading.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_-]+", "-", slug)
        return slug.strip("-")

    def _split_by_headings(self, md_text: str) -> List[Tuple[str, str, str]]:
        """
        Split markdown at ## boundaries.
        Returns list of (heading_text, section_content, anchor_slug).
        Content before the first ## becomes an "Introduction" section.
        """
        matches = list(_HEADING_RE.finditer(md_text))

        if not matches:
            return [("Document", md_text.strip(), "document")]

        sections: List[Tuple[str, str, str]] = []

        preamble = md_text[: matches[0].start()].strip()
        if preamble:
            sections.append(("Introduction", preamble, "introduction"))

        for i, match in enumerate(matches):
            heading = match.group(1).strip()
            anchor = self._slugify(heading)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
            # Strip deeper heading markers to produce clean plain text
            content = _DEEPER_HEADING_RE.sub("", md_text[start:end]).strip()
            if content:
                sections.append((heading, content, anchor))

        return sections

    def ingest_markdown(self, name: str, md_path: Path, filename: str) -> IngestionResult:
        source = Source.objects.create(name=name, type=Source.TYPE_MARKDOWN, origin=filename)

        text = md_path.read_text(encoding="utf-8")
        sections = self._split_by_headings(text)

        chunks: List[Tuple[str, str, Dict]] = []
        for heading, content, anchor in sections:
            citation_url = f"#{anchor}"
            meta: Dict = {
                "heading": heading,
                "anchor": anchor,
                "filename": filename,
                "citation_url": citation_url,
                "snippet": content[:200],
            }
            chunks.append((heading, content, meta))

        return self._embed_and_store(source, chunks)
