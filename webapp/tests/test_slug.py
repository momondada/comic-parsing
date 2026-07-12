from app.scraping.slug import chapter_row_key, derive_url_template, format_chapter, parse_comic_slug


def test_mgeko_style_with_trailing_suffix():
    ref = parse_comic_slug(
        "https://www.mgeko.cc/reader/en/delusional-hunter-in-another-world-chapter-84-eng-li/"
    )
    assert ref.comic == "delusional-hunter-in-another-world"
    assert ref.chapter == 84.0
    assert ref.confidence == "high"


def test_decimal_chapter():
    ref = parse_comic_slug("https://example.com/reader/some-comic-chapter-84.5/")
    assert ref.comic == "some-comic"
    assert ref.chapter == 84.5
    assert ref.confidence == "high"


def test_comic_title_containing_digits():
    ref = parse_comic_slug("https://example.com/solo-leveling-2-chapter-10/")
    assert ref.comic == "solo-leveling-2"
    assert ref.chapter == 10.0


def test_chapter_as_separate_segment():
    ref = parse_comic_slug(
        "https://comix.to/title/w0rv8-illusion-hunter-from-another-world/chapter-97"
    )
    assert ref.comic == "w0rv8-illusion-hunter-from-another-world"
    assert ref.chapter == 97.0
    assert ref.confidence == "medium"


def test_chapter_and_number_as_adjacent_segments():
    ref = parse_comic_slug(
        "https://asurascans.com/comics/helmut-the-forsaken-child-a80d257e/chapter/122"
    )
    assert ref.comic == "helmut-the-forsaken-child-a80d257e"
    assert ref.chapter == 122.0
    assert ref.confidence == "medium"


def test_derive_url_template_adjacent_segment_style():
    url = "https://asurascans.com/comics/helmut-the-forsaken-child-a80d257e/chapter/122"
    template = derive_url_template(url)
    assert template == (
        "https://asurascans.com/comics/helmut-the-forsaken-child-a80d257e/chapter/{chapter}"
    )
    assert template.replace("{chapter}", "133") == (
        "https://asurascans.com/comics/helmut-the-forsaken-child-a80d257e/chapter/133"
    )


def test_unparseable_falls_back_to_domain():
    ref = parse_comic_slug("https://example.com/some/random/page")
    assert ref.comic == "unparsed-example-com"
    assert ref.chapter is None
    assert ref.confidence == "none"


def test_chapter_row_key_fixed_width_and_sortable():
    a = parse_comic_slug("https://example.com/foo-chapter-9/")
    b = parse_comic_slug("https://example.com/foo-chapter-10/")
    c = parse_comic_slug("https://example.com/foo-chapter-9.5/")
    assert a.chapter_row_key == "000090"
    assert c.chapter_row_key == "000095"
    assert b.chapter_row_key == "000100"
    assert sorted([b.chapter_row_key, c.chapter_row_key, a.chapter_row_key]) == [
        a.chapter_row_key,
        c.chapter_row_key,
        b.chapter_row_key,
    ]


def test_derive_url_template_mgeko_style():
    url = "https://www.mgeko.cc/reader/en/delusional-hunter-in-another-world-chapter-84-eng-li/"
    template = derive_url_template(url)
    assert template == (
        "https://www.mgeko.cc/reader/en/"
        "delusional-hunter-in-another-world-chapter-{chapter}-eng-li/"
    )
    assert template.replace("{chapter}", "50") == (
        "https://www.mgeko.cc/reader/en/delusional-hunter-in-another-world-chapter-50-eng-li/"
    )


def test_derive_url_template_no_chapter_returns_none():
    assert derive_url_template("https://example.com/some/random/page") is None


def test_chapter_row_key_helper_matches_comicref_property():
    ref = parse_comic_slug("https://example.com/foo-chapter-9.5/")
    assert chapter_row_key(ref.chapter) == ref.chapter_row_key == "000095"
    assert chapter_row_key(None) == "000000"


def test_format_chapter_integer_vs_decimal():
    assert format_chapter(50) == "50"
    assert format_chapter(84.5) == "84.5"
