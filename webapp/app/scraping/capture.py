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


def capture_images(url: str) -> list[CapturedImage]:
    """Open url, capture jpg network responses, scroll to the bottom to
    trigger lazy-loaded images, then return everything captured in
    capture-time order. Runs synchronously (sync_playwright); callers on an
    event loop should run this in a thread pool.
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

    captured.sort(key=lambda item: item.time)
    return captured
