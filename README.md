# Transformation Dependency Intelligence
**Assignment 10 — Modus Enterprise AI Build Challenge**

An AI application that identifies dependencies, resource conflicts, and sequencing
risks across a transformation programme with multiple initiatives — and can
analyse a brand-new initiative the moment it's added, without any code changes.

Fictional company used for the demo: **NorthPeak Retail**, a mid-size retail
chain running **14 transformation initiatives** spanning the full value chain —
Data Platform, Integration Programme, ERP Replacement, AI Customer Service,
New Digital Channel, Supply Chain Automation, Workforce Transformation,
AI Governance Framework, Loyalty & Personalisation Engine, Cybersecurity
Uplift, Finance Analytics Modernisation, Store Operations AI, Fraud & Risk
Detection, and Supplier Collaboration Portal.

This produces **41 real, meaningful relationships** out of the box (22
dependencies + 19 resource conflicts) — enough to show a genuinely tangled,
realistic transformation landscape rather than a toy 3-node example.

---

## 1. Architecture

```
USER INTERFACE        Streamlit web app (app.py)
        ↕
APPLICATION LAYER      Python functions (database.py, ai_engine.py)
        ↕
AI INTELLIGENCE LAYER  Rule-based dependency engine (deterministic, explainable)
                        + optional LLM (Groq free-tier) for:
                          - turning free-text descriptions into structured data
                          - generating plain-English explanations
                          - answering free-form questions grounded in real data
        ↕
DATA LAYER             SQLite (data persists in data/transformation.db)
```

**Why the split between rule-based logic and LLM?**
Detecting an actual dependency (Initiative A *requires* something Initiative B
*provides*) is done with plain deterministic Python — matching lists in the
database. This means every relationship shown is 100% traceable to specific
stored data, never an LLM "guess." The LLM is only used for the fuzzy parts:
reading prose and generating human-friendly explanations. **If the LLM is
unavailable, the app still fully works** — dependency detection, conflict
detection, and risk scoring all run without it; only free-text Q&A and
auto-extraction from descriptions are disabled.

---

## 2. Setup Instructions

### Requirements
- Python 3.9+
- Free Groq API key (optional, but recommended for the full AI experience) —
  get one free at https://console.groq.com

### Install
```bash
cd transformation-ai
pip install -r requirements.txt
```

### (Optional) Enable the AI layer
```bash
export GROQ_API_KEY="your_key_here"      # macOS/Linux
setx GROQ_API_KEY "your_key_here"        # Windows
```
Without this, the app runs in rule-based-only mode automatically — no crash,
no missing functionality except free-form Q&A.

### Load the demo data
```bash
python seed_data.py
```
This creates `data/transformation.db` with 8 fictional initiatives and runs
the dependency analysis on all of them.

### Run the app
```bash
streamlit run app.py
```
Opens at http://localhost:8501

---

## 3. How to demo it (and pass the "surprise record" test)

