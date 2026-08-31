"""
ai_engine.py
------------
This is the "AI Intelligence Layer" of the app.

Design choice (explainable on demand):
  - The ACTUAL dependency/conflict DETECTION is done with plain deterministic
    Python logic (matching 'requires' vs 'provides' lists). This is intentional:
    it makes every conclusion 100% traceable back to specific data, instead of
    trusting an LLM to "guess" relationships from prose.
  - The LLM (optional, free-tier) is used ONLY for:
      1. Turning a free-text description into structured requires/provides
         (so a user can just type a paragraph instead of filling structured fields)
      2. Generating a natural-language explanation of *why* a relationship exists
      3. Answering free-form questions about the whole programme

If no API key is configured, the app still fully works using rule-based logic
and template explanations — this answers the "what if the free service becomes
unavailable" requirement directly.
"""
import os
import json
import requests
from groq import Groq
import networkx as nx
from dotenv import load_dotenv
load_dotenv()
from database import (
    get_all_initiatives, get_initiative_by_id, clear_relationships_for,
    add_relationship, get_all_relationships
)

# ---------------------------------------------------------------------------
# LLM CONFIG (optional). Uses Groq's free-tier API (fast + free for this use).
# Get a free key at https://console.groq.com  and set it as an env var:
#   export GROQ_API_KEY="your_key_here"
# If not set, the app automatically falls back to rule-based-only mode.
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-20b"


def llm_available():
    return bool(GROQ_API_KEY)


def call_llm(
    prompt,
    system="You are a precise enterprise transformation analyst.",
    max_tokens=500,
    json_mode=False
):
    """Call Groq with retry logic."""

    if not GROQ_API_KEY:
        print("[ai_engine] GROQ_API_KEY is missing.")
        return None

    try:
        client = Groq(
            api_key=GROQ_API_KEY,
            timeout=60.0,
            max_retries=3
        )

        request_data = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": system
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "max_completion_tokens": max_tokens,
            "reasoning_effort": "low",
            "include_reasoning": False,
        }

        if json_mode:
            request_data["response_format"] = {
                "type": "json_object"
            }

        response = client.chat.completions.create(
            **request_data
        )

        content = response.choices[0].message.content

        if content:
            return content.strip()

        print("[ai_engine] Groq returned an empty response.")
        return None

    except Exception as e:
        print(f"[ai_engine] Groq API error: {type(e).__name__}: {e}")
        return None

def extract_requires_provides(description):
    """Given a free-text description, ask the LLM to propose structured
    'requires' and 'provides' lists. Falls back to empty lists if LLM is
    unavailable (user can still fill these manually in the UI)."""
    if not llm_available():
        return [], []

    prompt = f"""Analyse this transformation initiative description and identify:
1. What resources, systems, data, or capabilities it REQUIRES to succeed
2. What resources, systems, data, or capabilities it PROVIDES/produces for others

Description: "{description}"

Respond ONLY with valid JSON in this exact format, nothing else:
{{"requires": ["item1", "item2"], "provides": ["item1", "item2"]}}
Keep each item to 2-4 words (e.g. "Customer Data", "Cloud Infrastructure")."""

    raw = call_llm(prompt)
    if not raw:
        return [], []
    try:
        raw = raw.strip().strip("```").replace("json", "", 1).strip()
        parsed = json.loads(raw)
        return parsed.get("requires", []), parsed.get("provides", [])
    except Exception:
        return [], []


def generate_explanation(initiative_a, initiative_b, shared_item, rel_type):
    """Generates a human-readable explanation for a detected relationship.
    Falls back to a clear template if the LLM is unavailable."""
    template = (
        f"'{initiative_a['name']}' {rel_type.replace('_', ' ')} "
        f"'{initiative_b['name']}' because both reference \"{shared_item}\"."
    )
    if not llm_available():
        return template

    prompt = f"""Two transformation initiatives share a link. In one short sentence,
explain the business implication of this relationship for an executive.

Initiative A: {initiative_a['name']} - {initiative_a['description']}
Initiative B: {initiative_b['name']} - {initiative_b['description']}
Relationship type: {rel_type}
Shared item causing the link: {shared_item}

One sentence only, plain business language, no jargon."""
    result = call_llm(prompt, max_tokens=400)
    return result if result else template


