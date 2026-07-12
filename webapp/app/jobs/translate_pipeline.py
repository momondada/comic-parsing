import asyncio
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from io import BytesIO

from PIL import Image
from starlette.concurrency import run_in_threadpool

from ..storage import blob, tables
from ..translation.bubbles import merge_lines_into_bubbles
from ..translation.gpt_translate import normalize_and_translate
from ..translation.ocr import read_lines

# One specific chapter (asurascans.com, ~800x13000-15000px webp pages)
# reproducibly crashed the whole App Service instance ("interrupted by app
# restart") — on B1 *and* B3 (4x the RAM made no difference), at both
# MAX_WORKERS=4 and fully serialized MAX_WORKERS=1, with no slowdown
# warning beforehand. A local offline repro of the image decode/crop/JPEG
# re-encode steps for all 11 pages ran cleanly, which rules out that code
# and points at something in the per-page network call (most likely the
# Vision OCR request) hitting a native-level crash rather than a plain
# Python exception or memory exhaustion.
#
# Rather than chase the exact cause further (would need real server crash
# logs), OCR now runs in a process pool instead of a thread pool: a crash
# in a worker PROCESS surfaces to the parent as a normal, catchable
# BrokenProcessPool exception instead of taking the whole app down with
# it, regardless of what's actually causing it.
MAX_WORKERS = 4
MAX_CONCURRENT_CHAPTERS = 3
_translate_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHAPTERS)


def _ocr_page(comic: str, chapter_row_key: str, filename: str):
    body = blob.download_page(comic, chapter_row_key, filename)
    with Image.open(BytesIO(body)) as img:
        width, height = img.size
    lines = read_lines(body)
    heights = [round(l.max_y - l.min_y) for l in lines]
    bubbles = merge_lines_into_bubbles(lines, width, height)
    print(
        f"[diagnostic] {filename}: {len(lines)} raw OCR lines "
        f"(heights={heights}) -> {len(bubbles)} merged bubbles",
        flush=True,
    )
    return filename, bubbles


def _process_chapter(comic: str, chapter_row_key: str) -> dict:
    filenames = blob.list_page_filenames(comic, chapter_row_key)
    filenames = [f for f in filenames if not f.endswith(".json")]

    per_page_bubbles = {}
    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(_ocr_page, comic, chapter_row_key, filename)
            for filename in filenames
        ]
        try:
            for future in as_completed(futures):
                filename, bubbles = future.result()
                per_page_bubbles[filename] = bubbles
        except BrokenProcessPool as e:
            raise RuntimeError(
                "an OCR worker process crashed while processing this chapter's pages"
            ) from e

    all_texts = [
        bubble.text_en for bubbles in per_page_bubbles.values() for bubble in bubbles
    ]
    translations = normalize_and_translate(all_texts)

    pages = {}
    idx = 0
    for filename, bubbles in per_page_bubbles.items():
        page_entries = []
        for bubble in bubbles:
            text_en, text_zh = translations[idx]
            page_entries.append(
                {
                    "text_en": text_en,
                    "text_zh": text_zh,
                    "left_pct": bubble.left_pct,
                    "top_pct": bubble.top_pct,
                    "width_pct": bubble.width_pct,
                    "height_pct": bubble.height_pct,
                }
            )
            idx += 1
        pages[filename] = page_entries

    return {"pages": pages}


async def run_translate(job_id: str, comic: str, chapter_row_key: str) -> None:
    # tables.* calls are blocking network I/O (Azure Table Storage), so each
    # one must go through run_in_threadpool — calling them directly here
    # would block the single asyncio event loop for the whole app until the
    # call returns, freezing every other request, not just this job.
    async with _translate_semaphore:
        await run_in_threadpool(
            tables.update_job,
            job_id,
            status="running",
            comic=comic,
            chapter_row_key=chapter_row_key,
        )

        try:
            data = await run_in_threadpool(_process_chapter, comic, chapter_row_key)
            await run_in_threadpool(blob.upload_chapter_translations, comic, chapter_row_key, data)
            await run_in_threadpool(tables.mark_chapter_translated, comic, chapter_row_key)
            await run_in_threadpool(tables.update_job, job_id, status="done")
        except Exception as e:
            traceback.print_exc()
            await run_in_threadpool(tables.update_job, job_id, status="failed", error=str(e))
