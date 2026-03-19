from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.price_benchmark_model import PriceBenchmark
from app.schemas.benchmark_schema import PriceBenchmarkCreate

router = APIRouter(prefix="/benchmarks", tags=["Price Benchmarks"])


@router.get("", response_model=dict)
async def list_benchmarks(
    category: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(PriceBenchmark)
    if category:
        query = query.filter(PriceBenchmark.category.ilike(f"%{category}%"))
    if search:
        query = query.filter(PriceBenchmark.item_name.ilike(f"%{search}%"))

    total_result = await db.scalar(
        query.with_only_columns(func.count(PriceBenchmark.id))
    )
    total = total_result or 0
    query = (
        query.order_by(PriceBenchmark.category, PriceBenchmark.item_name)
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": str(b.id),
                "item_name": b.item_name,
                "category": b.category,
                "unit": b.unit,
                "avg_price": b.avg_price,
                "min_price": b.min_price,
                "max_price": b.max_price,
                "source": b.source,
                "last_updated": b.last_updated.isoformat(),
            }
            for b in items
        ],
        "total": total,
        "page": page,
    }


@router.post("", response_model=dict, status_code=201)
async def create_benchmark(
    payload: PriceBenchmarkCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin")),
):
    benchmark = PriceBenchmark(**payload.model_dump())
    db.add(benchmark)
    await db.commit()
    await db.refresh(benchmark)
    return {"id": str(benchmark.id), "item_name": benchmark.item_name}


@router.put("/{benchmark_id}", response_model=dict)
async def update_benchmark(
    benchmark_id: UUID,
    payload: PriceBenchmarkCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(PriceBenchmark).filter(PriceBenchmark.id == benchmark_id)
    )
    benchmark = result.scalars().first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    for key, val in payload.model_dump().items():
        setattr(benchmark, key, val)
    await db.commit()
    return {"id": str(benchmark_id), "updated": True}


@router.delete("/{benchmark_id}", status_code=204)
async def delete_benchmark(
    benchmark_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("admin")),
):
    result = await db.execute(
        select(PriceBenchmark).filter(PriceBenchmark.id == benchmark_id)
    )
    benchmark = result.scalars().first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    await db.delete(benchmark)
    await db.commit()
