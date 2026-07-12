import asyncio
import uuid

from starlette.concurrency import run_in_threadpool

from ..scraping.capture import capture_images
from ..scraping.filters import filter_noise
from ..scraping.slug import chapter_row_key, derive_url_template, format_chapter, parse_comic_slug
from ..storage import blob, tables
from .translate_pipeline import run_translate

# Serializes scrape jobs so at most one headless Chromium instance runs at a
# time (a B1 plan's ~1.75GB RAM can't safely run two concurrently).
_job_semaphore = asyncio.Semaphore(1)


async def run(job_id: str, url: str) -> None:
    ref = parse_comic_slug(url)
    # tables.* calls are blocking network I/O (Azure Table Storage) and
    # filter_noise decodes every captured image (CPU-bound) — both must go
    # through run_in_threadpool inside this async function, otherwise they
    # block the single asyncio event loop for the whole app, not just this
    # job, freezing every other request until the call returns.
    await run_in_threadpool(
        tables.update_job,
        job_id,
        status="running",
        comic=ref.comic,
        chapter=ref.chapter_display,
        chapter_row_key=ref.chapter_row_key,
    )

    try:
        async with _job_semaphore:
            images = await run_in_threadpool(capture_images, url)
            filtered = await run_in_threadpool(filter_noise, images)

            if not filtered:
                await run_in_threadpool(
                    tables.update_job,
                    job_id,
                    status="failed",
                    error="no chapter images found on this page",
                )
                return

            page_count = await run_in_threadpool(
                blob.upload_chapter_images, ref.comic, ref.chapter_row_key, filtered
            )
            await run_in_threadpool(
                tables.upsert_chapter,
                comic=ref.comic,
                chapter_row_key=ref.chapter_row_key,
                chapter_display=ref.chapter_display,
                page_count=page_count,
                source_url=url,
            )
            if ref.confidence in ("high", "medium"):
                template = derive_url_template(url)
                if template:
                    await run_in_threadpool(tables.upsert_comic_template, ref.comic, template)
            await run_in_threadpool(
                tables.update_job,
                job_id,
                status="done",
                comic=ref.comic,
                chapter=ref.chapter_display,
                chapter_row_key=ref.chapter_row_key,
                page_count=page_count,
            )

        # Fire-and-forget: translation runs independently of the scrape job
        # and shouldn't make the caller wait for it. run_translate has its
        # own concurrency cap, so this is safe to kick off unconditionally
        # even from a batch download looping over many chapters.
        translate_job_id = str(uuid.uuid4())
        await run_in_threadpool(tables.create_job, translate_job_id, "")
        asyncio.create_task(run_translate(translate_job_id, ref.comic, ref.chapter_row_key))
    except Exception as e:
        await run_in_threadpool(tables.update_job, job_id, status="failed", error=str(e))


async def run_batch(batch_id: str, comic: str, start: int, end: int) -> None:
    template = await run_in_threadpool(tables.get_comic_template, comic)
    if not template:
        await run_in_threadpool(
            tables.update_batch,
            batch_id,
            status="failed",
            error="no known URL pattern for this comic yet — download at least one chapter manually first",
        )
        return

    await run_in_threadpool(tables.update_batch, batch_id, status="running")

    for n in range(start, end + 1):
        row_key = chapter_row_key(n)
        await run_in_threadpool(tables.update_batch, batch_id, current_chapter=str(n))

        if await run_in_threadpool(tables.get_chapter, comic, row_key):
            await run_in_threadpool(tables.increment_batch, batch_id, skipped=1)
            continue

        url = template.replace("{chapter}", format_chapter(n))
        job_id = str(uuid.uuid4())
        await run_in_threadpool(tables.create_job, job_id, url)
        await run(job_id, url)

        job = await run_in_threadpool(tables.get_job, job_id)
        if job and job["status"] == "done":
            await run_in_threadpool(tables.increment_batch, batch_id, done=1)
        else:
            await run_in_threadpool(tables.increment_batch, batch_id, failed=1)

    await run_in_threadpool(tables.update_batch, batch_id, status="done", current_chapter="")
