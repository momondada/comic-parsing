import re

# Matches this project's own download_novel.py script's delimiter format:
# "===== {label} =====" on its own line, e.g. "===== 第 1 話 =====".
CHAPTER_MARKER = re.compile(r"^===== (.+?) =====$", re.MULTILINE)


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
