"""
Ghost Supplier Detection Engine
Scores suppliers on multiple risk signals.
Returns supplier risk score 0-100 and detected flags.
"""

from app.models.supplier_model import Supplier


def compute_supplier_score(supplier: Supplier) -> dict:
    """
    Rule-based supplier risk scoring based on proposal Section 4.
    Returns {score, flags}
    """
    score = 0.0
    flags = []

    # 1. Company age — registered <6 months before tender
    if supplier.company_age_days is not None:
        if supplier.company_age_days < 90:
            score += 40
            flags.append(
                f"CRITICAL: Company registered only {supplier.company_age_days} days ago — "
                "ghost supplier indicator"
            )
        elif supplier.company_age_days < 180:
            score += 25
            flags.append(
                f"HIGH: Company is only {supplier.company_age_days} days old — "
                "registered shortly before tender"
            )
        elif supplier.company_age_days < 365:
            score += 10
            flags.append("MEDIUM: Company less than 1 year old")

    # 2. Tax compliance
    if supplier.tax_filings_count == 0:
        score += 30
        flags.append("CRITICAL: No tax filing history — possible shell company")
    elif supplier.tax_filings_count < 2:
        score += 15
        flags.append("HIGH: Minimal tax filing history")

    # 3. PEP directors — politically exposed persons are a strong corruption signal
    directors = supplier.directors or []
    pep_directors = [
        d for d in directors if getattr(d, "is_politically_exposed", False)
    ]
    if pep_directors:
        score += 20
        names = ", ".join(d.full_name for d in pep_directors)
        flags.append(
            f"HIGH: {len(pep_directors)} politically exposed director(s): {names}"
        )

    # 4. Physical address
    if supplier.has_physical_address is False:
        score += 20
        flags.append("HIGH: No verifiable physical address")

    # 5. Online presence
    if supplier.has_online_presence is False:
        score += 10
        flags.append("MEDIUM: No online presence found")

    # 6. No past projects — winning large contract with zero track record
    if (
        supplier.past_contracts_count == 0
        and supplier.company_age_days
        and supplier.company_age_days > 365
    ):
        score += 15
        flags.append("MEDIUM: No prior government contracts on record")

    return {
        "score": min(score, 100.0),
        "flags": flags,
    }


def compute_supplier_score_from_data(supplier_data: dict) -> dict:
    """
    Scorecard from raw dict (for cases where full ORM object isn't available).
    """

    class MockSupplier:
        pass

    class MockDirector:
        def __init__(self, d: dict):
            self.full_name = d.get("full_name", "Unknown")
            self.is_politically_exposed = d.get("is_politically_exposed", False)

    s = MockSupplier()
    s.company_age_days = supplier_data.get("company_age_days")
    s.tax_filings_count = supplier_data.get("tax_filings_count", 0)
    s.directors = [MockDirector(d) for d in supplier_data.get("directors", [])]
    s.has_physical_address = supplier_data.get("has_physical_address")
    s.has_online_presence = supplier_data.get("has_online_presence")
    s.past_contracts_count = supplier_data.get("past_contracts_count", 0)

    return compute_supplier_score(s)
