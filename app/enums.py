"""
app/enums.py
────────────
All application-wide Python enumerations.

Import from here in models, schemas, and routes to avoid circular imports
and keep enum definitions in a single source of truth.

Usage:
    from app.enums import RiskLevel, TenderStatus, ProcurementMethod, ...
"""

import enum

# ══════════════════════════════════════════════════════════════════════════════
# Risk & Corruption
# ══════════════════════════════════════════════════════════════════════════════


class RiskLevel(str, enum.Enum):
    """Composite corruption risk level assigned to a tender."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_score(cls, score: float) -> "RiskLevel":
        """Derive risk level from a 0-100 numeric score."""
        if score >= 80:
            return cls.CRITICAL
        if score >= 60:
            return cls.HIGH
        if score >= 40:
            return cls.MEDIUM
        return cls.LOW


class FlagType(str, enum.Enum):
    """Categories of detected red flags."""

    PRICE_INFLATION = "price_inflation"
    GHOST_SUPPLIER = "ghost_supplier"
    BID_RIGGING = "bid_rigging"
    SPEC_RESTRICTION = "spec_restriction"
    SINGLE_SOURCE = "single_source"
    COLLUSION = "collusion"
    KICKBACK = "kickback"
    CONTRACT_VARIATION = "contract_variation"
    DEADLINE_MANIPULATION = "deadline_manipulation"
    POLITICAL_PROXIMITY = "political_proximity"
    OTHER = "other"


class FlagSeverity(str, enum.Enum):
    """Severity of an individual red flag."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ══════════════════════════════════════════════════════════════════════════════
# Tender
# ══════════════════════════════════════════════════════════════════════════════


class TenderStatus(str, enum.Enum):
    """Lifecycle status of a tender."""

    DRAFT = "draft"
    PUBLISHED = "published"
    OPEN = "open"
    CLOSED = "closed"
    EVALUATED = "evaluated"
    AWARDED = "awarded"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class ProcurementMethod(str, enum.Enum):
    """
    Kenya Public Procurement and Asset Disposal Act 2015 — procurement methods.
    Reference: PPADA 2015 Part IV
    """

    OPEN_TENDER = "open_tender"
    RESTRICTED_TENDER = "restricted_tender"
    DIRECT_PROCUREMENT = "direct_procurement"
    REQUEST_FOR_QUOTATION = "request_for_quotation"
    REQUEST_FOR_PROPOSAL = "request_for_proposal"
    DESIGN_COMPETITION = "design_competition"
    LOW_VALUE_PROCUREMENT = "low_value_procurement"
    FORCE_ACCOUNT = "force_account"


class TenderCategory(str, enum.Enum):
    """Broad procurement category used for benchmarking."""

    WORKS = "works"  # construction, civil engineering
    GOODS = "goods"  # equipment, supplies
    SERVICES = "services"  # consultancy, professional services
    NON_CONSULTANCY = "non_consultancy"  # cleaning, security, transport
    ICT = "ict"  # software, hardware, IT services
    HEALTH = "health"  # drugs, medical equipment
    EDUCATION = "education"  # textbooks, school furniture


# ══════════════════════════════════════════════════════════════════════════════
# Supplier / Company
# ══════════════════════════════════════════════════════════════════════════════


