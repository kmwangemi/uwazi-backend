"""
Procurement — Seed Data Definitions

Single source of truth for all permissions, roles, and their mappings.
Used by both the seeder and tests.

Adding a new permission:
    1. Add it to PERMISSIONS with a category and description.
    2. Add it to the appropriate role in ROLE_PERMISSION_MAP.
    3. Run: python -m app.db.seeds.run

Adding a new role:
    1. Add it to ROLES.
    2. Add a key for it in ROLE_PERMISSION_MAP with its permission list.
    3. Run: python -m app.seeds.run
"""

# ── Permissions ───────────────────────────────────────────────────────────────
# Format: { "name": ("category", "human-readable description") }

PERMISSIONS: dict[str, tuple[str, str]] = {
    # Tenders
    "create_tender": ("tenders", "Create new tenders"),
    "view_tender": ("tenders", "View tender records and metadata"),
    "update_tender": ("tenders", "Update tender status and approved amounts"),
    "score_tender": ("tenders", "Trigger or re-trigger fraud scoring on a tender"),
    # Features
    "view_features": ("features", "View engineered ML features for a tender"),
    "manage_features": ("features", "Recompute and override engineered features"),
    # Fraud & Scores
    "view_score": ("fraud", "View fraud scores, explanations, and alerts"),
    # Cases
    "create_case": ("cases", "Open a new fraud investigation case"),
    "assign_case": ("cases", "Assign a case to an analyst"),
    "update_case": ("cases", "Update case status, add notes, resolve alerts"),
    # Admin — Rules
    "manage_rules": ("admin", "Create, update, and toggle fraud detection rules"),
    # Admin — Models
    "view_models": ("admin", "View registered ML model versions"),
    "deploy_model": ("admin", "Register and deploy ML model versions"),
    # Admin — Users
    "manage_users": ("admin", "Create users, assign roles, deactivate accounts"),
    # Analytics
    "view_analytics": ("analytics", "Access dashboard KPIs and provider analytics"),
    # Audit
    "view_audit_logs": ("audit", "View the immutable system audit trail"),
    # Bids
    "submit_bid": ("bids", "Submit a bid on an open tender"),
    "view_bids": ("bids", "View bids submitted on a tender"),
    "update_bid": ("bids", "Edit or withdraw a submitted bid before the deadline"),
    "view_own_bids": ("bids", "View own submitted bids and their evaluation status"),
}


# ── Roles ─────────────────────────────────────────────────────────────────────
# Format: { "name": ("display_name", "description", is_system_role) }

ROLES: dict[str, tuple[str, str, bool]] = {
    "investigator": (
        "Investigator",
        "Reviews flagged tenders, creates and works on investigation cases, and resolves alerts",
        True,
    ),
    "supplier": (
        "Supplier",
        "Submits bids, views own tender status and procurement notices",
        True,
    ),
    "procurement_officer": (
        "Procurement Officer",
        "Creates and manages tenders, reviews submissions, and oversees the procurement lifecycle",
        True,
    ),
    "admin": (
        "Administrator",
        "Full system access including user management and rule configuration",
        True,
    ),
    "data_scientist": (
        "Data Scientist",
        "Access to ML features, model registry, and model deployment",
        True,
    ),
    "auditor": (
        "Auditor",
        "Read-only access to audit logs and analytics for compliance review",
        True,
    ),
}


# ── Role → Permission Mapping ─────────────────────────────────────────────────

ROLE_PERMISSION_MAP: dict[str, list[str]] = {
    "investigator": [
        "view_tender",
        "view_score",
        "view_features",
        "view_bids",
        "create_case",
        "assign_case",
        "update_case",
        "update_tender",
        "view_analytics",
        "view_audit_logs",
    ],
    "supplier": [
        "view_tender",
        "submit_bid",
        "update_bid",
        "view_own_bids",
    ],
    "procurement_officer": [
        "create_tender",
        "view_tender",
        "update_tender",
        "score_tender",
        "view_score",
        "view_bids",
        "view_analytics",
        "view_audit_logs",
    ],
    "admin": [
        # All permissions
        *PERMISSIONS.keys(),
    ],
    "data_scientist": [
        "view_tender",
        "view_score",
        "view_features",
        "manage_features",
        "score_tender",
        "view_models",
        "deploy_model",
        "view_analytics",
    ],
    "auditor": [
        "view_audit_logs",
        "view_analytics",
        "view_tender",
        "view_score",
    ],
}


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
}
