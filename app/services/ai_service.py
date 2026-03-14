"""
AI Service — integrates Anthropic Claude for:
1. Tender risk narrative analysis
2. Whistleblower report triage
3. Investigation package generation
4. Natural language query interface
5. Automated red-flag explanations
"""

import json
import re
from typing import Optional

import anthropic

from app.core.config import settings


def _get_client() -> anthropic.Anthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ─────────────────────────────────────────────
# 1. Tender Risk Narrative Analysis
# ─────────────────────────────────────────────


def analyze_tender_risk(
    tender_title: str,
    tender_description: Optional[str],
    estimated_value: Optional[float],
    county: Optional[str],
    procurement_method: Optional[str],
    price_score: float,
    supplier_score: float,
    spec_score: float,
    total_score: float,
    risk_flags: list[str],
    price_benchmark_comparison: Optional[dict] = None,
) -> dict:
    """
    Sends tender data to Claude for a detailed narrative risk analysis.
    Returns: { ai_analysis, recommended_action, investigation_priority }
    """
    client = _get_client()

    flags_text = (
        "\n".join(f"- {f}" for f in risk_flags) if risk_flags else "None detected"
    )

    benchmark_text = ""
    if price_benchmark_comparison:
        benchmark_text = f"""
Price Benchmark Comparison:
- Market average: KES {price_benchmark_comparison.get('market_avg', 'N/A')}
- Tender price: KES {price_benchmark_comparison.get('tender_price', 'N/A')}
- Deviation: {price_benchmark_comparison.get('deviation_pct', 'N/A')}%
"""

    prompt = f"""You are an expert anti-corruption analyst at Kenya's Ethics and Anti-Corruption Commission (EACC).
Analyze this public procurement tender for corruption risk indicators.

TENDER DETAILS:
Title: {tender_title}
Description: {tender_description or "Not provided"}
Estimated Value: KES {estimated_value:,.0f if estimated_value else "Unknown"}
County/Entity: {county or "National"}
Procurement Method: {procurement_method or "Not specified"}

AUTOMATED RISK SCORES (0-100, higher = more suspicious):
- Price Inflation Score: {price_score:.1f}/100
- Supplier Risk Score: {supplier_score:.1f}/100  
- Specification Restrictiveness Score: {spec_score:.1f}/100
- COMPOSITE RISK SCORE: {total_score:.1f}/100
{benchmark_text}
DETECTED RED FLAGS:
{flags_text}

TASK: Provide a concise investigation-ready analysis covering:
1. PRIMARY CONCERN: What is the most likely corruption scheme at play?
2. KEY EVIDENCE: Which specific data points are most suspicious and why?
3. RECOMMENDED ACTION: What should investigators do next? (be specific)
4. LEGAL FRAMEWORK: Which Kenyan laws / PPOA regulations may have been violated?
5. URGENCY: Rate as IMMEDIATE (≤24h), URGENT (≤7 days), or ROUTINE

Be direct and actionable. Reference similar known Kenyan corruption cases where relevant (e.g., NYS scandal, Afya House, COVID PPE).
Keep response under 400 words."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    analysis_text = message.content[0].text

    # Extract recommended action (first sentence after "RECOMMENDED ACTION:")
    recommended = ""
    lines = analysis_text.split("\n")
    for i, line in enumerate(lines):
        if "RECOMMENDED ACTION" in line.upper():
            # Get next non-empty line
            for next_line in lines[i + 1 :]:
                if next_line.strip():
                    recommended = next_line.strip().lstrip(":-").strip()
                    break
            break

    return {
        "ai_analysis": analysis_text,
        "recommended_action": recommended or "Review required by investigator.",
    }


# ─────────────────────────────────────────────
# 2. Whistleblower Report Triage
# ─────────────────────────────────────────────


def triage_whistleblower_report(
    report_text: str,
    related_tender_title: Optional[str] = None,
) -> dict:
    """
    AI triage of an anonymous whistleblower report.
    Returns: { triage_summary, credibility_score, allegation_type, is_credible }
    """
    client = _get_client()

    tender_context = (
        f"\nRelated Tender: {related_tender_title}" if related_tender_title else ""
    )

    prompt = f"""You are a senior investigator at Kenya's EACC conducting triage on an anonymous whistleblower report about public procurement corruption.{tender_context}

WHISTLEBLOWER REPORT:
{report_text}

