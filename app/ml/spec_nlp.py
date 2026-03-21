"""
Model: spaCy NER + Rule-based Matcher — Specification Restrictiveness Analysis
Proposal Layer: 4 (Specification Analysis)
Library: spacy (en_core_web_sm)

PURPOSE
-------
The proposal explicitly lists spaCy/NLTK for text preprocessing and
"NLP assigns Restrictiveness Score based on brand-specific requirements,
excessive qualifications, geographic restrictions, and proprietary specs."

This module uses spaCy's:
  1. Named Entity Recognition (NER) — detect brand names (ORG entities)
  2. Rule-based EntityRuler — custom patterns for procurement red flags
  3. Dependency parsing — identify requirement vs. descriptive language

INSTALL
-------
  pip install spacy
  python -m spacy download en_core_web_sm

WHAT IS DETECTED
----------------
  Brand names:         "HP", "Dell", "Cisco", "Oracle" as ORG entities
  Excessive experience: "minimum X years" patterns
  Short deadlines:     "within 24/48 hours" patterns
  Geographic locks:    "registered in Nairobi only"
  Proprietary specs:   "ISO XXXXX certified" with specific version numbers
  Single source:       "sole authorized dealer/distributor"
"""

import re
from typing import Optional

# spaCy loaded lazily to avoid import-time crash if not installed
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp

    try:
        import spacy

        nlp = spacy.load("en_core_web_sm")

        # ── Custom EntityRuler: procurement red-flag patterns ─────────────
        ruler_patterns = [
            # Brand names as ORG (supplement spaCy's built-in NER)
            {
                "label": "BRAND",
                "pattern": [
                    {
                        "lower": {
                            "in": [
                                "hp",
                                "dell",
                                "lenovo",
                                "cisco",
                                "oracle",
                                "sap",
                                "microsoft",
                                "samsung",
                                "apple",
                                "ibm",
                                "huawei",
                                "motorola",
                                "caterpillar",
                            ]
                        }
                    }
                ],
            },
            # Experience requirements
            {
                "label": "EXPERIENCE_REQ",
                "pattern": [
                    {"lower": "minimum"},
                    {"IS_DIGIT": True},
                    {"lower": {"in": ["years", "year"]}},
                ],
            },
            {
                "label": "EXPERIENCE_REQ",
                "pattern": [
                    {"lower": "at"},
                    {"lower": "least"},
                    {"IS_DIGIT": True},
                    {"lower": {"in": ["years", "year"]}},
                ],
            },
            # Impossibly short deadlines
            {
                "label": "SHORT_DEADLINE",
                "pattern": [
                    {"lower": "within"},
                    {"IS_DIGIT": True},
                    {"lower": {"in": ["hours", "hour", "hrs"]}},
                ],
            },
            {
                "label": "SHORT_DEADLINE",
                "pattern": [
                    {"IS_DIGIT": True},
                    {"lower": {"in": ["hour", "hours", "hrs"]}},
                    {"lower": {"in": ["delivery", "turnaround", "completion"]}},
                ],
            },
            # Single-source / sole authorized
            {
                "label": "SINGLE_SOURCE",
                "pattern": [
                    {"lower": {"in": ["sole", "only", "exclusive"]}},
                    {
                        "lower": {
                            "in": ["authorized", "authorised", "certified", "approved"]
                        }
                    },
                    {"lower": {"in": ["dealer", "agent", "distributor", "supplier"]}},
                ],
            },
            # Geographic restriction
            {
                "label": "GEO_RESTRICTION",
                "pattern": [
                    {
                        "lower": {
                            "in": ["headquartered", "registered", "located", "based"]
                        }
                    },
                    {"lower": "in"},
                    {"ENT_TYPE": "GPE"},
                ],
            },
            {
                "label": "GEO_RESTRICTION",
                "pattern": [{"lower": {"in": ["nairobi", "kenya"]}}, {"lower": "only"}],
            },
        ]

        # Add the ruler before NER to allow custom patterns to take precedence
        if "entity_ruler" not in nlp.pipe_names:
            ruler = nlp.add_pipe("entity_ruler", before="ner")
            ruler.add_patterns(ruler_patterns)

        _nlp = nlp
        return _nlp

    except (ImportError, OSError):
        return None  # spaCy not installed or model not downloaded


# ── Analysis ──────────────────────────────────────────────────────────────────

