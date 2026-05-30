"""
ScoringAgent — 100-point multi-factor lead ranking.

Points breakdown:
  35 — email found          (primary; 0 = discard immediately)
  20 — review count         (logarithmic bands)
  15 — Google rating        (quality signal)
  10 — has website          (professional presence)
   5 — has phone            (contactable)
  15 — category relevance   (LLM-scored match to niche, cached by category+niche)

Threshold: ≥ 40 = high quality, < 40 = rejected.
"""
from __future__ import annotations

from functools import lru_cache

from a2a.types import AgentCard, AgentSkill, Artifact, Task, TaskResult
from agents.base import A2AAgent
from helpers import _lead_hash, normalize_email_list
from llm import call_llm


def _review_score(count: int) -> int:
    if count >= 200:
        return 20
    if count >= 100:
        return 15
    if count >= 50:
        return 10
    if count >= 20:
        return 5
    return 0


def _rating_score(rating: float) -> int:
    if rating >= 4.5:
        return 15
    if rating >= 4.0:
        return 10
    if rating >= 3.5:
        return 5
    return 0


@lru_cache(maxsize=256)
def _llm_category_relevance(category: str, niche: str) -> int:
    """LLM rates how relevant this business category is to the niche (0-15)."""
    if not category or not niche:
        return 5
    prompt_system = "You are a lead-qualification assistant. Respond with a single integer 0-15."
    prompt_user = (
        f"Business category: '{category}'\n"
        f"Target niche: '{niche}'\n\n"
        "Rate how relevant this business is as an outreach target for a software engineer "
        "pitching web development / digital solutions. "
        "15 = perfect match (e.g. cleaning business for cleaning niche), "
        "0 = completely irrelevant. Reply with only the integer."
    )
    try:
        raw = call_llm(prompt_system, prompt_user, temperature=0).strip()
        score = int("".join(c for c in raw if c.isdigit()) or "5")
        return max(0, min(15, score))
    except Exception:
        return 5


def score_lead(lead: dict, niche: str) -> int:
    emails = normalize_email_list(lead.get("emails", []))
    if not emails:
        return 0

    score = 35  # email found
    score += _review_score(int(lead.get("reviewsCount") or 0))
    score += _rating_score(float(lead.get("totalScore") or 0))
    if lead.get("website"):
        score += 10
    if lead.get("phone"):
        score += 5
    score += _llm_category_relevance(lead.get("category") or "", niche)
    return min(score, 100)


class ScoringAgent(A2AAgent):
    """Scores and ranks enriched leads using the 100-point system."""

    @property
    def agent_card(self) -> AgentCard:
        return AgentCard(
            name="ScoringAgent",
            description="Multi-factor lead scorer: email presence, reviews, rating, website, phone, LLM relevance.",
            version="1.0.0",
            skills=[
                AgentSkill(
                    id="score-leads",
                    name="Score Leads",
                    description="Assign a 0-100 quality score to each enriched lead.",
                    input_modes=["data"],
                    output_modes=["data"],
                )
            ],
        )

    def process(self, task: Task) -> TaskResult:
        data = task.message.get_data()
        enriched_leads: list[dict] = data.get("enriched_leads", [])
        niche: str = data.get("niche", "local businesses")

        scored = []
        for lead in enriched_leads:
            lead = dict(lead)
            lead["lead_hash"] = _lead_hash(lead)
            lead["score"] = score_lead(lead, niche)
            scored.append(lead)

        scored.sort(key=lambda l: l["score"], reverse=True)

        summary = {
            "total": len(scored),
            "high_quality": sum(1 for l in scored if l["score"] >= 40),
            "rejected": sum(1 for l in scored if l["score"] < 40),
            "top_score": scored[0]["score"] if scored else 0,
        }

        return TaskResult(
            task_id=task.id,
            status="completed",
            artifacts=[
                Artifact(name="scored_leads", data=scored),
                Artifact(name="scoring_summary", data=summary),
            ],
        )
