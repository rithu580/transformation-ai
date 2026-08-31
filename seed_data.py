"""
seed_data.py
------------
Populates the database with a fictional transformation programme so the app
has something to demo immediately. Run this once: `python seed_data.py`

Fictional company: "NorthPeak Retail" - a mid-size retail chain undergoing
digital transformation. 14 initiatives spanning the full value chain
(data, integration, finance, customer, digital, supply chain, HR,
governance, marketing, security) so the dependency graph is realistically
tangled, not a toy 3-node example — this is meant to feel like a genuine
enterprise transformation portfolio rather than a demo-only dataset.
"""

from database import init_db, add_initiative, get_all_initiatives
from ai_engine import analyse_initiative

INITIATIVES = [
    {
        "name": "Data Platform",
        "description": "Build a centralised cloud data platform to unify customer, sales, and inventory data across all stores.",
        "requires": ["Cloud Infrastructure"],
        "provides": ["Customer Data", "Sales Data", "Inventory Data", "Unified Data Access"],
        "owner": "Head of Data",
        "timeline": "Q1-Q2 2026",
    },
    {
        "name": "Integration Programme",
        "description": "Establish standard APIs and middleware so all systems (POS, ERP, CRM) can talk to each other reliably.",
        "requires": ["Cloud Infrastructure"],
        "provides": ["Integration Programme", "System Connectivity", "API Standards"],
        "owner": "Enterprise Architect",
        "timeline": "Q1 2026",
    },
    {
        "name": "ERP Replacement",
        "description": "Replace the legacy ERP system with a modern cloud ERP to improve finance and supply chain visibility.",
        "requires": ["Integration Programme", "Change Management Team"],
        "provides": ["Modern ERP", "Financial Data", "Supply Chain Data"],
        "owner": "CFO Office",
        "timeline": "Q2-Q4 2026",
    },
    {
        "name": "AI Customer Service",
        "description": "Deploy an AI chatbot and virtual assistant to handle customer queries across web, app, and store kiosks.",
        "requires": ["Customer Data", "Unified Data Access", "NLP Model"],
        "provides": ["Automated Customer Support", "Customer Sentiment Data"],
        "owner": "Head of Customer Experience",
        "timeline": "Q3 2026",
    },
    {
        "name": "New Digital Channel",
        "description": "Launch a new mobile app and personalised online shopping experience for customers.",
        "requires": ["Customer Data", "Unified Data Access", "System Connectivity"],
        "provides": ["Digital Sales Channel", "App Usage Data"],
        "owner": "Head of Digital",
        "timeline": "Q3-Q4 2026",
    },
    {
        "name": "Supply Chain Automation",
        "description": "Automate demand forecasting and warehouse replenishment using AI-driven inventory models.",
        "requires": ["Inventory Data", "Supply Chain Data", "Modern ERP"],
        "provides": ["Automated Replenishment", "Forecast Accuracy Improvement"],
        "owner": "Head of Supply Chain",
        "timeline": "Q4 2026",
    },
    {
        "name": "Workforce Transformation",
        "description": "Reskill store and support staff for new digital tools and AI-augmented workflows, and redesign roles.",
        "requires": ["Change Management Team"],
        "provides": ["Reskilled Workforce", "Updated Role Definitions"],
        "owner": "Head of HR",
        "timeline": "Q2-Q4 2026",
    },
    {
        "name": "AI Governance Framework",
        "description": "Establish policies, oversight, and risk controls for all AI systems being deployed across the business.",
        "requires": ["Change Management Team"],
        "provides": ["AI Risk Controls", "Compliance Sign-off"],
        "owner": "Chief Risk Officer",
        "timeline": "Q1 2026 (ongoing)",
    },
    {
        "name": "Loyalty & Personalisation Engine",
        "description": "AI-driven personalised offers and a revamped loyalty programme based on unified customer behaviour data.",
        "requires": ["Customer Data", "Unified Data Access", "App Usage Data"],
        "provides": ["Personalised Offers", "Loyalty Programme Data"],
        "owner": "Head of Marketing",
        "timeline": "Q4 2026",
    },
    {
        "name": "Cybersecurity Uplift",
        "description": "Modernise identity, access management, and threat monitoring across all new digital and cloud systems.",
        "requires": ["Cloud Infrastructure"],
        "provides": ["Security Controls", "Compliance Sign-off"],
        "owner": "CISO",
        "timeline": "Q1-Q3 2026",
    },
    {
        "name": "Finance Analytics Modernisation",
        "description": "Build AI-assisted forecasting and reporting on top of the new ERP's financial data.",
        "requires": ["Financial Data", "Modern ERP"],
        "provides": ["Financial Forecasts", "Automated Reporting"],
        "owner": "CFO Office",
        "timeline": "Q4 2026",
    },
    {
        "name": "Store Operations AI",
        "description": "AI-powered scheduling and task management for in-store staff, tied to real-time footfall and sales data.",
        "requires": ["Sales Data", "Reskilled Workforce", "Security Controls"],
        "provides": ["Optimised Staff Scheduling"],
        "owner": "Head of Retail Operations",
        "timeline": "Q4 2026 - Q1 2027",
    },
    {
        "name": "Fraud & Risk Detection",
        "description": "Real-time fraud detection across online and in-store transactions using AI models on customer and financial data.",
        "requires": ["Customer Data", "Financial Data", "Security Controls"],
        "provides": ["Fraud Risk Scores"],
        "owner": "Chief Risk Officer",
        "timeline": "Q1 2027",
    },
    {
        "name": "Supplier Collaboration Portal",
        "description": "A digital portal for suppliers to view forecasts and coordinate replenishment directly with NorthPeak's systems.",
        "requires": ["System Connectivity", "Automated Replenishment"],
        "provides": ["Supplier Visibility Data"],
        "owner": "Head of Supply Chain",
        "timeline": "Q1 2027",
    },
]


def run_seed():
    init_db()
    existing = {i["name"] for i in get_all_initiatives()}
    new_ids = []
    for item in INITIATIVES:
        if item["name"] in existing:
            print(f"Skipping (already exists): {item['name']}")
            continue
        new_id = add_initiative(
            item["name"], item["description"], item["requires"], item["provides"],
            item["owner"], item["timeline"]
        )
        new_ids.append(new_id)
        print(f"Added: {item['name']} (id={new_id})")

    print(f"\nRunning dependency analysis for all {len(get_all_initiatives())} initiatives...")
    for init in get_all_initiatives():
        analyse_initiative(init["id"])
    print("Done. Launch the app with: streamlit run app.py")


if __name__ == "__main__":
    run_seed()
