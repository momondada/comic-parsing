from fastapi import APIRouter, Request

from ..rendering import templates

router = APIRouter()


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})
