import asyncio
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FutureTimeoutError
from concurrent.futures.process import BrokenProcessPool
from io import BytesIO

from PIL import Image
from starlette.concurrency import run_in_threadpool

from ..storage import blob, tables
from ..translation.bubbles import merge_lines_into_bubbles
from ..translation.gpt_translate import normalize_and_translate
from ..translation.ocr import read_lines

# One specific chapter (asurascans.com, ~800x13000-15000px webp pages)
# reproducibly took down the whole App Service instance. Log Stream showed
# the real shape of it: OCR completed cleanly through page 004, then the
# instance went silent mid-request on page 005 — no exception, no crash
# traceback — until Azure's platform health check gave up on the
# unresponsive container and force-replaced it ~1s before the old one's
# own shutdown log even appeared (24s later). That's a hang, not a crash,
# and it recurred identically across every concurrency configuration
# tried (B1/B3, MAX_WORKERS 1 and 4), which pointed away from resource
# exhaustion and at a stalled network call with no client-side timeout —
# confirmed the Vision client had none configured (see translation/ocr.py,
# now fixed there). OCR still runs in a process pool as a second layer of
# defense: even an unrelated hang or crash in a worker now surfaces as a
# catchable error instead of taking the whole app down with it.
MAX_WORKERS = 4
MAX_CONCURRENT_CHAPTERS = 3
_translate_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHAPTERS)

# Backstop in case something other than the OCR SDK call itself hangs
# (its own connection/read timeouts are set in translation/ocr.py) — bounds
# total OCR time for a chapter instead of risking an indefinite hang.
PAGE_TIMEOUT_SECONDS = 60


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

    per_page_bubbles = {}
    executor = ProcessPoolExecutor(max_workers=MAX_WORKERS)
    try:
        futures = [
            executor.submit(_ocr_page, comic, chapter_row_key, filename)
            for filename in filenames
        ]
        try:
            total_timeout = PAGE_TIMEOUT_SECONDS * max(len(filenames), 1)
            for future in as_completed(futures, timeout=total_timeout):
                filename, bubbles = future.result()
                per_page_bubbles[filename] = bubbles
        except BrokenProcessPool as e:
            raise RuntimeError(
                "an OCR worker process crashed while processing this chapter's pages"
            ) from e
        except FutureTimeoutError as e:
            raise RuntimeError(
                "OCR timed out — a worker process appears to be stuck"
            ) from e
    finally:
        # wait=False + cancel_futures: don't let a stuck worker hang this
        # shutdown call too — that would just move the hang here instead
        # of fixing it.
        executor.shutdown(wait=False, cancel_futures=True)

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
