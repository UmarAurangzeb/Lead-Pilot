"""
A2A (Agent-to-Agent) protocol types — mirrors the Google A2A open spec.
https://google.github.io/A2A

For this project agents run in-process; endpoint="in-process" signals that.
In production, endpoint would be an HTTP URL and Task dispatch would go over
the network using the same Task/Message/Artifact envelope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class AgentSkill:
    id: str
    name: str
    description: str
    input_modes: List[str] = field(default_factory=lambda: ["data"])
    output_modes: List[str] = field(default_factory=lambda: ["data"])


@dataclass
class AgentCard:
    """Capability declaration for an A2A agent (served at /.well-known/agent.json in prod)."""
    name: str
    description: str
    version: str
    skills: List[AgentSkill]
    endpoint: str = "in-process"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "endpoint": self.endpoint,
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "inputModes": s.input_modes,
                    "outputModes": s.output_modes,
                }
                for s in self.skills
            ],
        }


@dataclass
class TextPart:
    text: str
    type: str = "text"


@dataclass
class DataPart:
    data: Dict = field(default_factory=dict)
    type: str = "data"


Part = Union[TextPart, DataPart]


@dataclass
class Message:
    role: str  # "user" | "agent"
    parts: List[Part] = field(default_factory=list)

    def get_data(self) -> Dict:
        for part in self.parts:
            if isinstance(part, DataPart):
                return part.data
        return {}

    def get_text(self) -> str:
        for part in self.parts:
            if isinstance(part, TextPart):
                return part.text
        return ""


@dataclass
class Task:
    id: str
    agent_name: str
    message: Message
    metadata: Dict = field(default_factory=dict)


@dataclass
class Artifact:
    name: str
    data: Any
    mime_type: str = "application/json"


@dataclass
class TaskResult:
    task_id: str
    status: str  # "completed" | "failed" | "in_progress"
    artifacts: List[Artifact] = field(default_factory=list)
    error: Optional[str] = None

    def first(self, name: str) -> Any:
        """Return data of the first artifact matching name."""
        for a in self.artifacts:
            if a.name == name:
                return a.data
        return None
