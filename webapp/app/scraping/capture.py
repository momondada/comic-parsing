import time
from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

JPG_EXTENSIONS = (".jpg", ".jpeg")
CHROMIUM_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]

# Each supported site gets its own scraping mechanism and image format,
# picked explicitly by domain rather than inferred (e.g. "try the
# embedded-JSON shortcut, fall back to a browser if it finds nothing") —
# the two approaches differ too much (one's a plain HTTP GET expecting
# webp/png/etc., the other drives a real browser expecting jpg) to treat
# as one generic path with a fallback.
ASURA_DOMAIN = "asurascans.com"
MGEKO_DOMAIN = "mgeko.cc"


@dataclass
class CapturedImage:
    url: str
    time: float
    body: bytes


def get_filename_from_url(url: str) -> str:
    path = urlparse(url).path
    return path.rsplit("/", 1)[-1]


def is_jpg(url: str, content_type: str) -> bool:
    filename = get_filename_from_url(url).lower()
    if filename.endswith(JPG_EXTENSIONS):
        return True
    return content_type.split(";")[0].strip().lower() == "image/jpeg"


def scroll_to_bottom(page, pause_ms=1000, max_stable_rounds=3):
    stable_rounds = 0
    last_height = page.evaluate("document.body.scrollHeight")
    while stable_rounds < max_stable_rounds:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            stable_rounds += 1
        else:
            stable_rounds = 0
            last_height = new_height


def _sort_key(image: "CapturedImage") -> tuple[float, float]:
    """Sort by the page number in the original filename (e.g. 1.jpg, 2.jpg,
    ...) when the site names pages that way — browsers fetch images
    concurrently, so arrival order often doesn't match reading order.
    Non-numeric filenames (e.g. stray comment-section images) sort after all
    numeric ones, in capture-time order as a stable fallback.
    """
    filename = get_filename_from_url(image.url)
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    try:
        page_number = float(stem)
    except ValueError:
        page_number = float("inf")
    return (page_number, image.time)


def _capture_via_browser(url: str) -> list[CapturedImage]:
    """Open a real browser, capture jpg network responses, and scroll to
    the bottom to trigger lazy-loaded images — for sites (e.g. mgeko.cc)
    that only load pages that way. Runs synchronously (sync_playwright);
    callers on an event loop should run this in a thread pool.
    """
    captured: list[CapturedImage] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        page = browser.new_page()

        def handle_response(response):
            content_type = response.headers.get("content-type", "")
            if not is_jpg(response.url, content_type):
                return
            try:
                body = response.body()
            except Exception:
                return
            captured.append(CapturedImage(url=response.url, time=time.time(), body=body))

        page.on("response", handle_response)

        page.goto(url, wait_until="load")
        scroll_to_bottom(page)
        page.wait_for_timeout(1500)

        page.remove_listener("response", handle_response)
        browser.close()

    captured.sort(key=_sort_key)
    return captured


def capture_images(url: str) -> list[CapturedImage]:
    """Return a chapter's page images, dispatched by the source site's
    domain rather than guessed from image format or page shape.
    """
    domain = urlparse(url).netloc.lower()

    if ASURA_DOMAIN in domain:
        from .static_html import try_capture_images

        images = try_capture_images(url)
        if images is None:
            raise RuntimeError(
                f"expected {ASURA_DOMAIN}'s embedded page-list JSON but found "
                "none — the page layout may have changed"
            )
        return images

    if MGEKO_DOMAIN in domain:
        return _capture_via_browser(url)

    raise RuntimeError(f"no scraping method is set up for this site yet: {domain}")
