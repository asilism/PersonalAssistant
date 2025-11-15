"""
TaskDispatcher - Dispatches tasks for execution
"""

import asyncio
from typing import Optional

from .types import State, StateType, PlanState, PlanUpdate
from .mcp_executor import MCPExecutor
from .tracker import TaskTracker
from .placeholder_resolver import PlaceholderResolver
from .event_emitter import get_event_emitter


class TaskDispatcher:
    """TaskDispatcher - Executes plan steps using MCP"""

    def __init__(self, tracker: TaskTracker, executor: MCPExecutor):
        self.tracker = tracker
        self.executor = executor
        self.resolver = PlaceholderResolver()
        self.event_emitter = get_event_emitter()

    async def invoke(self, state: State) -> State:
        """
        Invoke dispatcher - execute plan steps
        """
        if state.type != StateType.DISPATCH:
            return state

        if not state.plan:
            state.type = StateType.ERROR
            state.error = "No plan available for dispatch"
            return state

        plan = state.plan

        # Save plan to tracker
        await self.tracker.persist_plan(plan)

        # Clear resolver for new plan execution
        self.resolver.clear()

        # Execute steps
        try:
            # For simplicity, execute steps sequentially
            # In production, respect dependencies and execute in parallel when possible
            for step in plan.steps:
                # Emit step started event
                await self.event_emitter.emit_step_started(
                    trace_id=state.trace.trace_id,
                    plan_id=plan.plan_id,
                    step_id=step.step_id,
                    step_description=step.description,
                    tool_name=step.tool_name
                )

                # Resolve placeholders in step input
                resolved_step = self.resolver.resolve_step_input(step)

                # Execute step with resolved input
                result = await self.executor.execute_step(resolved_step)

                # Emit step completed or failed event
                if result.status == "success":
                    await self.event_emitter.emit_step_completed(
                        trace_id=state.trace.trace_id,
                        plan_id=plan.plan_id,
                        step_id=step.step_id,
                        step_description=step.description,
                        output=result.output,
                        duration=result.duration
                    )
                else:
                    await self.event_emitter.emit_step_failed(
                        trace_id=state.trace.trace_id,
                        plan_id=plan.plan_id,
                        step_id=step.step_id,
                        step_description=step.description,
                        error=result.error or "Unknown error",
                        duration=result.duration
                    )

                # Register successful step outputs for future placeholder resolution
                if result.status == "success" and result.output is not None:
                    self.resolver.register_step_result(step.step_id, result.output)

                # Save result
                await self.tracker.append_step_result(plan.plan_id, result)

                # Update plan state
                update = PlanUpdate(
                    plan_id=plan.plan_id,
                    status=PlanState.IN_PROGRESS,
                    completed_steps=len(self.tracker.get_step_results(plan.plan_id)),
                    total_steps=len(plan.steps),
                    last_step_result=result
                )
                await self.tracker.persist_plan_update(update)

                # If step failed and is critical, stop execution
                if result.status == "failure":
                    # For now, continue execution even on failure
                    # In production, check if step is critical
                    pass

            # All steps executed, gather results
            results = await self.tracker.get_aggregated_results_for_group(plan.plan_id)
            state.results = results

            # Update plan state to completed
            update = PlanUpdate(
                plan_id=plan.plan_id,
                status=PlanState.COMPLETED,
                completed_steps=len(results.completed_steps),
                total_steps=results.total_steps
            )
            await self.tracker.persist_plan_update(update)

            # Transition to decision making
            state.type = StateType.PLAN_OR_DECIDE
            return state

        except Exception as e:
            state.type = StateType.ERROR
            state.error = f"Dispatch failed: {str(e)}"
            return state
