import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

from .static_html import fetch_text

NOVEL_DOMAIN = "syosetu.com"

CHAPTER_PATH = re.compile(r"^/([^/]+)/(\d+)/?$")

HIRAGANA = range(0x3040, 0x30A0)
KATAKANA = range(0x30A0, 0x3100)


@dataclass
class NovelRef:
    novel_code: str
    chapter: int


def parse_novel_url(url: str) -> NovelRef | None:
    """https://ncode.syosetu.com/{code}/{n}/ (trailing slash optional) ->
    NovelRef(code, n). Returns None if the URL isn't shaped like a syosetu
    chapter URL.
    """
    path = urlparse(url).path
    match = CHAPTER_PATH.match(path)
    if not match:
        return None
    return NovelRef(novel_code=match.group(1), chapter=int(match.group(2)))


class _NovelTextParser(HTMLParser):
    """Extracts the chapter body from syosetu's
    <div class="js-novel-text p-novel__text">...</div>, one line per <p>
    element, ignoring nested formatting tags (<font> etc.) and their
    attributes entirely — just the text content.
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


def is_japanese(text: str) -> bool:
    """Cheap heuristic: real Japanese prose almost always uses hiragana for
    particles/conjugation even in kanji-heavy text, so its presence is a
    reliable "needs translation" signal without a language-ID dependency.
    """
    return any(ord(ch) in HIRAGANA or ord(ch) in KATAKANA for ch in text)


def parse_toc_latest(html: str, novel_code: str) -> int | None:
    """The table-of-contents page lists every chapter as a link back to
    itself; scoping the pattern to this exact novel_code avoids picking up
    unrelated links elsewhere on the page.
    """
    pattern = re.compile(r'href="/' + re.escape(novel_code) + r'/(\d+)/?"')
    numbers = [int(n) for n in pattern.findall(html)]
    return max(numbers) if numbers else None


def find_latest_chapter(novel_code: str) -> int | None:
    """Fetch the novel's table-of-contents page and find the highest
    chapter number listed there. Returns None if nothing was found.
    """
    toc_url = f"https://ncode.syosetu.com/{novel_code}/"
    return parse_toc_latest(fetch_text(toc_url), novel_code)


def chapter_url(novel_code: str, chapter: int) -> str:
    return f"https://ncode.syosetu.com/{novel_code}/{chapter}/"
