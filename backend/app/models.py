from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    dashboard_data = Column(JSONB, nullable=False)
    source_filename = Column(String(255))
    ticker_count = Column(Integer)
    date_count = Column(Integer)
    industry_count = Column(Integer)


class Index(Base):
    __tablename__ = "indices"

    id = Column(Integer, primary_key=True, index=True)
    bbg_ticker = Column(String(100), unique=True, nullable=False)
    short_name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IndexMembership(Base):
    __tablename__ = "index_memberships"
    __table_args__ = (
        UniqueConstraint(
            "index_id", "ticker", "as_of_date", name="uq_index_ticker_date"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    index_id = Column(Integer, ForeignKey("indices.id"), nullable=False, index=True)
    ticker = Column(String(100), nullable=False, index=True)
    bbg_ticker = Column(String(100), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    weight = Column(Float, nullable=True)


class TickerDescription(Base):
    __tablename__ = "ticker_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(100), unique=True, nullable=False, index=True)
    bbg_ticker = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    source_field = Column(String(100), nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    embedded_at = Column(DateTime(timezone=True), nullable=True)
