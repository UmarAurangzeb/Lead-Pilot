from __future__ import annotations

from a2a.types import AgentCard, AgentSkill, Artifact, Task, TaskResult
from agents.base import A2AAgent
from helpers import enrich_leads_with_emails


class EnrichmentAgent(A2AAgent):
    """Scrapes contact emails from each lead's website using Playwright."""

    @property
    def agent_card(self) -> AgentCard:
        return AgentCard(
            name="EnrichmentAgent",
            description="Extracts email addresses from business websites via headless Playwright scraping.",
            version="1.0.0",
            skills=[
                AgentSkill(
                    id="scrape-emails",
                    name="Scrape Emails",
                    description="Visit each lead's website and pull all reachable email addresses.",
                    input_modes=["data"],
                    output_modes=["data"],
                )
            ],
        )

    def process(self, task: Task) -> TaskResult:
        data = task.message.get_data()
        raw_leads: list[dict] = data.get("raw_leads", [])

        if not raw_leads:
            return TaskResult(task_id=task.id, status="failed", error="No raw leads provided.")

        try:
            enriched = enrich_leads_with_emails(raw_leads)
            return TaskResult(
                task_id=task.id,
                status="completed",
                artifacts=[Artifact(name="enriched_leads", data=enriched)],
            )
        except Exception as exc:
            return TaskResult(task_id=task.id, status="failed", error=str(exc))
