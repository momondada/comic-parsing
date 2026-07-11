import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, model_validator

from ..jobs.pipeline import run as run_job
from ..jobs.pipeline import run_batch
from ..storage import tables

router = APIRouter()

MAX_BATCH_SIZE = 300


class BatchRange(BaseModel):
    start: int
    end: int

    @model_validator(mode="after")
    def _validate_range(self):
        if self.start < 1 or self.end < 1:
            raise ValueError("chapter numbers must be positive")
        if self.end < self.start:
            raise ValueError("end must be >= start")
        if self.end - self.start + 1 > MAX_BATCH_SIZE:
            raise ValueError(f"range too large (max {MAX_BATCH_SIZE} chapters per batch)")
        return self


@router.post("/api/comics/{comic}/batch")
def submit_batch(comic: str, payload: BatchRange, background_tasks: BackgroundTasks):
    if not tables.list_chapters(comic):
        raise HTTPException(status_code=404, detail="comic not found")

    batch_id = str(uuid.uuid4())
    tables.create_batch(batch_id, comic, payload.start, payload.end)
    background_tasks.add_task(run_batch, batch_id, comic, payload.start, payload.end)
    return {"batch_id": batch_id}


@router.get("/api/batches/{batch_id}")
def batch_status(batch_id: str):
    batch = tables.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return {
        "status": batch["status"],
        "total": batch.get("total", 0),
        "done": batch.get("done", 0),
        "skipped": batch.get("skipped", 0),
        "failed": batch.get("failed", 0),
        "current_chapter": batch.get("current_chapter", ""),
        "error": batch.get("error", ""),
    }


@router.post("/api/chapters/{comic}/{chapter_row_key}/rescrape")
def rescrape_chapter(comic: str, chapter_row_key: str, background_tasks: BackgroundTasks):
    chapter = tables.get_chapter(comic, chapter_row_key)
    if chapter is None:
        raise HTTPException(status_code=404, detail="chapter not found")

    job_id = str(uuid.uuid4())
    tables.create_job(job_id, chapter["source_url"])
    background_tasks.add_task(run_job, job_id, chapter["source_url"])
    return {"job_id": job_id}
