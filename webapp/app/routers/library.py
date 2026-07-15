from fastapi import APIRouter, HTTPException, Request

from ..rendering import templates
from ..storage import blob, tables

router = APIRouter()


@router.get("/library")
def library(request: Request):
    comics = tables.list_comics()
    display_names = tables.get_comic_display_names(comics)
    return templates.TemplateResponse(
        request, "library.html", {"comics": comics, "display_names": display_names}
    )


@router.get("/library/{comic}")
def chapters(request: Request, comic: str):
    chapter_rows = tables.list_chapters(comic)
    if not chapter_rows:
        raise HTTPException(status_code=404, detail="comic not found")
    display_name = tables.get_comic_display_names([comic])[comic]

    if tables.get_work_kind(comic) == "novel":
        return templates.TemplateResponse(
            request,
            "novel_chapters.html",
            {"comic": comic, "chapters": chapter_rows, "display_name": display_name},
        )

    return templates.TemplateResponse(
        request,
        "chapters.html",
        {"comic": comic, "chapters": chapter_rows, "display_name": display_name},
    )


@router.get("/reader/{comic}/{chapter_row_key}")
def reader(request: Request, comic: str, chapter_row_key: str):
    entity = tables.get_chapter(comic, chapter_row_key)
    if entity is None:
        raise HTTPException(status_code=404, detail="chapter not found")

    all_chapters = tables.list_chapters(comic)
    index = next(
        (i for i, c in enumerate(all_chapters) if c["RowKey"] == chapter_row_key), None
    )
    prev_chapter = all_chapters[index - 1] if index is not None and index > 0 else None
    next_chapter = (
        all_chapters[index + 1]
        if index is not None and index + 1 < len(all_chapters)
        else None
    )

    if tables.get_work_kind(comic) == "novel":
        data = blob.download_novel_chapter(comic, chapter_row_key)
        return templates.TemplateResponse(
            request,
            "novel_reader.html",
            {
                "comic": comic,
                "chapter_row_key": chapter_row_key,
                "chapter_display": entity.get("chapter_display", ""),
                "text_zh": data.get("text_zh", "") if data else "",
                "prev_chapter": prev_chapter,
                "next_chapter": next_chapter,
            },
        )

    filenames = blob.list_page_filenames(comic, chapter_row_key)
    return templates.TemplateResponse(
        request,
        "reader.html",
        {
            "comic": comic,
            "chapter_row_key": chapter_row_key,
            "chapter_display": entity.get("chapter_display", ""),
            "filenames": filenames,
            "prev_chapter": prev_chapter,
            "next_chapter": next_chapter,
        },
    )
