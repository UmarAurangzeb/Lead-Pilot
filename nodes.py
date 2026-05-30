"""
LangGraph node functions — each node delegates to its A2A agent via the dispatcher.

The dispatcher is initialised once at module load so agents (and their caches)
persist across graph iterations within the same run.
"""
from __future__ import annotations

from uuid import uuid4

from langgraph.graph import END

import memory
from a2a import A2ADispatcher, DataPart, Message, Task
from agents import (
    EnrichmentAgent,
    LeadDiscoveryAgent,
    OutreachAgent,
    QueryGeneratorAgent,
    ScoringAgent,
)
from state import LeadState

# ── A2A dispatcher — registered once, shared across all graph nodes ──────────

_dispatcher = A2ADispatcher()
_dispatcher.register(QueryGeneratorAgent())
_dispatcher.register(LeadDiscoveryAgent())
_dispatcher.register(EnrichmentAgent())
_dispatcher.register(ScoringAgent())
_dispatcher.register(OutreachAgent())


def _task(agent_name: str, **kwargs) -> Task:
    return Task(
        id=str(uuid4()),
        agent_name=agent_name,
        message=Message(role="user", parts=[DataPart(data=kwargs)]),
    )


# ── Nodes ────────────────────────────────────────────────────────────────────

def query_generator(state: LeadState) -> dict:
    result = _dispatcher.send(_task(
        "QueryGeneratorAgent",
        niche=state.get("niche", "local businesses"),
        countries=state.get("countries") or ["Pakistan"],
    ))
    if result.status == "failed":
        raise RuntimeError(f"QueryGeneratorAgent failed: {result.error}")
    return {"queries": result.first("queries")}


def lead_finder(state: LeadState) -> dict:
    result = _dispatcher.send(_task(
        "LeadDiscoveryAgent",
        queries=state["queries"],
    ))
    if result.status == "failed":
        raise RuntimeError(f"LeadDiscoveryAgent failed: {result.error}")
    return {"raw_leads": result.first("raw_leads")}


def enrich_leads(state: LeadState) -> dict:
    result = _dispatcher.send(_task(
        "EnrichmentAgent",
        raw_leads=state["raw_leads"],
    ))
    if result.status == "failed":
        raise RuntimeError(f"EnrichmentAgent failed: {result.error}")
    return {"enriched_leads": result.first("enriched_leads")}


def score_leads(state: LeadState) -> dict:
    result = _dispatcher.send(_task(
        "ScoringAgent",
        enriched_leads=state["enriched_leads"],
        niche=state.get("niche", "local businesses"),
    ))
    if result.status == "failed":
        raise RuntimeError(f"ScoringAgent failed: {result.error}")
    scored = result.first("scored_leads") or []
    summary = result.first("scoring_summary") or {}
    return {"scored_leads": scored, "scoring_summary": summary}


def route_leads(state: LeadState) -> dict:
    niche = state.get("niche", "")
    high = [dict(l) for l in state["scored_leads"] if l["score"] >= 40]
    low  = [dict(l) for l in state["scored_leads"] if l["score"] < 40]

    for l in high:
        l["status"] = "QUALIFIED"
        l["niche"] = niche
    for l in low:
        l["status"] = "REJECTED"
        l["niche"] = niche

    memory.save_leads(high + low)
    return {"high_quality": high, "rejected": low}


def route_function(state: LeadState) -> str:
    if state.get("high_quality"):
        return "outreach"
    if (state.get("iteration") or 0) >= 3:
        return END
    return "query_optimizer"


def query_optimizer(state: LeadState) -> dict:
    iteration = (state.get("iteration") or 0) + 1
    result = _dispatcher.send(_task(
        "QueryGeneratorAgent",
        niche=state.get("niche", "local businesses"),
        countries=state.get("countries") or ["Pakistan"],
    ))
    return {
        "iteration": iteration,
        "queries": result.first("queries") or [],
    }


def outreach_agent(state: LeadState) -> dict:
    result = _dispatcher.send(_task(
        "OutreachAgent",
        high_quality=state.get("high_quality") or [],
        niche=state.get("niche", "local businesses"),
    ))
    return {"emails": result.first("emails") or []}
