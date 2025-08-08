from datetime import datetime

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class MyVideo(Base):
    __tablename__ = "my_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    published_at: Mapped[datetime | None] = mapped_column()
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    retention_30s: Mapped[float | None] = mapped_column(Float)
    retention_60s: Mapped[float | None] = mapped_column(Float)
    v30: Mapped[float | None] = mapped_column(Float)
    v60: Mapped[float | None] = mapped_column(Float)
    v180: Mapped[float | None] = mapped_column(Float)
    v24: Mapped[float | None] = mapped_column(Float)