class SupplierVerificationStatus(str, enum.Enum):
    """KRA / eCitizen verification state of a supplier."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    BLACKLISTED = "blacklisted"
    DEREGISTERED = "deregistered"


class EntityType(str, enum.Enum):
    """Classification of a procuring entity."""

    MINISTRY = "ministry"
    STATE_DEPARTMENT = "state_department"
    COUNTY_GOVERNMENT = "county_government"
    STATE_CORPORATION = "state_corporation"
    INDEPENDENT_OFFICE = "independent_office"
    CONSTITUTIONAL_COMMISSION = "constitutional_commission"


# ══════════════════════════════════════════════════════════════════════════════
# Bid
# ══════════════════════════════════════════════════════════════════════════════


class BidStatus(str, enum.Enum):
    """Evaluation status of a submitted bid."""

    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    AWARDED = "awarded"
    WITHDRAWN = "withdrawn"


# ══════════════════════════════════════════════════════════════════════════════
# Document
# ══════════════════════════════════════════════════════════════════════════════


class DocumentType(str, enum.Enum):
    """Type of document attached to a tender."""

    TENDER_NOTICE = "tender_notice"
    BIDDING_DOCUMENT = "bidding_document"
    ADDENDUM = "addendum"
    BID_SUBMISSION = "bid_submission"
    EVALUATION_REPORT = "evaluation_report"
    CONTRACT = "contract"
    COMPLETION_CERTIFICATE = "completion_certificate"
    INVOICE = "invoice"
    OTHER = "other"


# ══════════════════════════════════════════════════════════════════════════════
# Contract
# ══════════════════════════════════════════════════════════════════════════════


class ContractStatus(str, enum.Enum):
    """Status of an awarded contract."""

    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    DISPUTED = "disputed"
    SUSPENDED = "suspended"


# ══════════════════════════════════════════════════════════════════════════════
# Whistleblower
# ══════════════════════════════════════════════════════════════════════════════


class AllegationType(str, enum.Enum):
    """Allegation categories for whistleblower reports."""

    PRICE_INFLATION = "price_inflation"
    GHOST_SUPPLIER = "ghost_supplier"
    BID_RIGGING = "bid_rigging"
    KICKBACK = "kickback"
    SPEC_MANIPULATION = "spec_manipulation"
    BRIBERY = "bribery"
    CONFLICT_OF_INTEREST = "conflict_of_interest"
    FRAUD = "fraud"
    OTHER = "other"


class WhistleblowerUrgency(str, enum.Enum):
    """AI-triaged urgency level of a whistleblower report."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ══════════════════════════════════════════════════════════════════════════════
# User / Auth
# ══════════════════════════════════════════════════════════════════════════════


class UserRole(str, enum.Enum):
    """
    System roles.
    - viewer:       read-only access to public data
    - investigator: can trigger risk analysis, access investigation packages,
                    review whistleblower reports
    - admin:        full access including user management, ML training,
                    scraper control, and data management
    """

    VIEWER = "viewer"
    INVESTIGATOR = "investigator"
    ADMIN = "admin"


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


# ---------------------------------------------------------------------------
# RBAC / Auth Domain
# ---------------------------------------------------------------------------


class TokenType(str, enum.Enum):
    """JWT token classification."""

    ACCESS = "access"
    REFRESH = "refresh"


# ---------------------------------------------------------------------------
# Audit Domain
# ---------------------------------------------------------------------------


class AuditAction(str, enum.Enum):
    """Standardised action codes for the audit log."""

    # Auth
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESHED = "TOKEN_REFRESHED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"

    # User management
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    ROLE_ASSIGNED = "ROLE_ASSIGNED"
    ROLE_REMOVED = "ROLE_REMOVED"

    # Fraud
    CLAIM_SCORED = "CLAIM_SCORED"
    SCORE_OVERRIDDEN = "SCORE_OVERRIDDEN"

    # Cases
    CASE_CREATED = "CASE_CREATED"
    CASE_ASSIGNED = "CASE_ASSIGNED"
    CASE_STATUS_UPDATED = "CASE_STATUS_UPDATED"
    CASE_NOTE_ADDED = "CASE_NOTE_ADDED"
    CASE_CLOSED = "CASE_CLOSED"

    # Admin
    RULE_CREATED = "RULE_CREATED"
    RULE_UPDATED = "RULE_UPDATED"
    RULE_TOGGLED = "RULE_TOGGLED"
    MODEL_REGISTERED = "MODEL_REGISTERED"
    MODEL_DEPLOYED = "MODEL_DEPLOYED"