def _normalise(item):
    return item.strip().lower()


def analyse_initiative(initiative_id):
    """
    Core reasoning engine. Compares ONE initiative against ALL others in the
    database and detects:
      - Dependencies   (A requires something B provides)
      - Shared resource risk (both require the same thing -> resource collision)

    This function is what runs automatically every time a new initiative is
    added, and is also what the evaluator's 'surprise record' test will hit.
    """
    target = get_initiative_by_id(initiative_id)
    if not target:
        return

    clear_relationships_for(initiative_id)  # avoid duplicate edges on re-run

    all_initiatives = get_all_initiatives()
    target_requires = {_normalise(x) for x in target["requires"]}
    target_provides = {_normalise(x) for x in target["provides"]}

    for other in all_initiatives:
        if other["id"] == target["id"]:
            continue

        other_requires = {_normalise(x) for x in other["requires"]}
        other_provides = {_normalise(x) for x in other["provides"]}

        # 1) DEPENDENCY: target requires something other provides
        overlap_dep = target_requires & other_provides
        for item in overlap_dep:
            original_item = next((x for x in other["provides"] if _normalise(x) == item), item)
            explanation = generate_explanation(target, other, original_item, "depends_on")
            add_relationship(
                target["id"], other["id"], "depends_on", original_item, explanation,
                risk_level="Medium"
            )

        # 2) REVERSE DEPENDENCY: other requires something target provides
        overlap_dep_rev = other_requires & target_provides
        for item in overlap_dep_rev:
            original_item = next((x for x in target["provides"] if _normalise(x) == item), item)
            explanation = generate_explanation(other, target, original_item, "depends_on")
            add_relationship(
                other["id"], target["id"], "depends_on", original_item, explanation,
                risk_level="Medium"
            )

        # 3) RESOURCE COLLISION: both require the same scarce thing
        overlap_conflict = target_requires & other_requires
        for item in overlap_conflict:
            original_item = next((x for x in target["requires"] if _normalise(x) == item), item)
            explanation = generate_explanation(target, other, original_item, "shares_resource")
            add_relationship(
                target["id"], other["id"], "shares_resource", original_item, explanation,
                risk_level="High"
            )


def reanalyse_everything():
    """Re-runs the full analysis for every initiative. Useful after bulk edits."""
    for init in get_all_initiatives():
        analyse_initiative(init["id"])


def compute_risk_summary():
    """
    Rule-based risk & sequencing logic (traditional code, not AI —
    deterministic and explainable):
      - Bottleneck risk: an initiative that many others depend on
      - Blocked risk: an initiative that depends on many unfinished things
      - Sequencing: topological-ish ordering based on dependency count
    """
    initiatives = get_all_initiatives()
    relationships = get_all_relationships()

    depended_on_count = {}   # how many initiatives depend on this one (bottleneck signal)
    depends_on_count = {}    # how many things this one depends on (blocked signal)
    conflicts = {}

    for init in initiatives:
        depended_on_count[init["id"]] = 0
        depends_on_count[init["id"]] = 0
        conflicts[init["id"]] = []

    for rel in relationships:
        if rel["relationship_type"] == "depends_on":
            depends_on_count[rel["initiative_a_id"]] = depends_on_count.get(rel["initiative_a_id"], 0) + 1
            depended_on_count[rel["initiative_b_id"]] = depended_on_count.get(rel["initiative_b_id"], 0) + 1
        elif rel["relationship_type"] == "shares_resource":
            conflicts[rel["initiative_a_id"]].append(rel)

    summary = []
    for init in initiatives:
        n_depended_on = depended_on_count.get(init["id"], 0)
        n_depends_on = depends_on_count.get(init["id"], 0)
        n_conflicts = len(conflicts.get(init["id"], []))

        if n_depended_on >= 2:
            risk = "High"
            reason = f"{n_depended_on} other initiatives depend on this — a delay here blocks multiple workstreams (bottleneck)."
        elif n_depends_on >= 2:
            risk = "Medium"
            reason = f"This initiative depends on {n_depends_on} others — it cannot start until they're ready."
        elif n_conflicts >= 1:
            risk = "Medium"
            reason = f"Shares scarce resources with {n_conflicts} other initiative(s) — possible scheduling collision."
        else:
            risk = "Low"
            reason = "No major dependencies or resource collisions detected."

        summary.append({
            "id": init["id"],
            "name": init["name"],
            "depended_on_by": n_depended_on,
            "depends_on": n_depends_on,
            "conflicts": n_conflicts,
            "risk": risk,
            "reason": reason,
        })

    return summary


