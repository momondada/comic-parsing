from app.scraping.latest_chapter import parse_asurascans_latest, parse_mgeko_latest


def test_parse_asurascans_latest_finds_max_chapter():
    html = """
    <a href="/comics/helmut-the-forsaken-child-a80d257e/chapter/1" data-astro-prefetch="hover" class="group flex items-center justify-between px-4 py-4 transition-colors hover:bg-white/5">Chapter 1</a>
    <a href="/comics/helmut-the-forsaken-child-a80d257e/chapter/133" data-astro-prefetch="hover" class="group flex items-center justify-between px-4 py-4 transition-colors hover:bg-white/5">Chapter 133</a>
    <a href="/comics/helmut-the-forsaken-child-a80d257e/chapter/50" data-astro-prefetch="hover" class="group flex items-center justify-between px-4 py-4 transition-colors hover:bg-white/5">Chapter 50</a>
    """
    assert parse_asurascans_latest(html, "/comics/helmut-the-forsaken-child-a80d257e") == 133.0


def test_parse_asurascans_latest_ignores_other_series_links():
    html = """
    <a href="/comics/helmut-the-forsaken-child-a80d257e/chapter/10">Chapter 10</a>
    <a href="/comics/some-other-series/chapter/999">Chapter 999</a>
    """
    assert parse_asurascans_latest(html, "/comics/helmut-the-forsaken-child-a80d257e") == 10.0


def test_parse_asurascans_latest_no_matches_returns_none():
    assert parse_asurascans_latest("<p>nothing here</p>", "/comics/some-series") is None


def test_parse_mgeko_latest_finds_max_chapter():
    html = """
    <select>
    <option value="/reader/en/manga-q1113-chapter-405-eng-li/">Chapter: 405-eng-li</option>
    <option value="/reader/en/manga-q1113-chapter-408-eng-li/">Chapter: 408-eng-li</option>
    <option value="/reader/en/manga-q1113-chapter-406-eng-li/">Chapter: 406-eng-li</option>
    </select>
    """
    assert parse_mgeko_latest(html, "manga-q1113") == 408.0


def test_parse_mgeko_latest_no_matches_returns_none():
    assert parse_mgeko_latest("<select></select>", "manga-q1113") is None
