from app.translation.novel_text import join_chapters, split_chapters


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


def test_join_chapters_round_trips_with_split():
    chapters = [("第 1 話", "內容一。"), ("第 2 話", "內容二。")]
    joined = join_chapters(chapters)
    assert split_chapters(joined) == chapters
