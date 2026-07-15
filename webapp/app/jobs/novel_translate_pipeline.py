from starlette.concurrency import run_in_threadpool

from ..scraping.slug import chapter_row_key
from ..storage import blob, tables
from ..translation.novel_text import chapter_number, join_chapters
from ..translation.novel_translate import translate_chapter


async def run_novel_translation(
    batch_id: str, novel_slug: str, chapters: list[tuple[str, str]]
) -> None:
    # Every blocking call (Table Storage, blob storage, GPT translation)
    # must go through run_in_threadpool — this is an async function, so an
    # un-wrapped blocking call would freeze the whole app's single event
    # loop, not just this job.
    await run_in_threadpool(tables.set_work_kind, novel_slug, "novel")
    await run_in_threadpool(tables.update_batch, batch_id, status="running")

    translated: list[tuple[str, str]] = []
    for idx, (label, body) in enumerate(chapters, start=1):
        await run_in_threadpool(tables.update_batch, batch_id, current_chapter=label)

        try:
            translated_body = await run_in_threadpool(translate_chapter, body)
            await run_in_threadpool(tables.increment_batch, batch_id, done=1)
        except Exception:
            # Keep the original text for this chapter rather than dropping
            # it, so the failure is visible in the output instead of just
            # silently missing.
            translated_body = body
            await run_in_threadpool(tables.increment_batch, batch_id, failed=1)

        translated.append((label, translated_body))

        # Store this chapter into the library immediately — as it becomes
        # available, not only once the whole batch finishes — so the user
        # can start reading while the rest is still translating.
        row_key = chapter_row_key(chapter_number(label, idx))
        await run_in_threadpool(
            blob.upload_novel_chapter, novel_slug, row_key, label, translated_body
        )
        await run_in_threadpool(
            tables.upsert_chapter,
            comic=novel_slug,
            chapter_row_key=row_key,
            chapter_display=label,
            page_count=1,
            source_url="",
        )

    combined_text = join_chapters(translated)
    await run_in_threadpool(blob.upload_novel_combined, novel_slug, combined_text)
    await run_in_threadpool(tables.update_batch, batch_id, status="done", current_chapter="")