Analyze this report and respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{{
  "credibility_score": <integer 0-100>,
  "allegation_type": "<one of: price_inflation|ghost_supplier|bid_rigging|kickback|specification_manipulation|contract_variation|other>",
  "key_allegations": ["<list of specific, extractable allegations>"],
  "corroborating_evidence_needed": ["<list of specific documents/data to verify>"],
  "triage_summary": "<2-3 sentence plain English summary of what is alleged and its significance>",
  "is_credible": <true|false>,
  "urgency": "<IMMEDIATE|URGENT|ROUTINE>",
  "identity_risk": "<LOW|MEDIUM|HIGH - risk that submitter could be identified from content>"
}}

Score credibility based on: specificity of allegations, verifiable claims, consistency with known patterns, seriousness of allegation."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code blocks if present
    raw = re.sub(r"```json\s*|\s*```", "", raw).strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {
            "credibility_score": 50,
            "allegation_type": "other",
            "triage_summary": raw[:300],
            "is_credible": None,
            "urgency": "ROUTINE",
            "identity_risk": "LOW",
        }

    return result


# ─────────────────────────────────────────────
# 3. Tender Specification Analysis (AI-enhanced)
# ─────────────────────────────────────────────


def analyze_tender_specifications(
    spec_text: str, tender_value: Optional[float] = None
) -> dict:
    """
    Uses Claude to detect restrictive/tailored specifications that may exclude competition.
    Returns: { restrictiveness_score, issues, explanation }
    """
    client = _get_client()

    prompt = f"""You are an expert in Kenya's Public Procurement and Asset Disposal Act (PPADA 2015).
Analyze these tender specifications for anti-competitive or corruption-enabling patterns.

TENDER SPECIFICATIONS:
{spec_text[:3000]}

{"Estimated contract value: KES " + f"{tender_value:,.0f}" if tender_value else ""}

Respond ONLY with valid JSON:
{{
  "restrictiveness_score": <integer 0-100>,
  "issues": [
    {{
      "type": "<brand_specific|excessive_experience|short_deadline|geographic_restriction|proprietary_spec|other>",
      "excerpt": "<exact text from specifications>",
      "explanation": "<why this is problematic>",
      "severity": "<low|medium|high>"
    }}
  ],
  "single_source_indicators": <true|false>,
  "competition_impact": "<LOW|MEDIUM|HIGH - degree to which specs limit competition>",
  "overall_assessment": "<1-2 sentence summary>"
}}"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"```json\s*|\s*```", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "restrictiveness_score": 0,
            "issues": [],
            "overall_assessment": "Analysis failed. Manual review required.",
        }


# ─────────────────────────────────────────────
# 4. Natural Language Query Interface
# ─────────────────────────────────────────────


def natural_language_query(
    user_question: str,
    context_data: dict,
) -> str:
    """
    Lets users ask questions in plain English about the procurement data.
    context_data: relevant stats/records fetched from DB to ground the answer.
    """
    client = _get_client()

    prompt = f"""You are a helpful analyst for Kenya's public procurement transparency portal.
Answer the user's question using ONLY the data provided. Do not invent numbers.
If data is insufficient, say so clearly.

AVAILABLE DATA:
{json.dumps(context_data, indent=2, default=str)[:4000]}

USER QUESTION: {user_question}

Provide a clear, concise answer in plain English. Use specific figures from the data."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


# ─────────────────────────────────────────────
# 5. Investigation Package Generator
# ─────────────────────────────────────────────


def generate_investigation_package(
    tender: dict,
    risk_score: dict,
    supplier: Optional[dict],
    bids: Optional[list],
    similar_cases: Optional[list] = None,
) -> str:
    """
    Generates a structured investigation briefing document for EACC investigators.
    Returns formatted Markdown text.
    """
    client = _get_client()

    prompt = f"""You are preparing an investigation briefing package for EACC investigators.
Generate a professional, court-admissible quality investigation memo based on the following data.

TENDER DATA:
{json.dumps(tender, indent=2, default=str)}

RISK ASSESSMENT:
{json.dumps(risk_score, indent=2, default=str)}

SUPPLIER DATA:
{json.dumps(supplier, indent=2, default=str) if supplier else "Not available"}

BIDS:
{json.dumps(bids, indent=2, default=str) if bids else "Not available"}

SIMILAR PAST CASES:
{json.dumps(similar_cases, indent=2, default=str) if similar_cases else "None on file"}

Generate a structured investigation package in Markdown with these sections:
1. EXECUTIVE SUMMARY (3-4 sentences)
2. CORRUPTION RISK ASSESSMENT (score breakdown, what each score means)
3. KEY RED FLAGS (numbered list, most serious first)
4. EVIDENCE CHECKLIST (documents investigators should obtain)
5. RECOMMENDED INVESTIGATION STEPS (numbered, actionable)
6. APPLICABLE LAWS & REGULATIONS
7. SIMILAR PRECEDENT CASES

Be specific, reference actual Kenyan legal statutes, and write for a legal/investigative audience."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
