import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.bid_schema import BidCreate, BidResponse, BidUpdate
from app.services import bid_service
from app.services.cloudinary_service import upload_bid_document

bid_router = APIRouter()

DbDependency = Annotated[AsyncSession, Depends(get_db)]


@bid_router.post(
    "/bids",
    response_model=BidResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_bid(
    db: DbDependency,
    data: str = Form(...),
    technical_documents: list[UploadFile] = File(default=[]),
    financial_documents: list[UploadFile] = File(default=[]),
    compliance_documents: list[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
):
    bid_data = BidCreate(**json.loads(data))

    # Generate a temp reference for folder naming before DB insert
    temp_ref = f"TEMP-{str(uuid.uuid4())[:8].upper()}"

    # Upload all documents to Cloudinary
    tech_uploaded = [
        await upload_bid_document(f, temp_ref, "technical")
        for f in technical_documents
        if f.filename
    ]
    fin_uploaded = [
        await upload_bid_document(f, temp_ref, "financial")
        for f in financial_documents
        if f.filename
    ]
    comp_uploaded = [
        await upload_bid_document(f, temp_ref, "compliance")
        for f in compliance_documents
        if f.filename
    ]

    return await bid_service.create_bid(
        db=db,
        bid_data=bid_data,
        submitted_by=current_user.id,
        technical_documents=tech_uploaded,
        financial_documents=fin_uploaded,
        compliance_documents=comp_uploaded,
    )


@bid_router.get("/bids/tender/{tender_id}", response_model=list[BidResponse])
async def list_bids_for_tender(
    tender_id: uuid.UUID,
    db: DbDependency,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
):
    return await bid_service.list_bids_for_tender(db, tender_id, skip, limit)


@bid_router.get("/bids/supplier/{supplier_id}", response_model=list[BidResponse])
async def list_bids_for_supplier(
    supplier_id: uuid.UUID,
    db: DbDependency,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
):
    return await bid_service.list_bids_for_supplier(db, supplier_id, skip, limit)


@bid_router.get("/bids/{bid_id}", response_model=BidResponse)
async def get_bid(
    bid_id: uuid.UUID,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    return await bid_service.get_bid_by_id(db, bid_id)


@bid_router.patch("/bids/{bid_id}", response_model=BidResponse)
async def update_bid(
    bid_id: uuid.UUID,
    bid_data: BidUpdate,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    return await bid_service.update_bid(db, bid_id, bid_data)


@bid_router.delete("/bids/{bid_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bid(
    bid_id: uuid.UUID,
    db: DbDependency,
    current_user=Depends(get_current_user),
):
    await bid_service.delete_bid(db, bid_id)
