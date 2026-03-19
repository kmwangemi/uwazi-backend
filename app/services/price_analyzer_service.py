"""
Price Inflation Detection Engine
Compares tender prices against market benchmarks.
Returns a price risk score 0-100 and detected flags.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price_benchmark_model import PriceBenchmark


async def find_benchmark(
    db: AsyncSession, category: str, item_keywords: str
) -> Optional[PriceBenchmark]:
    """
    Fuzzy match tender category/title against price benchmarks.
    Uses simple keyword matching for MVP; can be upgraded with embeddings.
    """
    keywords = item_keywords.lower().split()

    # Try exact category match first
    result = await db.execute(
        select(PriceBenchmark).filter(PriceBenchmark.category.ilike(f"%{category}%"))
    )
    benchmark = result.scalars().first()
    if benchmark:
        return benchmark

    # Fallback: keyword search on item_name
    for kw in keywords:
        if len(kw) > 3:  # skip short words
            result = await db.execute(
                select(PriceBenchmark).filter(PriceBenchmark.item_name.ilike(f"%{kw}%"))
            )
            benchmark = result.scalars().first()
            if benchmark:
                return benchmark

    return None


def calculate_price_deviation(tender_price: float, market_price: float) -> float:
    """Returns deviation as a percentage. Positive = inflated."""
    if market_price <= 0:
        return 0.0
    return ((tender_price - market_price) / market_price) * 100


async def compute_price_score(
    db: AsyncSession,
    tender_value: Optional[float],
    category: Optional[str],
    title: str,
) -> dict:
    """
    Main price analysis function.
    Returns {score, flags, benchmark_comparison}
    """
    flags = []
    score = 0.0
    benchmark_comparison = None

    if not tender_value or tender_value <= 0:
        return {"score": 0.0, "flags": [], "benchmark_comparison": None}

    benchmark = await find_benchmark(db, category or "", title)

    if benchmark:
        deviation = calculate_price_deviation(tender_value, benchmark.avg_price)
        benchmark_comparison = {
            "item": benchmark.item_name,
            "market_avg": benchmark.avg_price,
            "tender_price": tender_value,
            "deviation_pct": round(deviation, 2),
            "unit": benchmark.unit,
            "category": benchmark.category,
        }

        if deviation >= 100:
            score = 100.0
            flags.append(
                f"CRITICAL: Tender price is {deviation:.0f}% above market average "
                f"(KES {tender_value:,.0f} vs benchmark KES {benchmark.avg_price:,.0f})"
            )
        elif deviation >= 50:
            score = 70.0
            flags.append(
                f"HIGH: Price is {deviation:.0f}% above market — "
                f"KES {tender_value:,.0f} vs benchmark KES {benchmark.avg_price:,.0f}"
            )
        elif deviation >= 20:
            score = 30.0
            flags.append(f"MEDIUM: Price is {deviation:.0f}% above market benchmark")

    # High absolute value alone is a signal (>500M KES)
    if tender_value > 500_000_000 and score < 40:
        score = max(score, 40.0)
        flags.append(
            "HIGH VALUE: Contract exceeds KES 500M — requires additional scrutiny"
        )

    return {
        "score": min(score, 100.0),
        "flags": flags,
        "benchmark_comparison": benchmark_comparison,
    }
