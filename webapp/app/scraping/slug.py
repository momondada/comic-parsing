import re
from dataclasses import dataclass
from urllib.parse import urlparse

PRIMARY = re.compile(r"^(?P<comic>.+?)-chapter-(?P<chapter>\d+(?:\.\d+)?)(?:-.*)?$", re.I)
CHAPTER_SEGMENT = re.compile(r"^chapter[-_]?(?P<chapter>\d+(?:\.\d+)?)$", re.I)
CHAPTER_ANYWHERE = re.compile(r"chapter[-_/]?(?P<chapter>\d+(?:\.\d+)?)", re.I)
BOILERPLATE = {"reader", "en", "read", "manga", "comic", "comics", "series", "title"}


@dataclass
class ComicRef:
    comic: str
    chapter: float | None
    confidence: str  # "high" | "medium" | "low" | "none"

    @property
    def chapter_display(self) -> str:
        if self.chapter is None:
            return "unknown"
        if self.chapter == int(self.chapter):
            return str(int(self.chapter))
        return str(self.chapter)

    @property
    def chapter_row_key(self) -> str:
        if self.chapter is None:
            return "000000"
        return f"{round(self.chapter * 10):06d}"


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
