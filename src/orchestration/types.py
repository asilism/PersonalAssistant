"""
Core types and data models for the Orchestration system
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class StateType(str, Enum):
    """State types for the orchestration state machine"""
    INIT = "INIT"
    PLAN_OR_DECIDE = "PLAN_OR_DECIDE"
    DISPATCH = "DISPATCH"
    HUMAN_IN_THE_LOOP = "HUMAN_IN_THE_LOOP"
    FINAL = "FINAL"
    ERROR = "ERROR"


class PlanState(str, Enum):
    """Plan execution state"""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class TraceContext(BaseModel):
    """Trace context for debugging and monitoring"""
    trace_id: str
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None


class ToolDefinition(BaseModel):
    """MCP Tool definition"""
    name: str
    description: str
    input_schema: dict[str, Any]


class OrchestrationSettings(BaseModel):
    """Orchestration settings"""
    llm_model: str
    llm_api_key: str
    llm_base_url: Optional[str] = None
    max_retries: int = 3
    timeout: int = 30000
    available_tools: list[ToolDefinition]


class Step(BaseModel):
    """Individual step in the execution plan"""
    step_id: str
    tool_name: str
    input: dict[str, Any]
    description: str
    dependencies: list[str] = Field(default_factory=list)


class Guard(BaseModel):
    """Guard condition for plan execution"""
    condition: str
    action: str  # "skip" | "fail" | "human_review"


class Plan(BaseModel):
    """Execution plan"""
    plan_id: str
    steps: list[Step]
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    guards: list[Guard] = Field(default_factory=list)


class StepResult(BaseModel):
    """Step execution result"""
    step_id: str
    status: str  # "success" | "failure" | "skipped"
    output: Optional[Any] = None
    error: Optional[str] = None
    executed_at: datetime
    duration: float  # milliseconds


class AggregatedGroupResults(BaseModel):
    """Aggregated results for a group of steps"""
    plan_id: str
    completed_steps: list[StepResult]
    failed_steps: list[StepResult]
    total_steps: int
    success_rate: float


class Decision(BaseModel):
    """Decision from Planner"""
    type: str  # "final" | "nextSteps" | "needsHuman" | "failed"
    payload: Any
    reason: Optional[str] = None


class FinalSummary(BaseModel):
    """Final response to user"""
    success: bool
    message: str
    results: Optional[Any] = None
    execution_time: float
    plan_id: Optional[str] = None


class ContextBundle(BaseModel):
    """Context bundle (simplified - RAG removed)"""
    session_id: str
    conversation_history: list[str] = Field(default_factory=list)
    additional_context: dict[str, Any] = Field(default_factory=dict)


class State(BaseModel):
    """Main state for the LangGraph state machine"""
    type: StateType
    session_id: str
    user_id: str
    tenant: str
    request_text: str
    trace: TraceContext
    context: Optional[ContextBundle] = None
    plan: Optional[Plan] = None
    plan_state: Optional[PlanState] = None
    results: Optional[AggregatedGroupResults] = None
    error: Optional[str] = None
    final_payload: Optional[Any] = None
    retry_counts: dict[str, int] = Field(default_factory=dict)  # Track retry attempts per step

    class Config:
        arbitrary_types_allowed = True


class PlanSummary(BaseModel):
    """Plan summary for history"""
    plan_id: str
    request_text: str
    status: PlanState
    completed_at: Optional[datetime] = None


class HistorySummary(BaseModel):
    """History summary from TaskTracker"""
    session_id: str
    user_id: str
    recent_plans: list[PlanSummary]
    total_requests: int
    success_rate: float


class PlanUpdate(BaseModel):
    """Plan update event"""
    plan_id: str
    status: PlanState
    completed_steps: int
    total_steps: int
    last_step_result: Optional[StepResult] = None
