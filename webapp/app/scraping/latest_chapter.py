import re
from urllib.parse import urlparse

from .static_html import fetch_text

ASURA_DOMAIN = "asurascans.com"
MGEKO_DOMAIN = "mgeko.cc"

ASURA_SERIES_PATH = re.compile(r"^(/comics/[^/]+)/chapter/")


def parse_asurascans_latest(html: str, series_path: str) -> float | None:
    """series_path is e.g. "/comics/helmut-the-forsaken-child-a80d257e" —
    the series index page lists every chapter as a link back to itself, so
    scoping the pattern to that exact path avoids picking up "related
    series" links elsewhere on the page.
    """
    pattern = re.compile(re.escape(series_path) + r"/chapter/(\d+(?:\.\d+)?)")
    numbers = [float(n) for n in pattern.findall(html)]
    return max(numbers) if numbers else None


def parse_mgeko_latest(html: str, comic: str) -> float | None:
    """comic is the site-inferred slug (e.g. "manga-q1113"); the chapter
    picker's <option value="..."> entries embed it the same way the page's
    own URL does.
    """
    pattern = re.compile(
        r'<option[^>]*value="[^"]*' + re.escape(comic) + r'-chapter-(\d+(?:\.\d+)?)-[^"]*"'
    )
    numbers = [float(n) for n in pattern.findall(html)]
    return max(numbers) if numbers else None


def find_latest_chapter(comic: str, sample_chapter_url: str) -> float | None:
    """Given a comic slug and a known chapter URL from it, find the highest
    chapter number currently listed on the source site. Returns None if
    this isn't a site we know how to check, or nothing was found.
    """
    domain = urlparse(sample_chapter_url).netloc.lower()

    if ASURA_DOMAIN in domain:
        parsed = urlparse(sample_chapter_url)
        match = ASURA_SERIES_PATH.match(parsed.path)
        if not match:
            return None
        series_path = match.group(1)
        series_url = f"{parsed.scheme}://{parsed.netloc}{series_path}/"
        return parse_asurascans_latest(fetch_text(series_url), series_path)

    if MGEKO_DOMAIN in domain:
        return parse_mgeko_latest(fetch_text(sample_chapter_url), comic)

    return None