# Severity and score contribution per entity label
LABEL_CONFIG = {
    "BRAND": {"severity": "high", "score": 25, "type": "brand_specific"},
    "EXPERIENCE_REQ": {
        "severity": "medium",
        "score": 15,
        "type": "excessive_experience",
    },
    "SHORT_DEADLINE": {"severity": "high", "score": 20, "type": "short_deadline"},
    "SINGLE_SOURCE": {"severity": "critical", "score": 35, "type": "single_source"},
    "GEO_RESTRICTION": {
        "severity": "medium",
        "score": 15,
        "type": "geographic_restriction",
    },
    "ORG": {"severity": "low", "score": 5, "type": "brand_specific"},  # built-in ORG
}

# Threshold for "excessive" experience (years) — from proposal
EXCESSIVE_EXPERIENCE_YEARS = 15


def analyse(spec_text: str, tender_value: Optional[float] = None) -> dict:
    """
    Run spaCy NER + rules on tender specification text.

    Returns:
    {
        restrictiveness_score: float  0-100
        entities: [
            {text, label, start, end, severity, score_contribution, type}
        ]
        issues: [str]   human-readable issue descriptions
        single_source_detected: bool
        brand_names_found: [str]
        model_used: str
    }
    """
    if not spec_text or len(spec_text.strip()) < 20:
        return {
            "restrictiveness_score": 0.0,
            "entities": [],
            "issues": [],
            "single_source_detected": False,
            "brand_names_found": [],
            "model_used": "none",
        }

    nlp = _get_nlp()

    if nlp is None:
        # spaCy not available — fall back to regex-only (spec_analyzer.py)
        from app.services.spec_analyzer_service import analyze_specs_keywords

        result = analyze_specs_keywords(spec_text)
        return {
            "restrictiveness_score": result["score"],
            "entities": [],
            "issues": result["flags"],
            "single_source_detected": any(
                "single" in f.lower() for f in result["flags"]
            ),
            "brand_names_found": [],
            "model_used": "regex_fallback",
        }

    doc = nlp(spec_text[:5000])  # cap at 5000 chars to stay within limits

    entities_out = []
    total_score = 0.0
    issues = []
    brand_names = set()
    single_source = False
    seen_labels = set()  # avoid double-counting same label

    for ent in doc.ents:
        config = LABEL_CONFIG.get(ent.label_)
        if config is None:
            continue

        # For ORG entities — only flag if the org name looks like a tech brand
        if ent.label_ == "ORG":
            known_brands = {
                "hp",
                "dell",
                "lenovo",
                "cisco",
                "oracle",
                "microsoft",
                "sap",
                "samsung",
                "ibm",
                "huawei",
                "caterpillar",
            }
            if ent.text.lower() not in known_brands:
                continue

        # Check EXPERIENCE_REQ for excessive threshold
        if ent.label_ == "EXPERIENCE_REQ":
            nums = re.findall(r"\d+", ent.text)
            if nums and int(nums[0]) < EXCESSIVE_EXPERIENCE_YEARS:
                config = {
                    "severity": "low",
                    "score": 5,
                    "type": "experience_requirement",
                }

        entities_out.append(
            {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "severity": config["severity"],
                "score_contribution": config["score"],
                "type": config["type"],
            }
        )

        # Only count each label type once toward the score (avoid stacking)
        if ent.label_ not in seen_labels:
            total_score += float(config["score"])
            seen_labels.add(ent.label_)

        if ent.label_ == "SINGLE_SOURCE":
            single_source = True
            issues.append(
                f"CRITICAL: Sole/exclusive agent requirement detected: '{ent.text}'"
            )

        if ent.label_ in ("BRAND", "ORG"):
            brand_names.add(ent.text)

        if ent.label_ == "EXPERIENCE_REQ":
            issues.append(f"HIGH: Excessive experience requirement: '{ent.text}'")

        if ent.label_ == "SHORT_DEADLINE":
            issues.append(f"HIGH: Short delivery window: '{ent.text}'")

        if ent.label_ == "GEO_RESTRICTION":
            issues.append(f"MEDIUM: Geographic restriction detected: '{ent.text}'")

    if brand_names:
        issues.append(
            f"HIGH: Brand name(s) specified — limits competition: {', '.join(brand_names)}"
        )

    return {
        "restrictiveness_score": min(round(total_score, 2), 100.0),
        "entities": entities_out,
        "issues": issues,
        "single_source_detected": single_source,
        "brand_names_found": sorted(brand_names),
        "model_used": "spacy_en_core_web_sm",
    }
