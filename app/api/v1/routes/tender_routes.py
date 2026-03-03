import json
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.enums_model import RiskLevel, TenderStatus
from app.schemas.tender_schema import TenderCreate, TenderResponse, TenderUpdate
from app.services import tender_service
from app.services.cloudinary_service import upload_tender_attachment

tender_router = APIRouter()

DbDependency = Annotated[AsyncSession, Depends(get_db)]


@tender_router.post(
    "/tenders",
    response_model=TenderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tender(
    db: DbDependency,
    data: str = Form(...),
    attachments: list[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
):
    tender_data = TenderCreate(**json.loads(data))
    uploaded = []
    for file in attachments:
        if file.filename:
            meta = await upload_tender_attachment(file, tender_data.tender_number)
            uploaded.append(meta)
    return await tender_service.create_tender(
        db=db,
        tender_data=tender_data,
        created_by=current_user.id,
        attachments=uploaded,
    )


@tender_router.get("/tenders", response_model=list[TenderResponse])
async def list_tenders(
    db: DbDependency,
    search: Optional[str] = Query(None),
    status: Optional[TenderStatus] = Query(None),
    risk_level: Optional[RiskLevel] = Query(None),
    county: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_flagged: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return await tender_service.list_tenders(
        db=db,
        search=search,
        status=status,
        risk_level=risk_level,
        county=county,
        category=category,
        is_flagged=is_flagged,
        skip=skip,
        limit=limit,
    )


@tender_router.get("/tenders/{tender_id}", response_model=TenderResponse)
async def get_tender(tender_id: uuid.UUID, db: DbDependency):
    return await tender_service.get_tender_by_id(db, tender_id)


@tender_router.patch("/tenders/{tender_id}", response_model=TenderResponse)
async def update_tender(
    tender_id: uuid.UUID,
    tender_data: TenderUpdate,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    return await tender_service.update_tender(db, tender_id, tender_data)


@tender_router.delete("/tenders/{tender_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tender(
    tender_id: uuid.UUID,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    await tender_service.delete_tender(db, tender_id)
