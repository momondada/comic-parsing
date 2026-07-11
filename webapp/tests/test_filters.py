from io import BytesIO

from PIL import Image

from app.scraping.capture import CapturedImage
from app.scraping.filters import filter_noise


def _make_jpg(width: int, height: int, quality: int = 90) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), color=(120, 130, 140)).save(
        buf, format="JPEG", quality=quality
    )
    return buf.getvalue()


def test_keeps_uniformly_sized_chapter_pages():
    images = [
        CapturedImage(url=f"https://x/{i}.jpg", time=float(i), body=_make_jpg(800, 1200))
        for i in range(5)
    ]
    survivors = filter_noise(images)
    assert len(survivors) == 5


def test_drops_small_avatar_noise_among_real_pages():
    pages = [
        CapturedImage(url=f"https://x/page{i}.jpg", time=float(i), body=_make_jpg(800, 1200))
        for i in range(10)
    ]
    avatars = [
        CapturedImage(url="https://x/avatar1.jpg", time=100.0, body=_make_jpg(64, 64)),
        CapturedImage(url="https://x/avatar2.jpg", time=101.0, body=_make_jpg(48, 48)),
    ]
    survivors = filter_noise(pages + avatars)
    survivor_urls = {img.url for img in survivors}
    assert len(survivors) == 10
    assert "https://x/avatar1.jpg" not in survivor_urls
    assert "https://x/avatar2.jpg" not in survivor_urls


def test_drops_non_image_bodies():
    images = [
        CapturedImage(url="https://x/real.jpg", time=0.0, body=_make_jpg(800, 1200)),
        CapturedImage(url="https://x/broken.jpg", time=1.0, body=b"not-a-jpg"),
    ]
    survivors = filter_noise(images)
    assert [img.url for img in survivors] == ["https://x/real.jpg"]


def test_empty_input_returns_empty():
    assert filter_noise([]) == []
