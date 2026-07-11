import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from starlette.concurrency import run_in_threadpool

from ..storage import blob, tables
from ..translation.gpt_translate import translate_page

MAX_WORKERS = 4


def _process_page(comic: str, chapter_row_key: str, filename: str):
    body = blob.download_page(comic, chapter_row_key, filename)
    bubbles = translate_page(body)
    return filename, [
        {
            "text_en": b.text_en,
            "text_zh": b.text_zh,
            "left_pct": b.left_pct,
            "top_pct": b.top_pct,
            "width_pct": b.width_pct,
            "height_pct": b.height_pct,
        }
        for b in bubbles
    ]


def _process_chapter(comic: str, chapter_row_key: str) -> dict:
    filenames = blob.list_page_filenames(comic, chapter_row_key)
    filenames = [f for f in filenames if f.endswith(".jpg")]

    pages = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(_process_page, comic, chapter_row_key, filename)
            for filename in filenames
        ]
        for future in as_completed(futures):
            filename, entries = future.result()
            pages[filename] = entries

    return {"pages": pages}


async def run_translate(job_id: str, comic: str, chapter_row_key: str) -> None:
    tables.update_job(job_id, status="running", comic=comic, chapter_row_key=chapter_row_key)

    try:
        data = await run_in_threadpool(_process_chapter, comic, chapter_row_key)
        await run_in_threadpool(blob.upload_chapter_translations, comic, chapter_row_key, data)
        tables.mark_chapter_translated(comic, chapter_row_key)
        tables.update_job(job_id, status="done")
    except Exception as e:
        traceback.print_exc()
        tables.update_job(job_id, status="failed", error=str(e))
