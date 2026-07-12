import time
from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

JPG_EXTENSIONS = (".jpg", ".jpeg")
CHROMIUM_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]


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


def capture_images(url: str) -> list[CapturedImage]:
    """Return a chapter's page images.

    Tries the fast path first: some sites embed the full ordered page list
    directly in the page's HTML (see static_html.py), needing only a plain
    HTTP GET. Falls back to opening a real browser, capturing jpg network
    responses, and scrolling to the bottom to trigger lazy-loaded images,
    for sites that only load pages that way (e.g. mgeko.cc). Runs
    synchronously (sync_playwright); callers on an event loop should run
    this in a thread pool.
    """
    from .static_html import try_capture_images

    static_result = try_capture_images(url)
    if static_result is not None:
        return static_result

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
