"""
app.py
------
Streamlit UI for the Transformation Dependency Intelligence app.

Layers demonstrated here (map this to your architecture explanation):
  USER INTERFACE      -> this file (Streamlit)
  APPLICATION LAYER    -> function calls into database.py / ai_engine.py
  AI INTELLIGENCE      -> ai_engine.py (rule-based + optional LLM)
  DATA LAYER           -> database.py (SQLite, persists across restarts)
"""

import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components

from database import (
    init_db, add_initiative, get_all_initiatives, get_all_relationships,
)
from ai_engine import (
    analyse_initiative, compute_risk_summary, compute_sequencing, answer_question,
    llm_available, extract_requires_provides, reanalyse_everything
)

st.set_page_config(page_title="Transformation Dependency Intelligence", layout="wide")
init_db()

# =========================
# CUSTOM UI DESIGN
# =========================
st.markdown("""
<style>

.stApp {
    background:
        radial-gradient(circle at 10% 10%, rgba(244,114,182,0.15), transparent 30%),
        radial-gradient(circle at 90% 20%, rgba(236,72,153,0.10), transparent 30%),
        linear-gradient(135deg, #fff1f7, #fce7f3);
}

.block-container {
    max-width: 1400px;
    padding-top: 2rem;
}

/* Header */
.main-header {
    background: linear-gradient(90deg, #1e3a8a, #4338ca);
    padding: 25px 30px;
    border-radius: 16px;
    margin-bottom: 25px;
    color: white;
    box-shadow: 0 8px 25px rgba(190,24,93,0.20);
}

.main-header h1 {
    color: white !important;
    margin: 0;
    font-size: 2.2rem;
}

.main-header p {
    color: #fce7f3;
    margin-top: 8px;
    margin-bottom: 0;
}

/* Buttons */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
}

/* Input fields */
.stTextInput input,
.stTextArea textarea {
    border-radius: 8px;
}

/* Tables */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
}

</style>
""", unsafe_allow_html=True)

# =========================
# PAGE HEADER
# =========================
st.markdown("""
<div class="main-header">
    <h1>🔗 Transformation Dependency Intelligence</h1>
    <p>NorthPeak Retail — transformation programme intelligence platform</p>
</div>
""", unsafe_allow_html=True)

if not llm_available():
    st.info(
        "ℹ️ Running in **rule-based mode** (no GROQ_API_KEY set). Dependency detection, "
        "risk scoring, and sequencing all work fully. To enable AI-generated explanations "
        "and free-form Q&A, set the GROQ_API_KEY environment variable (free at console.groq.com) "
        "and restart the app.",
        icon="ℹ️",
    )

tab1, tab2, tab3, tab4 = st.tabs(
    ["➕ Add Initiative", "🕸️ Dependency Map", "⚠️ Risks & Sequencing", "💬 Ask the System"]
)

