import streamlit as st
import sys
import os
import json
import tempfile
import time

sys.path.append('.')

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Intelli-Credit",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1F3864;
        margin-bottom: 0;
    }
    .sub-title {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .decision-approve {
        background: linear-gradient(135deg, #1E8449, #27AE60);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        text-align: center;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 2px;
        margin: 1rem 0;
    }
    .decision-review {
        background: linear-gradient(135deg, #B7950B, #F39C12);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        text-align: center;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 2px;
        margin: 1rem 0;
    }
    .decision-reject {
        background: linear-gradient(135deg, #922B21, #E74C3C);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        text-align: center;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 2px;
        margin: 1rem 0;
    }
    .metric-card {
        background: #F8F9FA;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .flag-high {
        background: #FADBD8;
        border-left: 4px solid #E74C3C;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin: 0.4rem 0;
    }
    .flag-medium {
        background: #FDEBD0;
        border-left: 4px solid #F39C12;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin: 0.4rem 0;
    }
    .flag-low {
        background: #EBF5FB;
        border-left: 4px solid #3498DB;
        padding: 0.75rem 1rem;
        border-radius: 4px;
        margin: 0.4rem 0;
    }
    .step-complete {
        color: #1E8449;
        font-weight: 600;
    }
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1F3864;
        border-bottom: 2px solid #1F3864;
        padding-bottom: 0.3rem;
        margin: 1.5rem 0 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Header ───────────────────────────────────────────────────────────
st.markdown('<p class="main-title">🏦 Intelli-Credit</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">AI-Powered Credit Appraisal System — IIT Hyderabad Hackathon 2026</p>', unsafe_allow_html=True)
st.divider()


# ── Sidebar — File Uploads ────────────────────────────────────────────
with st.sidebar:
    st.header("📂 Upload Documents")

    pdf_file = st.file_uploader(
        "Annual Report / ITR / CA Certificate *",
        type=["pdf"],
        help="Required — upload the company's financial document"
    )

    company_name_input = st.text_input(
        "Company Name (optional)",
        placeholder="Auto-extracted from document if blank"
    )

    st.markdown("---")
    st.subheader("Optional Documents")

    gst_file = st.file_uploader(
        "GST Data (JSON)",
        type=["json"],
        help="GSTR-3B and GSTR-2A reconciliation data"
    )

    bank_file = st.file_uploader(
        "Bank Statement (CSV)",
        type=["csv"],
        help="6-month bank statement for circular trading detection"
    )

    st.markdown("---")

    run_button = st.button(
        "🚀 Run Appraisal",
        type="primary",
        use_container_width=True,
        disabled=pdf_file is None
    )

    if pdf_file is None:
        st.caption("⬆ Upload a PDF to get started")

    st.markdown("---")
    st.caption("Built by Team Intelli-Credit\nNayef · Noor · Arfa · Meiraj")


# ── Main area — idle state ────────────────────────────────────────────
if not run_button:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**Step 1 — Upload**\nUpload the company's financial document (PDF) and optionally GST + bank data.")
    with col2:
        st.info("**Step 2 — Analyze**\nOur AI pipeline extracts financials, detects fraud signals, and researches company risk.")
    with col3:
        st.info("**Step 3 — Decision**\nGet a credit score, APPROVE/REVIEW/REJECT decision, and a downloadable CAM report.")


# ── Pipeline execution ────────────────────────────────────────────────
if run_button and pdf_file:

    # Save uploaded files to temp paths
    tmp_dir = tempfile.mkdtemp()

    pdf_path  = os.path.join(tmp_dir, pdf_file.name)
    with open(pdf_path, "wb") as f:
        f.write(pdf_file.read())

    gst_path = None
    if gst_file:
        gst_path = os.path.join(tmp_dir, "gst.json")
        with open(gst_path, "wb") as f:
            f.write(gst_file.read())

    bank_path = None
    if bank_file:
        bank_path = os.path.join(tmp_dir, "bank.csv")
        with open(bank_path, "wb") as f:
            f.write(bank_file.read())

    company_name = company_name_input.strip() or None

    # ── Progress display ──────────────────────────────────────────
    st.markdown('<p class="section-header">⚙ Pipeline Progress</p>', unsafe_allow_html=True)

    step1 = st.empty()
    step2 = st.empty()
    step3 = st.empty()
    step4 = st.empty()
    results_placeholder = st.empty()

    try:
        from agents.ingestor       import run_ingestor
        from agents.researcher     import run_research_agent
        from agents.recommender    import run_recommender
        from generators.cam_generator import generate_cam

        # ── Step 1 ────────────────────────────────────────────────
        step1.info("⏳ **Step 1/4** — Extracting and analyzing financial document...")
        financial_data = run_ingestor(
            pdf_path=pdf_path,
            company_name=company_name or "Unknown Company",
            gst_json_path=gst_path,
            bank_csv_path=bank_path
        )

        if not financial_data:
            st.error("❌ Agent 1 failed — could not extract data from document.")
            st.stop()

        extracted_name = financial_data.get("company", {}).get("name")
        if not company_name and extracted_name:
            company_name = extracted_name

        step1.success(f"✅ **Step 1/4** — Financial data extracted for **{company_name}**")

        # ── Step 2 ────────────────────────────────────────────────
        step2.info(f"⏳ **Step 2/4** — Researching {company_name} online...")
        industry = financial_data.get("company", {}).get("industry") or "General"
        research_data = run_research_agent(company_name, industry=industry)

        if not research_data:
            research_data = {
                "company_name": company_name,
                "promoter_risk":   {"adverse_news_found": False, "score_impact": 0},
                "litigation_risk": {"cases_found": 0, "score_impact": 0},
                "sector_risk":     {"sector": "Unknown", "score_impact": 0},
                "overall_research_score": 100,
                "red_flags": []
            }

        adverse = research_data.get("promoter_risk", {}).get("adverse_news_found", False)
        step2.success(f"✅ **Step 2/4** — Research complete {'⚠ Adverse news found' if adverse else '— No adverse news'}")

        # ── Step 3 ────────────────────────────────────────────────
        step3.info("⏳ **Step 3/4** — Calculating credit score...")
        decision_data = run_recommender(financial_data, research_data)

        if not decision_data:
            st.error("❌ Agent 3 failed — could not calculate credit score.")
            st.stop()

        step3.success(f"✅ **Step 3/4** — Credit score calculated: **{decision_data['credit_score']}/100**")

        # ── Step 4 ────────────────────────────────────────────────
        step4.info("⏳ **Step 4/4** — Generating Credit Approval Memo...")
        cam_path = generate_cam(financial_data, research_data, decision_data)
        step4.success("✅ **Step 4/4** — CAM document generated")

        st.divider()

        # ══════════════════════════════════════════════════════════
        # RESULTS
        # ══════════════════════════════════════════════════════════

        decision = decision_data.get("decision", "REVIEW")
        score    = decision_data.get("credit_score", 0)

        # ── Decision banner ───────────────────────────────────────
        css_class = {
            "APPROVE": "decision-approve",
            "REVIEW":  "decision-review",
            "REJECT":  "decision-reject"
        }.get(decision, "decision-review")

        st.markdown(f"""
        <div class="{css_class}">
            {decision}<br>
            <span style="font-size:1.1rem; font-weight:400; letter-spacing:0">
                Credit Score: {score} / 100
            </span><br>
            <span style="font-size:0.85rem; font-weight:400; opacity:0.9">
                {decision_data.get('decision_rationale', '')}
            </span>
        </div>
        """, unsafe_allow_html=True)

        # ── Score breakdown metrics ───────────────────────────────
        st.markdown('<p class="section-header">📊 Score Breakdown</p>', unsafe_allow_html=True)
        breakdown = decision_data.get("score_breakdown", {})

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Base Score",       f"{breakdown.get('base_score', 100)}")
        col2.metric("Financial Health", f"{breakdown.get('financial_score', 0):+d}")
        col3.metric("Fraud Signals",    f"{breakdown.get('fraud_signal_score', 0):+d}")
        col4.metric("Research Risk",    f"{breakdown.get('research_score', 0):+d}")
        col5.metric("Final Score",      f"{breakdown.get('final_score', score)} / 100")

        # ── Financial metrics ─────────────────────────────────────
        st.markdown('<p class="section-header">💰 Financial Metrics</p>', unsafe_allow_html=True)
        financials = financial_data.get("financials", {})
        company    = financial_data.get("company", {})

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Company Details**")
            st.table({
                "Field": ["Company", "CIN", "Industry", "Financial Year"],
                "Value": [
                    company.get("name", "N/A"),
                    company.get("cin", "N/A"),
                    company.get("industry", "N/A"),
                    str(financials.get("year", "N/A"))
                ]
            })

        with col2:
            st.markdown("**Key Financials (Rs. Cr)**")

            def fmt(val):
                return f"Rs. {val:,.2f} Cr" if val is not None else "N/A"
            def fmt_ratio(val):
                return f"{val:.2f}x" if val is not None else "N/A"

            st.table({
                "Metric": ["Revenue", "Net Profit", "Total Assets", "Total Debt", "Cash"],
                "Value": [
                    fmt(financials.get("revenue_cr")),
                    fmt(financials.get("net_profit_cr")),
                    fmt(financials.get("total_assets_cr")),
                    fmt(financials.get("total_debt_cr")),
                    fmt(financials.get("cash_cr")),
                ]
            })

        # Ratios
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("DSCR",          fmt_ratio(financials.get("dscr")),       help="Target: >= 1.5x")
        col2.metric("Debt / Equity", fmt_ratio(financials.get("debt_to_equity")), help="Target: <= 2.0x")
        col3.metric("Current Ratio", fmt_ratio(financials.get("current_ratio")),  help="Target: >= 1.2x")
        col4.metric("Collateral",    fmt_ratio(financials.get("collateral_coverage_ratio")), help="Target: >= 1.5x")

        # ── Red flags ─────────────────────────────────────────────
        st.markdown('<p class="section-header">🚩 Red Flags</p>', unsafe_allow_html=True)
        red_flags = decision_data.get("red_flags", [])

        if red_flags:
            for flag in red_flags:
                severity  = flag.get("severity", "LOW")
                css       = {"HIGH": "flag-high", "MEDIUM": "flag-medium", "LOW": "flag-low"}.get(severity, "flag-low")
                icon      = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(severity, "🔵")
                st.markdown(f"""
                <div class="{css}">
                    {icon} <strong>{flag.get('category')}</strong> — {flag.get('description')}
                    &nbsp;&nbsp;<span style="color:#666; font-size:0.85rem">{flag.get('score_impact', 0):+d} pts</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No red flags identified.")

        # ── Download CAM ──────────────────────────────────────────
        st.markdown('<p class="section-header">📄 Credit Approval Memo</p>', unsafe_allow_html=True)

        if cam_path and os.path.exists(cam_path):
            with open(cam_path, "rb") as f:
                cam_bytes = f.read()
            st.download_button(
                label="⬇ Download CAM Report (.docx)",
                data=cam_bytes,
                file_name=f"CAM_{company_name.replace(' ', '_')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                type="primary"
            )
        else:
            st.warning("CAM file not found — check outputs folder.")

    except Exception as e:
        st.error(f"Pipeline error: {str(e)}")
        st.exception(e)