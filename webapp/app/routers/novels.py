from fastapi import APIRouter, HTTPException, Response

from ..storage import blob

router = APIRouter()


@router.get("/media/novels/{novel}/pdf")
def download_novel_pdf(novel: str):
    data = blob.download_novel_pdf(novel)
    if data is None:
        raise HTTPException(status_code=404, detail="no translated chapters yet")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{novel}.pdf"'},
    )
