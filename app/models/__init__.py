"""
app/models/__init__.py
──────────────────────
Model registry — imports every model class so that:

  1. SQLAlchemy's mapper can discover all tables before Base.metadata.create_all()
     or Alembic autogenerate runs.

  2. Any module in the project can do:
         from app.models import Tender, Supplier, RiskScore, ...
     without knowing which file each model lives in.

  3. Enum classes are re-exported here so existing code that does
         from app.models import RiskLevel
     continues to work unchanged.

Model files (one class per file):
    user.py                 → User
    procuring_entity.py     → ProcuringEntity
    supplier.py             → Supplier
    director.py             → Director
    tender.py               → Tender
    bid.py                  → Bid
    contract.py             → Contract
    risk_score.py           → RiskScore
    red_flag.py             → RedFlag
    tender_document.py      → TenderDocument
    price_benchmark.py      → PriceBenchmark
    whistleblower_report.py → WhistleblowerReport

IMPORTANT — import order matters for foreign key resolution:
  Import parent tables before child tables that reference them.
  Current safe order: User → ProcuringEntity → Supplier → Director
                      → Tender → Bid → Contract → RiskScore
                      → RedFlag → TenderDocument → PriceBenchmark
                      → WhistleblowerReport
"""

# ── Enum re-exports (backwards compatibility) ─────────────────────────────────
from app.enums import (  # noqa: F401
    AllegationType,
    BidStatus,
    ContractStatus,
    DocumentType,
    EntityType,
    FlagSeverity,
    FlagType,
    ProcurementMethod,
    RiskLevel,
    SupplierVerificationStatus,
    TenderCategory,
    TenderStatus,
    UserRole,
    WhistleblowerUrgency,
)
from app.models.alert_model import Alert
from app.models.association_tables_model import role_permissions, user_roles
from app.models.audit_log_model import AuditLog
from app.models.bid_model import Bid  # noqa: F401
from app.models.contract_model import Contract  # noqa: F401
from app.models.director_model import Director  # noqa: F401
from app.models.permission_model import Permission
from app.models.price_benchmark_model import PriceBenchmark  # noqa: F401
from app.models.procuring_entity_model import ProcuringEntity  # noqa: F401
from app.models.red_flag_model import RedFlag  # noqa: F401
from app.models.refresh_token_model import RefreshToken
from app.models.risk_score_model import RiskScore  # noqa: F401
from app.models.role_model import Role
from app.models.supplier_model import Supplier  # noqa: F401
from app.models.tender_document_model import TenderDocument  # noqa: F401
from app.models.tender_model import Tender  # noqa: F401

# ── Models (import order = FK dependency order) ───────────────────────────────
from app.models.user_model import User  # noqa: F401
from app.models.whistleblower_report_model import WhistleblowerReport  # noqa: F401
from app.models.investigation_model import Investigation

__all__ = [
    # Models
    "Alert",
    "AuditLog",
    "RefreshToken",
    "Permission",
    "User",
    "Role",
    "ProcuringEntity",
    "Supplier",
    "Director",
    "Tender",
    "Bid",
    "Contract",
    "RiskScore",
    "RedFlag",
    "TenderDocument",
    "PriceBenchmark",
    "WhistleblowerReport",
    # Association tables
    "user_roles",
    "role_permissions",
    # Enums
    "AllegationType",
    "BidStatus",
    "ContractStatus",
    "DocumentType",
    "EntityType",
    "FlagSeverity",
    "FlagType",
    "ProcurementMethod",
    "RiskLevel",
    "SupplierVerificationStatus",
    "TenderCategory",
    "TenderStatus",
    "UserRole",
    "WhistleblowerUrgency",
    "Investigation",
]
