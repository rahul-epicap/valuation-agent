import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["template"])

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "template")
TEMPLATE_PATH = os.path.normpath(os.path.join(TEMPLATE_DIR, "template.xlsx"))


@router.get("/template")
async def download_template():
    """Download the Excel template file."""
    if not os.path.isfile(TEMPLATE_PATH):
        raise HTTPException(status_code=404, detail="Template file not found")
    return FileResponse(
        path=TEMPLATE_PATH,
        filename="template.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
