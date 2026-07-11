import re
from dataclasses import dataclass
from urllib.parse import urlparse

PRIMARY = re.compile(r"^(?P<comic>.+?)-chapter-(?P<chapter>\d+(?:\.\d+)?)(?:-.*)?$", re.I)
CHAPTER_SEGMENT = re.compile(r"^chapter[-_]?(?P<chapter>\d+(?:\.\d+)?)$", re.I)
CHAPTER_ANYWHERE = re.compile(r"chapter[-_/]?(?P<chapter>\d+(?:\.\d+)?)", re.I)
TEMPLATE_PATTERN = re.compile(r"(chapter[-_]?)(\d+(?:\.\d+)?)", re.I)
BOILERPLATE = {"reader", "en", "read", "manga", "comic", "comics", "series", "title"}


def chapter_row_key(chapter: float | None) -> str:
    if chapter is None:
        return "000000"
    return f"{round(chapter * 10):06d}"


def format_chapter(chapter: float) -> str:
    if chapter == int(chapter):
        return str(int(chapter))
    return str(chapter)


def derive_url_template(url: str) -> str | None:
    """Replace the chapter-number segment of a chapter URL with '{chapter}'.

    Lets a batch job reconstruct other chapters' URLs for the same comic
    (e.g. .../foo-chapter-84-eng-li/ -> .../foo-chapter-{chapter}-eng-li/).
    Returns None if no confident chapter-number segment is found.
    """
    match = TEMPLATE_PATTERN.search(url)
    if not match:
        return None
    start, end = match.span(2)
    return url[:start] + "{chapter}" + url[end:]


@dataclass
class ComicRef:
    comic: str
    chapter: float | None
    confidence: str  # "high" | "medium" | "low" | "none"

    @property
    def chapter_display(self) -> str:
        if self.chapter is None:
            return "unknown"
        return format_chapter(self.chapter)

    @property
    def chapter_row_key(self) -> str:
        return chapter_row_key(self.chapter)


def parse_comic_slug(url: str) -> ComicRef:
    path = urlparse(url).path
    segments = [s for s in path.strip("/").split("/") if s]

    if segments:
        m = PRIMARY.match(segments[-1])
        if m:
            return ComicRef(_normalize(m["comic"]), float(m["chapter"]), confidence="high")

    for i, seg in enumerate(segments):
        m = CHAPTER_SEGMENT.match(seg)
        if m:
            comic = next(
                (s for s in reversed(segments[:i]) if s.lower() not in BOILERPLATE), None
            )
            if comic:
                return ComicRef(_normalize(comic), float(m["chapter"]), confidence="medium")

    m = CHAPTER_ANYWHERE.search(path)
    if m:
        comic = next(
            (s for s in segments if "-" in s and s.lower() not in BOILERPLATE), None
        )
        if comic:
            return ComicRef(_normalize(comic), float(m["chapter"]), confidence="low")

    domain = urlparse(url).netloc.replace(".", "-")
    return ComicRef(f"unparsed-{domain}", None, confidence="none")


def _normalize(comic: str) -> str:
    comic = comic.lower().strip("-")
    comic = re.sub(r"-{2,}", "-", comic)
    return comic
