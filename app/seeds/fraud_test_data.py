"""
app/db/seeds/fraud_test_data.py
────────────────────────────────
Comprehensive seed data for fraud detection testing.

50 tenders, 20 suppliers, 10 procuring entities, 15 directors,
40 bids, 10 contracts, 20 price benchmarks — all wired to exercise
every detection engine in the ML stack.

Fraud patterns seeded:
    [P1] Price inflation      — tender value 2–5× market benchmark
    [P2] Ghost supplier       — age < 180 days, zero tax filings, no address
    [P3] Spec restriction     — brand names, excessive experience, short deadlines
    [P4] Bid collusion        — near-identical bid amounts on same tender
    [P5] Contract variation   — awarded value >> estimated value
    [P6] PEP director         — politically exposed person as company director
    [P7] Direct procurement   — restricted method on high-value tender
    [P8] Deadline mani.       — submission window < 72 hours
    [P9] Cross-supplier dirs  — same director on multiple companies

Run with:
    python -m app.seeds.fraud_test_data
    python -m app.seeds.fraud_test_data teardown
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.enums import (
    BidStatus,
    ContractStatus,
    ProcurementMethod,
    SupplierVerificationStatus,
    TenderCategory,
    TenderStatus,
)
from app.models.bid_model import Bid
from app.models.contract_model import Contract
from app.models.director_model import Director
from app.models.price_benchmark_model import PriceBenchmark
from app.models.procuring_entity_model import ProcuringEntity
from app.models.supplier_model import Supplier
from app.models.tender_model import Tender

now = datetime.now(timezone.utc)


# ── 1. PRICE BENCHMARKS (20) ──────────────────────────────────────────────────
# Kenya-specific market reference prices used by price_analyzer.py
# and IsolationForest (ml/price_anomaly.py)

BENCHMARKS = [
    # Construction & civil works
    dict(
        item_name="Road construction (tarmac)",
        category="works",
        unit="per km",
        avg_price=21_500_000,
        min_price=18_000_000,
        max_price=28_000_000,
        std_dev=2_800_000,
        source="Kenya KeNHA Schedule 2024",
        year=2024,
    ),
    dict(
        item_name="Portland cement",
        category="works",
        unit="per 50kg bag",
        avg_price=750,
        min_price=680,
        max_price=920,
        std_dev=65,
        source="KNBS Construction Price Index 2024",
        year=2024,
    ),
    dict(
        item_name="Steel reinforcement bar (Y16)",
        category="works",
        unit="per tonne",
        avg_price=115_000,
        min_price=100_000,
        max_price=135_000,
        std_dev=9_500,
        source="KNBS Construction Price Index 2024",
        year=2024,
    ),
    dict(
        item_name="School classroom block (permanent)",
        category="works",
        unit="per classroom",
        avg_price=2_800_000,
        min_price=2_200_000,
        max_price=3_600_000,
        std_dev=380_000,
        source="Ministry of Education cost norms 2023",
        year=2023,
    ),
    dict(
        item_name="Borehole drilling",
        category="works",
        unit="per metre",
        avg_price=12_000,
        min_price=9_500,
        max_price=16_000,
        std_dev=1_800,
        source="Water Resources Authority 2024",
        year=2024,
    ),
    # ICT equipment
    dict(
        item_name="Laptop computer (mid-range)",
        category="ict",
        unit="each",
        avg_price=80_000,
        min_price=60_000,
        max_price=110_000,
        std_dev=12_000,
        source="PPIP Historical Awards 2023-2024",
        year=2024,
    ),
    dict(
        item_name="Desktop computer",
        category="ict",
        unit="each",
        avg_price=65_000,
        min_price=50_000,
        max_price=85_000,
        std_dev=9_000,
        source="PPIP Historical Awards 2023-2024",
        year=2024,
    ),
    dict(
        item_name="Network switch (24-port)",
        category="ict",
        unit="each",
        avg_price=45_000,
        min_price=35_000,
        max_price=65_000,
        std_dev=8_500,
        source="PPIP Historical Awards 2023-2024",
        year=2024,
    ),
    dict(
        item_name="CCTV camera system (16 cameras)",
        category="ict",
        unit="per system",
        avg_price=350_000,
        min_price=280_000,
        max_price=480_000,
        std_dev=52_000,
        source="PPIP Historical Awards 2023-2024",
        year=2024,
    ),
    # Vehicles
    dict(
        item_name="Toyota Land Cruiser (V8)",
        category="goods",
        unit="each",
        avg_price=9_500_000,
        min_price=8_800_000,
        max_price=10_500_000,
        std_dev=480_000,
        source="Kenya National Treasury vehicle schedule 2024",
        year=2024,
    ),
    dict(
        item_name="Saloon vehicle (1500cc)",
        category="goods",
        unit="each",
        avg_price=2_200_000,
        min_price=1_900_000,
        max_price=2_700_000,
        std_dev=230_000,
        source="Kenya National Treasury vehicle schedule 2024",
        year=2024,
    ),
    # Medical & health
    dict(
        item_name="Artemether-Lumefantrine 80/480mg (24 tabs)",
        category="health",
        unit="per pack",
        avg_price=180,
        min_price=140,
        max_price=240,
        std_dev=28,
        source="KEMSA price list 2024",
        year=2024,
    ),
    dict(
        item_name="Surgical gloves (latex, size M, 100 pairs)",
        category="health",
        unit="per box",
        avg_price=1_200,
        min_price=900,
        max_price=1_600,
        std_dev=180,
        source="KEMSA price list 2024",
        year=2024,
    ),
    dict(
        item_name="Hospital bed (standard ward)",
        category="health",
        unit="each",
        avg_price=45_000,
        min_price=35_000,
        max_price=60_000,
        std_dev=7_000,
        source="KEMSA equipment schedule 2024",
        year=2024,
    ),
    # Education
    dict(
        item_name="Secondary school textbook",
        category="education",
        unit="each",
        avg_price=850,
        min_price=650,
        max_price=1_200,
        std_dev=140,
        source="Kenya Institute of Curriculum Dev. 2024",
        year=2024,
    ),
    dict(
        item_name="School desk (double, wooden)",
        category="education",
        unit="each",
        avg_price=4_500,
        min_price=3_500,
        max_price=6_000,
        std_dev=600,
        source="Ministry of Education cost norms 2023",
        year=2023,
    ),
    # Office & supplies
    dict(
        item_name="Office printing paper (A4, 80gsm, ream)",
        category="goods",
        unit="per ream",
        avg_price=550,
        min_price=480,
        max_price=680,
        std_dev=55,
        source="PPIP Historical Awards 2024",
        year=2024,
    ),
    dict(
        item_name="Office chair (ergonomic)",
        category="goods",
        unit="each",
        avg_price=18_000,
        min_price=12_000,
        max_price=28_000,
        std_dev=4_500,
        source="PPIP Historical Awards 2024",
        year=2024,
    ),
    # Consultancy & services
    dict(
        item_name="IT consultancy (senior consultant)",
        category="services",
        unit="per day",
        avg_price=35_000,
        min_price=25_000,
        max_price=55_000,
        std_dev=8_000,
        source="PPIP Historical Awards 2023-2024",
        year=2024,
    ),
    dict(
        item_name="Security guard services",
        category="services",
        unit="per guard per month",
        avg_price=22_000,
        min_price=18_000,
        max_price=28_000,
        std_dev=2_800,
        source="PPIP Historical Awards 2024",
        year=2024,
    ),
]


# ── 2. PROCURING ENTITIES (10) ────────────────────────────────────────────────

ENTITIES = [
    dict(
        name="Ministry of Health",
        entity_type="ministry",
        county=None,
        code="MOH",
        corruption_history_score=42.0,
        investigation_count=3,
    ),
    dict(
        name="Nairobi City County Government",
        entity_type="county_government",
        county="Nairobi",
        code="NRB-CGV",
        corruption_history_score=71.0,
        investigation_count=8,
    ),
    dict(
        name="Kisumu County Government",
        entity_type="county_government",
        county="Kisumu",
        code="KSM-CGV",
        corruption_history_score=58.0,
        investigation_count=4,
    ),
    dict(
        name="Kenya National Highways Authority",
        entity_type="state_corporation",
        county=None,
        code="KENHA",
        corruption_history_score=35.0,
        investigation_count=2,
    ),
    dict(
        name="Ministry of Education",
        entity_type="ministry",
        county=None,
        code="MOE",
        corruption_history_score=28.0,
        investigation_count=1,
    ),
    dict(
        name="Mombasa County Government",
        entity_type="county_government",
        county="Mombasa",
        code="MBA-CGV",
        corruption_history_score=65.0,
        investigation_count=6,
    ),
    dict(
        name="Kenya Revenue Authority",
        entity_type="state_corporation",
        county=None,
        code="KRA",
        corruption_history_score=22.0,
        investigation_count=1,
    ),
    dict(
        name="Turkana County Government",
        entity_type="county_government",
        county="Turkana",
        code="TRK-CGV",
        corruption_history_score=82.0,
        investigation_count=11,
    ),
    dict(
        name="Kenya Power & Lighting Company",
        entity_type="state_corporation",
        county=None,
        code="KPLC",
        corruption_history_score=48.0,
        investigation_count=3,
    ),
    dict(
        name="Ministry of Interior",
        entity_type="ministry",
        county=None,
        code="MOI",
        corruption_history_score=55.0,
        investigation_count=5,
    ),
]


# ── 3. SUPPLIERS (20) ─────────────────────────────────────────────────────────
# Mix of clean, suspicious, and ghost suppliers

SUPPLIERS = [
    # ── CLEAN suppliers (low risk) ──
    dict(
        name="Safaricom Business Solutions Ltd",
        registration_number="CPR/2015/001100",
        kra_pin="A001100567B",
        company_age_days=3285,
        tax_filings_count=36,
        address="Waiyaki Way, Westlands, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=True,
        past_contracts_count=18,
        past_contracts_value=45_000_000,
        verification_status=SupplierVerificationStatus.VERIFIED,
        is_verified=True,
        risk_score=8.5,
    ),
    dict(
        name="Kenya Infrastructure Partners Ltd",
        registration_number="CPR/2012/004422",
        kra_pin="A004422567D",
        company_age_days=4380,
        tax_filings_count=48,
        address="Upperhill Road, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=True,
        past_contracts_count=32,
        past_contracts_value=890_000_000,
        verification_status=SupplierVerificationStatus.VERIFIED,
        is_verified=True,
        risk_score=12.0,
    ),
    dict(
        name="East Africa Medical Supplies Ltd",
        registration_number="CPR/2010/002233",
        kra_pin="A002233789E",
        company_age_days=5110,
        tax_filings_count=56,
        address="Industrial Area, Enterprise Road, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=True,
        past_contracts_count=41,
        past_contracts_value=320_000_000,
        verification_status=SupplierVerificationStatus.VERIFIED,
        is_verified=True,
        risk_score=9.0,
    ),
    dict(
        name="Techbridge ICT Solutions",
        registration_number="CPR/2017/007788",
        kra_pin="A007788123F",
        company_age_days=2555,
        tax_filings_count=28,
        address="Delta Towers, Westlands, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=True,
        past_contracts_count=14,
        past_contracts_value=78_000_000,
        verification_status=SupplierVerificationStatus.VERIFIED,
        is_verified=True,
        risk_score=15.0,
    ),
    dict(
        name="BuildRight Contractors Kenya",
        registration_number="CPR/2013/003344",
        kra_pin="A003344456G",
        company_age_days=3830,
        tax_filings_count=44,
        address="Ngong Road, Karen, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=True,
        past_contracts_count=27,
        past_contracts_value=560_000_000,
        verification_status=SupplierVerificationStatus.VERIFIED,
        is_verified=True,
        risk_score=11.0,
    ),
    # ── SUSPICIOUS suppliers (medium risk) ──
    dict(
        name="Apex General Supplies",
        registration_number="CPR/2021/009911",
        kra_pin="A009911234H",
        company_age_days=720,
        tax_filings_count=4,
        address="P.O. Box 44521, Nairobi",
        county="Nairobi",
        has_physical_address=False,
        has_online_presence=False,
        past_contracts_count=3,
        past_contracts_value=12_000_000,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=55.0,
    ),
    dict(
        name="Horizon Trading Co. Ltd",
        registration_number="CPR/2020/008833",
        kra_pin="A008833567I",
        company_age_days=980,
        tax_filings_count=3,
        address="P.O. Box 12345, Mombasa",
        county="Mombasa",
        has_physical_address=False,
        has_online_presence=False,
        past_contracts_count=5,
        past_contracts_value=28_000_000,
        verification_status=SupplierVerificationStatus.PENDING,
        is_verified=False,
        risk_score=62.0,
    ),
    dict(
        name="Rapid Solutions Kenya",
        registration_number="CPR/2022/011122",
        kra_pin="A011122890J",
        company_age_days=540,
        tax_filings_count=2,
        address="Tom Mboya Street, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=2,
        past_contracts_value=8_500_000,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=58.0,
    ),
    dict(
        name="Summit Procurement Services",
        registration_number="CPR/2021/010055",
        kra_pin="A010055123K",
        company_age_days=810,
        tax_filings_count=5,
        address="Kimathi Street, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=4,
        past_contracts_value=19_000_000,
        verification_status=SupplierVerificationStatus.PENDING,
        is_verified=False,
        risk_score=48.0,
    ),
    dict(
        name="Coastal General Merchants",
        registration_number="CPR/2020/009977",
        kra_pin="A009977456L",
        company_age_days=1100,
        tax_filings_count=6,
        address="Moi Avenue, Mombasa",
        county="Mombasa",
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=7,
        past_contracts_value=35_000_000,
        verification_status=SupplierVerificationStatus.PENDING,
        is_verified=False,
        risk_score=44.0,
    ),
    # ── GHOST suppliers (high/critical risk) — [P2] ──
    dict(
        name="Quickfix Procurement Ltd",
        registration_number="CPR/2023/019988",
        kra_pin="A019988123M",
        company_age_days=45,  # [P2] < 180 days
        tax_filings_count=0,  # [P2] zero filings
        address="",  # [P2] no address
        county="Nairobi",
        has_physical_address=False,
        has_online_presence=False,
        past_contracts_count=0,
        past_contracts_value=0,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=88.0,
    ),
    dict(
        name="Phantom Contractors Ltd",
        registration_number="CPR/2024/020012",
        kra_pin="A020012999N",
        company_age_days=12,  # [P2] extremely new
        tax_filings_count=0,
        address="",
        county="Nairobi",
        has_physical_address=False,
        has_online_presence=False,
        past_contracts_count=0,
        past_contracts_value=0,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=95.0,
    ),
    dict(
        name="Mirage Supplies Co.",
        registration_number="CPR/2023/018877",
        kra_pin="A018877000O",
        company_age_days=90,
        tax_filings_count=0,
        address="",
        county="Kisumu",
        has_physical_address=False,
        has_online_presence=False,
        past_contracts_count=0,
        past_contracts_value=0,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=91.0,
    ),
    dict(
        name="Shadow Infrastructure Ltd",
        registration_number="CPR/2024/021100",
        kra_pin="A021100111P",
        company_age_days=8,  # [P2] 8 days old
        tax_filings_count=0,
        address="",
        county="Turkana",
        has_physical_address=False,
        has_online_presence=False,
        past_contracts_count=0,
        past_contracts_value=0,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=97.0,
    ),
    dict(
        name="Blank Canvas Enterprises",
        registration_number="CPR/2023/017766",
        kra_pin="A017766222Q",
        company_age_days=120,
        tax_filings_count=0,
        address="",
        county="Mombasa",
        has_physical_address=False,
        has_online_presence=False,
        past_contracts_count=0,
        past_contracts_value=0,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=86.0,
    ),
    # ── BLACKLISTED supplier ──
    dict(
        name="Crooked Ventures Ltd",
        registration_number="CPR/2019/006655",
        kra_pin="A006655333R",
        company_age_days=1800,
        tax_filings_count=2,
        address="River Road, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=8,
        past_contracts_value=42_000_000,
        verification_status=SupplierVerificationStatus.BLACKLISTED,
        is_verified=False,
        is_blacklisted=True,
        blacklist_reason="Convicted of bid rigging — EACC Case 2022/CR/004",
        risk_score=99.0,
    ),
    # ── COLLUSION cluster — same director, related bids [P4, P9] ──
    dict(
        name="Alpha Builders Kenya",
        registration_number="CPR/2018/005544",
        kra_pin="A005544444S",
        company_age_days=2100,
        tax_filings_count=14,
        address="Thika Road, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=9,
        past_contracts_value=95_000_000,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=72.0,
    ),
    dict(
        name="Beta Construction Ltd",
        registration_number="CPR/2018/005545",
        kra_pin="A005545444T",
        company_age_days=2098,
        tax_filings_count=13,
        address="Thika Road, Nairobi",
        county="Nairobi",  # same address [P9]
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=8,
        past_contracts_value=88_000_000,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=74.0,
    ),
    dict(
        name="Gamma Works Ltd",
        registration_number="CPR/2018/005546",
        kra_pin="A005546444U",
        company_age_days=2097,
        tax_filings_count=12,
        address="Thika Road, Nairobi",
        county="Nairobi",  # same address [P9]
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=7,
        past_contracts_value=82_000_000,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=73.0,
    ),
    dict(
        name="Delta Supply Chain Ltd",
        registration_number="CPR/2019/006677",
        kra_pin="A006677555V",
        company_age_days=1650,
        tax_filings_count=9,
        address="Industrial Area, Nairobi",
        county="Nairobi",
        has_physical_address=True,
        has_online_presence=False,
        past_contracts_count=6,
        past_contracts_value=55_000_000,
        verification_status=SupplierVerificationStatus.UNVERIFIED,
        is_verified=False,
        risk_score=67.0,
    ),
]


# ── 4. TENDERS (50) ──────────────────────────────────────────────────────────
# Keyed by index to entity index above (0-based)
# fraud_tags are comments only — the risk engine will compute actual flags

TENDERS = [
    # ── CLEAN tenders (low risk, should score 0–35) ──
    dict(
        title="Supply of Office Stationery FY 2024/25",
        entity_idx=4,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=850_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of standard office stationery for schools including pens, paper, "
        "folders and printer cartridges.",
        deadline_days=30,
        reference_number="MOE/OT/2024/001",
    ),
    dict(
        title="Routine Maintenance of Meru-Nanyuki Road",
        entity_idx=3,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=38_000_000,
        county="Meru",
        status=TenderStatus.OPEN,
        description="Routine maintenance and pothole patching along the 45km Meru-Nanyuki road.",
        deadline_days=21,
        reference_number="KENHA/OT/2024/101",
    ),
    dict(
        title="Supply of ARV Drugs — Quarterly",
        entity_idx=0,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=12_500_000,
        county="Nairobi",
        status=TenderStatus.CLOSED,
        description="Supply of anti-retroviral drugs for dispensation in public health facilities.",
        deadline_days=-5,
        reference_number="MOH/OT/2024/045",
    ),
    dict(
        title="ICT Infrastructure Upgrade — KRA Offices",
        entity_idx=6,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=22_000_000,
        county="Nairobi",
        status=TenderStatus.EVALUATED,
        description="Supply and installation of network equipment, servers and workstations.",
        deadline_days=-15,
        reference_number="KRA/OT/2024/012",
    ),
    dict(
        title="Construction of 10 Classrooms — Kisumu County",
        entity_idx=2,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=28_000_000,
        county="Kisumu",
        status=TenderStatus.OPEN,
        description="Construction of ten permanent classroom blocks in selected primary schools.",
        deadline_days=25,
        reference_number="KSM/OT/2024/088",
    ),
    # ── PRICE INFLATION tenders [P1] (should trigger price_score flags) ──
    dict(
        title="Supply of 200 Laptops — Nairobi County Assembly",  # [P1] 3× market
        entity_idx=1,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7] direct procurement
        estimated_value=48_000_000,  # KES 240k/unit vs 80k benchmark
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of 200 laptops for county assembly members and staff. "
        "Must be Dell XPS 15 brand only.",  # [P3] brand restriction
        deadline_days=7,
        reference_number="NRB/DP/2024/031",
    ),
    dict(
        title="Purchase of 5 Toyota Land Cruisers",  # [P1] 2× market
        entity_idx=7,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=95_000_000,  # KES 19M/unit vs 9.5M benchmark
        county="Turkana",
        status=TenderStatus.OPEN,
        description="Purchase of five Toyota Land Cruiser V8 vehicles for county executive use.",
        deadline_days=5,
        reference_number="TRK/DP/2024/008",
    ),
    dict(
        title="Supply of Surgical Gloves and Consumables",  # [P1] 4× market
        entity_idx=0,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.RESTRICTED_TENDER,  # [P7]
        estimated_value=8_400_000,  # vs ~2.4M expected
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of surgical gloves (latex) and other theatre consumables.",
        deadline_days=10,
        reference_number="MOH/RT/2024/022",
    ),
    dict(
        title="Construction of 5km Road — Turkana County",  # [P1] 3× market
        entity_idx=7,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=322_500_000,  # KES 64.5M/km vs 21.5M benchmark
        county="Turkana",
        status=TenderStatus.OPEN,
        description="Construction of 5km tarmac road in Lodwar town.",
        deadline_days=14,
        reference_number="TRK/OT/2024/015",
    ),
    dict(
        title="Supply of School Textbooks — 50,000 Copies",  # [P1] 2.5× market
        entity_idx=4,
        category=TenderCategory.EDUCATION,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=106_250_000,  # KES 2,125/book vs 850 benchmark
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of secondary school textbooks for Form 1-4 students.",
        deadline_days=18,
        reference_number="MOE/OT/2024/067",
    ),
    dict(
        title="ICT Security Consultancy Services",  # [P1] 5× market
        entity_idx=6,
        category=TenderCategory.SERVICES,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=26_250_000,  # 150 days × KES 175k/day vs 35k benchmark
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Provision of ICT security audit and consultancy services.",
        deadline_days=3,
        reference_number="KRA/DP/2024/005",
    ),  # [P8] 3-day deadline
    # ── SPEC RESTRICTION tenders [P3] ──
    dict(
        title="Supply of Computers — Ministry of Interior",
        entity_idx=9,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=19_500_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of 300 desktop computers. Must be HP EliteDesk brand only. "
        "Supplier must have minimum 20 years experience in ICT supply.",  # [P3]
        deadline_days=12,
        reference_number="MOI/OT/2024/019",
    ),
    dict(
        title="Maintenance of KPLC Grid Equipment",
        entity_idx=8,
        category=TenderCategory.SERVICES,
        procurement_method=ProcurementMethod.RESTRICTED_TENDER,
        estimated_value=45_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Maintenance and repair of high voltage grid equipment. "
        "Equipment must be sourced solely from Schneider Electric. "  # [P3] sole source
        "Completion required within 24 hours of contract award.",  # [P3]
        deadline_days=2,
        reference_number="KPLC/RT/2024/007",
    ),  # [P8]
    dict(
        title="Construction of Mombasa County Offices",
        entity_idx=5,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=180_000_000,
        county="Mombasa",
        status=TenderStatus.OPEN,
        description="Construction of a 5-floor county government office block. "
        "Contractor must have completed at least 3 similar projects within last 2 years "
        "in Mombasa County only.",  # [P3] geographic restriction
        deadline_days=21,
        reference_number="MBA/OT/2024/044",
    ),
    dict(
        title="Supply of Security Systems — Kisumu",
        entity_idx=2,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=5_600_000,
        county="Kisumu",
        status=TenderStatus.OPEN,
        description="Supply and installation of CCTV systems. Must use Hikvision brand cameras. "
        "Engineer must have minimum 15 years experience.",  # [P3]
        deadline_days=4,
        reference_number="KSM/DP/2024/011",
    ),  # [P8]
    # ── DEADLINE MANIPULATION tenders [P8] ──
    dict(
        title="Emergency Supply of Medical Equipment",
        entity_idx=0,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.RESTRICTED_TENDER,
        estimated_value=35_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Emergency supply of medical equipment for county referral hospitals.",
        deadline_days=1,
        reference_number="MOH/RT/2024/031",
    ),  # [P8] 1 day!
    dict(
        title="Supply of Fuel — Turkana County Fleet",
        entity_idx=7,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=18_000_000,
        county="Turkana",
        status=TenderStatus.OPEN,
        description="Supply of diesel and petrol fuel for county government fleet.",
        deadline_days=2,
        reference_number="TRK/DP/2024/019",
    ),  # [P8]
    dict(
        title="Renovation of Interior Ministry Offices",
        entity_idx=9,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=28_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Renovation and refurbishment of Ministry of Interior offices.",
        deadline_days=1,
        reference_number="MOI/DP/2024/003",
    ),  # [P8]
    # ── COLLUSION setup tenders [P4] — will have near-identical bids ──
    dict(
        title="Construction of Nairobi County Markets",
        entity_idx=1,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=250_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Construction of three modern market complexes in Nairobi sub-counties.",
        deadline_days=28,
        reference_number="NRB/OT/2024/055",
    ),
    dict(
        title="Supply of Water Treatment Chemicals",
        entity_idx=2,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=9_500_000,
        county="Kisumu",
        status=TenderStatus.OPEN,
        description="Supply of water treatment chemicals for Kisumu water treatment plant.",
        deadline_days=20,
        reference_number="KSM/OT/2024/099",
    ),
    dict(
        title="Road Rehabilitation — Mombasa CBD",
        entity_idx=5,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=420_000_000,
        county="Mombasa",
        status=TenderStatus.OPEN,
        description="Rehabilitation of 20km urban roads in Mombasa CBD.",
        deadline_days=30,
        reference_number="MBA/OT/2024/062",
    ),
    # ── GHOST SUPPLIER tenders — awarded to ghost companies [P2] ──
    dict(
        title="Supply of Printing Equipment — Turkana",  # ghost supplier will bid here
        entity_idx=7,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=12_000_000,
        county="Turkana",
        status=TenderStatus.CLOSED,
        description="Supply of high-speed printers and photocopiers.",
        deadline_days=-2,
        reference_number="TRK/DP/2024/021",
    ),
    dict(
        title="General Cleaning Services — Mombasa County",  # ghost supplier bid
        entity_idx=5,
        category=TenderCategory.SERVICES,
        procurement_method=ProcurementMethod.RESTRICTED_TENDER,
        estimated_value=6_500_000,
        county="Mombasa",
        status=TenderStatus.CLOSED,
        description="Provision of general cleaning and sanitation services.",
        deadline_days=-3,
        reference_number="MBA/RT/2024/018",
    ),
    # ── HIGH VALUE, CRITICAL RISK tenders ──
    dict(
        title="Construction of Turkana County Hospital",
        entity_idx=7,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=1_800_000_000,  # KES 1.8B
        county="Turkana",
        status=TenderStatus.OPEN,
        description="Construction of a 200-bed county referral hospital. "
        "Must use Skanska Group as the main contractor.",  # [P3] sole source
        deadline_days=7,
        reference_number="TRK/OT/2024/001",
    ),  # [P8]
    dict(
        title="Nairobi County Smart City ICT Platform",
        entity_idx=1,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=750_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Design and implementation of smart city ICT platform.",
        deadline_days=5,
        reference_number="NRB/DP/2024/001",
    ),  # [P8]
    dict(
        title="KENHA Highway Expansion — Nairobi-Mombasa",
        entity_idx=3,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=12_000_000_000,  # KES 12B
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Expansion of the Nairobi-Mombasa highway to dual carriageway.",
        deadline_days=45,
        reference_number="KENHA/OT/2024/001",
    ),
    # ── More standard/clean tenders (filling to 50) ──
    dict(
        title="Supply of Laboratory Equipment — MOH",
        entity_idx=0,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=15_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of laboratory diagnostic equipment for county hospitals.",
        deadline_days=22,
        reference_number="MOH/OT/2024/088",
    ),
    dict(
        title="Borehole Drilling — Turkana North",
        entity_idx=7,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=8_400_000,
        county="Turkana",
        status=TenderStatus.OPEN,
        description="Drilling of 7 boreholes across Turkana North sub-county.",
        deadline_days=25,
        reference_number="TRK/OT/2024/038",
    ),
    dict(
        title="Supply of School Furniture — 500 Desks",
        entity_idx=4,
        category=TenderCategory.EDUCATION,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=2_250_000,
        county="Kisumu",
        status=TenderStatus.OPEN,
        description="Supply of 500 double wooden school desks.",
        deadline_days=18,
        reference_number="MOE/OT/2024/102",
    ),
    dict(
        title="Security Guard Services — KRA Buildings",
        entity_idx=6,
        category=TenderCategory.SERVICES,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=5_280_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Provision of 20 security guards for 12 months.",
        deadline_days=14,
        reference_number="KRA/OT/2024/033",
    ),
    dict(
        title="Supply of Hospital Beds — Mombasa County",
        entity_idx=5,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=4_500_000,
        county="Mombasa",
        status=TenderStatus.OPEN,
        description="Supply of 100 standard ward hospital beds.",
        deadline_days=20,
        reference_number="MBA/OT/2024/077",
    ),
    dict(
        title="Repair of KPLC Transformers — Coast Region",
        entity_idx=8,
        category=TenderCategory.SERVICES,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=32_000_000,
        county="Mombasa",
        status=TenderStatus.OPEN,
        description="Repair and refurbishment of distribution transformers.",
        deadline_days=16,
        reference_number="KPLC/OT/2024/022",
    ),
    dict(
        title="Supply of ARV Drugs Q2 2024",
        entity_idx=0,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=9_800_000,
        county="Nairobi",
        status=TenderStatus.CLOSED,
        description="Supply of ARV drugs for dispensation at public health facilities.",
        deadline_days=-10,
        reference_number="MOH/OT/2024/051",
    ),
    dict(
        title="Road Marking — Nairobi CBD",
        entity_idx=1,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=4_200_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Road marking and signage installation in Nairobi CBD.",
        deadline_days=12,
        reference_number="NRB/OT/2024/071",
    ),
    dict(
        title="Supply of Network Equipment — MOI",
        entity_idx=9,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=8_100_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of routers, switches and network cabling.",
        deadline_days=19,
        reference_number="MOI/OT/2024/028",
    ),
    dict(
        title="Renovation of Kisumu County Health Facilities",
        entity_idx=2,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=22_000_000,
        county="Kisumu",
        status=TenderStatus.OPEN,
        description="Renovation of 8 health centres in Kisumu County.",
        deadline_days=28,
        reference_number="KSM/OT/2024/112",
    ),
    # ── Tenders 36–50: mixed risk ──
    dict(
        title="Supply of Fuel — MOH Fleet Q3",
        entity_idx=0,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=3_600_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of diesel and petrol for Ministry fleet.",
        deadline_days=10,
        reference_number="MOH/OT/2024/095",
    ),
    dict(
        title="Printing of Election Materials",  # [P1] suspiciously high
        entity_idx=9,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.RESTRICTED_TENDER,  # [P7]
        estimated_value=48_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Printing of voter registration forms and election materials.",
        deadline_days=3,
        reference_number="MOI/RT/2024/011",
    ),  # [P8]
    dict(
        title="KENHA Bridge Construction — Tana River",
        entity_idx=3,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=680_000_000,
        county="Tana River",
        status=TenderStatus.OPEN,
        description="Construction of a dual-lane bridge across Tana River.",
        deadline_days=35,
        reference_number="KENHA/OT/2024/055",
    ),
    dict(
        title="Supply of Medicines — Mombasa County Q3",
        entity_idx=5,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=14_200_000,
        county="Mombasa",
        status=TenderStatus.OPEN,
        description="Supply of essential medicines for Mombasa county hospitals.",
        deadline_days=17,
        reference_number="MBA/OT/2024/088",
    ),
    dict(
        title="ICT Support Services — KPLC",
        entity_idx=8,
        category=TenderCategory.SERVICES,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=18_750_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Provision of ICT helpdesk and infrastructure support services.",
        deadline_days=6,
        reference_number="KPLC/DP/2024/014",
    ),
    dict(
        title="Supply of Office Furniture — KRA",
        entity_idx=6,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=6_480_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of office desks, chairs and cabinets.",
        deadline_days=15,
        reference_number="KRA/OT/2024/041",
    ),
    dict(
        title="Water Supply Infrastructure — Turkana",
        entity_idx=7,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=85_000_000,
        county="Turkana",
        status=TenderStatus.OPEN,
        description="Construction of water supply pipeline and storage tanks.",
        deadline_days=30,
        reference_number="TRK/OT/2024/049",
    ),
    dict(
        title="Supply of Personal Protective Equipment",
        entity_idx=0,
        category=TenderCategory.HEALTH,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=7_800_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of PPE including gloves, masks and gowns for health workers.",
        deadline_days=14,
        reference_number="MOH/OT/2024/109",
    ),
    dict(
        title="Rehabilitation of Kisumu Port Access Road",
        entity_idx=2,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=55_000_000,
        county="Kisumu",
        status=TenderStatus.OPEN,
        description="Rehabilitation of 8km access road to Kisumu port.",
        deadline_days=22,
        reference_number="KSM/OT/2024/128",
    ),
    dict(
        title="Supply of Body Scanners — Ports",  # [P1] overpriced
        entity_idx=9,
        category=TenderCategory.ICT,
        procurement_method=ProcurementMethod.RESTRICTED_TENDER,  # [P7]
        estimated_value=95_000_000,
        county="Mombasa",
        status=TenderStatus.OPEN,
        description="Supply and installation of full-body scanners at port of entry. "
        "Must be from L3Harris Technologies only.",  # [P3]
        deadline_days=5,
        reference_number="MOI/RT/2024/017",
    ),  # [P8]
    dict(
        title="Road Lighting — Nairobi Expressway",
        entity_idx=1,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=62_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Installation of LED street lighting along Nairobi Expressway.",
        deadline_days=24,
        reference_number="NRB/OT/2024/084",
    ),
    dict(
        title="Supply of Classroom Furniture — Turkana",
        entity_idx=4,
        category=TenderCategory.EDUCATION,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=3_375_000,
        county="Turkana",
        status=TenderStatus.OPEN,
        description="Supply of 750 double desks for primary schools.",
        deadline_days=20,
        reference_number="MOE/OT/2024/118",
    ),
    dict(
        title="KPLC Pre-paid Meter Supply",
        entity_idx=8,
        category=TenderCategory.GOODS,
        procurement_method=ProcurementMethod.OPEN_TENDER,
        estimated_value=240_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Supply of 50,000 smart pre-paid electricity meters.",
        deadline_days=28,
        reference_number="KPLC/OT/2024/031",
    ),
    dict(
        title="Construction of MOH Headquarters Annex",  # [P1] overpriced
        entity_idx=0,
        category=TenderCategory.WORKS,
        procurement_method=ProcurementMethod.DIRECT_PROCUREMENT,  # [P7]
        estimated_value=320_000_000,
        county="Nairobi",
        status=TenderStatus.OPEN,
        description="Construction of a 3-floor annex to the Ministry of Health HQ. "
        "Must be completed within 48 hours of contract signing.",  # [P3]
        deadline_days=2,
        reference_number="MOH/DP/2024/004",
    ),  # [P8]
]


# ── 5. BIDS (40) ─────────────────────────────────────────────────────────────
# Format: (tender_idx, supplier_idx, amount, is_winner, proposal_text_snippet)
# Collusion bids [P4] share near-identical proposal text + similar amounts

_CLEAN_PROPOSAL = (
    "We hereby submit our bid for the above tender. Our company has extensive experience "
    "in this field having completed similar projects successfully. We offer competitive "
    "pricing and guarantee quality delivery within the stipulated timeframe."
)

_COLLUDING_PROPOSAL_A = (
    "We submit our competitive bid for this tender. Our firm possesses the requisite "
    "technical capacity and financial capability to deliver these works on time and within "
    "budget. We have completed 12 similar projects in the region."
)

_COLLUDING_PROPOSAL_B = (  # Nearly identical to A — TF-IDF will flag this [P4]
    "We submit our competitive bid for this tender. Our firm possesses the requisite "
    "technical capacity and financial capability to deliver these works on time and within "
    "budget. We have completed 11 similar projects in the region."
)

_COLLUDING_PROPOSAL_C = (  # Also nearly identical [P4]
    "We submit our competitive bid for this tender. Our firm possesses the requisite "
    "technical capacity and financial capability to deliver these works on time and within "
    "budget. We have completed 10 similar projects in the region."
)

BIDS = [
    # Clean tender 0 — stationery
    (0, 0, 820_000, True, _CLEAN_PROPOSAL),
    (0, 5, 845_000, False, _CLEAN_PROPOSAL),
    # Clean tender 1 — road maintenance
    (1, 1, 37_200_000, True, _CLEAN_PROPOSAL),
    (1, 4, 38_800_000, False, _CLEAN_PROPOSAL),
    # Price inflated tender 5 — laptops [P1]
    (5, 10, 47_500_000, True, _CLEAN_PROPOSAL),  # ghost supplier wins [P2]
    (5, 3, 46_900_000, False, _CLEAN_PROPOSAL),
    # Price inflated + ghost supplier — vehicles [P1, P2]
    (6, 11, 94_000_000, True, _CLEAN_PROPOSAL),  # Phantom Contractors wins
    (6, 6, 93_500_000, False, _CLEAN_PROPOSAL),
    # Direct procurement — surgical supplies [P1, P7]
    (7, 12, 8_350_000, True, _CLEAN_PROPOSAL),  # Mirage Supplies
    (7, 9, 8_400_000, False, _CLEAN_PROPOSAL),
    # Spec restriction — computers [P3]
    (11, 3, 19_200_000, True, _CLEAN_PROPOSAL),
    (11, 7, 19_450_000, False, _CLEAN_PROPOSAL),
    # Deadline manipulation — emergency medical [P8]
    (15, 13, 34_500_000, True, _CLEAN_PROPOSAL),  # Shadow Infrastructure [P2]
    (15, 2, 35_200_000, False, _CLEAN_PROPOSAL),
    # COLLUSION bids — Nairobi markets [P4]  tender_idx=18
    (18, 16, 248_000_000, True, _COLLUDING_PROPOSAL_A),  # Alpha Builders
    (18, 17, 249_500_000, False, _COLLUDING_PROPOSAL_B),  # Beta Construction  [P4]
    (18, 18, 251_000_000, False, _COLLUDING_PROPOSAL_C),  # Gamma Works         [P4]
    # COLLUSION bids — water chemicals [P4]  tender_idx=19
    (19, 16, 9_350_000, True, _COLLUDING_PROPOSAL_A),
    (19, 17, 9_420_000, False, _COLLUDING_PROPOSAL_B),  # [P4]
    # COLLUSION bids — Mombasa road [P4]  tender_idx=20
    (20, 16, 418_000_000, False, _COLLUDING_PROPOSAL_A),
    (20, 17, 415_000_000, True, _COLLUDING_PROPOSAL_B),  # [P4]
    (20, 18, 421_000_000, False, _COLLUDING_PROPOSAL_C),  # [P4]
    (20, 19, 422_500_000, False, _CLEAN_PROPOSAL),
    # Ghost supplier awarded — printing equipment [P2]  tender_idx=21
    (21, 14, 11_800_000, True, _CLEAN_PROPOSAL),  # Blank Canvas Enterprises
    (21, 10, 11_950_000, False, _CLEAN_PROPOSAL),
    # Ghost supplier — cleaning services [P2]  tender_idx=22
    (22, 12, 6_400_000, True, _CLEAN_PROPOSAL),  # Mirage Supplies
    (22, 5, 6_480_000, False, _CLEAN_PROPOSAL),
    # High value — Turkana hospital [P1, P3, P8]  tender_idx=23
    (23, 1, 1_780_000_000, True, _CLEAN_PROPOSAL),
    (23, 4, 1_810_000_000, False, _CLEAN_PROPOSAL),
    # Clean bids for remaining tenders
    (2, 2, 12_300_000, True, _CLEAN_PROPOSAL),
    (2, 9, 12_480_000, False, _CLEAN_PROPOSAL),
    (3, 3, 21_800_000, True, _CLEAN_PROPOSAL),
    (3, 0, 22_100_000, False, _CLEAN_PROPOSAL),
    (4, 4, 27_500_000, True, _CLEAN_PROPOSAL),
    (4, 1, 27_900_000, False, _CLEAN_PROPOSAL),
    (8, 1, 318_000_000, True, _CLEAN_PROPOSAL),
    (8, 4, 321_000_000, False, _CLEAN_PROPOSAL),
    (24, 1, 11_900_000_000, True, _CLEAN_PROPOSAL),
    (24, 4, 12_050_000_000, False, _CLEAN_PROPOSAL),
    (25, 1, 74_500_000_000 // 1000, True, _CLEAN_PROPOSAL),
    (25, 4, 75_000_000_000 // 1000, False, _CLEAN_PROPOSAL),
]


# ── 6. CONTRACTS (10) ─────────────────────────────────────────────────────────
# Some with large value variation [P5]

CONTRACTS = [
    # Clean contract
    dict(
        tender_idx=0,
        supplier_idx=0,
        contract_value=820_000,
        original_tender_value=850_000,
        value_variation_pct=-3.5,
        status=ContractStatus.COMPLETED,
        variation_count=0,
        awarded_days_ago=60,
    ),
    dict(
        tender_idx=1,
        supplier_idx=1,
        contract_value=37_200_000,
        original_tender_value=38_000_000,
        value_variation_pct=-2.1,
        status=ContractStatus.ACTIVE,
        variation_count=0,
        awarded_days_ago=30,
    ),
    # Price inflated contract — variation [P5]
    dict(
        tender_idx=5,
        supplier_idx=10,
        contract_value=68_000_000,  # KES 68M vs estimated 48M — [P5] +42% variation
        original_tender_value=48_000_000,
        value_variation_pct=41.7,
        status=ContractStatus.ACTIVE,
        variation_count=3,  # 3 addenda [P5]
        awarded_days_ago=15,
    ),
    dict(
        tender_idx=6,
        supplier_idx=11,
        contract_value=135_000_000,  # [P5] +42% — ghost supplier wins high-value contract
        original_tender_value=95_000_000,
        value_variation_pct=42.1,
        status=ContractStatus.ACTIVE,
        variation_count=2,
        awarded_days_ago=10,
    ),
    # Ghost supplier contract [P2, P5]
    dict(
        tender_idx=21,
        supplier_idx=14,
        contract_value=15_500_000,  # [P5] +29% variation
        original_tender_value=12_000_000,
        value_variation_pct=29.2,
        status=ContractStatus.ACTIVE,
        variation_count=2,
        awarded_days_ago=5,
    ),
    dict(
        tender_idx=22,
        supplier_idx=12,
        contract_value=9_800_000,  # [P5] +51% — HIGH severity variation
        original_tender_value=6_500_000,
        value_variation_pct=50.8,
        status=ContractStatus.ACTIVE,
        variation_count=4,
        awarded_days_ago=3,
    ),
    # Collusion winners
    dict(
        tender_idx=18,
        supplier_idx=16,
        contract_value=295_000_000,  # [P5] +18%
        original_tender_value=250_000_000,
        value_variation_pct=18.0,
        status=ContractStatus.ACTIVE,
        variation_count=1,
        awarded_days_ago=20,
    ),
    dict(
        tender_idx=19,
        supplier_idx=16,
        contract_value=9_350_000,
        original_tender_value=9_500_000,
        value_variation_pct=-1.6,
        status=ContractStatus.ACTIVE,
        variation_count=0,
        awarded_days_ago=18,
    ),
    # Large value variation — CRITICAL [P5]
    dict(
        tender_idx=7,
        supplier_idx=12,
        contract_value=16_800_000,  # [P5] +100% — CRITICAL variation
        original_tender_value=8_400_000,
        value_variation_pct=100.0,
        status=ContractStatus.DISPUTED,
        variation_count=6,  # 6 addenda — strong manipulation signal
        awarded_days_ago=45,
    ),
    dict(
        tender_idx=23,
        supplier_idx=1,
        contract_value=2_520_000_000,  # [P5] +40%
        original_tender_value=1_800_000_000,
        value_variation_pct=40.0,
        status=ContractStatus.ACTIVE,
        variation_count=3,
        awarded_days_ago=7,
    ),
]


# ── 7. DIRECTORS ──────────────────────────────────────────────────────────────
# [P6] PEP directors, [P9] cross-supplier shared directors

DIRECTORS = [
    # Clean directors
    dict(
        supplier_idx=0,
        full_name="James Mwangi Kariuki",
        national_id="12345678",
        role_title="Managing Director",
        is_politically_exposed=False,
    ),
    dict(
        supplier_idx=1,
        full_name="Grace Akinyi Otieno",
        national_id="23456789",
        role_title="Chief Executive Officer",
        is_politically_exposed=False,
    ),
    dict(
        supplier_idx=2,
        full_name="Peter Kimani Njoroge",
        national_id="34567890",
        role_title="Managing Director",
        is_politically_exposed=False,
    ),
    # PEP directors [P6]
    dict(
        supplier_idx=5,
        full_name="Hon. Samuel Kipchoge Ruto",
        national_id="45678901",
        role_title="Chairman",
        is_politically_exposed=True,
        pep_details="Former MP, Rift Valley. Brother of current county governor.",
    ),
    dict(
        supplier_idx=10,
        full_name="Hon. Elizabeth Auma Odhiambo",
        national_id="56789012",
        role_title="Director",
        is_politically_exposed=True,
        pep_details="Spouse of Cabinet Secretary, Ministry of Interior.",
    ),
    dict(
        supplier_idx=13,
        full_name="James Mwenda Kariuki",
        national_id="67890123",
        role_title="Managing Director",
        is_politically_exposed=True,
        pep_details="Son-in-law of sitting County Governor, Turkana.",
    ),
    # CROSS-SUPPLIER shared director [P9] — same person on 3 companies
    dict(
        supplier_idx=16,
        full_name="David Omondi Ochieng",
        national_id="78901234",
        role_title="Managing Director",
        is_politically_exposed=False,
    ),
    dict(
        supplier_idx=17,
        full_name="David Omondi Ochieng",
        national_id="78901234",  # [P9] same ID!
        role_title="Director",
        is_politically_exposed=False,
    ),
    dict(
        supplier_idx=18,
        full_name="David Omondi Ochieng",
        national_id="78901234",  # [P9] same ID!
        role_title="Secretary",
        is_politically_exposed=False,
    ),
    # Another cross-supplier shared director [P9]
    dict(
        supplier_idx=10,
        full_name="Mary Wanjiku Kamau",
        national_id="89012345",
        role_title="Director",
        is_politically_exposed=False,
    ),
    dict(
        supplier_idx=11,
        full_name="Mary Wanjiku Kamau",
        national_id="89012345",  # [P9]
        role_title="Director",
        is_politically_exposed=False,
    ),
    # Blacklisted supplier director
    dict(
        supplier_idx=15,
        full_name="John Njuguna Mwangi",
        national_id="90123456",
        role_title="Managing Director",
        is_politically_exposed=True,
        pep_details="Former procurement officer, convicted of bid rigging.",
    ),
]


# ── SEEDER ─────────────────────────────────────────────────────────────────────


async def seed():
    async with AsyncSessionLocal() as db:
        print("\n🌱 Seeding price benchmarks...")
        for b in BENCHMARKS:
            db.add(PriceBenchmark(**b))
        await db.flush()
        print(f"   ✓ {len(BENCHMARKS)} benchmarks")

        print("🌱 Seeding procuring entities...")
        entity_objs = []
        for e in ENTITIES:
            obj = ProcuringEntity(**e)
            db.add(obj)
            entity_objs.append(obj)
        await db.flush()
        print(f"   ✓ {len(entity_objs)} entities")

        print("🌱 Seeding suppliers...")
        supplier_objs = []
        for s in SUPPLIERS:
            data = {k: v for k, v in s.items() if k != "is_blacklisted"}
            is_blacklisted = s.get("is_blacklisted", False)
            obj = Supplier(**data, is_blacklisted=is_blacklisted)
            db.add(obj)
            supplier_objs.append(obj)
        await db.flush()
        print(f"   ✓ {len(supplier_objs)} suppliers")

        print("🌱 Seeding directors...")
        for d in DIRECTORS:
            s_idx = d.pop("supplier_idx")
            obj = Director(**d, supplier_id=supplier_objs[s_idx].id)
            db.add(obj)
            d["supplier_idx"] = s_idx  # restore for re-runs
        await db.flush()
        print(f"   ✓ {len(DIRECTORS)} directors")

        print("🌱 Seeding tenders...")
        tender_objs = []
        for t in TENDERS:
            e_idx = t.pop("entity_idx")
            dd = t.pop("deadline_days")
            obj = Tender(
                **t,
                entity_id=entity_objs[e_idx].id,
                submission_deadline=now + timedelta(days=dd),
                source="manual",
            )
            db.add(obj)
            tender_objs.append(obj)
            t["entity_idx"] = e_idx
            t["deadline_days"] = dd
        await db.flush()
        print(f"   ✓ {len(tender_objs)} tenders")

        print("🌱 Seeding bids...")
        bid_count = 0
        for t_idx, s_idx, amount, is_winner, proposal in BIDS:
            if t_idx >= len(tender_objs) or s_idx >= len(supplier_objs):
                continue
            obj = Bid(
                tender_id=tender_objs[t_idx].id,
                supplier_id=supplier_objs[s_idx].id,
                bid_amount=amount,
                is_winner=is_winner,
                status=BidStatus.AWARDED if is_winner else BidStatus.SUBMITTED,
                proposal_text=proposal,
                submitted_at=now - timedelta(days=2),
            )
            db.add(obj)
            bid_count += 1
        await db.flush()
        print(f"   ✓ {bid_count} bids")

        print("🌱 Seeding contracts...")
        contract_count = 0
        for c in CONTRACTS:
            t_idx = c["tender_idx"]
            s_idx = c["supplier_idx"]
            if t_idx >= len(tender_objs) or s_idx >= len(supplier_objs):
                continue
            obj = Contract(
                tender_id=tender_objs[t_idx].id,
                supplier_id=supplier_objs[s_idx].id,
                contract_value=c["contract_value"],
                original_tender_value=c["original_tender_value"],
                value_variation_pct=c["value_variation_pct"],
                status=c["status"],
                variation_count=c["variation_count"],
                awarded_at=now - timedelta(days=c["awarded_days_ago"]),
                currency="KES",
            )
            db.add(obj)
            contract_count += 1
        await db.flush()
        print(f"   ✓ {contract_count} contracts")

        await db.commit()

        print("\n✅ Seed complete!")
        print(
            f"   {len(BENCHMARKS)} benchmarks | {len(entity_objs)} entities | "
            f"{len(supplier_objs)} suppliers | {len(DIRECTORS)} directors"
        )
        print(
            f"   {len(tender_objs)} tenders | {bid_count} bids | {contract_count} contracts"
        )
        print("\n🔍 Key fraud patterns seeded:")
        print(
            "   [P1] Price inflation    → tenders idx 5,6,7,8,9,10,36 (2–5× benchmark)"
        )
        print(
            "   [P2] Ghost suppliers    → suppliers idx 10–14 (age<180d, no filings/address)"
        )
        print("   [P3] Spec restriction   → tenders idx 5,11,12,13,14,23,46")
        print(
            "   [P4] Bid collusion      → tenders idx 18,19,20 (near-identical proposals)"
        )
        print(
            "   [P5] Contract variation → contracts with >25% value increase + addenda"
        )
        print(
            "   [P6] PEP directors      → suppliers idx 5,10,13,15 (politically exposed)"
        )
        print("   [P7] Direct procurement → tenders idx 5,6,7,10,15,16,17,40")
        print("   [P8] Short deadline     → tenders idx 10,13,14,15,16,17,23,24")
        print(
            "   [P9] Shared directors   → David Omondi on suppliers 16,17,18 (national_id match)"
        )
        print("\n📋 Suggested API test sequence:")
        print(
            "   POST /api/risk/compute/{tender_5_id}   ← laptops, should score CRITICAL"
        )
        print(
            "   POST /api/risk/compute/{tender_23_id}  ← hospital, should score CRITICAL"
        )
        print(
            "   GET  /api/tenders/{tender_18_id}/collusion-analysis  ← should flag 3 bidders"
        )
        print(
            "   GET  /api/suppliers/{supplier_11_id}   ← Phantom Contractors, score ~95"
        )
        print("   GET  /api/dashboard/stats")
        print("   GET  /api/dashboard/heatmap")
        print(
            "\n   Tender/supplier IDs are printed to DB or retrieve via GET /api/tenders\n"
        )


async def teardown():
    async with AsyncSessionLocal() as db:
        print("🗑️  Tearing down seed data...")
        for model in [
            Bid,
            Contract,
            Director,
            Tender,
            Supplier,
            ProcuringEntity,
            PriceBenchmark,
        ]:
            await db.execute(delete(model))
        await db.commit()
        print("✅ All seed data removed.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "teardown":
        asyncio.run(teardown())
    else:
        asyncio.run(seed())
