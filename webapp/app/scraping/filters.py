from io import BytesIO
from statistics import median

from PIL import Image

from .capture import CapturedImage

MIN_BYTES = 8_000
MIN_DIMENSION = 150
BYTE_SIZE_RATIO = 0.25
WIDTH_RATIO = 0.5


def _dimensions(body: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(BytesIO(body)) as img:
            return img.size
    except Exception:
        return None


def filter_noise(images: list[CapturedImage]) -> list[CapturedImage]:
    """Drop non-chapter-page jpgs (avatars, icons, etc.) without site-specific rules.

    Real chapter pages within one capture cluster tightly in size; stray small
    images (avatars, emoji, upload thumbnails) sit far below the median.
    """
    candidates = []
    for img in images:
        dims = _dimensions(img.body)
        if dims is None:
            continue
        width, height = dims
        if len(img.body) < MIN_BYTES or min(width, height) < MIN_DIMENSION:
            continue
        candidates.append((img, len(img.body), width))

    if not candidates:
        return []

    median_size = median(size for _, size, _ in candidates)
    median_width = median(width for _, _, width in candidates)

    return [
        img
        for img, size, width in candidates
        if size >= BYTE_SIZE_RATIO * median_size and width >= WIDTH_RATIO * median_width
    ]
