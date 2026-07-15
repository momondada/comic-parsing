import re

# Matches this project's own download_novel.py script's delimiter format:
# "===== {label} =====" on its own line, e.g. "===== 第 1 話 =====".
CHAPTER_MARKER = re.compile(r"^===== (.+?) =====$", re.MULTILINE)

CHAPTER_NUMBER = re.compile(r"(\d+(?:\.\d+)?)")
SLUG_CLEANUP = re.compile(r"[^a-z0-9]+")


def chapter_number(label: str, fallback_index: int) -> float:
    """Pull the chapter number out of a label like "第 148 話" so chapters
    from a later upload of the same novel sort/append correctly after
    earlier ones — falls back to upload order if the label has no number.
    """
    match = CHAPTER_NUMBER.search(label)
    return float(match.group(1)) if match else float(fallback_index)


def slugify_filename(filename: str) -> str:
    """Derive a stable novel identifier from the uploaded filename (e.g.
    "n1662ds.txt" -> "n1662ds") so re-uploading the same novel later
    reuses the same library entry instead of creating a new one.
    """
    stem = filename.rsplit(".", 1)[0].lower()
    slug = SLUG_CLEANUP.sub("-", stem).strip("-")
    return slug or "novel"


def split_chapters(text: str) -> list[tuple[str, str]]:
    """Split an uploaded novel txt into (label, body) pairs. Falls back to
    treating the whole file as one chunk if no markers are found.
    """
    matches = list(CHAPTER_MARKER.finditer(text))
    if not matches:
        stripped = text.strip()
        return [("內容", stripped)] if stripped else []

    chapters = []
    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chapters.append((label, body))
    return chapters


def join_chapters(chapters: list[tuple[str, str]]) -> str:
    """Inverse of split_chapters, preserving the same delimiter format."""
    parts = [f"===== {label} =====\n\n{body}\n" for label, body in chapters]
    return "\n".join(parts)