# ---------------------------------------------------------------------------
# TAB 1 — Add a new initiative (this is the "surprise record" entry point)
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Add a new transformation initiative")
    st.caption("This is the live-test entry point — add any new initiative and the system "
               "will automatically detect how it connects to everything already stored.")

    with st.form("add_initiative_form", clear_on_submit=False):
        name = st.text_input("Initiative name *", placeholder="e.g. Fraud Detection AI")
        description = st.text_area(
            "Description *",
            placeholder="Describe what this initiative does, in plain business language."
        )

        col1, col2 = st.columns(2)
        with col1:
            owner = st.text_input("Owner", placeholder="e.g. Head of Risk")
        with col2:
            timeline = st.text_input("Timeline", placeholder="e.g. Q2 2026")

        st.markdown("**Requires** (what this initiative needs — comma separated)")
        requires_manual = st.text_input(
            "requires_manual", placeholder="e.g. Customer Data, Cloud Infrastructure",
            label_visibility="collapsed"
        )

        st.markdown("**Provides** (what this initiative produces for others — comma separated)")
        provides_manual = st.text_input(
            "provides_manual", placeholder="e.g. Fraud Risk Scores",
            label_visibility="collapsed"
        )

        use_ai_extract = st.checkbox(
            "Let AI infer requires/provides from the description too (merged with anything typed above)",
            value=llm_available(), disabled=not llm_available()
        )

        submitted = st.form_submit_button("Add & Analyse Initiative", type="primary")

    if submitted:
        if not name or not description:
            st.error("Name and description are required.")
        else:
            requires = [x.strip() for x in requires_manual.split(",") if x.strip()]
            provides = [x.strip() for x in provides_manual.split(",") if x.strip()]

            if use_ai_extract and llm_available():
                with st.spinner("AI is reading the description to identify requirements/outputs..."):
                    ai_requires, ai_provides = extract_requires_provides(description)
                    requires = list(set(requires + ai_requires))
                    provides = list(set(provides + ai_provides))

            new_id = add_initiative(name, description, requires, provides, owner, timeline)

            with st.spinner("Analysing dependencies, conflicts, and risks against existing initiatives..."):
                analyse_initiative(new_id)

            st.success(f"✅ '{name}' added and analysed. Detected requires: {requires} | provides: {provides}")
            st.info("Check the **Dependency Map** and **Risks & Sequencing** tabs to see how it connects.")

    st.divider()
    st.subheader("Current initiatives in the programme")
    initiatives = get_all_initiatives()
    if initiatives:
        df = pd.DataFrame([{
            "Name": i["name"], "Owner": i["owner"], "Timeline": i["timeline"],
            "Requires": ", ".join(i["requires"]), "Provides": ", ".join(i["provides"])
        } for i in initiatives])
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.info("Initiatives are stored permanently in the programme database.")
    else:
        st.warning(
            "No initiatives yet. Add one above, or run `python seed_data.py` for a demo dataset."
        )

        
        
