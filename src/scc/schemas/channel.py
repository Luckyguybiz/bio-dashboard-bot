from pydantic import BaseModel


class ChannelCreate(BaseModel):
    channel_id: str | None = None
    url: str | None = None
    niche: str | None = None


class ChannelRead(BaseModel):
    id: int
    channel_id: str
    niche: str | None = None

    class Config:
        orm_mode = True
