import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..jobs.pipeline import run as run_job
from ..storage import tables

router = APIRouter(prefix="/api/jobs")


class SubmitUrl(BaseModel):
    url: str


@router.post("")
def submit_job(payload: SubmitUrl, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    tables.create_job(job_id, payload.url)
    background_tasks.add_task(run_job, job_id, payload.url)
    return {"job_id": job_id}


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
