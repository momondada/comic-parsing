from app.scraping.slug import parse_comic_slug


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
