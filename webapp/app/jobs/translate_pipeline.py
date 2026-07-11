from io import BytesIO

from PIL import Image
from starlette.concurrency import run_in_threadpool

from ..storage import blob, tables
from ..translation.bubbles import merge_lines_into_bubbles
from ..translation.ocr import read_lines
from ..translation.translate_client import translate_texts


def _process_chapter(comic: str, chapter_row_key: str) -> dict:
    filenames = blob.list_page_filenames(comic, chapter_row_key)
    filenames = [f for f in filenames if f.endswith(".jpg")]

    per_page_bubbles = {}
    for filename in filenames:
        body = blob.download_page(comic, chapter_row_key, filename)
        with Image.open(BytesIO(body)) as img:
            width, height = img.size
        lines = read_lines(body)
        bubbles = merge_lines_into_bubbles(lines, width, height)
        per_page_bubbles[filename] = bubbles

    all_texts = [
        bubble.text_en for bubbles in per_page_bubbles.values() for bubble in bubbles
    ]
    translations = translate_texts(all_texts)

    pages = {}
    idx = 0
    for filename, bubbles in per_page_bubbles.items():
        page_entries = []
        for bubble in bubbles:
            page_entries.append(
                {
                    "text_zh": translations[idx],
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
    tables.update_job(job_id, status="running", comic=comic, chapter_row_key=chapter_row_key)

    try:
        data = await run_in_threadpool(_process_chapter, comic, chapter_row_key)
        await run_in_threadpool(blob.upload_chapter_translations, comic, chapter_row_key, data)
        tables.mark_chapter_translated(comic, chapter_row_key)
        tables.update_job(job_id, status="done")
    except Exception as e:
        tables.update_job(job_id, status="failed", error=str(e))
