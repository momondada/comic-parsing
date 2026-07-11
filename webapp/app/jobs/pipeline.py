import asyncio

from starlette.concurrency import run_in_threadpool

from ..scraping.capture import capture_images
from ..scraping.filters import filter_noise
from ..scraping.slug import parse_comic_slug
from ..storage import blob, tables

# Serializes scrape jobs so at most one headless Chromium instance runs at a
# time (a B1 plan's ~1.75GB RAM can't safely run two concurrently).
_job_semaphore = asyncio.Semaphore(1)


async def run(job_id: str, url: str) -> None:
    ref = parse_comic_slug(url)
    tables.update_job(
        job_id,
        status="running",
        comic=ref.comic,
        chapter=ref.chapter_display,
        chapter_row_key=ref.chapter_row_key,
    )

    try:
        async with _job_semaphore:
            images = await run_in_threadpool(capture_images, url)
            filtered = filter_noise(images)

            if not filtered:
                tables.update_job(
                    job_id,
                    status="failed",
                    error="no chapter images found on this page",
                )
                return

            page_count = await run_in_threadpool(
                blob.upload_chapter_images, ref.comic, ref.chapter_row_key, filtered
            )
            tables.upsert_chapter(
                comic=ref.comic,
                chapter_row_key=ref.chapter_row_key,
                chapter_display=ref.chapter_display,
                page_count=page_count,
                source_url=url,
            )
            tables.update_job(
                job_id,
                status="done",
                comic=ref.comic,
                chapter=ref.chapter_display,
                chapter_row_key=ref.chapter_row_key,
                page_count=page_count,
            )
    except Exception as e:
        tables.update_job(job_id, status="failed", error=str(e))
