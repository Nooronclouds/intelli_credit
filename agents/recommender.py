import json
import os
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────
FINANCIAL_DATA_PATH = "outputs/financial_data.json"
RESEARCH_DATA_PATH  = "outputs/research_data.json"
DECISION_OUTPUT     = "outputs/decision.json"


def load_data():
    """Load Agent 1 and Agent 2 outputs."""
    financial_data, research_data = {}, {}

    if os.path.exists(FINANCIAL_DATA_PATH):
        with open(FINANCIAL_DATA_PATH) as f:
            financial_data = json.load(f)
        print(f"  Loaded: {FINANCIAL_DATA_PATH}")
    else:
        print(f"  WARNING: {FINANCIAL_DATA_PATH} not found — run ingestor.py first")

    if os.path.exists(RESEARCH_DATA_PATH):
        with open(RESEARCH_DATA_PATH) as f:
            research_data = json.load(f)
        print(f"  Loaded: {RESEARCH_DATA_PATH}")
    else:
        print(f"  WARNING: {RESEARCH_DATA_PATH} not found — run researcher.py first")

    return financial_data, research_data


def score_financials(financials):
    """
    Score based on extracted financial ratios.
    Max possible from this section: 45 points.
    """
    score = 0
    breakdown = []

    # Net Profit
    net_profit = financials.get("net_profit_cr")
    if net_profit is not None:
        if net_profit > 0:
            score += 15
            breakdown.append({"factor": "Net Profit", "points": +15, "note": f"Profitable: Rs. {net_profit:.2f} Cr"})
        else:
            score -= 20
            breakdown.append({"factor": "Net Profit", "points": -20, "note": f"Loss-making: Rs. {net_profit:.2f} Cr"})
    else:
        breakdown.append({"factor": "Net Profit", "points": 0, "note": "Data not available"})

    # DSCR — Debt Service Coverage Ratio
    dscr = financials.get("dscr")
    if dscr is not None:
        if dscr >= 2.0:
            score += 15
            breakdown.append({"factor": "DSCR", "points": +15, "note": f"Strong: {dscr:.2f}x (>= 2.0)"})
        elif dscr >= 1.5:
            score += 10
            breakdown.append({"factor": "DSCR", "points": +10, "note": f"Adequate: {dscr:.2f}x (>= 1.5)"})
        elif dscr >= 1.0:
            score += 5
            breakdown.append({"factor": "DSCR", "points": +5, "note": f"Marginal: {dscr:.2f}x (>= 1.0)"})
        else:
            score -= 15
            breakdown.append({"factor": "DSCR", "points": -15, "note": f"Weak: {dscr:.2f}x (< 1.0)"})
    else:
        breakdown.append({"factor": "DSCR", "points": 0, "note": "Data not available"})

    # Debt to Equity
    dte = financials.get("debt_to_equity")
    if dte is not None:
        if dte <= 1.0:
            score += 10
            breakdown.append({"factor": "Debt/Equity", "points": +10, "note": f"Conservative: {dte:.2f}x (<= 1.0)"})
        elif dte <= 2.0:
            score += 5
            breakdown.append({"factor": "Debt/Equity", "points": +5, "note": f"Acceptable: {dte:.2f}x (<= 2.0)"})
        else:
            score -= 10
            breakdown.append({"factor": "Debt/Equity", "points": -10, "note": f"High leverage: {dte:.2f}x (> 2.0)"})
    else:
        breakdown.append({"factor": "Debt/Equity", "points": 0, "note": "Data not available"})

    # Current Ratio
    cr = financials.get("current_ratio")
    if cr is not None:
        if cr >= 1.5:
            score += 5
            breakdown.append({"factor": "Current Ratio", "points": +5, "note": f"Strong liquidity: {cr:.2f}x"})
        elif cr >= 1.0:
            score += 2
            breakdown.append({"factor": "Current Ratio", "points": +2, "note": f"Adequate liquidity: {cr:.2f}x"})
        else:
            score -= 8
            breakdown.append({"factor": "Current Ratio", "points": -8, "note": f"Liquidity risk: {cr:.2f}x (< 1.0)"})
    else:
        breakdown.append({"factor": "Current Ratio", "points": 0, "note": "Data not available"})

    return score, breakdown


def score_fraud_signals(financial_data):
    """
    Apply penalties from GST fraud and circular trading detection.
    These come pre-calculated from Agent 1.
    Max penalty: -32 points.
    """
    score = 0
    breakdown = []

    # GST Analysis
    gst = financial_data.get("gst_analysis", {})
    gst_impact = gst.get("score_impact", 0)
    gst_flag = gst.get("flag", "UNKNOWN")
    score += gst_impact
    breakdown.append({
        "factor": f"GST Reconciliation ({gst_flag})",
        "points": gst_impact,
        "note": gst.get("note", "")
    })

    # Circular Trading
    ct = financial_data.get("circular_trading", {})
    ct_impact = ct.get("score_impact", 0)
    ct_level = ct.get("risk_level", "LOW")
    score += ct_impact
    breakdown.append({
        "factor": f"Circular Trading ({ct_level} risk)",
        "points": ct_impact,
        "note": f"{ct.get('cycles_found', 0)} suspicious transaction cycle(s) detected"
    })

    return score, breakdown


