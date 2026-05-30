from __future__ import annotations

from a2a.types import AgentCard, AgentSkill, Artifact, Task, TaskResult
from agents.base import A2AAgent
from helpers import fetch_places


class LeadDiscoveryAgent(A2AAgent):
    """Fetches business listings from Google Places via Apify."""

    @property
    def agent_card(self) -> AgentCard:
        return AgentCard(
            name="LeadDiscoveryAgent",
            description="Queries Apify Google Places scraper and returns normalised business records.",
            version="1.0.0",
            skills=[
                AgentSkill(
                    id="fetch-places",
                    name="Fetch Places",
                    description="Run a list of search queries against Google Maps and return business data.",
                    input_modes=["data"],
                    output_modes=["data"],
                )
            ],
        )

    def process(self, task: Task) -> TaskResult:
        data = task.message.get_data()
        queries: list[str] = data.get("queries", [])

        if not queries:
            return TaskResult(task_id=task.id, status="failed", error="No queries provided.")

        try:
            raw_leads = fetch_places(queries)
            return TaskResult(
                task_id=task.id,
                status="completed",
                artifacts=[Artifact(name="raw_leads", data=raw_leads)],
            )
        except Exception as exc:
            return TaskResult(task_id=task.id, status="failed", error=str(exc))
