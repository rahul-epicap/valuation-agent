from sqlalchemy import Column, DateTime, Integer, JSON, String, func

from app.db import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    dashboard_data = Column(JSON, nullable=False)
    source_filename = Column(String(255))
    ticker_count = Column(Integer)
    date_count = Column(Integer)
    industry_count = Column(Integer)
