import html
import re
import time
import urllib.request

from .capture import CapturedImage

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Some statically-rendered reader pages (e.g. Astro islands, as seen on
# asurascans.com) embed the full ordered page list directly in the page's
# HTML as serialized hydration props, in the shape
# {"url":[0,"https://.../page.webp"]}. When present, the page list can be
# read straight out of one plain HTTP GET with no browser/JS execution
# needed at all — much faster and more reliable than network-capture +
# scroll-triggered lazy loading.
PAGE_URL_PATTERN = re.compile(
    r'"url":\[0,"(https?://[^"]+?\.(?:jpe?g|png|webp|gif)(?:\?[^"]*)?)"\]'
)


def extract_page_urls(page_html: str) -> list[str]:
    """Pull ordered page image URLs out of embedded hydration JSON, if any."""
    return PAGE_URL_PATTERN.findall(html.unescape(page_html))


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,zh-TW;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def fetch_text(url: str) -> str:
    return _fetch(url).decode("utf-8", errors="replace")


def try_capture_images(url: str) -> list[CapturedImage] | None:
    """Return page images parsed straight out of the page's HTML, or None
    if this page doesn't have that embedded-JSON shape — callers should
    fall back to full browser-based capture in that case.
    """
    try:
        page_html = fetch_text(url)
    except Exception:
        return None

    page_urls = extract_page_urls(page_html)
    if not page_urls:
        return None

    return [CapturedImage(url=u, time=time.time(), body=_fetch(u)) for u in page_urls]
