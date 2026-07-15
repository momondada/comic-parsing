from app.scraping.novel import (
    extract_novel_text,
    is_japanese,
    parse_novel_url,
    parse_toc_latest,
)
from app.translation.novel_pdf import build_pdf


def test_parse_novel_url_with_trailing_slash():
    ref = parse_novel_url("https://ncode.syosetu.com/n1662ds/1/")
    assert ref.novel_code == "n1662ds"
    assert ref.chapter == 1


def test_parse_novel_url_without_trailing_slash():
    ref = parse_novel_url("https://ncode.syosetu.com/n1662ds/148")
    assert ref.novel_code == "n1662ds"
    assert ref.chapter == 148


def test_parse_novel_url_unrelated_url_returns_none():
    assert parse_novel_url("https://example.com/some/random/page") is None


def test_extract_novel_text_single_line_strips_nested_font_tags():
    html = (
        '<div class="js-novel-text p-novel__text">'
        '<p id="L1"><font dir="auto" style="vertical-align: inherit;">'
        '<font dir="auto" style="vertical-align: inherit;">'
        "但這卻是一個很常見的故事。"
        "</font></font></p>"
        "</div>"
    )
    assert extract_novel_text(html) == "但這卻是一個很常見的故事。"


def test_extract_novel_text_joins_multiple_paragraphs_with_newline():
    html = (
        '<div class="js-novel-text p-novel__text">'
        '<p id="L1">第一行。</p>'
        '<p id="L2">第二行。</p>'
        '<p id="L3">第三行。</p>'
        "</div>"
    )
    assert extract_novel_text(html) == "第一行。\n第二行。\n第三行。"


def test_extract_novel_text_ignores_content_outside_target_div():
    html = (
        "<div><p>不需要的頁首文字</p></div>"
        '<div class="js-novel-text p-novel__text"><p id="L1">正文內容。</p></div>'
        "<div><p>不需要的頁尾文字</p></div>"
    )
    assert extract_novel_text(html) == "正文內容。"


def test_extract_novel_text_no_target_div_returns_empty_string():
    assert extract_novel_text("<div><p>no novel text here</p></div>") == ""


def test_is_japanese_detects_hiragana():
    assert is_japanese("これは普通の物語だった。") is True


def test_is_japanese_false_for_pure_chinese_text():
    assert is_japanese("這是一個很常見的故事。") is False


def test_parse_toc_latest_finds_max_chapter():
    html = """
    <a href="/n1662ds/1/">第1話</a>
    <a href="/n1662ds/148/">第148話</a>
    <a href="/n1662ds/50/">第50話</a>
    """
    assert parse_toc_latest(html, "n1662ds") == 148


def test_parse_toc_latest_no_matches_returns_none():
    assert parse_toc_latest("<p>nothing here</p>", "n1662ds") is None


def test_build_pdf_returns_valid_pdf_bytes():
    pdf_bytes = build_pdf(
        "測試小說",
        [("1", "第一段文字。\n第二段文字。"), ("2", "第二話的內容。")],
    )
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 0
