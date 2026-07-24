import pdfplumber
import pytesseract
import requests
import json
import os
import re
import numpy as np
from PIL import Image

from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

os.environ["CUDA_VISIBLE_DEVICES"] = ""  # force sentence-transformers to CPU

# ── Tesseract location (cross-platform) ─────────────────────────────
# On Windows, point at the standard installer path if present.
# On Linux/macOS (e.g. Streamlit Cloud, where tesseract-ocr is installed
# via packages.txt) it is already on PATH, so we leave the default.
_WIN_TESSERACT = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(_WIN_TESSERACT):
    pytesseract.pytesseract.tesseract_cmd = _WIN_TESSERACT

# ── Output path ──────────────────────────────────────────────────────
OUTPUT_PATH = "outputs/financial_data.json"

# ── Document type RAG queries ────────────────────────────────────────
# Each document type gets different queries because they use
# different terminology for the same financial concepts
DOC_TYPE_QUERIES = {
    "annual_report": [
        "CIN corporate identity number PAN company registration",
        "board of directors managing director chairman",
        "total revenue income from operations interest income",
        "profit after tax net profit PAT",
        "total assets financial assets loans",
        "total debt borrowings debt securities liabilities",
        "equity shareholders funds net worth reserves",
        "cash and cash equivalents bank balance",
        "industry gold loan NBFC financial services manufacturing",
    ],
    "itr": [
        "gross total income total income assessment year",
        "business income profession income salary income",
        "tax paid advance tax TDS refund",
        "net profit loss from business",
        "total assets liabilities balance sheet ITR",
        "depreciation capital gains",
        "PAN permanent account number assessee name",
        "equity capital reserves surplus",
        "cash bank balance current assets",
    ],
    "ca_certificate": [
        "turnover gross receipts total income",
        "net profit loss audited accounts",
        "total assets liabilities net worth",
        "statutory audit certified accounts",
        "directors partners proprietor name",
        "outstanding loans borrowings debt",
        "cash bank balances current assets",
        "equity capital reserves",
        "CIN PAN registration number",
    ],
    "bank_statement_pdf": [
        "opening balance closing balance",
        "total credits total debits",
        "average balance minimum balance",
        "account number IFSC branch",
        "salary credit EMI debit",
        "bounce dishonour return",
    ],
}


def detect_document_type(text):
    """
    Auto-detect what kind of financial document this is.
    Uses keyword frequency scoring.
    """
    text_lower = text[:5000].lower()

    scores = {
        "annual_report": 0,
        "itr": 0,
        "ca_certificate": 0,
        "bank_statement_pdf": 0,
    }

    # Annual report signals
    if "annual report" in text_lower: scores["annual_report"] += 3
    if "board of directors" in text_lower: scores["annual_report"] += 2
    if "statement of profit and loss" in text_lower: scores["annual_report"] += 3
    if "standalone" in text_lower: scores["annual_report"] += 2
    if "consolidated" in text_lower: scores["annual_report"] += 1

    # ITR signals
    if "income tax return" in text_lower: scores["itr"] += 3
    if "assessment year" in text_lower: scores["itr"] += 3
    if "gross total income" in text_lower: scores["itr"] += 2
    if "itr-" in text_lower: scores["itr"] += 3
    if "form 16" in text_lower: scores["itr"] += 2

    # CA Certificate signals
    if "auditor" in text_lower: scores["ca_certificate"] += 2
    if "chartered accountant" in text_lower: scores["ca_certificate"] += 3
    if "certificate" in text_lower: scores["ca_certificate"] += 1
    if "statutory audit" in text_lower: scores["ca_certificate"] += 2
    if "udin" in text_lower: scores["ca_certificate"] += 3

    # Bank statement signals
    if "account statement" in text_lower: scores["bank_statement_pdf"] += 3
    if "opening balance" in text_lower: scores["bank_statement_pdf"] += 2
    if "closing balance" in text_lower: scores["bank_statement_pdf"] += 2
    if "transaction date" in text_lower: scores["bank_statement_pdf"] += 2

    detected = max(scores, key=scores.get)
    confidence = scores[detected]
    print(f"  Detected document type: {detected.upper()} (score: {confidence})")
    return detected


