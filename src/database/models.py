from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Mention(Base):
    """Stores ingested social/web mentions and their processed sentiment analysis."""

    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Sentiment & crisis fields (nullable prior to analysis or if processing is pending)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    severity_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Mention id={self.id} platform={self.platform!r} post_id={self.post_id!r} sentiment={self.sentiment!r}>"


class AlertLog(Base):
    """Stores records of triggered threshold or crisis alerts."""

    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    severity_level: Mapped[str] = mapped_column(String(20), nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False)
    alert_message: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<AlertLog id={self.id} severity_level={self.severity_level!r} triggered_at={self.triggered_at}>"

