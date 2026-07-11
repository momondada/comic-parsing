from dataclasses import dataclass
from statistics import median

from .ocr import OcrLine

GAP_RATIO = 0.7
OVERLAP_RATIO = 0.3
PADDING_RATIO = 0.15


@dataclass
class Bubble:
    text_en: str
    left_pct: float
    top_pct: float
    width_pct: float
    height_pct: float


def _horizontal_overlap(a: OcrLine, b: OcrLine) -> float:
    return max(0.0, min(a.max_x, b.max_x) - max(a.min_x, b.min_x))


def _should_merge(a: OcrLine, b: OcrLine, median_h: float) -> bool:
    gap = max(a.min_y, b.min_y) - min(a.max_y, b.max_y)
    if gap > GAP_RATIO * median_h:
        return False
    overlap = _horizontal_overlap(a, b)
    narrower = min(a.max_x - a.min_x, b.max_x - b.min_x)
    if narrower <= 0:
        return False
    return overlap >= OVERLAP_RATIO * narrower


def merge_lines_into_bubbles(
    lines: list[OcrLine], image_width: int, image_height: int
) -> list[Bubble]:
    """Cluster nearby OCR lines into one bounding box per dialogue bubble.

    Heuristic, not exact: merges lines with a small vertical gap and enough
    horizontal overlap. Real speech-bubble detection would need a vision
    model; this is a cheap approximation good enough for an overlay.
    """
    if not lines:
        return []

    heights = [line.max_y - line.min_y for line in lines if line.max_y > line.min_y]
    median_h = median(heights) if heights else 1.0

    parent = list(range(len(lines)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            if _should_merge(lines[i], lines[j], median_h):
                union(i, j)

    groups: dict[int, list[OcrLine]] = {}
    order: dict[int, int] = {}
    for idx, line in enumerate(lines):
        root = find(idx)
        groups.setdefault(root, []).append(line)
        order.setdefault(root, idx)

    bubbles = []
    for root in sorted(groups, key=lambda r: order[r]):
        members = sorted(groups[root], key=lambda l: (l.min_y, l.min_x))
        min_x = min(m.min_x for m in members)
        min_y = min(m.min_y for m in members)
        max_x = max(m.max_x for m in members)
        max_y = max(m.max_y for m in members)

        pad_x = (max_x - min_x) * PADDING_RATIO
        pad_y = (max_y - min_y) * PADDING_RATIO
        min_x = max(0.0, min_x - pad_x)
        min_y = max(0.0, min_y - pad_y)
        max_x = min(float(image_width), max_x + pad_x)
        max_y = min(float(image_height), max_y + pad_y)

        text_en = "\n".join(m.text for m in members)

        bubbles.append(
            Bubble(
                text_en=text_en,
                left_pct=100 * min_x / image_width,
                top_pct=100 * min_y / image_height,
                width_pct=100 * (max_x - min_x) / image_width,
                height_pct=100 * (max_y - min_y) / image_height,
            )
        )

    return bubbles
