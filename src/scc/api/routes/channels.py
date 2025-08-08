from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.db import get_session
from ...models import Channel
from ...schemas import ChannelCreate, ChannelRead

router = APIRouter()


def _extract_channel_id(data: ChannelCreate) -> str:
    if data.channel_id:
        return data.channel_id
    if data.url:
        return data.url.rstrip("/").split("/")[-1]
    raise HTTPException(status_code=400, detail="channel_id or url required")


@router.post("/channels", response_model=ChannelRead)
def add_channel(
    payload: ChannelCreate, db: Session = Depends(get_session)
):  # noqa: B008
    channel_id = _extract_channel_id(payload)
    channel = Channel(channel_id=channel_id, niche=payload.niche, url=payload.url)
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/channels", response_model=list[ChannelRead])
def list_channels(db: Session = Depends(get_session)):  # noqa: B008
    return db.query(Channel).all()
