from app.scraping.capture import CapturedImage, _sort_key


def test_sorts_by_numeric_filename_not_arrival_order():
    # Mirrors the real capture order we observed against mgeko.cc: responses
    # arrive scrambled relative to the page sequence 0.jpg..11.jpg.
    scrambled = [
        CapturedImage(url="https://x/2.jpg", time=1.0, body=b""),
        CapturedImage(url="https://x/8.jpg", time=2.0, body=b""),
        CapturedImage(url="https://x/0.jpg", time=3.0, body=b""),
        CapturedImage(url="https://x/1.jpg", time=4.0, body=b""),
    ]
    ordered = sorted(scrambled, key=_sort_key)
    assert [img.url for img in ordered] == [
        "https://x/0.jpg",
        "https://x/1.jpg",
        "https://x/2.jpg",
        "https://x/8.jpg",
    ]


def test_non_numeric_filenames_sort_after_numeric_ones_by_capture_time():
    images = [
        CapturedImage(url="https://x/Cutie_abc.jpg", time=1.0, body=b""),
        CapturedImage(url="https://x/1.jpg", time=5.0, body=b""),
        CapturedImage(url="https://x/0.jpg", time=4.0, body=b""),
        CapturedImage(url="https://x/IMG_2026.jpg", time=2.0, body=b""),
    ]
    ordered = sorted(images, key=_sort_key)
    assert [img.url for img in ordered] == [
        "https://x/0.jpg",
        "https://x/1.jpg",
        "https://x/Cutie_abc.jpg",
        "https://x/IMG_2026.jpg",
    ]
