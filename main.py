import sys
import os
import json

# Windows consoles default to cp1252, which can't encode the ✓/→ glyphs in
# our progress logs. Force UTF-8 so the CLI doesn't crash on print().
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append('.')

from agents.ingestor       import run_ingestor
from agents.researcher     import run_research_agent
from agents.recommender    import run_recommender
from generators.cam_generator import generate_cam


def run_pipeline(
    pdf_path,
    gst_json_path=None,
    bank_csv_path=None,
    company_name=None,       # optional — extracted from PDF if not provided
    doc_type=None            # optional — auto-detected if not provided
):
    print("\n" + "="*60)
    print("   INTELLI-CREDIT — AI CREDIT APPRAISAL PIPELINE")
    print("="*60)

    # ── Agent 1 — Data Ingestor ──────────────────────────────────
    print("\n[STEP 1/4] Running Data Ingestor...")
    financial_data = run_ingestor(
        pdf_path=pdf_path,
        company_name=company_name or "Unknown Company",
        gst_json_path=gst_json_path,
        bank_csv_path=bank_csv_path,
        doc_type=doc_type
    )

    if not financial_data:
        print("\n✗ Pipeline failed — Agent 1 returned no data.")
        return None

    # Pull company name from extraction if not provided by user
    extracted_name = financial_data.get("company", {}).get("name")
    if not company_name and extracted_name:
        company_name = extracted_name
        print(f"  Company name extracted from document: {company_name}")
    elif not company_name:
        print("  WARNING: Could not extract company name from document.")
        company_name = "Unknown Company"

    # ── Agent 2 — Research Agent ─────────────────────────────────
    print(f"\n[STEP 2/4] Running Research Agent for: {company_name}...")
    industry = financial_data.get("company", {}).get("industry", "General")
    research_data = run_research_agent(company_name, industry=industry)

    if not research_data:
        print("  WARNING: Research agent returned no data — continuing with empty research.")
        research_data = {
            "company_name": company_name,
            "promoter_risk":  {"adverse_news_found": False, "score_impact": 0},
            "litigation_risk": {"cases_found": 0, "score_impact": 0},
            "sector_risk":     {"sector": "Unknown", "score_impact": 0},
            "overall_research_score": 100,
            "red_flags": []
        }

    # ── Agent 3 — Credit Recommender ─────────────────────────────
    print("\n[STEP 3/4] Running Credit Recommender...")
    decision_data = run_recommender(financial_data, research_data)

    if not decision_data:
        print("\n✗ Pipeline failed — Agent 3 returned no data.")
        return None

    # ── CAM Generator ────────────────────────────────────────────
    print("\n[STEP 4/4] Generating Credit Approval Memo...")
    cam_path = generate_cam(financial_data, research_data, decision_data)

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "="*60)
    print("   PIPELINE COMPLETE")
    print("="*60)
    print(f"   Company  : {company_name}")
    print(f"   Score    : {decision_data['credit_score']}/100")
    print(f"   Decision : {decision_data['decision']}")
    print(f"   CAM      : {cam_path}")
    print("="*60 + "\n")

    return {
        "financial_data": financial_data,
        "research_data":  research_data,
        "decision_data":  decision_data,
        "cam_path":       cam_path
    }


if __name__ == "__main__":
    # ── Default test run ─────────────────────────────────────────
    result = run_pipeline(
        pdf_path="data/sample_annual_report.pdf",
        gst_json_path="data/sample_gst.json",
        bank_csv_path="data/sample_bank_statement.csv",
        company_name="Muthoot Finance Ltd"
    )