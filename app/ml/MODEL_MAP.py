"""
═══════════════════════════════════════════════════════════════════════════════
AI / ML MODEL MAP  —  AI Procurement Monitoring System
Based on: "AI-Powered Procurement Monitoring and Anti-Corruption System" proposal
═══════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 2  —  Price Inflation Detection                                      │
├──────────────┬──────────────────────────┬───────────────────────────────────┤
│ Model        │ IsolationForest           │ sklearn.ensemble                  │
│ File         │ app/ml/price_anomaly.py   │                                   │
│ Input        │ [price, category_code,    │                                   │
│              │  county_code, value_log]  │                                   │
│ Output       │ anomaly_score (-1/1)      │                                   │
│ Use          │ Detect price outliers     │                                   │
│              │ beyond simple deviation   │                                   │
│ Service      │ services/price_analyzer   │                                   │
└──────────────┴──────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 3  —  Ghost Supplier Detection                                       │
├──────────────┬──────────────────────────┬───────────────────────────────────┤
│ Model 1      │ RandomForestClassifier    │ sklearn.ensemble                  │
│ File         │ app/ml/supplier_risk.py   │                                   │
│ Input        │ [company_age_days,        │                                   │
│              │  tax_filings, director_   │                                   │
│              │  count, address_score,    │                                   │
│              │  online_score,            │                                   │
│              │  past_contracts]          │                                   │
│ Output       │ ghost_probability (0-1)   │                                   │
│ Use          │ P(ghost supplier)         │                                   │
│ Service      │ services/supplier_checker │                                   │
├──────────────┼──────────────────────────┼───────────────────────────────────┤
│ Model 2      │ IsolationForest           │ sklearn.ensemble                  │
│ File         │ app/ml/supplier_anomaly   │                                   │
│ Input        │ same features             │                                   │
│ Output       │ anomaly flag              │                                   │
│ Use          │ Unsupervised outlier      │                                   │
│              │ detection — no labels     │                                   │
│              │ needed for new suppliers  │                                   │
│ Service      │ services/supplier_checker │                                   │
└──────────────┴──────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4  —  Specification Analysis & Collusion Detection                   │
├──────────────┬──────────────────────────┬───────────────────────────────────┤
│ Model 1      │ TF-IDF + Cosine Similarity│ sklearn.feature_extraction.text   │
│ File         │ app/ml/collusion.py       │                                   │
│ Input        │ bid proposal texts        │                                   │
│ Output       │ similarity_matrix (0-1)   │                                   │
│ Use          │ Detect identical/cloned   │                                   │
│              │ bid proposals (collusion) │                                   │
│ Service      │ services/collusion_detector│                                  │
├──────────────┼──────────────────────────┼───────────────────────────────────┤
│ Model 2      │ spaCy NER + keyword rules │ spacy en_core_web_sm              │
│ File         │ app/ml/spec_nlp.py        │                                   │
│ Input        │ tender spec text          │                                   │
│ Output       │ restrictiveness_score,    │                                   │
│              │ flagged_entities          │                                   │
│ Use          │ Brand names, excessive    │                                   │
│              │ requirements, single-     │                                   │
│              │ source indicators         │                                   │
│ Service      │ services/spec_analyzer    │                                   │
└──────────────┴──────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 5  —  Predictive Risk Scoring (MAIN CORRUPTION MODEL)                │
├──────────────┬──────────────────────────┬───────────────────────────────────┤
│ Model        │ XGBClassifier             │ xgboost                           │
│ File         │ app/ml/xgb_risk_model.py  │                                   │
│ Input        │ [price_deviation_pct,     │                                   │
│              │  supplier_ghost_prob,     │                                   │
│              │  spec_restrictiveness,    │                                   │
│              │  contract_value_log,      │                                   │
│              │  procurement_method_enc,  │                                   │
│              │  entity_history_score,    │                                   │
│              │  deadline_days,           │                                   │
│              │  bid_count,               │                                   │
│              │  single_bidder,           │                                   │
│              │  political_proximity]     │                                   │
│ Output       │ corruption_probability    │                                   │
│              │ (0.0–1.0) → scaled 0-100 │                                   │
│ Use          │ Final corruption risk     │                                   │
│              │ score — trained on EACC   │                                   │
│              │ historical cases          │                                   │
│ Service      │ services/risk_engine      │                                   │
│ Fallback     │ Weighted rule-based if    │                                   │
│              │ model not trained yet     │                                   │
└──────────────┴──────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 6  —  Temporal / Spending Pattern Analysis                           │
├──────────────┬──────────────────────────┬───────────────────────────────────┤
│ Model        │ Prophet (Facebook)        │ prophet                           │
│ File         │ app/ml/spending_forecast  │                                   │
│ Input        │ (date, spend) time-series │                                   │
│              │ per entity/county         │                                   │
│ Output       │ forecast, anomaly_dates   │                                   │
│ Use          │ Detect abnormal spend      │                                  │
│              │ spikes near elections,    │                                   │
│              │ year-end budget rushes    │                                   │
│ Service      │ routes/dashboard (charts) │                                   │
└──────────────┴──────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  CROSS-CUTTING  —  LLM (Generative AI for reports & NL interface)           │
├──────────────┬──────────────────────────┬───────────────────────────────────┤
│ Model        │ Claude claude-opus-4-6    │ anthropic SDK                     │
│ File         │ app/services/ai_service   │                                   │
│ Use 1        │ Risk narrative analysis   │ POST /tenders/{id}/analyze-risk   │
│ Use 2        │ Whistleblower triage      │ POST /whistleblower/submit        │
│ Use 3        │ Investigation package     │ GET  /tenders/{id}/investigation  │
│ Use 4        │ NL query interface        │ POST /dashboard/ai-query          │
│ Use 5        │ Spec deep analysis        │ POST /analyze/specifications      │
│ Note         │ LLM wraps the ML scores   │ Narrative explanation of numbers  │
│              │ — ML scores are primary,  │                                   │
│              │ LLM explains them         │                                   │
└──────────────┴──────────────────────────┴───────────────────────────────────┘

SUMMARY TABLE
─────────────────────────────────────────────────────────────────────────────
 #   Model                    Library           Proposal Layer  Service File
─────────────────────────────────────────────────────────────────────────────
 1   IsolationForest          sklearn           Layer 2         price_anomaly
 2   RandomForestClassifier   sklearn           Layer 3         supplier_risk
 3   IsolationForest          sklearn           Layer 3         supplier_anomaly
 4   TF-IDF + Cosine Sim      sklearn           Layer 4         collusion
 5   spaCy NER pipeline       spacy             Layer 4         spec_nlp
 6   XGBClassifier            xgboost           Layer 5         xgb_risk_model
 7   Prophet                  prophet           Layer 6         spending_forecast
 8   Claude claude-opus-4-6   anthropic         Cross-cutting   ai_service
─────────────────────────────────────────────────────────────────────────────
"""
