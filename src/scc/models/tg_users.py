from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


class TgUser(Base):
    __tablename__ = "tg_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    tz: Mapped[str | None] = mapped_column(String)
    brief_time: Mapped[str | None] = mapped_column(String)

    watchlists = relationship("Watchlist", back_populates="user")
