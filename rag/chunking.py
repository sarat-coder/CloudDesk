from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_WINDOW_SIZE = 900
_WINDOW_OVERLAP = 150


@dataclass
class Article:
    slug: str
    title: str
    category: str
    tags: list[str]
    summary: str
    body: str


@dataclass
class ArticleChunk:
    id: str           # "{slug}#chunk-{n}"
    article_id: str   # slug
    title: str
    heading: str
    text: str         # raw chunk text
    prefixed_text: str  # "{title} - {heading}: {text}" — embedded
    category: str
    tags: list[str] = field(default_factory=list)
    source: str = ""  # "kb://{slug}#chunk-{n}"
    snippet: str = ""  # first 200 chars of text


def _parse_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    fm_text = m.group(1)
    body = raw[m.end():]
    result: dict[str, object] = {}
    for line in fm_text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"')
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            items = [item.strip().strip('"') for item in inner.split(",") if item.strip()]
            result[key] = items
        else:
            result[key] = val
    return result, body


def load_article_files(kb_dir: str) -> list[Article]:
    articles: list[Article] = []
    for path in sorted(Path(kb_dir).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(raw)
        slug = path.stem
        articles.append(
            Article(
                slug=slug,
                title=str(fm.get("title", slug)),
                category=str(fm.get("category", "other")),
                tags=list(fm.get("tags", [])),  # type: ignore[arg-type]
                summary=str(fm.get("summary", "")),
                body=body.strip(),
            )
        )
    return articles


def chunk_article(article: Article) -> list[ArticleChunk]:
    """Split on headings, then 900/150 windows, prefix each chunk."""
    sections: list[tuple[str, str]] = _split_sections(article)
    chunks: list[ArticleChunk] = []
    chunk_index = 0
    for heading, text in sections:
        for window in _sliding_windows(text, _WINDOW_SIZE, _WINDOW_OVERLAP):
            chunk_id = f"{article.slug}#chunk-{chunk_index}"
            prefixed = f"{article.title} - {heading}: {window}"
            chunks.append(
                ArticleChunk(
                    id=chunk_id,
                    article_id=article.slug,
                    title=article.title,
                    heading=heading,
                    text=window,
                    prefixed_text=prefixed,
                    category=article.category,
                    tags=list(article.tags),
                    source=f"kb://{article.slug}#chunk-{chunk_index}",
                    snippet=window[:200],
                )
            )
            chunk_index += 1
    return chunks


def _split_sections(article: Article) -> list[tuple[str, str]]:
    """Split article body into (heading, text) sections."""
    parts = re.split(r"(^#{1,6}\s+.+$)", article.body, flags=re.MULTILINE)
    sections: list[tuple[str, str]] = []
    current_heading = article.title
    current_parts: list[str] = []
    for part in parts:
        if re.match(r"^#{1,6}\s+", part):
            text = "\n".join(current_parts).strip()
            if text:
                sections.append((current_heading, text))
            current_heading = re.sub(r"^#{1,6}\s+", "", part).strip()
            current_parts = []
        else:
            current_parts.append(part)
    text = "\n".join(current_parts).strip()
    if text:
        sections.append((current_heading, text))
    if not sections:
        sections = [(article.title, article.body)]
    return sections


def _sliding_windows(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    windows: list[str] = []
    step = size - overlap
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        windows.append(text[start:end])
        if end == len(text):
            break
        start += step
    return windows
