from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import batches, jobs, library, media, submit
from .storage import blob, tables

app = FastAPI(title="Comic Reader")

app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static"
)

app.include_router(submit.router)
app.include_router(jobs.router)
app.include_router(library.router)
app.include_router(media.router)
app.include_router(batches.router)


@app.on_event("startup")
def on_startup():
    tables.ensure_tables()
    blob.ensure_container()
    tables.reconcile_stuck_jobs()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
