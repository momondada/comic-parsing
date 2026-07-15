import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..jobs.novel_pipeline import prepare_novel_batch, run_novel_batch
from ..jobs.pipeline import run as run_job
from ..scraping.novel import NOVEL_DOMAIN
from ..storage import tables

router = APIRouter(prefix="/api/jobs")


class SubmitUrl(BaseModel):
    url: str


@router.post("")
def submit_job(payload: SubmitUrl, background_tasks: BackgroundTasks):
    domain = urlparse(payload.url).netloc.lower()

    if NOVEL_DOMAIN in domain:
        result = prepare_novel_batch(payload.url)
        if result is None:
            raise HTTPException(
                status_code=400,
                detail="couldn't parse this novel URL, or it's already up to date",
            )
        batch_id, novel_code, start, end = result
        background_tasks.add_task(run_novel_batch, batch_id, novel_code, start, end)
        return {"kind": "novel", "batch_id": batch_id, "comic": novel_code}

    job_id = str(uuid.uuid4())
    tables.create_job(job_id, payload.url)
    background_tasks.add_task(run_job, job_id, payload.url)
    return {"kind": "comic", "job_id": job_id}


@router.get("/{job_id}")
def job_status(job_id: str):
    job = tables.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "status": job["status"],
        "comic": job.get("comic", ""),
        "chapter": job.get("chapter", ""),
        "chapter_row_key": job.get("chapter_row_key", ""),
        "page_count": job.get("page_count", 0),
        "error": job.get("error", ""),
    }
