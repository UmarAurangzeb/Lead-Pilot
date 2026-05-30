from __future__ import annotations

from abc import ABC, abstractmethod

from a2a.types import AgentCard, Task, TaskResult


class A2AAgent(ABC):
    """Base class for all LeadPilot A2A agents."""

    @property
    @abstractmethod
    def agent_card(self) -> AgentCard: ...

    @abstractmethod
    def process(self, task: Task) -> TaskResult: ...
