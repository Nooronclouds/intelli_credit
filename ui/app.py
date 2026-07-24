import streamlit as st
import sys
import os
import tempfile

# Agents print ✓/→ glyphs; on Windows (cp1252 console) that raises
# UnicodeEncodeError. Force UTF-8 so pipeline logging can't crash a run.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append('.')

# ── Secrets: expose GEMINI_API_KEY to the agents (they read os.getenv) ──
# On Streamlit Cloud the key lives in st.secrets; locally it comes from .env.
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass  # no secrets.toml locally — fall back to .env / environment

from dotenv import load_dotenv
load_dotenv()

import copy
import pandas as pd
from agents.ingestor import DEFAULT_SCHEMA

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Intelli-Credit",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Reference data ───────────────────────────────────────────────────
SECTORS = [
    "NBFC", "Banking", "Manufacturing", "IT / Technology",
    "Real Estate", "Pharma / Healthcare", "FMCG / Consumer", "Other",
]
LOAN_TYPES = [
    "Term Loan", "Working Capital", "Cash Credit / Overdraft",
    "Project Finance", "Loan Against Property", "Other",
]

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1F3864; margin-bottom: 0; }
    .sub-title  { font-size: 1rem; color: #666; margin-bottom: 1rem; }

    /* Stepper */
    .stepper { display: flex; gap: 0.5rem; margin: 0.5rem 0 1.5rem 0; }
    .step {
        flex: 1; text-align: center; padding: 0.6rem 0.5rem; border-radius: 8px;
        font-weight: 600; font-size: 0.9rem; border: 1px solid #E0E0E0; background: #F8F9FA; color: #999;
    }
    .step.active   { background: #1F3864; color: #fff; border-color: #1F3864; }
    .step.done     { background: #E8F1E8; color: #1E8449; border-color: #C4E0C4; }

    .decision-approve, .decision-review, .decision-reject {
        color: white; padding: 2rem; border-radius: 12px; text-align: center;
        font-size: 2rem; font-weight: 800; letter-spacing: 2px; margin: 1rem 0;
    }
    .decision-approve { background: linear-gradient(135deg, #1E8449, #27AE60); }
    .decision-review  { background: linear-gradient(135deg, #B7950B, #F39C12); }
    .decision-reject  { background: linear-gradient(135deg, #922B21, #E74C3C); }

    .flag-high   { background: #FADBD8; border-left: 4px solid #E74C3C; padding: 0.75rem 1rem; border-radius: 4px; margin: 0.4rem 0; }
    .flag-medium { background: #FDEBD0; border-left: 4px solid #F39C12; padding: 0.75rem 1rem; border-radius: 4px; margin: 0.4rem 0; }
    .flag-low    { background: #EBF5FB; border-left: 4px solid #3498DB; padding: 0.75rem 1rem; border-radius: 4px; margin: 0.4rem 0; }

    .section-header {
        font-size: 1.1rem; font-weight: 700; color: #1F3864;
        border-bottom: 2px solid #1F3864; padding-bottom: 0.3rem; margin: 1.5rem 0 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state ────────────────────────────────────────────────────
def init_state():
    ss = st.session_state
    ss.setdefault("stage", "onboarding")       # onboarding | documents | results
    ss.setdefault("onboarding_step", 1)        # 1 = entity, 2 = loan
    ss.setdefault("entity", {})
    ss.setdefault("loan", {})
    ss.setdefault("results", None)
    ss.setdefault("schema", copy.deepcopy(DEFAULT_SCHEMA))


def goto(stage, rerun=True):
    st.session_state.stage = stage
    if rerun:
        st.rerun()


init_state()


# ── Header + stepper ─────────────────────────────────────────────────
st.markdown('<p class="main-title">🏦 Intelli-Credit</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">AI-Powered Credit Appraisal — from raw documents to an explainable decision</p>', unsafe_allow_html=True)

STAGE_ORDER = ["onboarding", "documents", "results"]
STAGE_LABELS = {"onboarding": "1 · Entity Onboarding", "documents": "2 · Document Ingestion", "results": "3 · Report"}
_cur = STAGE_ORDER.index(st.session_state.stage)
chips = ""
for i, s in enumerate(STAGE_ORDER):
    cls = "active" if i == _cur else ("done" if i < _cur else "")
    chips += f'<div class="step {cls}">{STAGE_LABELS[s]}</div>'
st.markdown(f'<div class="stepper">{chips}</div>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════
# STAGE 1 — ENTITY ONBOARDING  (multi-step form)
# ═════════════════════════════════════════════════════════════════════
def render_onboarding():
    ss = st.session_state
    entity = ss.entity
    loan = ss.loan

    # ── Step 1 of 2 — Entity details ─────────────────────────────────
    if ss.onboarding_step == 1:
        st.markdown('<p class="section-header">🏢 Entity Details &nbsp;<span style="color:#999;font-size:0.8rem">Step 1 of 2</span></p>', unsafe_allow_html=True)
        with st.form("entity_form"):
            c1, c2 = st.columns(2)
            with c1:
                company_name = st.text_input("Company Name *", value=entity.get("company_name", ""))
                cin = st.text_input("CIN", value=entity.get("cin", ""), placeholder="e.g. L65910KL1997PLC011300")
                sector = st.selectbox(
                    "Sector *", SECTORS,
                    index=SECTORS.index(entity["sector"]) if entity.get("sector") in SECTORS else 0,
                )
            with c2:
                pan = st.text_input("PAN", value=entity.get("pan", ""), placeholder="e.g. AAACX1234C")
                turnover_cr = st.number_input(
                    "Annual Turnover (₹ Cr)", min_value=0.0, step=1.0,
                    value=float(entity.get("turnover_cr", 0.0)),
                )
            submitted = st.form_submit_button("Next → Loan Details", type="primary", use_container_width=True)

        if submitted:
            if not company_name.strip():
                st.error("Company Name is required.")
            else:
                ss.entity = {
                    "company_name": company_name.strip(),
                    "cin": cin.strip(),
                    "pan": pan.strip(),
                    "sector": sector,
                    "turnover_cr": turnover_cr,
                }
                ss.onboarding_step = 2
                st.rerun()

    # ── Step 2 of 2 — Loan details ───────────────────────────────────
    else:
        st.markdown('<p class="section-header">💵 Loan Details &nbsp;<span style="color:#999;font-size:0.8rem">Step 2 of 2</span></p>', unsafe_allow_html=True)
        with st.form("loan_form"):
            c1, c2 = st.columns(2)
            with c1:
                loan_type = st.selectbox(
                    "Loan Type *", LOAN_TYPES,
                    index=LOAN_TYPES.index(loan["type"]) if loan.get("type") in LOAN_TYPES else 0,
                )
                amount_cr = st.number_input(
                    "Loan Amount (₹ Cr) *", min_value=0.0, step=1.0,
                    value=float(loan.get("amount_cr", 0.0)),
                )
            with c2:
                tenure_months = st.number_input(
                    "Tenure (months) *", min_value=1, max_value=600, step=1,
                    value=int(loan.get("tenure_months", 36)),
                )
                interest_rate = st.number_input(
                    "Interest Rate (% p.a.)", min_value=0.0, max_value=100.0, step=0.25,
                    value=float(loan.get("interest_rate", 12.0)),
                )
            cols = st.columns([1, 1])
            back = cols[0].form_submit_button("← Back", use_container_width=True)
            submitted = cols[1].form_submit_button("Continue → Upload Documents", type="primary", use_container_width=True)

        if back:
            ss.onboarding_step = 1
            st.rerun()
        if submitted:
            if amount_cr <= 0:
                st.error("Loan Amount must be greater than 0.")
            else:
                ss.loan = {
                    "type": loan_type,
                    "amount_cr": amount_cr,
                    "tenure_months": int(tenure_months),
                    "interest_rate": interest_rate,
                }
                goto("documents")


# ═════════════════════════════════════════════════════════════════════
# STAGE 2 — DOCUMENT INGESTION  +  run pipeline
# ═════════════════════════════════════════════════════════════════════
def render_documents():
    ss = st.session_state
    entity = ss.entity
    loan = ss.loan

    # Entity recap
    st.markdown(
        f"**{entity.get('company_name','—')}** · {entity.get('sector','—')} · "
        f"Turnover ₹{entity.get('turnover_cr',0):,.0f} Cr &nbsp;|&nbsp; "
        f"{loan.get('type','—')} of ₹{loan.get('amount_cr',0):,.0f} Cr "
        f"for {loan.get('tenure_months','—')} months @ {loan.get('interest_rate','—')}%"
    )
    st.divider()

    if not os.getenv("GEMINI_API_KEY"):
        st.warning("⚠️ No `GEMINI_API_KEY` configured — extraction will fail. "
                   "Add it to `.env` locally or to Streamlit **Secrets** when deployed.")

    st.markdown('<p class="section-header">📂 Upload Documents</p>', unsafe_allow_html=True)
    st.caption("Financial document is required; GST and bank data unlock fraud-signal checks.")

    c1, c2, c3 = st.columns(3)
    with c1:
        pdf_file = st.file_uploader("Annual Report / ITR / CA Cert (PDF) *", type=["pdf"])
    with c2:
        gst_file = st.file_uploader("GST Data (JSON)", type=["json"])
    with c3:
        bank_file = st.file_uploader("Bank Statement (CSV)", type=["csv"])

    # ── Dynamic output schema ────────────────────────────────────────
    st.markdown('<p class="section-header">🧩 Output Schema</p>', unsafe_allow_html=True)
    with st.expander("Define what to extract — add, remove, or edit fields", expanded=False):
        st.caption(
            "The AI extracts exactly these fields into your schema. The scoring "
            "fields (net_profit_cr, dscr, debt_to_equity, current_ratio) feed the "
            "credit score — renaming them still extracts the value but skips that "
            "score component."
        )
        schema_df = pd.DataFrame(ss.schema, columns=["group", "field", "type", "description"])
        edited = st.data_editor(
            schema_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="schema_editor",
            column_config={
                "group": st.column_config.SelectboxColumn("Group", options=["company", "financials"], required=True),
                "field": st.column_config.TextColumn("Field name", required=True),
                "type": st.column_config.SelectboxColumn("Type", options=["string", "number", "list"], required=True),
                "description": st.column_config.TextColumn("Description / hint", width="large"),
            },
        )
        cleaned = [
            {k: ("" if pd.isna(v) else v) for k, v in row.items()}
            for row in edited.to_dict("records")
        ]
        ss.schema = [r for r in cleaned if str(r.get("field", "")).strip()]

        rc = st.columns([1, 3])
        if rc[0].button("↺ Reset to default"):
            ss.schema = copy.deepcopy(DEFAULT_SCHEMA)
            st.session_state.pop("schema_editor", None)
            st.rerun()
        rc[1].caption(f"{len(ss.schema)} field(s) defined.")

    nav = st.columns([1, 1, 2])
    if nav[0].button("← Back", use_container_width=True):
        ss.onboarding_step = 2
        goto("onboarding")
    run = nav[2].button("🚀 Run Appraisal", type="primary", use_container_width=True, disabled=pdf_file is None)

    if run and pdf_file:
        results = run_pipeline_ui(entity, loan, pdf_file, gst_file, bank_file, ss.schema)
        if results:
            ss.results = results
            goto("results")


def run_pipeline_ui(entity, loan, pdf_file, gst_file, bank_file, schema=None):
    """Persist uploads to temp files and run the 4-agent pipeline with progress."""
    tmp_dir = tempfile.mkdtemp()

    pdf_path = os.path.join(tmp_dir, pdf_file.name)
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

    company_name = entity.get("company_name") or "Unknown Company"

    st.markdown('<p class="section-header">⚙ Pipeline Progress</p>', unsafe_allow_html=True)
    s1, s2, s3, s4 = st.empty(), st.empty(), st.empty(), st.empty()

    try:
        from agents.ingestor import run_ingestor
        from agents.researcher import run_research_agent
        from agents.recommender import run_recommender
        from generators.cam_generator import generate_cam

        # Step 1 — extraction
        s1.info("⏳ **Step 1/4** — Extracting & analysing financial document…")
        financial_data = run_ingestor(
            pdf_path=pdf_path, company_name=company_name,
            gst_json_path=gst_path, bank_csv_path=bank_path,
            schema=schema,
        )
        if not financial_data:
            s1.error("❌ Agent 1 failed — could not extract data from document.")
            return None

        # Prefer the analyst-provided sector over the auto-guessed one
        if entity.get("sector") and entity["sector"] != "Other":
            financial_data.setdefault("company", {})["industry"] = entity["sector"]
        # Carry the onboarding context into the record for the report
        financial_data["entity_profile"] = entity
        financial_data["loan_details"] = loan
        s1.success(f"✅ **Step 1/4** — Financial data extracted for **{company_name}**")

        # Step 2 — research
        s2.info(f"⏳ **Step 2/4** — Researching {company_name} online…")
        industry = financial_data.get("company", {}).get("industry") or "General"
        research_data = run_research_agent(company_name, industry=industry) or {
            "company_name": company_name,
            "promoter_risk": {"adverse_news_found": False, "score_impact": 0},
            "litigation_risk": {"cases_found": 0, "score_impact": 0},
            "sector_risk": {"sector": "Unknown", "score_impact": 0},
            "overall_research_score": 100, "red_flags": [],
        }
        adverse = research_data.get("promoter_risk", {}).get("adverse_news_found", False)
        s2.success(f"✅ **Step 2/4** — Research complete {'⚠ Adverse news found' if adverse else '— no adverse news'}")

        # Step 3 — decision
        s3.info("⏳ **Step 3/4** — Scoring creditworthiness…")
        decision_data = run_recommender(financial_data, research_data)
        if not decision_data:
            s3.error("❌ Agent 3 failed — could not calculate credit score.")
            return None
        s3.success(f"✅ **Step 3/4** — Credit score: **{decision_data['credit_score']}/100**")

        # Step 4 — CAM
        s4.info("⏳ **Step 4/4** — Generating Credit Approval Memo…")
        cam_path = generate_cam(financial_data, research_data, decision_data)
        s4.success("✅ **Step 4/4** — CAM document generated")

        return {
            "financial_data": financial_data,
            "research_data": research_data,
            "decision_data": decision_data,
            "cam_path": cam_path,
            "company_name": company_name,
        }

    except Exception as e:
        st.error(f"Pipeline error: {e}")
        st.exception(e)
        return None


# ═════════════════════════════════════════════════════════════════════
# STAGE 3 — RESULTS
# ═════════════════════════════════════════════════════════════════════
def render_results():
    ss = st.session_state
    r = ss.results
    if not r:
        goto("documents")
        return

    financial_data = r["financial_data"]
    decision_data = r["decision_data"]
    company_name = r["company_name"]
    entity = ss.entity
    loan = ss.loan

    decision = decision_data.get("decision", "REVIEW")
    score = decision_data.get("credit_score", 0)
    css_class = {"APPROVE": "decision-approve", "REVIEW": "decision-review", "REJECT": "decision-reject"}.get(decision, "decision-review")

    st.markdown(f"""
    <div class="{css_class}">
        {decision}<br>
        <span style="font-size:1.1rem; font-weight:400; letter-spacing:0">Credit Score: {score} / 100</span><br>
        <span style="font-size:0.85rem; font-weight:400; opacity:0.9">{decision_data.get('decision_rationale', '')}</span>
    </div>
    """, unsafe_allow_html=True)

    # Loan under assessment
    st.markdown('<p class="section-header">💵 Facility Under Assessment</p>', unsafe_allow_html=True)
    lc = st.columns(4)
    lc[0].metric("Loan Type", loan.get("type", "—"))
    lc[1].metric("Amount", f"₹{loan.get('amount_cr', 0):,.0f} Cr")
    lc[2].metric("Tenure", f"{loan.get('tenure_months', '—')} mo")
    lc[3].metric("Interest", f"{loan.get('interest_rate', '—')}%")

    # Score breakdown
    st.markdown('<p class="section-header">📊 Score Breakdown</p>', unsafe_allow_html=True)
    breakdown = decision_data.get("score_breakdown", {})
    bc = st.columns(5)
    bc[0].metric("Base", f"{breakdown.get('base_score', 100)}")
    bc[1].metric("Financial", f"{breakdown.get('financial_score', 0):+d}")
    bc[2].metric("Fraud Signals", f"{breakdown.get('fraud_signal_score', 0):+d}")
    bc[3].metric("Research Risk", f"{breakdown.get('research_score', 0):+d}")
    bc[4].metric("Final", f"{breakdown.get('final_score', score)} / 100")

    # Financials
    st.markdown('<p class="section-header">💰 Financial Metrics</p>', unsafe_allow_html=True)
    financials = financial_data.get("financials", {})
    company = financial_data.get("company", {})

    def fmt(v):
        return f"₹ {v:,.2f} Cr" if v is not None else "N/A"

    def fmt_ratio(v):
        return f"{v:.2f}x" if v is not None else "N/A"

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Company Details**")
        st.table({
            "Field": ["Company", "CIN", "PAN", "Sector", "Financial Year"],
            "Value": [
                company.get("name", company_name),
                company.get("cin") or entity.get("cin") or "N/A",
                entity.get("pan") or "N/A",
                company.get("industry") or entity.get("sector") or "N/A",
                str(financials.get("year", "N/A")),
            ],
        })
    with c2:
        st.markdown("**Key Financials**")
        st.table({
            "Metric": ["Revenue", "Net Profit", "Total Assets", "Total Debt", "Cash"],
            "Value": [
                fmt(financials.get("revenue_cr")), fmt(financials.get("net_profit_cr")),
                fmt(financials.get("total_assets_cr")), fmt(financials.get("total_debt_cr")),
                fmt(financials.get("cash_cr")),
            ],
        })

    rc = st.columns(4)
    rc[0].metric("DSCR", fmt_ratio(financials.get("dscr")), help="Target ≥ 1.5x")
    rc[1].metric("Debt / Equity", fmt_ratio(financials.get("debt_to_equity")), help="Target ≤ 2.0x")
    rc[2].metric("Current Ratio", fmt_ratio(financials.get("current_ratio")), help="Target ≥ 1.2x")
    rc[3].metric("Collateral", fmt_ratio(financials.get("collateral_coverage_ratio")), help="Target ≥ 1.5x")

    # Red flags
    st.markdown('<p class="section-header">🚩 Red Flags</p>', unsafe_allow_html=True)
    red_flags = decision_data.get("red_flags", [])
    if red_flags:
        for flag in red_flags:
            severity = flag.get("severity", "LOW")
            css = {"HIGH": "flag-high", "MEDIUM": "flag-medium", "LOW": "flag-low"}.get(severity, "flag-low")
            icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵"}.get(severity, "🔵")
            st.markdown(f"""
            <div class="{css}">{icon} <strong>{flag.get('category')}</strong> — {flag.get('description')}
            &nbsp;&nbsp;<span style="color:#666; font-size:0.85rem">{flag.get('score_impact', 0):+d} pts</span></div>
            """, unsafe_allow_html=True)
    else:
        st.success("No red flags identified.")

    # Download + restart
    st.markdown('<p class="section-header">📄 Credit Approval Memo</p>', unsafe_allow_html=True)
    cam_path = r.get("cam_path")
    dc = st.columns([2, 1])
    if cam_path and os.path.exists(cam_path):
        with open(cam_path, "rb") as f:
            cam_bytes = f.read()
        dc[0].download_button(
            "⬇ Download CAM Report (.docx)", data=cam_bytes,
            file_name=f"CAM_{company_name.replace(' ', '_')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True, type="primary",
        )
    else:
        dc[0].warning("CAM file not found.")

    if dc[1].button("↺ New Appraisal", use_container_width=True):
        st.session_state.entity = {}
        st.session_state.loan = {}
        st.session_state.results = None
        st.session_state.onboarding_step = 1
        goto("onboarding")


# ── Router ───────────────────────────────────────────────────────────
stage = st.session_state.stage
if stage == "onboarding":
    render_onboarding()
elif stage == "documents":
    render_documents()
else:
    render_results()
