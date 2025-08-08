from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    video_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    url: Mapped[str | None] = mapped_column(String)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    is_short: Mapped[bool] = mapped_column(Boolean, default=True)
    cluster: Mapped[str | None] = mapped_column(String)
    hook_pattern: Mapped[str | None] = mapped_column(String)

    channel = relationship("Channel", back_populates="videos")
    snapshots = relationship("VideoSnapshot", back_populates="video")
    alerts = relationship("Alert", back_populates="video")
