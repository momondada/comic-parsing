from app.translation.novel_text import chapter_number, join_chapters, slugify_filename, split_chapters


def test_split_chapters_with_markers():
    text = (
        "===== 第 1 話 =====\n\n"
        "第一行。\n第二行。\n\n"
        "===== 第 2 話 =====\n\n"
        "第三行。\n"
    )
    chapters = split_chapters(text)
    assert chapters == [
        ("第 1 話", "第一行。\n第二行。"),
        ("第 2 話", "第三行。"),
    ]


def test_split_chapters_no_markers_falls_back_to_single_chunk():
    assert split_chapters("just plain text\nno markers here") == [
        ("內容", "just plain text\nno markers here")
    ]


def test_split_chapters_empty_text_returns_empty_list():
    assert split_chapters("") == []
    assert split_chapters("   \n  ") == []


def test_split_chapters_handles_crlf_line_endings():
    # Windows text-mode writes ("\n" -> "\r\n") previously broke every
    # marker match — confirmed live against a real 148-chapter upload,
    # which got treated as a single ~1.6MB "chapter" as a result.
    text = (
        "===== 第 1 話 =====\r\n\r\n"
        "第一行。\r\n第二行。\r\n\r\n"
        "===== 第 2 話 =====\r\n\r\n"
        "第三行。\r\n"
    )
    chapters = split_chapters(text)
    assert chapters == [
        ("第 1 話", "第一行。\n第二行。"),
        ("第 2 話", "第三行。"),
    ]


def test_join_chapters_round_trips_with_split():
    chapters = [("第 1 話", "內容一。"), ("第 2 話", "內容二。")]
    joined = join_chapters(chapters)
    assert split_chapters(joined) == chapters


def test_chapter_number_extracts_from_label():
    assert chapter_number("第 148 話", fallback_index=99) == 148.0


def test_chapter_number_falls_back_to_index_when_no_digits():
    assert chapter_number("內容", fallback_index=3) == 3.0


def test_slugify_filename_strips_extension_and_lowercases():
    assert slugify_filename("n1662ds.txt") == "n1662ds"
    assert slugify_filename("My Novel 2.TXT") == "my-novel-2"


def test_slugify_filename_empty_stem_falls_back_to_novel():
    assert slugify_filename(".txt") == "novel"
