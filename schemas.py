from pydantic import BaseModel
from typing import Literal, Optional, List
from datetime import datetime

class MemoryItem(BaseModel):
    """
    Represents a durable memory item stored in the memory system.
    """
    id: str
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: List[str]
    descriptor: str
    value: dict
    artifact_id: Optional[str]
    source: str
    run_id: str
    goal_id: Optional[str]
    confidence: float
    created_at: datetime

class Artifact(BaseModel):
    """
    Metadata for an artifact whose raw bytes are stored on disk.
    """
    id: str  # Format: "art:<sha256-prefix>"
    content_type: str
    size_bytes: int
    source: str
    descriptor: str

class Goal(BaseModel):
    """
    Represents a specific objective the agent is trying to accomplish.
    """
    id: str
    text: str
    done: bool
    attach_artifact_id: Optional[str]

class Observation(BaseModel):
    """
    The output of the Perception orchestrator, representing the current state of goals.
    """
    reasoning: str
    reasoning_type: str
    goals: List[Goal]
    
    @property
    def all_done(self) -> bool:
        return all(g.done for g in self.goals)
        
    def next_unfinished(self) -> Optional[Goal]:
        return next((g for g in self.goals if not g.done), None)

from pydantic import BaseModel, Field, field_validator
import json

class ToolCall(BaseModel):
    """
    A requested tool execution.
    """
    name: str
    arguments: dict = Field(..., json_schema_extra={"type": "string", "description": "Strictly serialized JSON string"})

    @field_validator("arguments", mode="before")
    @classmethod
    def parse_str_to_dict(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v

class DecisionOutput(BaseModel):
    """
    The output of the Decision selector, representing either a final answer or a tool call.
    """
    reasoning: str
    reasoning_type: str
    answer: Optional[str]
    tool_call: Optional[ToolCall]
    
    @property
    def is_answer(self) -> bool:
        return self.answer is not None