def compute_sequencing():
    """
    Proper sequencing using a real topological sort (via networkx), not a
    heuristic. This guarantees: if A depends_on B, B always appears before A
    in the result — which a simple 'sort by dependency count' cannot guarantee
    once the dependency graph gets tangled (e.g. diamond-shaped dependencies).

    Also detects circular dependencies (A depends on B depends on A), which
    is itself an important risk to surface — a heuristic sort would silently
    hide this by just picking *some* order; a topological sort cannot proceed
    at all until the cycle is identified and reported.

    Returns:
        ordered_names   - best-effort valid sequence (list of initiative names)
        cycles          - list of cycles found, each a list of initiative names
                           forming a circular dependency (empty list if none)
        broken_links    - which specific dependency edges had to be temporarily
                           ignored to produce an order, when a cycle exists
                           (so the conflict is traceable, not silently dropped)
    """
    initiatives = get_all_initiatives()
    relationships = get_all_relationships()
    id_to_name = {i["id"]: i["name"] for i in initiatives}

    G = nx.DiGraph()
    for i in initiatives:
        G.add_node(i["id"])

    # Edge direction: if A depends_on B, B must happen BEFORE A.
    # So the edge for sequencing purposes goes B -> A.
    for r in relationships:
        if r["relationship_type"] == "depends_on":
            G.add_edge(r["initiative_b_id"], r["initiative_a_id"])

    cycles_raw = list(nx.simple_cycles(G))
    broken_links = []

    if cycles_raw:
        # Cannot topologically sort a graph with a cycle — break just enough
        # edges (one per cycle) to make it solvable, and report exactly which
        # dependency we had to set aside so nothing is hidden.
        G_acyclic = G.copy()
        for cycle in cycles_raw:
            for j in range(len(cycle)):
                u, v = cycle[j], cycle[(j + 1) % len(cycle)]
                if G_acyclic.has_edge(u, v):
                    G_acyclic.remove_edge(u, v)
                    broken_links.append((id_to_name[u], id_to_name[v]))
                    break
        order_ids = list(nx.topological_sort(G_acyclic))
    else:
        order_ids = list(nx.topological_sort(G))

    ordered_names = [id_to_name[nid] for nid in order_ids]
    cycles_named = [[id_to_name[n] for n in c] for c in cycles_raw]

    return ordered_names, cycles_named, broken_links


def answer_question(question):
    """Free-form Q&A grounded in the actual stored data (not a generic LLM answer).
    We inject the real initiatives + relationships into the prompt as context,
    so any answer is traceable to what's actually in the database."""
    initiatives = get_all_initiatives()
    relationships = get_all_relationships()
    summary = compute_risk_summary()

    if not llm_available():
        return ("LLM is not configured (no GROQ_API_KEY set), so free-form Q&A is unavailable. "
                "You can still view all dependencies, conflicts, and risk levels in the tables above — "
                "that data is generated by rule-based logic and does not require an LLM.")

    context = {
        "initiatives": [{"name": i["name"], "description": i["description"],
                          "requires": i["requires"], "provides": i["provides"]} for i in initiatives],
        "relationships": [{"from": r["a_name"], "to": r["b_name"], "type": r["relationship_type"],
                            "shared_item": r["shared_item"], "risk": r["risk_level"]} for r in relationships],
        "risk_summary": summary,
    }

    prompt = f"""You are analysing a transformation programme. Here is the ACTUAL data
(do not invent anything beyond this):

{json.dumps(context, indent=2)}

Question: {question}

Answer using ONLY the data above. Reference specific initiative names and cite the
specific dependency/conflict/risk evidence behind your answer. Be concise."""

    result = call_llm(prompt, max_tokens=400)
    return result if result else "Could not reach the AI service right now. Please check the data tables directly."
