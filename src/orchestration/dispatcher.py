"""
TaskDispatcher - Dispatches tasks for execution
"""

import asyncio
from typing import Optional

from .types import State, StateType, PlanState, PlanUpdate
from .mcp_executor import MCPExecutor
from .tracker import TaskTracker


class TaskDispatcher:
    """TaskDispatcher - Executes plan steps using MCP"""

    def __init__(self, tracker: TaskTracker, executor: MCPExecutor):
        self.tracker = tracker
        self.executor = executor

    async def invoke(self, state: State) -> State:
        """
        Invoke dispatcher - execute plan steps
        """
        if state.type != StateType.DISPATCH:
            return state

        if not state.plan:
            print(f"\n[Dispatcher] ✗ ERROR: No plan available for dispatch")
            state.type = StateType.ERROR
            state.error = "No plan available for dispatch"
            return state

        plan = state.plan

        print(f"\n{'='*80}")
        print(f"[Dispatcher] Starting execution")
        print(f"[Dispatcher] Plan ID: {plan.plan_id}")
        print(f"[Dispatcher] Total steps: {len(plan.steps)}")
        print(f"[Dispatcher] Steps overview:")
        for i, step in enumerate(plan.steps, 1):
            print(f"  {i}. {step.description} (tool: {step.tool_name})")
        print(f"{'-'*80}\n")

        # Save plan to tracker
        await self.tracker.persist_plan(plan)

        # Execute steps
        try:
            # For simplicity, execute steps sequentially
            # In production, respect dependencies and execute in parallel when possible
            for i, step in enumerate(plan.steps, 1):
                print(f"[Dispatcher] Executing step {i}/{len(plan.steps)}")
                print(f"  - Step ID: {step.step_id}")
                print(f"  - Tool: {step.tool_name}")
                print(f"  - Description: {step.description}")
                print(f"  - Input: {step.input}")
                print(f"  - Dependencies: {step.dependencies}")

                # Execute step
                result = await self.executor.execute_step(step)

                print(f"[Dispatcher] Step {i} result:")
                print(f"  - Status: {result.status}")
                if result.status == "success":
                    print(f"  - Output: {result.output}")
                else:
                    print(f"  - Error: {result.error}")
                print(f"  - Duration: {result.duration:.2f}ms")
                print()

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
                    print(f"[Dispatcher] ⚠ Step {i} failed, but continuing execution")

            # All steps executed, gather results
            results = await self.tracker.get_aggregated_results_for_group(plan.plan_id)
            state.results = results

            print(f"{'-'*80}")
            print(f"[Dispatcher] Execution summary:")
            print(f"  - Total steps: {results.total_steps}")
            print(f"  - Completed: {len(results.completed_steps)}")
            print(f"  - Failed: {len(results.failed_steps)}")
            print(f"  - Success rate: {results.success_rate:.1%}")

            # Update plan state to completed
            update = PlanUpdate(
                plan_id=plan.plan_id,
                status=PlanState.COMPLETED,
                completed_steps=len(results.completed_steps),
                total_steps=results.total_steps
            )
            await self.tracker.persist_plan_update(update)

            print(f"[Dispatcher] ✓ All steps executed - transitioning to PLAN_OR_DECIDE state")
            print(f"{'='*80}\n")

            # Transition to decision making
            state.type = StateType.PLAN_OR_DECIDE
            return state

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"\n[Dispatcher] ✗ ERROR: {error_msg}")
            import traceback
            print(f"[Dispatcher] Traceback:")
            print(traceback.format_exc())
            print(f"{'='*80}\n")
            state.type = StateType.ERROR
            state.error = f"Dispatch failed: {error_msg}"
            return state