def score_research(research_data):
    """
    Apply penalties from web research — promoter, litigation, sector risk.
    These come pre-calculated from Agent 2.
    Max penalty: -26 points.
    """
    score = 0
    breakdown = []

    # Promoter Risk
    promoter = research_data.get("promoter_risk", {})
    p_impact = promoter.get("score_impact", 0)
    score += p_impact
    breakdown.append({
        "factor": "Promoter Risk",
        "points": p_impact,
        "note": "Adverse news detected" if p_impact < 0 else "No adverse news found"
    })

    # Litigation Risk
    litigation = research_data.get("litigation_risk", {})
    l_impact = litigation.get("score_impact", 0)
    l_cases = litigation.get("cases_found", 0)
    score += l_impact
    breakdown.append({
        "factor": "Litigation Risk",
        "points": l_impact,
        "note": f"{l_cases} pending legal case(s) found"
    })

    # Sector Risk
    sector = research_data.get("sector_risk", {})
    s_impact = sector.get("score_impact", 0)
    s_sentiment = sector.get("sector_sentiment", "UNKNOWN")
    score += s_impact
    breakdown.append({
        "factor": f"Sector Risk ({sector.get('sector', 'Unknown')} — {s_sentiment})",
        "points": s_impact,
        "note": sector.get("recent_rbi_actions", [""])[0]
    })

    return score, breakdown


def make_decision(total_score, red_flags):
    """
    Final credit decision based on total score and red flags.
    """
    # Hard reject conditions — regardless of score
    hard_reject_flags = [f for f in red_flags if f.get("severity") == "HIGH"]

    if hard_reject_flags:
        return "REJECT", "Hard reject triggered by high-severity risk flag"

    if total_score >= 70:
        return "APPROVE", "Score above approval threshold with acceptable risk profile"
    elif total_score >= 50:
        return "REVIEW", "Score in review band — requires senior credit officer assessment"
    else:
        return "REJECT", "Score below minimum threshold for credit approval"


def run_recommender(financial_data=None, research_data=None):
    """
    MAIN FUNCTION — called by main.py.
    Takes Agent 1 + Agent 2 outputs, produces credit decision.
    """
    print(f"\n{'='*50}")
    print("AGENT 3 — CREDIT RECOMMENDER")
    print(f"{'='*50}")

    # Load data if not passed directly
    if financial_data is None or research_data is None:
        print("\n[1/4] Loading agent outputs...")
        financial_data, research_data = load_data()
    else:
        print("\n[1/4] Using provided agent outputs...")

    financials = financial_data.get("financials", {})
    company    = financial_data.get("company", {})

    # Score each section
    print("\n[2/4] Scoring financial health...")
    fin_score, fin_breakdown = score_financials(financials)
    print(f"  Financial score: {fin_score:+d} pts")

    print("\n[3/4] Scoring fraud signals...")
    fraud_score, fraud_breakdown = score_fraud_signals(financial_data)
    print(f"  Fraud signal score: {fraud_score:+d} pts")

    print("\n[4/4] Scoring research signals...")
    research_score, research_breakdown = score_research(research_data)
    print(f"  Research score: {research_score:+d} pts")

    # Total score — starts at 100, deductions applied
    base_score  = 100
    total_score = base_score + fin_score + fraud_score + research_score
    total_score = max(0, min(100, total_score))  # clamp to 0-100

    # Collect all red flags from both agents
    red_flags = research_data.get("red_flags", [])

    # Add fraud flags from Agent 1 if they're bad
    gst_flag = financial_data.get("gst_analysis", {}).get("flag", "")
    if gst_flag == "REVENUE_INFLATION":
        red_flags.append({
            "category": "FRAUD_SIGNAL",
            "description": "GST revenue inflation detected — self-declared vs supplier-declared mismatch > 30%",
            "severity": "HIGH",
            "score_impact": -12
        })

    ct_risk = financial_data.get("circular_trading", {}).get("risk_level", "LOW")
    if ct_risk in ["MEDIUM", "HIGH"]:
        red_flags.append({
            "category": "CIRCULAR_TRADING",
            "description": f"Circular trading detected — {financial_data['circular_trading'].get('cycles_found', 0)} suspicious cycle(s)",
            "severity": "HIGH" if ct_risk == "HIGH" else "MEDIUM",
            "score_impact": financial_data["circular_trading"].get("score_impact", 0)
        })

    decision, decision_rationale = make_decision(total_score, red_flags)

    # Build decision output
    result = {
        "company_name": company.get("name", "Unknown"),
        "decision_timestamp": datetime.utcnow().isoformat(),
        "credit_score": total_score,
        "decision": decision,
        "decision_rationale": decision_rationale,
        "score_breakdown": {
            "base_score": base_score,
            "financial_score": fin_score,
            "fraud_signal_score": fraud_score,
            "research_score": research_score,
            "final_score": total_score
        },
        "detailed_breakdown": fin_breakdown + fraud_breakdown + research_breakdown,
        "red_flags": red_flags,
        "key_metrics": {
            "revenue_cr":               financials.get("revenue_cr"),
            "net_profit_cr":            financials.get("net_profit_cr"),
            "total_assets_cr":          financials.get("total_assets_cr"),
            "total_debt_cr":            financials.get("total_debt_cr"),
            "equity_cr":                financials.get("equity_cr"),
            "dscr":                     financials.get("dscr"),
            "debt_to_equity":           financials.get("debt_to_equity"),
            "collateral_coverage_ratio":financials.get("collateral_coverage_ratio"),
        }
    }

    os.makedirs("outputs", exist_ok=True)
    with open(DECISION_OUTPUT, "w") as f:
        json.dump(result, f, indent=4)

    print(f"\n{'='*50}")
    print(f"  Company  : {result['company_name']}")
    print(f"  Score    : {total_score}/100")
    print(f"  Decision : {decision}")
    print(f"  Rationale: {decision_rationale}")
    print(f"{'='*50}")
    print(f"\n✓ decision.json saved to {DECISION_OUTPUT}\n")

    return result


if __name__ == "__main__":
    result = run_recommender()
    print(json.dumps(result, indent=2))