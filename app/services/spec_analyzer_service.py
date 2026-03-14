"""
Tender Specification Restrictiveness Analyzer
MVP: keyword/regex-based analysis.
Enhanced: delegates to AI service for deeper analysis.
"""

import re
from typing import Optional

# Restrictive patterns based on PPADA violations commonly seen in Kenya
RESTRICTIVE_PATTERNS = [
    # Brand specification
    (
        r"\b(must be|only|exclusively)\s+(hp|dell|lenovo|samsung|cisco|oracle|sap|microsoft)\b",
        "brand_specific",
        "high",
        "Specifies brand name — limits competition",
    ),
    (
        r"\bspecific(ally)?\s+brand\b",
        "brand_specific",
        "high",
        "Explicitly requires specific brand",
    ),
    (
        r"\b(hp|dell|lenovo|cisco)\s+(brand|products?|equipment)\b",
        "brand_specific",
        "medium",
        "Brand name mentioned in requirements",
    ),
    # Excessive experience
    (
        r"minimum\s+(of\s+)?(15|20|25|30)\s+years",
        "excessive_experience",
        "high",
        "Excessive experience requirement (15+ years)",
    ),
    (
        r"at\s+least\s+(15|20|25|30)\s+years",
        "excessive_experience",
        "high",
        "Excessive experience requirement (15+ years)",
    ),
    (
        r"minimum\s+(of\s+)?(10|12)\s+years",
        "excessive_experience",
        "medium",
        "High experience requirement (10-12 years)",
    ),
    # Impossibly short deadlines
    (
        r"deliver(y|ed)?\s+within\s+(24|48)\s+hours",
        "short_deadline",
        "high",
        "24-48 hour delivery requirement limits competition",
    ),
    (
        r"submission\s+deadline.{0,30}(24|48)\s+hours",
        "short_deadline",
        "high",
        "Very short submission window",
    ),
    # Geographic restriction
    (
        r"(headquartered|registered|located|based)\s+in\s+nairobi\s+only",
        "geographic_restriction",
        "medium",
        "Geographic restriction to Nairobi only",
    ),
    # Single-source indicators
    (
        r"(sole|only|exclusive)\s+(authorized|certified|approved)\s+(dealer|agent|distributor)",
        "single_source",
        "critical",
        "Sole authorized dealer/agent requirement — single source",
    ),
    # Turnover thresholds sometimes used to exclude smaller firms
    (
        r"annual\s+turnover\s+of\s+(ksh|kes|ksh\.?)\s*[5-9]\d{8,}",
        "financial_barrier",
        "medium",
        "Very high turnover threshold may exclude legitimate bidders",
    ),
]


def analyze_specs_keywords(spec_text: str) -> dict:
    """
    Fast keyword/regex based spec analysis.
    Returns {score, issues, flags}
    """
    if not spec_text:
        return {"score": 0.0, "issues": [], "flags": []}

    text_lower = spec_text.lower()
    issues = []
    flags = []
    score = 0.0

    severity_scores = {"critical": 35, "high": 20, "medium": 10, "low": 5}

    for pattern, issue_type, severity, description in RESTRICTIVE_PATTERNS:
        matches = re.findall(pattern, text_lower)
        if matches:
            excerpt_match = re.search(pattern, text_lower)
            if excerpt_match:
                start = max(0, excerpt_match.start() - 30)
                end = min(len(spec_text), excerpt_match.end() + 30)
                excerpt = "..." + spec_text[start:end] + "..."
            else:
                excerpt = ""

            issues.append(
                {
                    "type": issue_type,
                    "severity": severity,
                    "description": description,
                    "excerpt": excerpt.strip(),
                }
            )
            flags.append(f"{severity.upper()}: {description}")
            score += severity_scores.get(severity, 5)

    return {
        "score": min(score, 100.0),
        "issues": issues,
        "flags": flags,
        "issue_count": len(issues),
    }


def compute_spec_score(
    spec_text: Optional[str], use_ai: bool = False, tender_value: Optional[float] = None
) -> dict:
    """
    Main spec analysis entry point.
    use_ai=True: also calls Claude for deeper analysis.
    """
    if not spec_text:
        return {"score": 0.0, "flags": [], "issues": [], "ai_analysis": None}

    # Base keyword analysis (fast, free)
    keyword_result = analyze_specs_keywords(spec_text)

    ai_result = None
    if use_ai and len(spec_text) > 100:
        try:
            from app.services.ai_service import analyze_tender_specifications

            ai_result = analyze_tender_specifications(spec_text, tender_value)
            # Use AI score if higher than keyword score
            ai_score = ai_result.get("restrictiveness_score", 0)
            final_score = max(keyword_result["score"], ai_score)
        except Exception:
            final_score = keyword_result["score"]
    else:
        final_score = keyword_result["score"]

    return {
        "score": final_score,
        "flags": keyword_result["flags"],
        "issues": keyword_result["issues"],
        "ai_analysis": ai_result,
    }
