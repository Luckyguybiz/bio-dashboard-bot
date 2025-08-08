from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_user_id: Mapped[int | None] = mapped_column(ForeignKey("tg_users.id"))
    niche: Mapped[str | None] = mapped_column(String)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id"))

    user = relationship("TgUser", back_populates="watchlists")
    channel = relationship("Channel", back_populates="watchlists")
