import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, Response, UploadFile

from ..jobs.novel_translate_pipeline import run_novel_translation
from ..rendering import templates
from ..storage import blob, tables
from ..translation.novel_text import slugify_filename, split_chapters

router = APIRouter()


@router.get("/novel-translate")
def novel_translate_page(request: Request):
    return templates.TemplateResponse(request, "novel_translate.html", {})


@router.post("/api/novel-translate")
async def submit_novel_translation(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="請上傳 .txt 檔案")

    raw = await file.read()
    text = raw.decode("utf-8", errors="replace")

    chapters = split_chapters(text)
    if not chapters:
        raise HTTPException(status_code=400, detail="檔案內容是空的")

    novel_slug = slugify_filename(file.filename)
    batch_id = str(uuid.uuid4())
    tables.create_batch(batch_id, novel_slug, 1, len(chapters))
    background_tasks.add_task(run_novel_translation, batch_id, novel_slug, chapters)
    return {"batch_id": batch_id, "novel": novel_slug}


@router.get("/media/novels/{novel}/download")
def download_novel_combined(novel: str):
    data = blob.download_novel_combined(novel)
    if data is None:
        raise HTTPException(status_code=404, detail="沒有已翻譯完成的章節")
    return Response(
        content=data,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{novel}_translated.txt"'},
    )
