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

        # Get existing results to preserve successful step outputs
        existing_results = await self.tracker.get_aggregated_results_for_group(plan.plan_id)

        # Clear resolver only if this is a fresh plan (no existing results)
        if not existing_results or existing_results.total_steps == 0:
            self.resolver.clear()
            print("[TaskDispatcher] Fresh plan - cleared resolver")
        else:
            # Preserve successful step outputs in resolver
            print(f"[TaskDispatcher] Preserving {len(existing_results.completed_steps)} successful step outputs")
            for completed_step in existing_results.completed_steps:
                if completed_step.output is not None:
                    self.resolver.register_step_result(completed_step.step_id, completed_step.output)

        # Execute steps - STEP-BY-STEP approach
        # Execute only ONE step at a time, then return to decision making
        try:
            # Find the first incomplete step
            executed_step = False
            for step in plan.steps:
                # Skip already successful steps
                already_completed = any(
                    r.step_id == step.step_id and r.status == "success"
                    for r in existing_results.completed_steps
                ) if existing_results else False

                if already_completed:
                    print(f"[TaskDispatcher] Skipping already completed step: {step.step_id}")
                    continue

                # Found an incomplete step - execute it
                print(f"[TaskDispatcher] Executing step: {step.step_id} ({step.description})")

                # Resolve placeholders in step input BEFORE emitting event
                resolved_step = self.resolver.resolve_step_input(step)

                # Emit step started event with resolved input
                await self.event_emitter.emit_step_started(
                    trace_id=state.trace.trace_id,
                    plan_id=plan.plan_id,
                    step_id=step.step_id,
                    step_description=step.description,
                    tool_name=step.tool_name,
                    tool_input=resolved_step.input  # Use resolved input for logging
                )

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

                # Mark that we executed a step
                executed_step = True

                # IMPORTANT: Execute only ONE step, then return to decision making
                # This allows LLM to analyze the result before proceeding
                print(f"[TaskDispatcher] Step {step.step_id} executed, transitioning to decision making")
                break

            # Gather current results
            results = await self.tracker.get_aggregated_results_for_group(plan.plan_id)
            state.results = results

            # Check if all steps are completed
            all_completed = len(results.completed_steps) + len(results.failed_steps) >= results.total_steps

            if all_completed:
                print(f"[TaskDispatcher] All steps executed ({results.total_steps} total)")
                # Update plan state to completed
                update = PlanUpdate(
                    plan_id=plan.plan_id,
                    status=PlanState.COMPLETED,
                    completed_steps=len(results.completed_steps),
                    total_steps=results.total_steps
                )
                await self.tracker.persist_plan_update(update)
            else:
                print(f"[TaskDispatcher] Progress: {len(results.completed_steps)}/{results.total_steps} completed, {len(results.failed_steps)} failed")

            # Always transition to decision making after executing a step
            # This allows LLM to analyze results and decide next action
            state.type = StateType.PLAN_OR_DECIDE
            return state

        except Exception as e:
            state.type = StateType.ERROR
            state.error = f"Dispatch failed: {str(e)}"
            return state
