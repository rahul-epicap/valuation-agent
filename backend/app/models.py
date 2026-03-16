import gzip

import orjson
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
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
    dashboard_data = Column(JSONB, nullable=True)  # Legacy; kept for old snapshots
    dashboard_data_compressed = Column(LargeBinary, nullable=True)  # gzip(JSON bytes)
    source_filename = Column(String(255))
    ticker_count = Column(Integer)
    date_count = Column(Integer)
    industry_count = Column(Integer)

    def get_data(self) -> dict | None:
        """Decompress and return dashboard data, preferring BYTEA over JSONB."""
        if self.dashboard_data_compressed is not None:
            return orjson.loads(gzip.decompress(self.dashboard_data_compressed))
        if self.dashboard_data is not None:
            return dict(self.dashboard_data)
        return None

    @staticmethod
    def compress(data: dict) -> bytes:
        """Compress a dashboard data dict for BYTEA storage."""
        return gzip.compress(orjson.dumps(data), compresslevel=6)

    def set_data(self, data: dict) -> None:
        """Gzip-compress and store dashboard data in BYTEA column."""
        self.dashboard_data_compressed = gzip.compress(
            orjson.dumps(data), compresslevel=1
        )
        self.dashboard_data = None


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
    isin = Column(String(20), nullable=True)
    source_field = Column(String(100), nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    embedded_at = Column(DateTime(timezone=True), nullable=True)
