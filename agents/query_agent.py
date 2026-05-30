from __future__ import annotations

from a2a.types import AgentCard, AgentSkill, Artifact, Task, TaskResult
from agents.base import A2AAgent
from helpers import generate_queries


class QueryGeneratorAgent(A2AAgent):
    """Generates diverse search queries for a given niche and target countries."""

    @property
    def agent_card(self) -> AgentCard:
        return AgentCard(
            name="QueryGeneratorAgent",
            description="Generates 5-15 targeted Google search queries for a niche in specified countries.",
            version="1.0.0",
            skills=[
                AgentSkill(
                    id="generate-queries",
                    name="Generate Queries",
                    description="Produce varied search queries to surface local SMB leads.",
                    input_modes=["data"],
                    output_modes=["data"],
                )
            ],
        )

    def process(self, task: Task) -> TaskResult:
        data = task.message.get_data()
        niche: str = data.get("niche", "local businesses")
        countries: list[str] = data.get("countries") or ["Pakistan"]

        try:
            queries = generate_queries(niche, countries)
            return TaskResult(
                task_id=task.id,
                status="completed",
                artifacts=[Artifact(name="queries", data=queries)],
            )
        except Exception as exc:
            return TaskResult(task_id=task.id, status="failed", error=str(exc))
