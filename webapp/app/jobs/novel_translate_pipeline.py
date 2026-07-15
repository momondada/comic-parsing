from starlette.concurrency import run_in_threadpool

from ..storage import blob, tables
from ..translation.novel_text import join_chapters
from ..translation.novel_translate import translate_chapter


async def run_novel_translation(batch_id: str, chapters: list[tuple[str, str]]) -> None:
    # Every blocking call (Table Storage, blob storage, GPT translation)
    # must go through run_in_threadpool — this is an async function, so an
    # un-wrapped blocking call would freeze the whole app's single event
    # loop, not just this job.
    await run_in_threadpool(tables.update_batch, batch_id, status="running")

    translated: list[tuple[str, str]] = []
    for label, body in chapters:
        await run_in_threadpool(tables.update_batch, batch_id, current_chapter=label)
        try:
            translated_body = await run_in_threadpool(translate_chapter, body)
            translated.append((label, translated_body))
            await run_in_threadpool(tables.increment_batch, batch_id, done=1)
        except Exception:
            # Keep the original text for this chapter rather than dropping
            # it, so the failure is visible in the output instead of just
            # silently missing.
            translated.append((label, body))
            await run_in_threadpool(tables.increment_batch, batch_id, failed=1)

    result_text = join_chapters(translated)
    await run_in_threadpool(blob.upload_novel_translation_result, batch_id, result_text)
    await run_in_threadpool(tables.update_batch, batch_id, status="done", current_chapter="")
