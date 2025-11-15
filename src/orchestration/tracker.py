"""
TaskTracker - Tracks task execution state and history
"""

from datetime import datetime
from typing import Optional

from .types import (
    Plan,
    PlanUpdate,
    StepResult,
    HistorySummary,
    AggregatedGroupResults,
    PlanState,
    PlanSummary
)
from .settings_manager import SettingsManager, ChatMessage


class TaskTracker:
    """TaskTracker - Tracks plan execution state and history"""

    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        # In-memory storage (in production, use a database)
        self._plans: dict[str, Plan] = {}
        self._plan_states: dict[str, PlanState] = {}
        self._step_results: dict[str, list[StepResult]] = {}
        self._session_history: dict[str, list[PlanSummary]] = {}
        self._session_active_plans: dict[str, str] = {}  # session_id -> plan_id mapping
        self._settings_manager = settings_manager or SettingsManager()

    async def persist_plan(self, plan: Plan) -> None:
        """Persist a new plan"""
        self._plans[plan.plan_id] = plan
        self._plan_states[plan.plan_id] = PlanState.PENDING
        # Only initialize step_results if this is a new plan
        if plan.plan_id not in self._step_results:
            self._step_results[plan.plan_id] = []

    async def persist_plan_update(self, update: PlanUpdate) -> None:
        """Update plan state"""
        self._plan_states[update.plan_id] = update.status

        if update.last_step_result:
            results = self._step_results.get(update.plan_id, [])

            # Check if this step_id already exists
            existing_index = next(
                (i for i, r in enumerate(results) if r.step_id == update.last_step_result.step_id),
                None
            )

            if existing_index is not None:
                # Update existing result
                results[existing_index] = update.last_step_result
            else:
                # Add new result
                results.append(update.last_step_result)

            self._step_results[update.plan_id] = results

    async def append_step_result(self, plan_id: str, result: StepResult) -> None:
        """Append a step result (prevents duplicates for same step_id)"""
        results = self._step_results.get(plan_id, [])

        # Check if this step_id already exists
        existing_index = next(
            (i for i, r in enumerate(results) if r.step_id == result.step_id),
            None
        )

        if existing_index is not None:
            # Update existing result
            results[existing_index] = result
        else:
            # Add new result
            results.append(result)

        self._step_results[plan_id] = results

    async def finalize_conversation(
        self,
        session_id: str,
        user_id: str,
        plan_id: str,
        request_text: str,
        final: dict[str, any]
    ) -> None:
        """Finalize conversation and store in history"""
        status = PlanState.COMPLETED if final.get("success") else PlanState.FAILED

        summary = PlanSummary(
            plan_id=plan_id,
            request_text=request_text,
            status=status,
            completed_at=datetime.now()
        )

        history = self._session_history.get(session_id, [])
        history.append(summary)
        self._session_history[session_id] = history

    async def get_history(self, session_id: str, user_id: str) -> HistorySummary:
        """Get history for a session"""
        history = self._session_history.get(session_id, [])

        success_count = len([h for h in history if h.status == PlanState.COMPLETED])
        success_rate = success_count / len(history) if history else 0.0

        return HistorySummary(
            session_id=session_id,
            user_id=user_id,
            recent_plans=history[-10:],  # Last 10 plans
            total_requests=len(history),
            success_rate=success_rate
        )

    async def is_current_group_complete(self, plan_id: str) -> bool:
        """Check if current group is complete"""
        plan = self._plans.get(plan_id)
        results = self._step_results.get(plan_id, [])

        if not plan:
            return False

        # Check if all steps are completed
        return len(results) == len(plan.steps)

    async def get_aggregated_results_for_group(
        self, plan_id: str
    ) -> AggregatedGroupResults:
        """Get aggregated results for a group"""
        plan = self._plans.get(plan_id)
        results = self._step_results.get(plan_id, [])

        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        completed_steps = [r for r in results if r.status == "success"]
        failed_steps = [r for r in results if r.status == "failure"]

        return AggregatedGroupResults(
            plan_id=plan_id,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            total_steps=len(plan.steps),
            success_rate=len(completed_steps) / len(results) if results else 0.0
        )

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get plan by ID"""
        return self._plans.get(plan_id)

    def get_plan_state(self, plan_id: str) -> Optional[PlanState]:
        """Get plan state"""
        return self._plan_states.get(plan_id)

    def get_step_results(self, plan_id: str) -> list[StepResult]:
        """Get all step results for a plan"""
        return self._step_results.get(plan_id, [])

    # Chat History Methods
    async def save_user_message(
        self,
        session_id: str,
        user_id: str,
        tenant: str,
        content: str
    ) -> bool:
        """Save user message to chat history"""
        return self._settings_manager.save_chat_message(
            session_id=session_id,
            user_id=user_id,
            tenant=tenant,
            role="user",
            content=content
        )

    async def save_assistant_message(
        self,
        session_id: str,
        user_id: str,
        tenant: str,
        content: str
    ) -> bool:
        """Save assistant message to chat history"""
        return self._settings_manager.save_chat_message(
            session_id=session_id,
            user_id=user_id,
            tenant=tenant,
            role="assistant",
            content=content
        )

    async def load_chat_history(
        self,
        session_id: str,
        limit: Optional[int] = 10
    ) -> list[ChatMessage]:
        """Load chat history for a session"""
        return self._settings_manager.get_chat_history(
            session_id=session_id,
            limit=limit
        )

    async def clear_chat_history(self, session_id: str) -> bool:
        """Clear chat history for a session"""
        return self._settings_manager.delete_chat_history(session_id)

    # Active Plan Management
    def set_active_plan(self, session_id: str, plan_id: str) -> None:
        """Set the active plan for a session"""
        self._session_active_plans[session_id] = plan_id

    def get_active_plan(self, session_id: str) -> Optional[Plan]:
        """
        Get the active plan for a session (if it's in NEEDS_HUMAN or IN_PROGRESS state)
        Returns None if no active plan or plan is completed/failed
        """
        plan_id = self._session_active_plans.get(session_id)
        if not plan_id:
            return None

        plan_state = self._plan_states.get(plan_id)
        if plan_state in [PlanState.NEEDS_HUMAN, PlanState.IN_PROGRESS, PlanState.PENDING]:
            return self._plans.get(plan_id)

        # Plan is completed or failed, clear active plan
        return None

    def clear_active_plan(self, session_id: str) -> None:
        """Clear the active plan for a session"""
        if session_id in self._session_active_plans:
            del self._session_active_plans[session_id]
