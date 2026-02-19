import enum


class UserRole(str, enum.Enum):
    """User roles in the system"""

    ADMIN = "admin"
    INVESTIGATOR = "investigator"
    SUPPLIER = "supplier"
    PROCUREMENT_OFFICER = "procurement_officer"


class ReportCategory(str, enum.Enum):
    PRICE_INFLATION = "price_inflation"
    GHOST_SUPPLIER = "ghost_supplier"
    CONFLICT_OF_INTEREST = "conflict_of_interest"
    BRIBERY = "bribery"


class ReportStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ReportPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AlertFlagType(str, enum.Enum):
    PRICE_INFLATION = "price_inflation"
    GHOST_SUPPLIER = "ghost_supplier"
    SPECIFICATION_TAILORING = "specification_tailoring"
    CONFLICT_OF_INTEREST = "conflict_of_interest"
    CARTEL_ACTIVITY = "cartel_activity"


class AlertSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalysisType(str, enum.Enum):
    PRICE_INFLATION = "price_inflation"
    SUPPLIER_VERIFICATION = "supplier_verification"
    SPECIFICATION_ANALYSIS = "specification_analysis"
    NETWORK_ANALYSIS = "network_analysis"
    ML_RISK_SCORING = "ml_risk_scoring"


class RiskLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NetworkNodeType(str, enum.Enum):
    SUPPLIER = "supplier"
    DIRECTOR = "director"
    OFFICIAL = "official"
    COMPANY = "company"


class NetworkRelationshipType(str, enum.Enum):
    DIRECTOR = "director"
    SHAREHOLDER = "shareholder"
    EMPLOYEE = "employee"
    FAMILY_MEMBER = "family_member"


class TenderStatus(str, enum.Enum):
    PUBLISHED = "published"
    AWARDED = "awarded"
    CANCELLED = "cancelled"


class VerificationCheckType(str, enum.Enum):
    REGISTRATION_AGE = "registration_age"
    PHYSICAL_ADDRESS = "physical_address"
    TAX_COMPLIANCE = "tax_compliance"
    NCA_REGISTRATION = "nca_registration"
    DIRECTOR_VERIFICATION = "director_verification"
    BLACKLIST_CHECK = "blacklist_check"
