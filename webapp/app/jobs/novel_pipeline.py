import uuid

from starlette.concurrency import run_in_threadpool

from ..scraping.novel import (
    chapter_url,
    extract_novel_text,
    find_latest_chapter,
    is_japanese,
    parse_novel_url,
)
from ..scraping.slug import chapter_row_key, format_chapter
from ..scraping.static_html import fetch_text
from ..storage import blob, tables
from ..translation.novel_pdf import build_pdf
from ..translation.novel_translate import translate_chapter

# A first-time submission could in principle walk hundreds of chapters
# (some web novels are very long), each costing a GPT call — cap a single
# submission the same way comic batch downloads already are (batches.py).
MAX_BATCH_SIZE = 300


def prepare_novel_batch(url: str) -> tuple[str, str, int, int] | None:
    """Parse a syosetu chapter URL and figure out the [start, end] chapter
    range to fetch — from wherever this novel already has through the
    site's current latest chapter, capped at MAX_BATCH_SIZE — then create
    the batch tracking row. Returns (batch_id, novel_code, start, end), or
    None if the URL isn't a syosetu chapter URL or there's nothing new.
    """
    ref = parse_novel_url(url)
    if ref is None:
        return None

    existing = tables.list_chapters(ref.novel_code)
    start = int(existing[-1]["chapter_display"]) + 1 if existing else 1

    latest = find_latest_chapter(ref.novel_code)
    if latest is None or latest < start:
        return None

    end = min(latest, start + MAX_BATCH_SIZE - 1)

    batch_id = str(uuid.uuid4())
    tables.create_batch(batch_id, ref.novel_code, start, end)
    tables.set_work_kind(ref.novel_code, "novel")
    return batch_id, ref.novel_code, start, end


def _regenerate_pdf(novel_code: str) -> None:
    display_name = tables.get_comic_display_names([novel_code])[novel_code]
    chapters = tables.list_chapters(novel_code)
    entries = []
    for row in chapters:
        data = blob.download_novel_chapter(novel_code, row["RowKey"])
        if data:
            entries.append((row["chapter_display"], data["text_zh"]))
    pdf_bytes = build_pdf(display_name, entries)
    blob.upload_novel_pdf(novel_code, pdf_bytes)


async def run_novel_batch(batch_id: str, novel_code: str, start: int, end: int) -> None:
    # Every blocking call (Table Storage, blob storage, HTTP fetch, GPT
    # translation) must go through run_in_threadpool — this is an async
    # function, so an un-wrapped blocking call would freeze the whole
    # app's single event loop, not just this batch.
    await run_in_threadpool(tables.update_batch, batch_id, status="running")

    for n in range(start, end + 1):
        row_key = chapter_row_key(n)
        await run_in_threadpool(tables.update_batch, batch_id, current_chapter=str(n))

        try:
            url = chapter_url(novel_code, n)
            page_html = await run_in_threadpool(fetch_text, url)
            text = await run_in_threadpool(extract_novel_text, page_html)

            if not text.strip():
                await run_in_threadpool(tables.increment_batch, batch_id, skipped=1)
                continue

            if await run_in_threadpool(is_japanese, text):
                text_zh = await run_in_threadpool(translate_chapter, text)
            else:
                text_zh = text

            await run_in_threadpool(blob.upload_novel_chapter, novel_code, row_key, text_zh)
            await run_in_threadpool(
                tables.upsert_chapter,
                comic=novel_code,
                chapter_row_key=row_key,
                chapter_display=format_chapter(n),
                page_count=1,
                source_url=url,
            )
            await run_in_threadpool(_regenerate_pdf, novel_code)
            await run_in_threadpool(tables.increment_batch, batch_id, done=1)
        except Exception:
            await run_in_threadpool(tables.increment_batch, batch_id, failed=1)

    await run_in_threadpool(tables.update_batch, batch_id, status="done", current_chapter="")
