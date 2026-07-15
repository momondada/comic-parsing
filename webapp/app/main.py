from pathlib import Path

import openai
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import batches, jobs, library, media, novel_translate, submit, translations
from .storage import blob, tables

print(f"[diagnostic] openai package version: {openai.__version__}", flush=True)

app = FastAPI(title="Comic Reader")

app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static"
)

app.include_router(submit.router)
app.include_router(jobs.router)
app.include_router(library.router)
app.include_router(media.router)
app.include_router(batches.router)
app.include_router(translations.router)
app.include_router(novel_translate.router)


@app.on_event("startup")
def on_startup():
    tables.ensure_tables()
    blob.ensure_container()
    tables.reconcile_stuck_jobs()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
