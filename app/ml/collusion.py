"""
Model: TF-IDF Vectorizer + Cosine Similarity — Bid Collusion Detection
Proposal Layer: 4 (Specification Analysis & Collusion Detection)
Library: sklearn.feature_extraction.text, sklearn.metrics.pairwise

PURPOSE
-------
The proposal specifically calls for "text similarity algorithms to compare
proposals — identical phrasing indicates collusion, single companies
submitting multiple bids through fronts, or officials sharing 'winning'
proposals with favored bidders."

METHOD
------
1. TF-IDF vectorises all bid proposal texts for a tender
2. Cosine similarity matrix computed between all pairs
3. Pairs above threshold flagged as potentially colluding
4. Also detects: same template shared across different tenders
   (official leaking bid template)

PROPOSAL TEXT SIGNALS (from proposal)
--------------------------------------
  - Identical formatting/phrasing between competing bids
  - Same company submitting multiple bids via fronts
  - Proposal matches spec template exactly → leak indicator

OUTPUT per bid pair
-------------------
  similarity_score: float  0.0–1.0
  is_collusion_flag: bool  True if > threshold
  collusion_type: str      "identical_bid" | "template_leak" | "front_company"
"""

import os
import pickle
from typing import Optional

import numpy as np

VECTORIZER_PATH = os.path.join(
    os.path.dirname(__file__), "weights", "collusion_tfidf.pkl"
)

# Thresholds from proposal / anti-collusion literature
COLLUSION_THRESHOLD = 0.75  # bids this similar are flagged
TEMPLATE_LEAK_THRESHOLD = 0.85  # bid matching spec almost exactly


# ── TF-IDF Vectorizer (fit once on corpus, reuse) ─────────────────────────────


def fit_vectorizer(all_texts: list[str]) -> None:
    """
    Fit TF-IDF on a corpus of bid proposal texts.
    Call once when you have enough historical data (100+ bids recommended).
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 3),  # unigrams, bigrams, trigrams
        max_features=10_000,
        sublinear_tf=True,  # dampens high-frequency terms
        min_df=2,  # ignore terms appearing in <2 docs
        strip_accents="unicode",
        analyzer="word",
    )
    vectorizer.fit(all_texts)

    os.makedirs(os.path.dirname(VECTORIZER_PATH), exist_ok=True)
    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)
    print(f"TF-IDF vectorizer fitted on {len(all_texts)} texts")


def _load_vectorizer():
    if not os.path.exists(VECTORIZER_PATH):
        return None
    with open(VECTORIZER_PATH, "rb") as f:
        return pickle.load(f)


# ── Collusion Detection ────────────────────────────────────────────────────────


def detect_bid_collusion(
    bids: list[dict],  # [{supplier_id, bid_amount, proposal_text}]
    tender_spec_text: Optional[str] = None,
) -> dict:
    """
    Analyse bids on a single tender for collusion signals.

    Returns:
    {
        collusion_pairs: [
            {
                supplier_a: str,
                supplier_b: str,
                similarity: float,
                collusion_type: str,
            }
        ],
        max_similarity: float,
        collusion_risk_score: float   0-100
        flagged: bool
    }
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    texts = [b.get("proposal_text", "") or "" for b in bids]
    supplier_ids = [str(b.get("supplier_id", i)) for i, b in enumerate(bids)]

    # Need at least 2 bids to compare
    if len(bids) < 2 or all(len(t.strip()) < 50 for t in texts):
        return {
            "collusion_pairs": [],
            "max_similarity": 0.0,
            "collusion_risk_score": 0.0,
            "flagged": False,
        }

    # Use fitted vectorizer if available, otherwise fit on the fly
    vectorizer = _load_vectorizer()
    if vectorizer is None:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        vectorizer.fit(texts + ([tender_spec_text] if tender_spec_text else []))

    bid_vectors = vectorizer.transform(texts)
    sim_matrix = cosine_similarity(bid_vectors)

    collusion_pairs = []
    n = len(bids)

    for i in range(n):
        for j in range(i + 1, n):
            sim = float(sim_matrix[i, j])
            if sim >= COLLUSION_THRESHOLD:
                collusion_type = "identical_bid" if sim >= 0.92 else "similar_bid"
                collusion_pairs.append(
                    {
                        "supplier_a": supplier_ids[i],
                        "supplier_b": supplier_ids[j],
                        "similarity": round(sim, 4),
                        "collusion_type": collusion_type,
                    }
                )

    # Check each bid against tender spec (template leak detection)
    if tender_spec_text:
        spec_vec = vectorizer.transform([tender_spec_text])
        for i, bid_vec in enumerate(bid_vectors):
            sim = float(cosine_similarity(bid_vec, spec_vec)[0][0])
            if sim >= TEMPLATE_LEAK_THRESHOLD:
                collusion_pairs.append(
                    {
                        "supplier_a": supplier_ids[i],
                        "supplier_b": "tender_specification",
                        "similarity": round(sim, 4),
                        "collusion_type": "template_leak",
                    }
                )

    max_sim = max((p["similarity"] for p in collusion_pairs), default=0.0)

    # Risk score: 0-100 based on number and severity of collusion pairs
    if not collusion_pairs:
        risk_score = 0.0
    else:
        # Scale: one critical pair = 80, each additional = +10
        risk_score = min(80 + (len(collusion_pairs) - 1) * 10, 100.0)
        # Boost for template leak (more serious)
        if any(p["collusion_type"] == "template_leak" for p in collusion_pairs):
            risk_score = min(risk_score + 15, 100.0)

    return {
        "collusion_pairs": collusion_pairs,
        "max_similarity": max_sim,
        "collusion_risk_score": round(risk_score, 2),
        "flagged": len(collusion_pairs) > 0,
    }


def analyse_cross_tender_collusion(
    supplier_id: str,
    all_bids: list[dict],  # [{tender_id, proposal_text}] for this supplier
) -> dict:
    """
    Check if a supplier submits nearly identical proposals across different tenders
    (copy-paste bidding = sign of front company network).
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if len(all_bids) < 2:
        return {"is_copy_paste_bidder": False, "avg_similarity": 0.0}

    texts = [b.get("proposal_text", "") for b in all_bids if b.get("proposal_text")]
    if len(texts) < 2:
        return {"is_copy_paste_bidder": False, "avg_similarity": 0.0}

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
    vectors = vectorizer.fit_transform(texts)
    sim_matrix = cosine_similarity(vectors)

    # Average similarity of all pairs (excluding self)
    n = len(texts)
    sims = [sim_matrix[i, j] for i in range(n) for j in range(i + 1, n)]
    avg_sim = float(np.mean(sims)) if sims else 0.0

    return {
        "is_copy_paste_bidder": avg_sim > 0.80,
        "avg_similarity": round(avg_sim, 4),
        "bid_count_analysed": len(texts),
    }
