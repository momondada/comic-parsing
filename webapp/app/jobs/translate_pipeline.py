import traceback

from starlette.concurrency import run_in_threadpool

from ..storage import blob, tables
from ..translation.gpt_translate import translate_page


def _process_chapter(comic: str, chapter_row_key: str) -> dict:
    filenames = blob.list_page_filenames(comic, chapter_row_key)
    filenames = [f for f in filenames if f.endswith(".jpg")]

    pages = {}
    for filename in filenames:
        body = blob.download_page(comic, chapter_row_key, filename)
        bubbles = translate_page(body)
        pages[filename] = [
            {
                "text_zh": b.text_zh,
                "left_pct": b.left_pct,
                "top_pct": b.top_pct,
                "width_pct": b.width_pct,
                "height_pct": b.height_pct,
            }
            for b in bubbles
        ]

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