def detect_unit(text):
    """
    Detect monetary unit used in document.
    Indian documents use millions, lakhs, or crores.
    """
    sample = text[:10000].lower()

    if "in millions" in sample or "h in millions" in sample or "rs. in millions" in sample:
        unit = "millions"
        conversion = "divide by 10 to convert to crores"
    elif "in lakhs" in sample or "h in lakhs" in sample or "rs. in lakhs" in sample:
        unit = "lakhs"
        conversion = "divide by 100 to convert to crores"
    elif "in crores" in sample or "h in crores" in sample or "rs. in crores" in sample:
        unit = "crores"
        conversion = "already in crores, use values directly"
    else:
        unit = "millions"
        conversion = "assume millions, divide by 10 to convert to crores"

    print(f"  Detected unit: {unit.upper()} → {conversion}")
    return unit, conversion


def extract_text_from_pdf(pdf_path):
    """
    Step 1: Extract text from PDF.
    Uses cache to avoid re-processing same file.
    Falls back to OCR for scanned documents.
    """
    cache_path = pdf_path.replace('.pdf', '_extracted.txt')

    if os.path.exists(cache_path):
        print("  Using cached extraction (instant)")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read(), 1.0

    text = ""
    confidence = 1.0

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        if len(text.strip()) < 500:
            print("  Digital extraction got little text. Trying OCR...")
            text = extract_text_with_ocr(pdf_path)
            confidence = 0.7

    except Exception as e:
        print(f"  pdfplumber failed: {e}. Trying OCR...")
        text = extract_text_with_ocr(pdf_path)
        confidence = 0.6

    with open(cache_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("  Text cached for future runs")

    return text, confidence


def extract_text_with_ocr(pdf_path):
    """
    OCR fallback for scanned PDFs.
    Only processes first 50 and last 50 pages to save time.
    """
    try:
        import pypdfium2 as pdfium

        text = ""
        pdf = pdfium.PdfDocument(pdf_path)
        total = len(pdf)
        pages_to_scan = sorted(set(
            list(range(min(50, total))) + list(range(max(0, total - 50), total))
        ))

        for page_number in pages_to_scan:
            page = pdf[page_number]
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()
            page_text = pytesseract.image_to_string(pil_image, lang='eng')
            text += page_text + "\n"
            print(f"  OCR done: page {page_number + 1}/{total}")

        return text

    except Exception as e:
        print(f"  OCR also failed: {e}")
        return ""


def build_rag_index(text, cache_dir="outputs", pdf_path=""):
    from sentence_transformers import SentenceTransformer
    import faiss

    import hashlib
    pdf_hash    = hashlib.md5(open(pdf_path, 'rb').read(4096)).hexdigest()[:8]
    index_path  = os.path.join(cache_dir, f"faiss_index_{pdf_hash}.bin")
    chunks_path = os.path.join(cache_dir, f"chunks_{pdf_hash}.json")

    # Load from cache if exists — instant
    if os.path.exists(index_path) and os.path.exists(chunks_path):
        print("  Using cached FAISS index (instant)")
        index = faiss.read_index(index_path)
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        return index, chunks, model

    # Build fresh
    chunk_size = 500  # characters per chunk
    overlap    = 50   # characters of overlap between chunks
    chunks     = []

    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size].strip()
        if chunk:
            chunks.append(chunk)

    print(f"  Built {len(chunks)} chunks from document")

    model      = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    embeddings = model.encode(
        chunks,
        show_progress_bar=True,
        batch_size=128,
        normalize_embeddings=True
    )
    embeddings = np.array(embeddings).astype('float32')

    dimension = embeddings.shape[1]
    index     = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # Save to cache
    os.makedirs(cache_dir, exist_ok=True)
    faiss.write_index(index, index_path)
    with open(chunks_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f)
    print("  FAISS index cached for future runs")

    return index, chunks, model


def query_rag(index, chunks, model, query, top_k=4):
    """
    Semantic search over FAISS index.
    Returns most relevant chunks for a query.
    """
    query_embedding = model.encode([query])
    query_embedding = np.array(query_embedding).astype('float32')
    distances, indices = index.search(query_embedding, top_k)
    relevant = [chunks[i] for i in indices[0] if i < len(chunks)]
    return "\n---\n".join(relevant)


