import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response

from ..jobs.translate_pipeline import run_translate
from ..storage import blob, tables

router = APIRouter()


@router.post("/api/chapters/{comic}/{chapter_row_key}/translate")
def submit_translation(comic: str, chapter_row_key: str, background_tasks: BackgroundTasks):
    if tables.get_chapter(comic, chapter_row_key) is None:
        raise HTTPException(status_code=404, detail="chapter not found")

    job_id = str(uuid.uuid4())
    tables.create_job(job_id, url="")
    background_tasks.add_task(run_translate, job_id, comic, chapter_row_key)
    return {"job_id": job_id}


@router.get("/api/chapters/{comic}/{chapter_row_key}/translations")
def get_translations(comic: str, chapter_row_key: str, response: Response):
    data = blob.download_chapter_translations(comic, chapter_row_key)
    if data is None:
        raise HTTPException(status_code=404, detail="not translated yet")
    # Chapters can be re-translated in place; without this, browsers/proxies
    # may keep serving a stale cached copy after a fresh translate run.
    response.headers["Cache-Control"] = "no-store"
    return data
