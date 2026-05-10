from helpers import enrich_leads_with_emails, fetch_places, generate_queries
from state import LeadState

def query_generator(state: LeadState):
    niche = state.get("niche", "local businesses")
    countries = state.get("countries") or ["Pakistan"]
    return {"queries": generate_queries(niche, countries)}


def lead_finder(state: LeadState):
    queries = state["queries"]
    raw_leads = fetch_places(queries)
    return {"raw_leads": raw_leads}

def enrich_leads(state: LeadState):
    enriched = enrich_leads_with_emails(state["raw_leads"])
    return {"enriched_leads": enriched}

def score_leads(state: LeadState):
    scored = []

    for lead in state["enriched_leads"]:
        score = 0

        if lead["reviewsCount"] > 50:
            score += 3
        if not lead.get("website"):
            score += 5

        lead["score"] = score
        scored.append(lead)

    return {"scored_leads": scored}

def route_leads(state: LeadState):
    high = [l for l in state["scored_leads"] if l["score"] >= 7]
    low = [l for l in state["scored_leads"] if l["score"] < 7]

    return {
        "high_quality": high,
        "rejected": low
    }

def route_function(state: LeadState):
    high_quality = state["high_quality"]
    rejected = state["rejected"]
    iterations = state.get("iteration", 0)
    if high_quality:
        return "outreach"
    else:
        if iterations > 3:
            return "END"
        return "query_optimizer"

def query_optimizer(state: LeadState):
    iteration = state.get("iteration", 0) + 1
    niche = state.get("niche", "local businesses")
    countries = state.get("countries") or ["Pakistan"]
    return {
        "iteration": iteration,
        "queries": generate_queries(niche, countries),
    }


def outreach_agent(state: LeadState):
    emails = []
    for lead in state["high_quality"]:
        emails.append(f"Email for {lead['title']}")

    return {"emails": emails}