def ask_llm_to_extract(rag_text, company_name="Unknown", unit="millions", conversion="divide by 10"):
    """
    Send RAG-retrieved chunks to Gemini for structured JSON extraction.
    """
    truncated_text = rag_text[:7000]

    prompt = f"""You are a financial data extraction assistant for Indian banks.
Extract key financial figures from this document and return ONLY a JSON object.

RULES:
- Return ONLY valid JSON. No explanation. No markdown. No backticks.
- CRITICAL: This document reports monetary values in {unit}
- YOU MUST pre-calculate all conversions: {conversion}
- Example if millions: 170990.93 → calculate 170990.93/10 = 17099.09 → write 17099.09
- Example if lakhs: 17099.30 → calculate 17099.30/100 = 170.99 → write 170.99
- Example if crores: 17099.09 → write 17099.09 directly
- NEVER write math expressions in JSON — only write the final calculated number
- Apply conversion to ALL values — revenue, profit, assets, debt, equity, cash
- Ignore LKR values (Sri Lanka) completely — INR only
- NEVER use commas inside numbers. Write 168770.14 not 168,770.14
- CIN looks like L65910KL1997PLC011300 — extract exactly if found
- directors should be a JSON array of name strings like ["Name One", "Name Two"]
- industry should be one word: NBFC or Banking or Manufacturing etc
- If a value is not found use null

JSON structure to fill:
{{
  "company": {{
    "name": "{company_name}",
    "cin": null,
    "pan": null,
    "directors": [],
    "industry": null,
    "loan_requested_cr": null
  }},
  "financials": {{
    "revenue_cr": null,
    "net_profit_cr": null,
    "total_assets_cr": null,
    "total_debt_cr": null,
    "equity_cr": null,
    "ebitda_cr": null,
    "cash_cr": null,
    "dscr": null,
    "debt_to_equity": null,
    "current_ratio": null,
    "collateral_value_cr": null,
    "collateral_coverage_ratio": null,
    "year": null
  }}
}}

Document text:
{truncated_text}"""

    try:
        print("  Sending to Gemini for extraction...")
        response = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 2048}
            },
            timeout=60
        )

        result = response.json()
        raw = result["candidates"][0]["content"]["parts"][0]["text"]
        print(f"  Gemini raw response: {raw[:300]}")

        start = raw.find('{')
        end   = raw.rfind('}') + 1
        if start == -1:
            print("  Gemini didn't return valid JSON.")
            return None

        clean_json = raw[start:end]
        try:
            return json.loads(clean_json)
        except json.JSONDecodeError:
            clean_json = re.sub(r'(\d),(\d)', r'\1\2', clean_json)
            try:
                return json.loads(clean_json)
            except Exception as e:
                print(f"  JSON parse failed: {e}")
                return None

    except Exception as e:
        print(f"  Gemini extraction failed: {e}")
        return None


def calculate_ratios(fin):
    """
    Auto-calculate derived ratios from extracted figures.
    """
    try:
        if fin.get("total_debt_cr") and fin.get("equity_cr") and fin["equity_cr"] > 0:
            fin["debt_to_equity"] = round(fin["total_debt_cr"] / fin["equity_cr"], 2)

        if fin.get("net_profit_cr") and fin.get("total_debt_cr") and fin["total_debt_cr"] > 0:
            fin["dscr"] = round(fin["net_profit_cr"] / (fin["total_debt_cr"] * 0.1), 2)

        if fin.get("total_assets_cr") and fin.get("total_debt_cr") and fin["total_debt_cr"] > 0:
            fin["collateral_coverage_ratio"] = round(fin["total_assets_cr"] / fin["total_debt_cr"], 2)
            fin["collateral_value_cr"] = fin["total_assets_cr"]

    except Exception as e:
        print(f"  Ratio calculation error: {e}")

    return fin


def analyze_gst(gstr3b_revenue, gstr2a_revenue):
    """
    GSTR-3B vs GSTR-2A reconciliation.
    Key Indian fraud detection feature.
    """
    if not gstr3b_revenue or not gstr2a_revenue:
        return {
            "gstr3b_revenue_cr": gstr3b_revenue,
            "gstr2a_revenue_cr": gstr2a_revenue,
            "mismatch_percentage": None,
            "flag": "INSUFFICIENT_DATA",
            "score_impact": 0,
            "note": "GST data not available for comparison"
        }

    mismatch = ((gstr3b_revenue - gstr2a_revenue) / gstr3b_revenue) * 100

    if mismatch > 30:
        flag, impact = "REVENUE_INFLATION", -12
        note = f"{mismatch:.1f}% gap between self-declared and supplier-declared revenue"
    elif mismatch > 15:
        flag, impact = "MODERATE_MISMATCH", -6
        note = f"{mismatch:.1f}% mismatch — moderate concern"
    else:
        flag, impact = "CLEAN", 0
        note = f"GST reconciliation clean — {mismatch:.1f}% variance"

    return {
        "gstr3b_revenue_cr": gstr3b_revenue,
        "gstr2a_revenue_cr": gstr2a_revenue,
        "mismatch_percentage": round(mismatch, 2),
        "flag": flag,
        "score_impact": impact,
        "note": note
    }


