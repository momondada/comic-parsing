"""Download all chapters of a syosetu.com novel into one plain-text file.

No translation — just the raw Japanese text, one chapter after another,
in order. Run locally (not part of the deployed webapp): syosetu.com
blocks requests from the Azure App Service's IP, but works fine from a
normal residential/office connection.

Usage:
    python download_novel.py https://ncode.syosetu.com/n1662ds/1/
    python download_novel.py n1662ds --output n1662ds.txt --start 1 --end 20
"""

import argparse
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8,zh-TW;q=0.7",
}

CHAPTER_PATH = re.compile(r"^/([^/]+)/(\d+)/?$")
DELAY_SECONDS = 1.5
MAX_RETRIES = 3


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_novel_code(url_or_code: str) -> str:
    if "/" not in url_or_code:
        return url_or_code
    path = urlparse(url_or_code).path
    match = CHAPTER_PATH.match(path)
    if match:
        return match.group(1)
    # Bare series URL like https://ncode.syosetu.com/n1662ds/
    segments = [s for s in path.strip("/").split("/") if s]
    if segments:
        return segments[0]
    raise ValueError(f"couldn't figure out the novel code from: {url_or_code}")


def chapter_url(novel_code: str, chapter: int) -> str:
    return f"https://ncode.syosetu.com/{novel_code}/{chapter}/"


def toc_url(novel_code: str) -> str:
    return f"https://ncode.syosetu.com/{novel_code}/"


MAX_TOC_PAGES = 100  # generous cap (100 chapters/page -> up to 10,000 chapters)


def find_latest_chapter(novel_code: str) -> int | None:
    """The table-of-contents page paginates at 100 chapters per page
    (?p=2, ?p=3, ...), so a long novel's later chapters won't show up on
    page 1 alone — walk pages until one has no chapter links left.
    """
    pattern = re.compile(r'href="/' + re.escape(novel_code) + r'/(\d+)/?"')
    all_numbers = []

    for page in range(1, MAX_TOC_PAGES + 1):
        url = toc_url(novel_code) if page == 1 else f"{toc_url(novel_code)}?p={page}"
        try:
            html_text = fetch_text(url)
        except urllib.error.HTTPError:
            break  # no more pages
        numbers = [int(n) for n in pattern.findall(html_text)]
        if not numbers:
            break
        all_numbers.extend(numbers)
        if page > 1:
            time.sleep(DELAY_SECONDS)

    return max(all_numbers) if all_numbers else None


class _NovelTextParser(HTMLParser):
    """Extracts the chapter body from syosetu's
    <div class="js-novel-text p-novel__text">...</div>, one line per <p>
    element, ignoring nested formatting tags (<font> etc.) entirely.
    """

    def __init__(self):
        super().__init__()
        self._in_target_div = False
        self._div_depth = 0
        self._in_p = False
        self._current_line: list[str] = []
        self.lines: list[str] = []

    def handle_starttag(self, tag, attrs):
        if not self._in_target_div:
            if tag == "div":
                classes = (dict(attrs).get("class") or "").split()
                if "js-novel-text" in classes:
                    self._in_target_div = True
                    self._div_depth = 1
            return

        if tag == "div":
            self._div_depth += 1
        elif tag == "p":
            self._in_p = True
            self._current_line = []

    def handle_endtag(self, tag):
        if not self._in_target_div:
            return

        if tag == "div":
            self._div_depth -= 1
            if self._div_depth == 0:
                self._in_target_div = False
        elif tag == "p" and self._in_p:
            self._in_p = False
            self.lines.append("".join(self._current_line).strip())

    def handle_data(self, data):
        if self._in_target_div and self._in_p:
            self._current_line.append(data)


def extract_novel_text(page_html: str) -> str:
    parser = _NovelTextParser()
    parser.feed(page_html)
    return "\n".join(parser.lines)


def fetch_chapter_with_retries(novel_code: str, chapter: int) -> str | None:
    url = chapter_url(novel_code, chapter)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return extract_novel_text(fetch_text(url))
        except Exception as e:
            print(f"  chapter {chapter}: attempt {attempt}/{MAX_RETRIES} failed ({e})")
            time.sleep(DELAY_SECONDS)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url_or_code", help="a chapter URL, series URL, or bare novel code")
    parser.add_argument("--output", help="output .txt path (default: {novel_code}.txt)")
    parser.add_argument("--start", type=int, default=1, help="first chapter (default: 1)")
    parser.add_argument(
        "--end", type=int, default=None, help="last chapter (default: auto-detect latest)"
    )
    args = parser.parse_args()

    novel_code = parse_novel_code(args.url_or_code)
    output_path = args.output or f"{novel_code}.txt"

    end = args.end
    if end is None:
        print(f"Checking latest chapter for {novel_code}...")
        end = find_latest_chapter(novel_code)
        if end is None:
            print("Couldn't find any chapter links on the table-of-contents page.")
            sys.exit(1)
        print(f"Latest chapter: {end}")

    print(f"Downloading chapters {args.start}-{end} into {output_path}")

    # newline="\n" forces LF-only output regardless of OS — on Windows,
    # the default text-mode write silently translates "\n" to "\r\n",
    # which broke the webapp's "===== label =====" delimiter matching
    # (its regex anchors "$" right before "\n", and a stray "\r" in
    # between silently fails every match).
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        for n in range(args.start, end + 1):
            print(f"Fetching chapter {n}/{end}...")
            text = fetch_chapter_with_retries(novel_code, n)
            if text is None:
                print(f"  chapter {n}: giving up after {MAX_RETRIES} attempts, skipping")
                continue
            f.write(f"===== 第 {n} 話 =====\n\n")
            f.write(text)
            f.write("\n\n")
            time.sleep(DELAY_SECONDS)

    print(f"Done. Saved to {output_path}")


if __name__ == "__main__":
    main()
