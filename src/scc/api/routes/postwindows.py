from fastapi import APIRouter

from ...services import postwindow_service

router = APIRouter()


@router.get("/postwindows")
def get_postwindows(niche: str | None = None):
    return {"windows": postwindow_service.get_postwindows(niche)}