def analyze_bank_statement(csv_path):
    """Parse bank statement CSV for flow patterns."""
    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        df.columns = [c.lower().strip() for c in df.columns]

        total_credits = df['credit_cr'].sum() if 'credit_cr' in df.columns else 0
        total_debits = df['debit_cr'].sum() if 'debit_cr' in df.columns else 0
        months = max(1, len(df) // 30)

        return {
            "avg_monthly_credit_cr": round(total_credits / months, 2),
            "avg_monthly_debit_cr": round(total_debits / months, 2),
            "min_balance_cr": round(df['balance_cr'].min(), 2) if 'balance_cr' in df.columns else None,
            "bounce_count_6months": 0,
            "gst_bank_revenue_match_pct": None,
            "irregular_patterns": []
        }
    except Exception as e:
        print(f"  Bank statement parsing failed: {e}")
        return {
            "avg_monthly_credit_cr": None, "avg_monthly_debit_cr": None,
            "min_balance_cr": None, "bounce_count_6months": None,
            "gst_bank_revenue_match_pct": None, "irregular_patterns": []
        }


def detect_circular_trading(csv_path):
    """NetworkX graph-based circular trading detection."""
    try:
        import pandas as pd
        import networkx as nx

        df = pd.read_csv(csv_path)
        df.columns = [c.lower().strip() for c in df.columns]
        df['date'] = pd.to_datetime(df['date'])

        def extract_party(desc):
            desc = str(desc)
            for prefix in ["Payment to ", "Receipt from ", "Client payment - ",
                           "Return payment from ", "payment - "]:
                if prefix.lower() in desc.lower():
                    idx = desc.lower().find(prefix.lower())
                    return desc[idx + len(prefix):].strip()
            return desc.strip()

        df['party'] = df['description'].apply(extract_party)
        G = nx.DiGraph()

        for _, row in df.iterrows():
            party = row['party']
            if pd.notna(row.get('credit_cr')) and row['credit_cr'] > 0:
                G.add_edge(party, 'OUR_COMPANY', amount=float(row['credit_cr']))
            if pd.notna(row.get('debit_cr')) and row['debit_cr'] > 0:
                G.add_edge('OUR_COMPANY', party, amount=float(row['debit_cr']))

        cycles = list(nx.simple_cycles(G))
        suspicious = [
            {"parties": c, "risk": "HIGH" if len(c) == 2 else "MEDIUM"}
            for c in cycles if 'OUR_COMPANY' in c and len(c) >= 2
        ]

        risk_level = "HIGH" if len(suspicious) > 3 else "MEDIUM" if suspicious else "LOW"
        score_impact = -20 if len(suspicious) > 3 else -10 if suspicious else 0

        return {
            "detected": len(suspicious) > 0,
            "cycles_found": len(suspicious),
            "suspicious_transactions": suspicious[:5],
            "risk_level": risk_level,
            "score_impact": score_impact
        }

    except Exception as e:
        print(f"  Circular trading detection failed: {e}")
        return {
            "detected": False, "cycles_found": 0,
            "suspicious_transactions": [], "risk_level": "LOW", "score_impact": 0
        }


def run_ingestor(pdf_path, company_name, gst_json_path=None, bank_csv_path=None, doc_type=None):
    """
    MAIN FUNCTION — called by main.py orchestrator.

    Parameters:
        pdf_path      : path to PDF (annual report / ITR / CA cert)
        company_name  : company name string
        gst_json_path : path to GST JSON file (optional)
        bank_csv_path : path to bank statement CSV (optional)
        doc_type      : "annual_report" | "itr" | "ca_certificate" | None = auto-detect
    """

    print(f"\n{'='*50}")
    print(f"AGENT 1 — DATA INGESTOR")
    print(f"Company: {company_name}")
    print(f"{'='*50}")

    # Step 1: Extract text from PDF
    print("\n[1/5] Extracting text from PDF...")
    if pdf_path and os.path.exists(pdf_path):
        raw_text, confidence = extract_text_from_pdf(pdf_path)
        print(f"  Extracted {len(raw_text)} characters (confidence: {confidence})")
    else:
        print("  No PDF provided — skipping extraction")
        raw_text, confidence = "", 0.5

    # Step 2: RAG + LLM extraction
    print("\n[2/5] Structuring data with RAG + LLM...")
    llm_output = None

    if raw_text:
        # Auto-detect doc type and unit if not provided
        if doc_type is None:
            doc_type = detect_document_type(raw_text)
        unit, conversion = detect_unit(raw_text)

        # Get queries for this document type
        queries = DOC_TYPE_QUERIES.get(doc_type, DOC_TYPE_QUERIES["annual_report"])

        print("  Building FAISS RAG index...")
        rag_index, rag_chunks, rag_model = build_rag_index(raw_text, pdf_path=pdf_path)

        print("  Querying RAG index...")
        seen = set()
        final_chunks = []

        for query in queries:
            result = query_rag(rag_index, rag_chunks, rag_model, query, top_k=3)
            for chunk in result.split("\n---\n"):
                chunk = chunk.strip()
                if chunk and chunk not in seen and 'LKR' not in chunk:
                    seen.add(chunk)
                    final_chunks.append(chunk)

        rag_text = "\n---\n".join(final_chunks[:15])
        print(f"  RAG retrieved {len(final_chunks)} unique relevant chunks")

        llm_output = ask_llm_to_extract(rag_text, company_name, unit, conversion)

    if llm_output:
        company_data = llm_output.get("company", {})
        # Deduplicate directors list
        if "directors" in company_data:
            company_data["directors"] = list(dict.fromkeys(company_data.get("directors", [])))
        financials = llm_output.get("financials", {})
        financials = calculate_ratios(financials)
    else:
        company_data = {"name": company_name}
        financials = {}

    # Step 3: GST Analysis
    print("\n[3/5] Running GST analysis...")
    gstr3b_rev = gstr2a_rev = None
    if gst_json_path and os.path.exists(gst_json_path):
        with open(gst_json_path, 'r') as f:
            gst_data = json.load(f)
            gstr3b_rev = gst_data.get("gstr3b", {}).get("total_taxable_supply_cr")
            gstr2a_rev = gst_data.get("gstr2a", {}).get("total_inward_supply_cr")

    gst_analysis = analyze_gst(gstr3b_rev, gstr2a_rev)
    print(f"  GST Flag: {gst_analysis['flag']} | Impact: {gst_analysis['score_impact']} pts")

    # Step 4: Bank Statement Analysis
    print("\n[4/5] Analyzing bank statement...")
    bank_analysis = {}
    circular_trading = {
        "detected": False, "cycles_found": 0,
        "suspicious_transactions": [], "risk_level": "LOW", "score_impact": 0
    }

    if bank_csv_path and os.path.exists(bank_csv_path):
        bank_analysis = analyze_bank_statement(bank_csv_path)
        circular_trading = detect_circular_trading(bank_csv_path)
        print(f"  Circular Trading: {circular_trading['risk_level']} | Impact: {circular_trading['score_impact']} pts")
    else:
        print("  No bank statement provided — skipping")

    # Step 5: Assemble final JSON
    print("\n[5/5] Assembling financial_data.json...")
    financial_data = {
        "company": company_data,
        "financials": financials,
        "gst_analysis": gst_analysis,
        "bank_analysis": bank_analysis,
        "circular_trading": circular_trading,
        "extraction_confidence": confidence,
        "doc_type_detected": doc_type
    }

    os.makedirs("outputs", exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(financial_data, f, indent=2, default=str)

    print(f"\n✓ financial_data.json saved to {OUTPUT_PATH}")
    print(f"{'='*50}\n")
    return financial_data


# ────────────────────────────────────────────────────────────────────
# HOW TO TEST WITH DIFFERENT DOCUMENTS:
#
# 1. ANOTHER COMPANY'S ANNUAL REPORT:
#    - Download from BSE: www.bseindia.com
#    - Search any company → Annual Reports → Download PDF
#    - Save to data/ folder, change pdf_path and company_name below
#
# 2. ITR DOCUMENT:
#    - Use any ITR PDF, set doc_type="itr"
#    - OR leave doc_type=None to auto-detect
#
# 3. CA CERTIFICATE:
#    - Use any CA audit certificate PDF
#    - Set doc_type="ca_certificate"
#
# 4. SCANNED PDF TEST:
#    - Use any scanned financial doc
#    - Watch for "Trying OCR..." in terminal output
#    - extraction_confidence will drop to 0.7
#
# FREE TEST DOCUMENTS:
#    BSE: www.bseindia.com/corporates/ann.html
#    NSE: www.nseindia.com
#    MCA: www.mca.gov.in
# ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = run_ingestor(
        pdf_path="data/sample_annual_report.pdf",
        company_name="Muthoot Finance Ltd",
        gst_json_path="data/sample_gst.json",
        bank_csv_path="data/sample_bank_statement.csv",
        doc_type=None,  # None = auto-detect | "annual_report" | "itr" | "ca_certificate"
    )
    print("Sample output:")
    print(json.dumps(result, indent=2, default=str))