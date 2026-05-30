"""
A2ADispatcher — in-process agent router.

In production this would be an HTTP client that POSTs Tasks to agent endpoints
discovered via their AgentCards. Here all agents share the same process and the
dispatcher simply looks up the registered agent by name and calls process().
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict

from .types import Task, TaskResult

if TYPE_CHECKING:
    from agents.base import A2AAgent

log = logging.getLogger(__name__)


class A2ADispatcher:
    def __init__(self) -> None:
        self._registry: Dict[str, "A2AAgent"] = {}

    def register(self, agent: "A2AAgent") -> None:
        name = agent.agent_card.name
        self._registry[name] = agent
        log.debug("A2A registered: %s  endpoint=%s", name, agent.agent_card.endpoint)

    def send(self, task: Task) -> TaskResult:
        agent = self._registry.get(task.agent_name)
        if agent is None:
            known = list(self._registry.keys())
            return TaskResult(
                task_id=task.id,
                status="failed",
                error=f"No agent registered as '{task.agent_name}'. Known: {known}",
            )
        log.info("A2A → %s  task=%s", task.agent_name, task.id)
        result = agent.process(task)
        log.info("A2A ← %s  status=%s", task.agent_name, result.status)
        return result

    def list_agents(self) -> list[dict]:
        return [a.agent_card.to_dict() for a in self._registry.values()]
