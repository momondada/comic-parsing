from fastapi import APIRouter, HTTPException, Request

from ..rendering import templates
from ..storage import blob, tables

router = APIRouter()


@router.get("/library")
def library(request: Request):
    comics = tables.list_comics()
    return templates.TemplateResponse(request, "library.html", {"comics": comics})


@router.get("/library/{comic}")
def chapters(request: Request, comic: str):
    chapter_rows = tables.list_chapters(comic)
    if not chapter_rows:
        raise HTTPException(status_code=404, detail="comic not found")
    return templates.TemplateResponse(
        request, "chapters.html", {"comic": comic, "chapters": chapter_rows}
    )


@router.get("/reader/{comic}/{chapter_row_key}")
def reader(request: Request, comic: str, chapter_row_key: str):
    entity = tables.get_chapter(comic, chapter_row_key)
    if entity is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    filenames = blob.list_page_filenames(comic, chapter_row_key)
    return templates.TemplateResponse(
        request,
        "reader.html",
        {
            "comic": comic,
            "chapter_row_key": chapter_row_key,
            "chapter_display": entity.get("chapter_display", ""),
            "filenames": filenames,
        },
    )
