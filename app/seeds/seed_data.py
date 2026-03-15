"""
Procurement (Uwazi) — Seed Data Definitions

Single source of truth for all permissions, roles, and their mappings.
Used by both the seeder and tests.

Roles in this system:
    - investigator    Reviews flagged tenders, manages cases, resolves alerts
    - admin           Full system access
    - data_scientist  ML features, model registry, and scoring
    - auditor         Read-only compliance access

Adding a new permission:
    1. Add it to PERMISSIONS with a category and description.
    2. Add it to the appropriate role(s) in ROLE_PERMISSION_MAP.
    3. Run: python -m app.db.seeds.run

Adding a new role:
    1. Add it to ROLES.
    2. Add a key for it in ROLE_PERMISSION_MAP with its permission list.
    3. Run: python -m app.db.seeds.run
"""

# ── Permissions ───────────────────────────────────────────────────────────────
# Format: { "name": ("category", "human-readable description") }

PERMISSIONS: dict[str, tuple[str, str]] = {
    # ── Tenders ──────────────────────────────────────────────────────────────
    "create_tender": ("tenders", "Create new tenders"),
    "view_tender": ("tenders", "View tender records and metadata"),
    "update_tender": ("tenders", "Update tender status and details"),
    "delete_tender": ("tenders", "Delete or archive a tender record"),
    "score_tender": ("tenders", "Trigger or re-trigger fraud scoring on a tender"),
    # ── Fraud & Risk Scores ───────────────────────────────────────────────────
    "view_score": ("fraud", "View fraud scores, risk levels, and red flags"),
    "view_risk_narrative": (
        "fraud",
        "View AI-generated risk narrative and investigation memo",
    ),
    "trigger_risk_analysis": (
        "fraud",
        "Manually trigger full risk recomputation on a tender",
    ),
    "view_red_flags": ("fraud", "View individual red flags and their evidence"),
    # ── Investigation Cases ───────────────────────────────────────────────────
    "create_case": ("cases", "Open a new fraud investigation case"),
    "view_case": ("cases", "View case details and timeline"),
    "assign_case": ("cases", "Assign a case to an investigator"),
    "update_case": ("cases", "Update case status, add notes, and resolve alerts"),
    "close_case": ("cases", "Close or archive a resolved investigation case"),
    "view_investigation_pkg": (
        "cases",
        "Access the AI-generated EACC investigation package",
    ),
    # ── AI / ML Models & Features ─────────────────────────────────────────────
    "view_features": ("ml", "View engineered ML features for a tender"),
    "manage_features": ("ml", "Recompute and override engineered ML features"),
    "view_models": ("ml", "View registered ML model versions and status"),
    "deploy_model": ("ml", "Register and deploy new ML model versions"),
    "train_model": ("ml", "Trigger model training or synthetic bootstrap"),
    "view_ml_status": ("ml", "View live status of all ML models"),
    "view_collusion_analysis": ("ml", "Access TF-IDF collusion analysis for a tender"),
    "view_spending_forecast": (
        "ml",
        "View Prophet-based procurement spending forecasts",
    ),
    # ── Suppliers & Bids ─────────────────────────────────────────────────────
    "view_supplier": ("suppliers", "View supplier profiles and risk scores"),
    "create_supplier": ("suppliers", "Add a new supplier to the system"),
    "update_supplier": ("suppliers", "Update supplier details and verification status"),
    "view_bids": ("suppliers", "View all bids submitted on a tender"),
    "view_supplier_risk": (
        "suppliers",
        "View supplier ghost-company risk profile and director network",
    ),
    # ── Whistleblower Reports ─────────────────────────────────────────────────
    "view_whistleblower": ("whistleblower", "View anonymised whistleblower reports"),
    "triage_whistleblower": (
        "whistleblower",
        "Review and update AI triage on whistleblower reports",
    ),
    "submit_whistleblower": (
        "whistleblower",
        "Submit an anonymous whistleblower report (public)",
    ),
    # ── Audit Logs & Analytics ────────────────────────────────────────────────
    "view_audit_logs": ("audit", "View the immutable system audit trail"),
    "view_analytics": ("analytics", "Access dashboard KPIs and county-level analytics"),
    "view_heatmap": ("analytics", "View county risk heatmap and geographic breakdown"),
    # ── User Management (admin only) ──────────────────────────────────────────
    "manage_users": ("admin", "Create users, assign roles, and deactivate accounts"),
    "manage_roles": ("admin", "Create and modify role-permission assignments"),
    "view_users": ("admin", "View all system users and their roles"),
}