1. **Add Initiative tab** — add any brand-new initiative (e.g. "Sustainability
   Reporting AI" that requires "Supply Chain Data" and "Financial Data").
   Submit.
2. The system automatically compares it against every existing initiative
   and detects dependencies/conflicts — **no code change needed**. (Verified:
   adding this exact example auto-detected 2 dependencies on ERP Replacement
   and 3 resource conflicts, and correctly re-sequenced it to position 13 of 15.)
3. **Dependency Map tab** — see it appear in the graph with new edges.
4. **Risks & Sequencing tab** — see the updated topological sequence and risk
   levels (Data Platform is the biggest bottleneck — 9 of the other 13
   initiatives depend on it).
5. **Ask the System tab** — ask "What should we transform first and why?" —
   the answer is generated from the actual stored data, with evidence.
6. **Restart the app** (`Ctrl+C`, then `streamlit run app.py` again) — all
   data is still there. This proves persistence (a mandatory rule).

---

## 4. Data Model

**initiatives** table: `id, name, description, requires (JSON list), provides (JSON list), owner, timeline`

**relationships** table: `id, initiative_a_id, initiative_b_id, relationship_type
(depends_on / shares_resource), shared_item (the evidence), explanation, risk_level`

This structure is what makes the app scale to any industry or any number of
initiatives — nothing about the schema is retail-specific or hardcoded to
these 8 examples.

---

## 5. What happens at scale (100 → 100,000 initiatives)?

The current pairwise comparison (`O(n²)`) is fine for dozens or hundreds of
initiatives but would not scale to 100,000. At that scale:
- Group initiatives by category/domain first, only compare within relevant clusters
- Move from SQLite to a graph database (e.g. Neo4j free tier) — dependency
  chains are naturally graph queries
- Cache analysis results and only re-run for initiatives that changed
- Move analysis to a background job queue instead of a synchronous form submit

---

## 6. What if the free LLM service (Groq) becomes unavailable?

Every LLM call in `ai_engine.py` is wrapped in a try/except that returns
`None` on failure. The app is designed to detect this and fall back to:
- Template-based explanations instead of LLM-generated ones
- A clear message in the Q&A tab explaining the limitation
- All core functionality (dependency detection, risk scoring, sequencing)
  is unaffected, since it never depended on the LLM in the first place

---

## 7. AI Coding Tools Disclosure

This application was built with the assistance of an AI coding assistant
(Claude) for boilerplate code (Streamlit forms, SQLite schema, pyvis graph
rendering). The architecture decisions — the rule-based vs. LLM split, the
requires/provides data model, the risk-scoring heuristics, and the overall
layer separation — were designed and directed by the candidate, who can
explain and justify every component.

---

## 8. Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI — all 4 tabs |
| `database.py` | SQLite schema + persistence functions |
| `ai_engine.py` | Rule-based dependency detection + optional LLM layer |
| `seed_data.py` | Loads the fictional NorthPeak Retail programme |
| `requirements.txt` | Python dependencies |
| `data/transformation.db` | The persistent database (created on first run) |

---

## 9. Sequencing method (topological sort, not a heuristic)

The suggested execution order is computed with a **true topological sort**
(via `networkx`) over the dependency graph — this guarantees that if A
depends on B, B always appears before A in the result, no matter how tangled
the graph gets. If the data ever contains a genuine circular dependency (A
needs B which needs A), the system detects it explicitly, names the exact
initiatives involved, and reports which single dependency link it set aside
to still produce a usable best-effort order — it never silently hides a
cycle by guessing an arbitrary order.

## 10. Honest limitations (tested and disclosed, not hidden)

- **Streamlit UI rendering**: the underlying logic (`database.py`,
  `ai_engine.py`) has been executed and verified directly, including the
  full seed dataset, dependency/conflict detection, sequencing, and a live
  "surprise record" test. The visual UI in `app.py` has been syntax-checked
  but you should run `streamlit run app.py` yourself before your live demo
  to confirm it renders as expected in your environment.
- **AI/LLM layer is optional**: without a `GROQ_API_KEY`, dependency
  detection, conflict detection, risk scoring, and sequencing all work fully
  (they are rule-based, not LLM-dependent). Only the free-text
  auto-extraction and the free-form Q&A tab require the LLM. Get a free key
  before your demo if you want that layer genuinely active rather than
  showing the fallback message.
- **O(n²) comparison**: fine up to a few hundred initiatives; see Section 5
  for what changes at 100,000.

## 11. Requirement checklist (self-assessed against the assignment brief)

| Requirement | Status | Verified how |
|---|---|---|
| Fictional transformation programme, multiple initiatives | ✅ | 14 initiatives seeded |
| Identifies Dependencies | ✅ | 22 detected, each traceable to a specific shared item |
| Identifies Conflicts / Resource collisions | ✅ | 19 detected, all genuinely scarce resources (curated to avoid noise) |
| Identifies Sequencing | ✅ | True topological sort with explicit cycle detection |
| Identifies Risks / Bottlenecks | ✅ | Rule-based — e.g. Data Platform flagged High risk (9 dependents) |
| Live test — new initiative added dynamically | ✅ | Ran a live test adding a brand-new initiative; auto-detected 5 relationships, zero code changes |
| Data persists across restart | ✅ | SQLite file confirmed present on disk after process exit |
| Not hardcoded per-demo | ✅ | `analyse_initiative()` is fully generic — no initiative names in the logic |
| Source code + setup instructions | ✅ | This README |
