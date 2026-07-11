import re

from fastapi import APIRouter, HTTPException, Response

from ..storage import blob

router = APIRouter()

FILENAME_PATTERN = re.compile(r"^\d{3}\.jpg$")


@router.get("/media/{comic}/{chapter_row_key}/{filename}")
def media(comic: str, chapter_row_key: str, filename: str):
    if not FILENAME_PATTERN.match(filename):
        raise HTTPException(status_code=400, detail="invalid filename")
    try:
        data = blob.download_page(comic, chapter_row_key, filename)
    except Exception:
        raise HTTPException(status_code=404, detail="page not found")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
