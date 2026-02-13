from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot
from app.services.excel_parser import parse_excel

router = APIRouter(tags=["upload"])


@router.post("/upload")
async def upload_excel(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload an Excel file, parse it, and create a new snapshot."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls).",
        )

    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    # Parse the Excel file
    try:
        dashboard_data = parse_excel(content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse Excel file: {e}")

    # Generate a name if not provided
    if not name:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        name = f"{file.filename} — {timestamp}"

    # Compute summary stats
    ticker_count = len(dashboard_data.get("tickers", []))
    date_count = len(dashboard_data.get("dates", []))
    industry_count = len(set(dashboard_data.get("industries", {}).values()))

    # Create the snapshot
    snapshot = Snapshot(
        name=name,
        dashboard_data=dashboard_data,
        source_filename=file.filename,
        ticker_count=ticker_count,
        date_count=date_count,
        industry_count=industry_count,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)

    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "source_filename": snapshot.source_filename,
        "ticker_count": ticker_count,
        "date_count": date_count,
        "industry_count": industry_count,
    }
