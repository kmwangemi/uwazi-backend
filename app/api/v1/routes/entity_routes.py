import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user_model import User
from app.schemas.entity_schema import (
    ProcuringEntityListResponse,
    ProcuringEntityResponse,
)
from app.services import entity_service

entity_router = APIRouter()

DbDependency = Annotated[AsyncSession, Depends(get_db)]


@entity_router.get("/entities", response_model=ProcuringEntityListResponse)
async def list_entities(
    db: DbDependency,
    search: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(
        None, description="MINISTRY | COUNTY | PARASTATAL | OTHER"
    ),
    county: Optional[str] = Query(None),
    is_flagged: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    return await entity_service.list_entities(
        db=db,
        search=search,
        entity_type=entity_type,
        county=county,
        is_flagged=is_flagged,
        skip=skip,
        limit=limit,
    )


@entity_router.get("/entities/{entity_id}", response_model=ProcuringEntityResponse)
async def get_entity(
    entity_id: uuid.UUID,
    db: DbDependency,
    current_user: User = Depends(get_current_user),
):
    return await entity_service.get_entity_by_id(db, entity_id)


@entity_router.get(
    "/entities/code/{entity_code}", response_model=ProcuringEntityResponse
)
async def get_entity_by_code(
    entity_code: str,
    db: DbDependency,
    current_user: User = Depends(get_current_user),
):
    return await entity_service.get_entity_by_code(db, entity_code)