# ---------------------------------------------------------------------------
# TAB 2 — Dependency map (visual graph + relationship table)
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Dependency & Conflict Map")

    # Always reload the latest data from SQLite
    relationships = get_all_relationships()
    initiatives = get_all_initiatives()

    if not initiatives:
        st.warning("No initiatives added yet. Add an initiative first.")
    else:
        # --- Visual graph ---
        net = Network(
            height="600px",
            width="100%",
            directed=True,
            bgcolor="##fff1f7"
        )

        added_nodes = set()

        # ALWAYS add every stored initiative as a node
        for i in initiatives:
            net.add_node(
                i["id"],
                label=i["name"],
                title=i["description"]
            )
            added_nodes.add(i["id"])

        # Add relationships when they exist
        color_map = {
            "depends_on": "#E67E22",
            "shares_resource": "#E74C3C"
        }

        for r in relationships:
            if (
                r["initiative_a_id"] not in added_nodes
                or r["initiative_b_id"] not in added_nodes
            ):
                continue

            edge_color = color_map.get(
                r["relationship_type"],
                "#999999"
            )

            label = (
                "depends on"
                if r["relationship_type"] == "depends_on"
                else "conflicts (shared resource)"
            )

            net.add_edge(
                r["initiative_a_id"],
                r["initiative_b_id"],
                title=f"{label}: {r['shared_item']}",
                label=r["shared_item"],
                color=edge_color
            )

        net.set_options("""
        var options = {
          "physics": {
            "stabilization": true,
            "barnesHut": {
              "gravitationalConstant": -8000
            }
          }
        }
        """)

        net.save_graph("graph.html")

        with open("graph.html", "r", encoding="utf-8") as f:
            components.html(f.read(), height=620)

        st.caption(
            "🟧 Orange = depends on   🟥 Red = resource conflict"
        )

        # --- Relationship evidence ---
        st.divider()
        st.subheader("Relationship evidence table")

        if relationships:
            st.caption(
                "Every edge above is traceable to a specific row here."
            )

            rel_df = pd.DataFrame([{
                "From": r["a_name"],
                "Relationship": r["relationship_type"],
                "To": r["b_name"],
                "Shared Item (evidence)": r["shared_item"],
                "Risk": r["risk_level"],
                "Explanation": r["explanation"]
            } for r in relationships])

            st.dataframe(
                rel_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info(
                "No relationships detected yet. "
                "The initiatives are stored, but no dependency or "
                "resource conflict has been identified between them."
            )

        # --- Re-analysis ---
        if st.button("🔄 Re-analyse all relationships"):
            with st.spinner(
                "Re-running dependency analysis across the whole programme..."
            ):
                reanalyse_everything()

            st.success("Done.")
            st.rerun()

# ---------------------------------------------------------------------------
# TAB 3 — Risk scoring & suggested sequencing (deterministic rule-based logic)
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Risk Assessment")
    st.caption("Risk levels are calculated with deterministic rules based on dependency counts — "
               "not an AI guess. This keeps the reasoning fully explainable.")

    summary = compute_risk_summary()
    if not summary:
        st.warning("No data yet.")
    else:
        risk_df = pd.DataFrame(summary)[["name", "depended_on_by", "depends_on", "conflicts", "risk", "reason"]]
        risk_df.columns = ["Initiative", "# Depend On This", "# This Depends On", "# Resource Conflicts", "Risk Level", "Why"]

        def highlight_risk(row):
            color = {"High": "#ffcccc", "Medium": "#fff3cd", "Low": "#d4edda"}.get(row["Risk Level"], "")
            return [f"background-color: {color}"] * len(row)

        st.dataframe(risk_df.style.apply(highlight_risk, axis=1), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Suggested sequencing")
        st.caption(
            "Calculated with a true topological sort of the dependency graph (via networkx) — "
            "guarantees every initiative appears strictly after everything it depends on, "
            "not just a rough ordering by dependency count."
        )

        ordered_names, cycles, broken_links = compute_sequencing()

        if cycles:
            st.error(
                "⚠️ **Circular dependency detected** — a valid full sequence isn't mathematically "
                "possible until this is resolved. This is a genuine risk to flag to the programme, "
                "not something the system should silently hide."
            )
            for cycle in cycles:
                st.markdown("🔁 Cycle: " + " → ".join(cycle) + f" → {cycle[0]}")
            st.caption(
                "To still show a best-effort sequence below, the system temporarily set aside "
                "one dependency link per cycle (shown here for full traceability):"
            )
            for a, b in broken_links:
                st.markdown(f"- Set aside: **{a} → {b}** (part of the cycle above)")
            st.markdown("**Best-effort sequence (resolve the cycle above before trusting this order):**")
        else:
            st.success("✅ No circular dependencies — this sequence is fully valid.")

        for idx, name in enumerate(ordered_names, start=1):
            st.markdown(f"**{idx}. {name}**")

# ---------------------------------------------------------------------------
# TAB 4 — Free-form Q&A grounded in the stored data
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("Ask the system a question")
    st.caption("Answers are generated from the ACTUAL stored initiatives and relationships above — "
               "not a generic LLM guess. This is what makes the answer traceable.")

    example_qs = [
        "What should we transform first and why?",
        "Which initiative is the biggest bottleneck?",
        "What happens if Data Platform is delayed?",
        "Where are the resource conflicts?",
    ]
    q_choice = st.selectbox("Try an example question, or type your own below:", ["-- choose --"] + example_qs)
    question = st.text_input("Your question", value="" if q_choice == "-- choose --" else q_choice)

    if st.button("Ask", type="primary") and question:
        with st.spinner("Reasoning over the stored programme data..."):
            answer = answer_question(question)
        st.markdown("### Answer")
        st.write(answer)

st.divider()
st.caption(
    "Architecture: Streamlit (UI) → Python app logic → SQLite (persistent storage) "
    "→ rule-based dependency engine + optional LLM (Groq free-tier) for interpretation/explanation."
)
