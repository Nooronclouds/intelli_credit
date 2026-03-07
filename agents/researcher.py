import json
from datetime import datetime
from ddgs import DDGS

OUTPUT_PATH = "outputs/research_data.json"


def search_news(company_name):
    results = []

    query = f"{company_name} fraud investigation RBI lawsuit"

    try:
        with DDGS() as ddgs:
            news = ddgs.text(query, max_results=5)

            for n in news:
                results.append({
                    "headline": n.get("title", ""),
                    "source": n.get("href", ""),
                    "date": "",
                    "sentiment": "NEUTRAL",
                    "risk_keywords": []
                })

    except Exception as e:
        print("Search failed, using fallback mock data")
        results = [
            {
                "headline": f"{company_name} CMD flags industry risk",
                "source": "Economic Times",
                "date": "2025-11-12",
                "sentiment": "NEUTRAL",
                "risk_keywords": []
            }
        ]

    return results
 

def analyze_promoter_risk(company_name):

    news_items = search_news(company_name)

    adverse_news = False
    fraud_mention = False

    ed_mention = False

    for item in news_items:
        headline = item["headline"].lower()

        if any(word in headline for word in ["fraud", "scam", "fir", "misappropriation"]):
            adverse_news = True
            fraud_mention = True
            item["sentiment"] = "HIGH_RISK"
            item["risk_keywords"].append("fraud/FIR")

        if any(word in headline for word in ["ed ", "enforcement", "pmla", "money laundering"]):
            adverse_news = True
            ed_mention = True
            item["sentiment"] = "HIGH_RISK"
            item["risk_keywords"].append("ED/PMLA")

        if any(word in headline for word in ["penalty", "non-compliance", "violation"]):
            item["sentiment"] = "MEDIUM_RISK"
            item["risk_keywords"].append("regulatory action")

    score_impact = -8 if adverse_news else 0

    return {
        "adverse_news_found": adverse_news,
        "news_items": news_items,
        "ed_mention": ed_mention,
        "fraud_mention": fraud_mention,
        "score_impact": score_impact
    }


def analyze_litigation(company_name):

    # Mock hackathon version
    cases_found = 3

    if cases_found == 0:
        score = 0
    elif cases_found <= 5:
        score = -5
    else:
        score = -10

    return {
        "cases_found": cases_found,
        "high_value_cases": 0,
        "nclt_mention": False,
        "ibc_mention": False,
        "score_impact": score,
        "sources": ["eCourts search — mock demo"]
    }


def analyze_sector_risk():

    return {
        "sector": "NBFC",
        "recent_rbi_actions": [
            "RBI tightened NBFC gold loan norms Oct 2024"
        ],
        "sector_sentiment": "CAUTIOUS",
        "headwinds": [
            "Rising interest rates",
            "Tighter RBI regulation"
        ],
        "tailwinds": [
            "Growing rural credit demand"
        ],
        "score_impact": -8
    }


def build_red_flags(promoter_risk, litigation_risk, sector_risk):

    red_flags = []

    if promoter_risk["score_impact"] < 0:
        red_flags.append({
            "category": "PROMOTER",
            "description": "Adverse news detected about promoter",
            "severity": "MEDIUM",
            "score_impact": promoter_risk["score_impact"]
        })

    if litigation_risk["cases_found"] > 0:
        red_flags.append({
            "category": "LITIGATION",
            "description": f"{litigation_risk['cases_found']} pending cases found",
            "severity": "LOW",
            "score_impact": litigation_risk["score_impact"]
        })

    if sector_risk["score_impact"] < 0:
        red_flags.append({
            "category": "SECTOR",
            "description": sector_risk["recent_rbi_actions"][0],
            "severity": "MEDIUM",
            "score_impact": sector_risk["score_impact"]
        })

    return red_flags


def run_research_agent(company_name):

    promoter_risk = analyze_promoter_risk(company_name)
    litigation_risk = analyze_litigation(company_name)
    sector_risk = analyze_sector_risk()

    red_flags = build_red_flags(
        promoter_risk,
        litigation_risk,
        sector_risk
    )

    research_data = {
        "company_name": company_name,
        "search_timestamp": datetime.utcnow().isoformat(),
        "promoter_risk": promoter_risk,
        "litigation_risk": litigation_risk,
        "sector_risk": sector_risk,
        "overall_research_score": 72,
        "red_flags": red_flags
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(research_data, f, indent=4)

    print("Research agent completed. Output saved.")


if __name__ == "__main__":
    run_research_agent("Muthoot Finance Ltd")