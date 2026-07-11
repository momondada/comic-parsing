from app.translation.bubbles import merge_lines_into_bubbles
from app.translation.ocr import OcrLine


def _line(text, min_x, min_y, max_x, max_y):
    return OcrLine(text=text, min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def test_stacked_lines_merge_into_one_bubble():
    lines = [
        _line("line one", 100, 100, 300, 130),
        _line("line two", 100, 135, 300, 165),
    ]
    bubbles = merge_lines_into_bubbles(lines, image_width=1000, image_height=1000)
    assert len(bubbles) == 1
    assert bubbles[0].text_en == "line one\nline two"


def test_widely_separated_lines_stay_separate():
    lines = [
        _line("top", 100, 50, 300, 80),
        _line("bottom", 100, 800, 300, 830),
    ]
    bubbles = merge_lines_into_bubbles(lines, image_width=1000, image_height=1000)
    assert len(bubbles) == 2


def test_horizontally_disjoint_lines_stay_separate():
    lines = [
        _line("left side", 50, 100, 150, 130),
        _line("right side", 700, 100, 900, 130),
    ]
    bubbles = merge_lines_into_bubbles(lines, image_width=1000, image_height=1000)
    assert len(bubbles) == 2


def test_single_line_produces_one_bubble_with_padding():
    lines = [_line("solo", 100, 100, 300, 140)]
    bubbles = merge_lines_into_bubbles(lines, image_width=1000, image_height=1000)
    assert len(bubbles) == 1
    b = bubbles[0]
    assert b.left_pct < 100 / 10  # padded outward from original 100px left edge
    assert b.width_pct > (300 - 100) / 10  # padded wider than the raw line width


def test_empty_input_returns_empty():
    assert merge_lines_into_bubbles([], image_width=1000, image_height=1000) == []


def test_bbox_stays_within_image_bounds():
    lines = [_line("edge", 0, 0, 50, 20)]
    bubbles = merge_lines_into_bubbles(lines, image_width=1000, image_height=1000)
    assert bubbles[0].left_pct >= 0
    assert bubbles[0].top_pct >= 0
