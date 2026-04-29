import re
import time
import urllib.parse
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple

import httpx
import trafilatura
from bs4 import BeautifulSoup

from api_support.models import Source
from api_support.services.base_ingestion import BaseIngestionService, IngestionResult

SKIP_EXTENSIONS = {
    ".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".mp4", ".mp3", ".woff", ".woff2", ".ttf", ".ico", ".xml",
    ".css", ".js", ".json", ".rss", ".atom",
}


class URLIngestionService(BaseIngestionService):

    def _slugify(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_-]+", "-", text)
        return text.strip("-")

    def _text_fragment(self, content: str, page_url: str) -> str:
        # Use first sentence capped at 80 chars for reliable fragment highlighting.
        # safe=",-." keeps text-fragment delimiters unencoded per spec.
        first_sentence = content.split(".")[0].strip()[:80]
        encoded = urllib.parse.quote(first_sentence, safe=",-.")
        return f"{page_url}#:~:text={encoded}"

    def _split_by_headings(self, html: str, base_url: str) -> List[Tuple[str, str, Dict]]:
        """Split HTML content at h1/h2/h3 boundaries into (title, content, metadata) tuples."""
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body") or soup

        # Derive initial heading from <title>
        title_tag = soup.find("title")
        current_heading = title_tag.get_text(strip=True) if title_tag else base_url
        current_paragraphs: List[str] = []
        chunks: List[Tuple[str, str, Dict]] = []

        def flush(heading: str, paragraphs: List[str]) -> None:
            if not paragraphs:
                return
            section_text = "\n\n".join(paragraphs)
            anchor = self._slugify(heading)
            citation_url = self._text_fragment(section_text, base_url)
            meta: Dict = {
                "source_url": base_url,
                "heading": heading,
                "anchor": anchor,
                "citation_url": citation_url,
            }
            chunks.append((heading, section_text, meta))

        for tag in body.descendants:
            if not hasattr(tag, "name") or tag.name is None:
                continue
            if tag.name in ("h1", "h2", "h3"):
                flush(current_heading, current_paragraphs)
                current_paragraphs = []
                current_heading = tag.get_text(strip=True)
            elif tag.name in ("p", "li", "td", "pre", "blockquote"):
                text = tag.get_text(strip=True)
                if text:
                    current_paragraphs.append(text)

        flush(current_heading, current_paragraphs)

        # Fallback: whole page as one chunk if no structure found
        if not chunks:
            text = trafilatura.extract(html, include_comments=False, include_tables=True) or \
                   soup.get_text(separator="\n", strip=True)
            page_title = title_tag.get_text(strip=True) if title_tag else base_url
            meta = {"source_url": base_url, "citation_url": base_url}
            chunks.append((page_title, text, meta))

        return chunks

    def _same_domain_links(self, html: str, base_url: str) -> List[str]:
        """Return deduplicated same-domain absolute URLs from <a href> tags."""
        parsed_base = urllib.parse.urlparse(base_url)
        soup = BeautifulSoup(html, "html.parser")
        seen: dict = {}
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            absolute = urllib.parse.urljoin(base_url, href)
            parsed = urllib.parse.urlparse(absolute)
            if parsed.scheme not in ("http", "https"):
                continue
            if parsed.netloc != parsed_base.netloc:
                continue
            ext = Path(parsed.path).suffix.lower()
            if ext in SKIP_EXTENSIONS:
                continue
            clean = urllib.parse.urlunparse(parsed._replace(query="", fragment=""))
            seen[clean] = None  # deduplicate, preserve order
        return list(seen.keys())

    def ingest_url(
        self,
        name: str,
        url: str,
        crawl_depth: int = 2,
        max_pages: int = 50,
    ) -> IngestionResult:
        source = Source.objects.create(name=name, type=Source.TYPE_URL, origin=url)

        visited: set = set()
        queue: deque = deque([(url, 0)])
        all_chunks: List[Tuple[str, str, Dict]] = []

        while queue and len(visited) < max_pages:
            current_url, depth = queue.popleft()
            if current_url in visited:
                continue

            ext = Path(urllib.parse.urlparse(current_url).path).suffix.lower()
            if ext in SKIP_EXTENSIONS:
                continue

            visited.add(current_url)

            try:
                resp = httpx.get(
                    current_url,
                    timeout=10,
                    follow_redirects=True,
                    headers={"User-Agent": "RAGBot/1.0 (+localhost; research crawler)"},
                )
                resp.raise_for_status()
                if "text/html" not in resp.headers.get("content-type", ""):
                    continue
                html = resp.text
            except Exception:
                continue

            time.sleep(0.5)  # polite rate limiting

            heading_chunks = self._split_by_headings(html, current_url)
            all_chunks.extend(heading_chunks)

            if depth < crawl_depth:
                for link in self._same_domain_links(html, current_url):
                    if link not in visited:
                        queue.append((link, depth + 1))

        return self._embed_and_store(source, all_chunks)