# ── Roles ─────────────────────────────────────────────────────────────────────
# Format: { "name": ("display_name", "description", is_system_role) }

ROLES: dict[str, tuple[str, str, bool]] = {
    "investigator": (
        "Investigator",
        "Reviews flagged tenders, opens and manages fraud investigation cases, "
        "accesses AI risk narratives and EACC investigation packages, and resolves alerts",
        True,
    ),
    "data_scientist": (
        "Data Scientist",
        "Access to ML features, model registry, training triggers, "
        "collusion analysis, and spending forecasts",
        True,
    ),
    "auditor": (
        "Auditor",
        "Read-only compliance access to audit logs, analytics, risk scores, "
        "and tender records — cannot modify any data",
        True,
    ),
    "admin": (
        "Administrator",
        "Full system access including user management, role configuration, "
        "model deployment, and all investigative features",
        True,
    ),
}


# ── Role → Permission Mapping ─────────────────────────────────────────────────

ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "investigator": [
        # Tenders
        "view_tender",
        "update_tender",
        "score_tender",
        # Fraud & risk
        "view_score",
        "view_risk_narrative",
        "trigger_risk_analysis",
        "view_red_flags",
        # Cases
        "create_case",
        "view_case",
        "assign_case",
        "update_case",
        "close_case",
        "view_investigation_pkg",
        # Suppliers & bids
        "view_supplier",
        "view_bids",
        "view_supplier_risk",
        # Whistleblower
        "view_whistleblower",
        "triage_whistleblower",
        # Analytics & audit
        "view_analytics",
        "view_heatmap",
        "view_audit_logs",
        # ML (read-only)
        "view_features",
        "view_ml_status",
        "view_collusion_analysis",
        "view_spending_forecast",
    ],
    "data_scientist": [
        # Tenders
        "view_tender",
        "score_tender",
        # Fraud & risk
        "view_score",
        "view_risk_narrative",
        "trigger_risk_analysis",
        "view_red_flags",
        # ML (full access)
        "view_features",
        "manage_features",
        "view_models",
        "deploy_model",
        "train_model",
        "view_ml_status",
        "view_collusion_analysis",
        "view_spending_forecast",
        # Suppliers & bids (read-only)
        "view_supplier",
        "view_bids",
        "view_supplier_risk",
        # Analytics
        "view_analytics",
        "view_heatmap",
    ],
    "auditor": [
        # Read-only across all relevant areas
        "view_tender",
        "view_score",
        "view_risk_narrative",
        "view_red_flags",
        "view_case",
        "view_supplier",
        "view_bids",
        "view_supplier_risk",
        "view_whistleblower",
        "view_audit_logs",
        "view_analytics",
        "view_heatmap",
        "view_ml_status",
        "view_users",
    ],
    "admin": [
        # Full access — all permissions
        *PERMISSIONS.keys(),
    ],
}


# ── Validation (runs at import time) ──────────────────────────────────────────
# Catches misconfigured mappings before the seeder runs.

_all_permission_names = set(PERMISSIONS.keys())
_all_role_names = set(ROLES.keys())

for _role, _perms in ROLE_PERMISSION_MAP.items():
    if _role not in _all_role_names:
        raise ValueError(
            f"ROLE_PERMISSION_MAP references unknown role: '{_role}'. "
            f"Add it to ROLES first."
        )
    _unknown = set(_perms) - _all_permission_names
    if _unknown:
        raise ValueError(
            f"Role '{_role}' references unknown permission(s): {_unknown}. "
            f"Add them to PERMISSIONS first."
        )


# ── Default Superuser ──────────────────────────────────────────────────────────
# Only created if no superuser exists.
# Values are loaded from environment variables — never hardcode credentials here.
# Required variables in your .env file:
#   SUPERUSER_EMAIL
#   SUPERUSER_FULL_NAME
#   SUPERUSER_PASSWORD

import os

from dotenv import load_dotenv

load_dotenv()

_email = os.getenv("SUPERUSER_EMAIL")
_name = os.getenv("SUPERUSER_FULL_NAME")
_password = os.getenv("SUPERUSER_PASSWORD")

_missing = [
    k
    for k, v in {
        "SUPERUSER_EMAIL": _email,
        "SUPERUSER_FULL_NAME": _name,
        "SUPERUSER_PASSWORD": _password,
    }.items()
    if not v
]

if _missing:
    raise EnvironmentError(
        f"Missing required environment variable(s): {', '.join(_missing)}\n"
        "Add them to your .env file before running the seeder."
    )

DEFAULT_SUPERUSER = {
    "email": _email,
    "full_name": _name,
    "password": _password,
    "is_superuser": True,
    "role": "admin",
}
