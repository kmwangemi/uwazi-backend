import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.logger import get_logger
from app.models.entity_model import ProcuringEntity

logger = get_logger(__name__)


def _generate_entity_code(entity_name: str, entity_type: str) -> str:
    slug = re.sub(r"[^A-Z0-9]", "", entity_name.upper())[:8]
    type_slug = re.sub(r"[^A-Z0-9]", "", entity_type.upper())[:6]  # clean + uppercase
    return f"{slug}-{type_slug}"

async def get_or_create_entity(
    db: AsyncSession,
    entity_name: str,
    entity_type: str,
    county: str | None,
) -> ProcuringEntity:
    """Return existing entity by name or create a new one."""
    result = await db.execute(
        select(ProcuringEntity).filter(ProcuringEntity.name == entity_name)
    )
    entity = result.scalars().first()

    if entity:
        return entity

    entity = ProcuringEntity(
        entity_code=_generate_entity_code(entity_name, entity_type),
        name=entity_name,
        entity_type=entity_type or "OTHER",
        county=county,
    )
    db.add(entity)
    await db.flush()  # gets the ID without committing yet
    return entity


async def list_entities(
    db: AsyncSession,
    search: Optional[str] = None,
    entity_type: Optional[str] = None,
    county: Optional[str] = None,
    is_flagged: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> dict:
    """
    Return a paginated list of procuring entities with total count.
    Supports filtering by search term, entity_type, county, and flagged status.
    """
    try:
        query = select(ProcuringEntity)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                ProcuringEntity.name.ilike(term)
                | ProcuringEntity.entity_code.ilike(term)
            )
        if entity_type:
            query = query.filter(ProcuringEntity.entity_type == entity_type.upper())
        if county:
            query = query.filter(ProcuringEntity.county.ilike(f"%{county}%"))
        if is_flagged is not None:
            # Entities with any flagged tenders
            query = query.filter(
                ProcuringEntity.flagged_tenders > 0
                if is_flagged
                else ProcuringEntity.flagged_tenders == 0
            )
        # Total count for pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        # Paginated results — highest expenditure first
        query = (
            query.order_by(ProcuringEntity.total_expenditure.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        entities = result.scalars().all()
        return {"total": total, "items": entities}
    except SQLAlchemyError as e:
        logger.error("Failed to list procuring entities", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch procuring entities.",
        ) from e


async def get_entity_by_id(
    db: AsyncSession,
    entity_id: uuid.UUID,
) -> ProcuringEntity:
    """Fetch a single procuring entity by its UUID."""
    try:
        result = await db.execute(
            select(ProcuringEntity).filter(ProcuringEntity.id == entity_id)
        )
        entity = result.scalars().first()
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procuring entity with id '{entity_id}' not found.",
            )
        return entity
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            "Failed to fetch procuring entity",
            extra={"entity_id": str(entity_id), "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch procuring entity.",
        ) from e


async def get_entity_by_code(
    db: AsyncSession,
    entity_code: str,
) -> ProcuringEntity:
    """Fetch a single procuring entity by its entity code."""
    try:
        result = await db.execute(
            select(ProcuringEntity).filter(ProcuringEntity.entity_code == entity_code.upper())
        )
        entity = result.scalars().first()
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Procuring entity with code '{entity_code}' not found.",
            )
        return entity
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(
            "Failed to fetch procuring entity by code",
            extra={"entity_code": entity_code, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch procuring entity.",
        ) from e