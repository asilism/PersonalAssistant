"""
Planner - Plans task execution using LLM
"""

import json
import re
import uuid
import os
from datetime import datetime
from typing import Optional, Any, List
from anthropic import Anthropic

from .types import (
    State,
    StateType,
    Plan,
    Step,
    StepResult,
    Decision,
    OrchestrationSettings,
    ContextBundle,
    AggregatedGroupResults,
    PlanState
)
from .llm_client import create_llm_client, LLMClient
from .validators import extract_missing_params
from .event_emitter import get_event_emitter

# Forward declaration to avoid circular import
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .tracker import TaskTracker


class Planner:
    """Planner - Uses LLM to create execution plans"""

    def __init__(self, settings: OrchestrationSettings, tracker: Optional['TaskTracker'] = None):
        self.settings = settings
        self.tracker = tracker
        self.event_emitter = get_event_emitter()

        # Create LLM client using provider from settings
        self.llm_client: LLMClient = create_llm_client(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            provider=settings.llm_provider,
            base_url=settings.llm_base_url
        )

        print(f"[Planner] Using {settings.llm_provider} with model {settings.llm_model}")

    async def invoke(self, state: State) -> State:
        """
        Invoke planner - decides next action based on state
        """
        if state.type == StateType.PLAN_OR_DECIDE:
            # Initial planning
            if not state.plan:
                return await self._create_initial_plan(state)
            # Decide next steps based on results
            else:
                return await self._decide_next(state)
        else:
            # Pass through if not in planning state
            return state

    async def _create_initial_plan(self, state: State) -> State:
        """Create initial execution plan from user request"""

        # Build prompt for LLM (provider-specific)
        prompt = self._get_initial_plan_prompt(state)

        try:
            # Call LLM
            print(f"[Planner] Generating initial plan for request: {state.request_text[:100]}...")
            content = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096
            )
            content = content.strip()

            print(f"[Planner] LLM response received, length: {len(content)} chars")

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            print(f"[Planner] Parsing JSON response...")
            print(f"[Planner] Raw JSON content: {content[:500]}...")  # Log first 500 chars

            # Try to parse JSON first, only apply fix if parsing fails
            try:
                response_data = json.loads(content)
                print(f"[Planner] JSON parsing successful")
            except json.JSONDecodeError as e:
                print(f"[Planner] Initial JSON parsing failed: {str(e)}")
                print(f"[Planner] Applying placeholder fix and retrying...")
                # Fix unquoted placeholders in JSON before parsing
                content = self._fix_placeholders_in_json(content)
                print(f"[Planner] After placeholder fix: {content[:500]}...")
                response_data = json.loads(content)
                print(f"[Planner] JSON parsing successful after fix")

            # Handle case where LLM wraps JSON in a string value (OpenRouter OSS models only)
            # Example: {"assistant to=commentary code": "[{...}]"}
            # Only apply this for OpenRouter to avoid affecting well-functioning providers
            if self.settings.llm_provider.lower() == "openrouter":
                if isinstance(response_data, dict) and not response_data.get("type"):
                    # Check if any value is a JSON string that we should parse
                    for key, value in response_data.items():
                        if isinstance(value, str) and (value.strip().startswith('[') or value.strip().startswith('{')):
                            try:
                                # Try to parse the string value as JSON
                                parsed_value = json.loads(value)
                                print(f"[Planner] [OpenRouter] Detected JSON-in-string: key='{key}', unwrapping...")
                                response_data = parsed_value
                                print(f"[Planner] [OpenRouter] Unwrapped response_data type: {type(response_data).__name__}")
                                break
                            except json.JSONDecodeError:
                                # Not valid JSON, continue checking other values
                                continue

            # Check if this is a direct response (no tools needed)
            if isinstance(response_data, dict) and response_data.get("type") == "direct_response":
                print(f"[Planner] Detected direct response (no tools needed)")
                message = response_data.get("message", "")

                # Return as final response
                state.type = StateType.FINAL
                state.final_payload = {
                    "message": message,
                    "data": {
                        "response_type": "direct",
                        "original_request": state.request_text
                    }
                }
                return state

            # Treat as execution plan
            steps_data = response_data if isinstance(response_data, list) else response_data.get("steps", [])
            print(f"[Planner] Successfully parsed {len(steps_data)} steps")

            # Create plan
            plan_id = str(uuid.uuid4())
            steps = []
            dependencies = {}

            for i, step_data in enumerate(steps_data):
                step_id = f"step_{i}"
                print(f"[Planner] Processing step {i}/{len(steps_data)-1}: {step_data.get('description', 'N/A')}")

                # Normalize dependencies - handle various input types
                raw_deps = step_data.get("dependencies", [])
                print(f"[Planner]   Raw dependencies: {raw_deps} (type: {type(raw_deps)})")

                normalized_deps = self._normalize_dependencies(raw_deps)
                print(f"[Planner]   Normalized dependencies: {normalized_deps}")

                try:
                    step = Step(
                        step_id=step_id,
                        tool_name=step_data["tool_name"],
                        input=step_data["input"],
                        description=step_data["description"],
                        dependencies=normalized_deps
                    )
                    steps.append(step)
                    dependencies[step_id] = step.dependencies
                    print(f"[Planner]   ✓ Step created successfully")
                except Exception as step_error:
                    print(f"[Planner]   ✗ Failed to create step {step_id}")
                    print(f"[Planner]   Error: {str(step_error)}")
                    print(f"[Planner]   Step data: {json.dumps(step_data, indent=2)}")
                    raise

            plan = Plan(
                plan_id=plan_id,
                steps=steps,
                dependencies=dependencies
            )

            print(f"[Planner] Plan created successfully with {len(steps)} steps")

            # Emit plan created event
            steps_data = [
                {
                    "step_id": step.step_id,
                    "tool_name": step.tool_name,
                    "description": step.description,
                    "dependencies": step.dependencies
                }
                for step in steps
            ]
            await self.event_emitter.emit_plan_created(
                trace_id=state.trace.trace_id,
                plan_id=plan_id,
                steps=steps_data,
                total_steps=len(steps)
            )

            # Update state
            state.plan = plan
            state.plan_state = PlanState.PENDING
            state.type = StateType.DISPATCH

            return state

        except json.JSONDecodeError as e:
            # JSON parsing failed
            print(f"[Planner] ERROR: JSON parsing failed")
            print(f"[Planner] JSONDecodeError: {str(e)}")
            print(f"[Planner] Failed content: {content}")
            state.type = StateType.ERROR
            state.error = f"Planning failed: Invalid JSON response from LLM - {str(e)}"
            return state
        except Exception as e:
            # Planning failed
            print(f"[Planner] ERROR: Planning failed with exception")
            print(f"[Planner] Exception type: {type(e).__name__}")
            print(f"[Planner] Exception message: {str(e)}")
            import traceback
            print(f"[Planner] Traceback:\n{traceback.format_exc()}")
            state.type = StateType.ERROR
            state.error = f"Planning failed: {str(e)}"
            return state

    async def _decide_next(self, state: State) -> State:
        """Decide next action based on current results"""

        # Increment total decision count
        state.total_decision_count += 1
        print(f"[Planner] Decision count: {state.total_decision_count}")

        # Check if total decision count exceeds maximum (prevent infinite loops)
        MAX_TOTAL_DECISIONS = 10
        if state.total_decision_count > MAX_TOTAL_DECISIONS:
            error_msg = f"Task failed: Exceeded maximum decision limit ({MAX_TOTAL_DECISIONS}). Possible infinite loop detected."
            print(f"[Planner] {error_msg}")
            state.type = StateType.ERROR
            state.error = error_msg
            return state

        results = state.results
        if not results:
            # No results yet, shouldn't happen
            print(f"[Planner] ERROR: No results available for decision")
            state.type = StateType.ERROR
            state.error = "No results available for decision"
            return state

        # Check for validation errors that require human input
        for failed_step in results.failed_steps:
            if failed_step.error and "Email validation failed" in failed_step.error:
                print(f"[Planner] Detected email validation failure in step {failed_step.step_id}")
                print(f"[Planner] Error: {failed_step.error}")

                # Extract missing parameter information
                missing_param_info = extract_missing_params(failed_step.error)
                question = missing_param_info.get("question", "유효한 입력이 필요합니다.")

                print(f"[Planner] Transitioning to HUMAN_IN_THE_LOOP")
                print(f"[Planner] Question: {question}")

                # Transition to Human-in-the-loop
                state.type = StateType.HUMAN_IN_THE_LOOP
                state.final_payload = {
                    "message": question,
                    "error": failed_step.error,
                    "failed_step_id": failed_step.step_id,
                    "missing_param": missing_param_info
                }
                return state

        # Check if any steps have exceeded max retries or have non-retryable errors
        max_retries = self.settings.max_retries  # Default is 3 from types.py
        steps_exceeded_retries = []
        steps_with_non_retryable_errors = []

        for failed_step in results.failed_steps:
            step_id = failed_step.step_id
            error_msg = failed_step.error or ""

            # Check for non-retryable errors (e.g., tool not found)
            if "No MCP server found for tool" in error_msg:
                steps_with_non_retryable_errors.append(step_id)
                print(f"[Planner] Step {step_id} has non-retryable error: {error_msg}")
                continue

            retry_count = state.retry_counts.get(step_id, 0)
            print(f"[Planner] Step {step_id} failure count: {retry_count + 1}/{max_retries}")

            if retry_count >= max_retries:
                steps_exceeded_retries.append(step_id)
                print(f"[Planner] Step {step_id} has exceeded max retries ({max_retries})")

        # If any steps have non-retryable errors, fail immediately with detailed message
        if steps_with_non_retryable_errors:
            failed_steps_info = []
            for failed_step in results.failed_steps:
                if failed_step.step_id in steps_with_non_retryable_errors:
                    failed_steps_info.append(f"{failed_step.step_id}: {failed_step.error}")

            error_msg = f"Task failed: Steps have non-retryable errors:\n" + "\n".join(failed_steps_info)
            print(f"[Planner] {error_msg}")
            state.type = StateType.ERROR
            state.error = error_msg
            return state

        # If any steps exceeded retries, fail the task
        if steps_exceeded_retries:
            error_msg = f"Task failed: The following steps exceeded maximum retry limit ({max_retries}): {', '.join(steps_exceeded_retries)}"
            print(f"[Planner] {error_msg}")
            state.type = StateType.ERROR
            state.error = error_msg
            return state

        # Increment retry counts for failed steps (excluding non-retryable)
        for failed_step in results.failed_steps:
            step_id = failed_step.step_id
            if step_id not in steps_with_non_retryable_errors:
                state.retry_counts[step_id] = state.retry_counts.get(step_id, 0) + 1
                print(f"[Planner] Incremented retry count for {step_id}: {state.retry_counts[step_id]}")

        # Check if there are pending steps (not yet executed)
        completed_step_ids = {step.step_id for step in results.completed_steps}
        failed_step_ids = {step.step_id for step in results.failed_steps}
        pending_steps = [
            step for step in state.plan.steps
            if step.step_id not in completed_step_ids and step.step_id not in failed_step_ids
        ]

        # If there are pending steps, resolve placeholders with LLM
        if pending_steps:
            print(f"[Planner] Found {len(pending_steps)} pending steps:")
            for step in pending_steps:
                print(f"[Planner]   - {step.step_id}: {step.description}")

            # Resolve placeholders for next step with LLM assistance
            return await self._resolve_placeholders_for_next_step(state, pending_steps, results)

        # All steps executed - now ask LLM for final decision
        print(f"[Planner] No pending steps. All steps have been executed.")
        print(f"[Planner] Asking LLM to make final decision...")

        # Build prompt for decision (provider-specific)
        prompt = self._get_decision_prompt(state, results)

        try:
            print(f"[Planner] Making decision for plan: {state.plan.plan_id if state.plan else 'N/A'}")
            content = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096
            )
            content = content.strip()

            print(f"[Planner] Decision response received, length: {len(content)} chars")

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            print(f"[Planner] Parsing decision JSON...")
            print(f"[Planner] Raw decision content: {content[:500]}...")

            # Try to parse JSON first, only apply fix if parsing fails
            try:
                decision_data = json.loads(content)
                print(f"[Planner] Decision JSON parsing successful")
            except json.JSONDecodeError as e:
                print(f"[Planner] Initial decision JSON parsing failed: {str(e)}")
                print(f"[Planner] Applying placeholder fix and retrying...")
                content = self._fix_placeholders_in_json(content)
                print(f"[Planner] After placeholder fix: {content[:500]}...")
                decision_data = json.loads(content)
                print(f"[Planner] Decision JSON parsing successful after fix")

            # Handle unwrapping of malformed responses (OpenRouter OSS models only)
            # Some OSS models may wrap the response or put JSON in strings
            # Only apply this for OpenRouter to avoid affecting well-functioning providers
            if self.settings.llm_provider.lower() == "openrouter":
                if isinstance(decision_data, dict) and "type" not in decision_data:
                    # First check if JSON is wrapped in a string value
                    # Example: {"commentary to=assistant...": "Answer."}
                    for key, value in decision_data.items():
                        if isinstance(value, str) and (value.strip().startswith('{') or value.strip().startswith('[')):
                            try:
                                parsed_value = json.loads(value)
                                print(f"[Planner] [OpenRouter] Detected JSON-in-string: key='{key}', unwrapping...")
                                decision_data = parsed_value
                                print(f"[Planner] [OpenRouter] Unwrapped decision_data type: {type(decision_data).__name__}")
                                break
                            except json.JSONDecodeError:
                                continue

                    # Then check for common wrapper fields
                    if isinstance(decision_data, dict) and "type" not in decision_data:
                        for wrapper_key in ["final_output", "response", "decision", "output"]:
                            if wrapper_key in decision_data and isinstance(decision_data[wrapper_key], dict):
                                print(f"[Planner] [OpenRouter] Detected wrapped response with '{wrapper_key}' field, unwrapping...")
                                decision_data = decision_data[wrapper_key]
                                print(f"[Planner] [OpenRouter] Unwrapped decision_data: {decision_data}")
                                break

            # Validate decision_data format
            if not isinstance(decision_data, dict):
                print(f"[Planner] ERROR: LLM returned invalid format (expected dict, got {type(decision_data).__name__})")
                print(f"[Planner] Raw content: {content}")
                # Default to final decision with the result if all steps completed successfully
                if results and all(r.get("status") == "success" for r in results):
                    print(f"[Planner] Defaulting to 'final' decision since all steps succeeded")
                    decision_data = {
                        "type": "final",
                        "reason": "All steps completed successfully (auto-recovered from LLM format error)",
                        "payload": {
                            "message": "Task completed successfully",
                            "data": results[-1].get("output") if results else None
                        }
                    }
                else:
                    raise ValueError(f"LLM returned invalid decision format: {type(decision_data).__name__}. Expected a JSON object with 'type' field.")

            if "type" not in decision_data:
                print(f"[Planner] ERROR: Decision data missing 'type' field after unwrapping")
                print(f"[Planner] Decision data: {decision_data}")
                raise ValueError(f"LLM decision missing required 'type' field. Got: {decision_data}")

            decision_type = decision_data["type"]
            print(f"[Planner] Decision type: {decision_type}")

            if decision_type == "final":
                # Task complete
                print(f"[Planner] Decision: Task completed")

                # Emit decision made event
                await self.event_emitter.emit_decision_made(
                    trace_id=state.trace.trace_id,
                    decision_type="final",
                    reason="All steps completed successfully",
                    next_action="finalize"
                )

                state.type = StateType.FINAL
                state.final_payload = decision_data["payload"]
                return state

            elif decision_type == "nextSteps":
                # Add more steps to plan
                print(f"[Planner] Decision: Next steps required")
                next_steps_data = decision_data["payload"].get("steps", [])
                print(f"[Planner] Processing {len(next_steps_data)} next steps...")

                # Process each next step
                updated_steps = []
                for i, step_data in enumerate(next_steps_data):
                    print(f"[Planner]   Processing next step {i+1}: {step_data.get('description', 'N/A')}")

                    # Normalize dependencies
                    raw_deps = step_data.get("dependencies", [])
                    normalized_deps = self._normalize_dependencies(raw_deps)
                    print(f"[Planner]   Dependencies normalized: {raw_deps} -> {normalized_deps}")

                    # Determine step_id (check if LLM provided 'id' field for retry)
                    if "id" in step_data:
                        step_id = step_data["id"]
                        print(f"[Planner]   Retry detected for step: {step_id}")
                    else:
                        # New step - generate new ID (consistent with initial plan: step_0, step_1, ...)
                        step_id = f"step_{len(state.plan.steps) + i}"
                        print(f"[Planner]   New step created: {step_id}")

                    # Get tool_name from either 'tool_name', 'tool', or 'action' field
                    tool_name = step_data.get("tool_name") or step_data.get("tool") or step_data.get("action")
                    if not tool_name:
                        print(f"[Planner]   ERROR: No tool_name found in step_data: {step_data}")
                        continue

                    # Get input from either 'input' or 'parameters' field
                    step_input = step_data.get("input") or step_data.get("parameters", {})

                    # Create step object
                    step = Step(
                        step_id=step_id,
                        tool_name=tool_name,
                        input=step_input,
                        description=step_data.get("description", ""),
                        dependencies=normalized_deps
                    )
                    updated_steps.append(step)
                    print(f"[Planner]   ✓ Step created: {step_id} with tool {tool_name}")

                # Update plan with new/updated steps
                if updated_steps:
                    # Check if we're updating existing steps or adding new ones
                    existing_step_ids = {s.step_id for s in state.plan.steps}
                    new_step_ids = {s.step_id for s in updated_steps}

                    # If updating existing steps, replace them
                    if new_step_ids & existing_step_ids:
                        print(f"[Planner]   Updating existing steps: {new_step_ids & existing_step_ids}")
                        # Create new steps list with updates
                        final_steps = []
                        updated_by_id = {s.step_id: s for s in updated_steps}
                        for step in state.plan.steps:
                            if step.step_id in updated_by_id:
                                final_steps.append(updated_by_id[step.step_id])
                            else:
                                final_steps.append(step)
                        state.plan.steps = final_steps
                    else:
                        # Adding new steps
                        print(f"[Planner]   Adding {len(updated_steps)} new steps to plan")
                        state.plan.steps.extend(updated_steps)

                    # Update dependencies dict
                    for step in updated_steps:
                        state.plan.dependencies[step.step_id] = step.dependencies

                    print(f"[Planner]   Plan now has {len(state.plan.steps)} total steps")

                # Emit decision made event
                await self.event_emitter.emit_decision_made(
                    trace_id=state.trace.trace_id,
                    decision_type="nextSteps",
                    reason=f"Additional {len(next_steps_data)} steps required",
                    next_action="dispatch"
                )

                # Transition to DISPATCH
                state.type = StateType.DISPATCH
                return state

            elif decision_type == "needsHuman":
                # Needs human input
                print(f"[Planner] Decision: Human intervention required")

                # Emit decision made event
                await self.event_emitter.emit_decision_made(
                    trace_id=state.trace.trace_id,
                    decision_type="needsHuman",
                    reason=decision_data.get("reason", "Human intervention required"),
                    next_action="human_in_the_loop"
                )

                state.type = StateType.HUMAN_IN_THE_LOOP
                state.final_payload = decision_data["payload"]
                return state

            elif decision_type == "failed":
                # Failed
                print(f"[Planner] Decision: Task failed")
                error_msg = decision_data["payload"].get("error", "Task failed")
                print(f"[Planner] Error: {error_msg}")

                # Emit decision made event
                await self.event_emitter.emit_decision_made(
                    trace_id=state.trace.trace_id,
                    decision_type="failed",
                    reason=error_msg,
                    next_action="error"
                )

                state.type = StateType.ERROR
                state.error = error_msg
                return state

            else:
                print(f"[Planner] ERROR: Unknown decision type: {decision_type}")
                state.type = StateType.ERROR
                state.error = f"Unknown decision type: {decision_type}"
                return state

        except json.JSONDecodeError as e:
            print(f"[Planner] ERROR: Decision JSON parsing failed")
            print(f"[Planner] JSONDecodeError: {str(e)}")
            print(f"[Planner] Failed content: {content}")
            state.type = StateType.ERROR
            state.error = f"Decision making failed: Invalid JSON response - {str(e)}"
            return state
        except Exception as e:
            print(f"[Planner] ERROR: Decision making failed with exception")
            print(f"[Planner] Exception type: {type(e).__name__}")
            print(f"[Planner] Exception message: {str(e)}")
            import traceback
            print(f"[Planner] Traceback:\n{traceback.format_exc()}")
            state.type = StateType.ERROR
            state.error = f"Decision making failed: {str(e)}"
            return state

    async def _resolve_placeholders_for_next_step(
        self,
        state: State,
        pending_steps: List[Step],
        results: AggregatedGroupResults
    ) -> State:
        """
        Resolve placeholders for the next pending step using LLM

        Args:
            state: Current state
            pending_steps: List of pending steps to execute
            results: Results from executed steps

        Returns:
            Updated state with resolved placeholders and DISPATCH type
        """
        # Find next step to execute (first pending step with satisfied dependencies)
        next_step = self._find_next_executable_step(pending_steps, results)

        if not next_step:
            # No executable step found, transition to error
            print(f"[Planner] ERROR: No executable step found among pending steps")
            state.type = StateType.ERROR
            state.error = "No executable step found"
            return state

        print(f"[Planner] Next step to execute: {next_step.step_id} - {next_step.description}")

        # Check if step has placeholders that need resolving
        has_placeholders = self._check_for_placeholders(next_step.input)

        if not has_placeholders:
            # No placeholders, just continue to dispatch
            print(f"[Planner] No placeholders found in {next_step.step_id}, continuing to DISPATCH")
            await self.event_emitter.emit_decision_made(
                trace_id=state.trace.trace_id,
                decision_type="continue",
                reason=f"Executing next step: {next_step.step_id}",
                next_action="dispatch"
            )
            state.type = StateType.DISPATCH
            return state

        # Get most recent step result for context
        latest_result = results.completed_steps[-1] if results.completed_steps else None

        if not latest_result:
            # No previous results, can't resolve placeholders
            print(f"[Planner] WARNING: No previous step results available for placeholder resolution")
            state.type = StateType.DISPATCH
            return state

        # Call LLM to resolve placeholders
        print(f"[Planner] Calling LLM to resolve placeholders for {next_step.step_id}")

        try:
            resolved_input = await self._call_llm_for_placeholder_resolution(
                next_step, latest_result, results, state
            )

            if resolved_input:
                # Update the step in the plan with resolved input
                for i, step in enumerate(state.plan.steps):
                    if step.step_id == next_step.step_id:
                        state.plan.steps[i].input = resolved_input
                        print(f"[Planner] Updated {next_step.step_id} with resolved input: {resolved_input}")
                        break
        except Exception as e:
            print(f"[Planner] ERROR: Failed to resolve placeholders: {str(e)}")
            import traceback
            print(f"[Planner] Traceback:\n{traceback.format_exc()}")
            # Continue anyway - dispatcher will try to resolve with PlaceholderResolver

        # Emit decision made event
        await self.event_emitter.emit_decision_made(
            trace_id=state.trace.trace_id,
            decision_type="continue",
            reason=f"Resolved placeholders for {next_step.step_id}, executing next",
            next_action="dispatch"
        )

        # Transition to DISPATCH
        state.type = StateType.DISPATCH
        return state

    def _find_next_executable_step(
        self,
        pending_steps: List[Step],
        results: AggregatedGroupResults
    ) -> Optional[Step]:
        """
        Find the next step that can be executed (all dependencies satisfied)

        Args:
            pending_steps: List of pending steps
            results: Results from executed steps

        Returns:
            Next executable step or None
        """
        completed_step_ids = {step.step_id for step in results.completed_steps}

        for step in pending_steps:
            # Check if all dependencies are satisfied
            if not step.dependencies:
                # No dependencies, can execute
                return step

            # Check if all dependencies are completed
            deps_satisfied = all(dep in completed_step_ids for dep in step.dependencies)
            if deps_satisfied:
                return step

        # No executable step found
        return None

    def _check_for_placeholders(self, data: Any) -> bool:
        """
        Check if data contains any placeholders ({{...}}, ${...}, or {...})

        Args:
            data: Data to check (can be dict, list, str, or primitive)

        Returns:
            True if placeholders found, False otherwise
        """
        import re

        # Pattern matches: {{...}}, ${...}, or {...}
        placeholder_pattern = re.compile(r'(\{\{([^}]+)\}\}|\$\{([^}]+)\}|\{([^}]+)\})')

        if isinstance(data, str):
            return bool(placeholder_pattern.search(data))
        elif isinstance(data, dict):
            return any(self._check_for_placeholders(v) for v in data.values())
        elif isinstance(data, list):
            return any(self._check_for_placeholders(item) for item in data)
        else:
            return False

    async def _call_llm_for_placeholder_resolution(
        self,
        next_step: Step,
        latest_result: 'StepResult',
        all_results: AggregatedGroupResults,
        state: State
    ) -> Optional[dict]:
        """
        Call LLM to resolve placeholders in next step's input

        Args:
            next_step: The step with placeholders to resolve
            latest_result: Most recent step result
            all_results: All step results for context
            state: Current state

        Returns:
            Resolved input dict or None if resolution failed
        """
        # Check if there's a HITL response in context
        hitl_response = None
        if state.context and state.context.additional_context:
            hitl_response = state.context.additional_context.get("hitl_response")

        # Build prompt for LLM
        hitl_context = ""
        if hitl_response:
            hitl_context = f"""
HUMAN INPUT (HITL Response):
The user has provided additional information: "{hitl_response}"
Use this information to resolve any missing parameters or placeholders.
"""

        prompt = f"""You are helping resolve placeholders in a task execution step.

MOST RECENT STEP EXECUTED:
- Step ID: {latest_result.step_id}
- Tool: {latest_result.tool_name if hasattr(latest_result, 'tool_name') else 'unknown'}
- Output: {json.dumps(latest_result.output, indent=2)}

ALL COMPLETED STEPS (for reference):
{self._format_all_step_results(all_results)}
{hitl_context}
NEXT STEP TO EXECUTE:
- Step ID: {next_step.step_id}
- Description: {next_step.description}
- Tool: {next_step.tool_name}
- Input (with placeholders): {json.dumps(next_step.input, indent=2)}

YOUR TASK:
1. Analyze the output from previous steps (especially the most recent one)
2. Read the NEXT STEP's description carefully to understand what specific item is needed
3. Search through arrays intelligently based on the description and user's original intent
4. Return the resolved input for {next_step.step_id}

CRITICAL INSTRUCTIONS FOR PLACEHOLDER RESOLUTION:

1. HOW TO EXTRACT VALUES FROM STEP OUTPUT:
   - Placeholder format: {{{{step_N.field_name}}}} or {{{{step_N}}}}
   - Navigate through the output structure to find the field
   - Example: If step_0 output is {{"success": true, "result": 200}}
     * {{{{step_0.result}}}} should resolve to 200 (the NUMBER, not the string "200")
     * {{{{step_0}}}} should resolve to the entire output object

2. TYPE PRESERVATION:
   - CRITICAL: Preserve the original data type of extracted values!
   - If the field contains a number (int or float), return it as a NUMBER, not a string
   - If the field contains a string, return it as a string
   - If the field contains an array or object, return it as-is
   - Example CORRECT resolutions:
     * {{{{step_0.result}}}} where result=200 → 200 (number, not "200")
     * {{{{step_0.result}}}} where result="completed" → "completed" (string)
     * {{{{step_0.count}}}} where count=5 → 5 (number, not "5")

3. ARRAY PLACEHOLDERS:
   - When you see {{{{step_X.array.0.field}}}}, DO NOT always pick index 0
   - Instead, analyze the step description and previous context to find the RIGHT item
   - Example: If step description is "Update Project Review event" and step_0 returned:
     * events: [{{"id": "event_1", "title": "Team Meeting"}}, {{"id": "event_2", "title": "Project Review"}}]
     * The placeholder {{{{step_0.events.0.id}}}} should resolve to "event_2" (not "event_1")
     * Because the description mentions "Project Review"

4. RESOLUTION EXAMPLES:
   Example 1 - Simple field extraction:
   - Step output: {{"success": true, "operation": "multiply", "result": 200}}
   - Placeholder: {{{{step_0.result}}}}
   - Resolved value: 200 (number)

   Example 2 - Nested field:
   - Step output: {{"success": true, "event": {{"id": "evt_123", "title": "Meeting"}}}}
   - Placeholder: {{{{step_0.event.id}}}}
   - Resolved value: "evt_123" (string)

   Example 3 - Multiple placeholders:
   - Input with placeholders: {{"numbers": ["{{{{step_0.result}}}}", 150]}}
   - Step_0 output: {{"success": true, "result": 200}}
   - Resolved input: {{"numbers": [200, 150]}}  ← 200 is a NUMBER, not "200"

IMPORTANT:
- If a placeholder describes a filter or search (e.g., "event where title='X'"), find the matching item
- Use the step description as a guide for which item to select from arrays
- Extract the exact field value requested with its ORIGINAL DATA TYPE
- Preserve all non-placeholder values as-is
- If you cannot resolve a placeholder, keep it as-is and explain in reasoning

Return ONLY valid JSON in this format:
{{
  "resolved_input": {{
    // The complete input dict with all placeholders resolved
    // REMEMBER: Preserve data types (numbers as numbers, strings as strings)
  }},
  "reasoning": "Brief explanation of how you resolved the placeholders"
}}

Return ONLY the JSON, no other text."""

        try:
            content = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048
            )
            content = content.strip()

            # Extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)

            # Try to parse JSON first, only apply fix if parsing fails
            try:
                data = json.loads(content)
                print(f"[Planner] Placeholder resolution JSON parsing successful")
            except json.JSONDecodeError as e:
                print(f"[Planner] Initial placeholder resolution JSON parsing failed: {str(e)}")
                print(f"[Planner] Applying placeholder fix and retrying...")
                content = self._fix_placeholders_in_json(content)
                data = json.loads(content)
                print(f"[Planner] Placeholder resolution JSON parsing successful after fix")

            resolved_input = data.get("resolved_input")
            reasoning = data.get("reasoning", "")

            print(f"[Planner] LLM resolved placeholders:")
            print(f"[Planner]   Reasoning: {reasoning}")
            print(f"[Planner]   Resolved input: {json.dumps(resolved_input, indent=2)}")

            return resolved_input

        except json.JSONDecodeError as e:
            print(f"[Planner] ERROR: Failed to parse LLM response as JSON")
            print(f"[Planner] JSONDecodeError: {str(e)}")
            print(f"[Planner] Response: {content}")
            return None
        except Exception as e:
            print(f"[Planner] ERROR: Failed to call LLM for placeholder resolution")
            print(f"[Planner] Exception: {str(e)}")
            import traceback
            print(f"[Planner] Traceback:\n{traceback.format_exc()}")
            return None

    def _format_all_step_results(self, results: AggregatedGroupResults) -> str:
        """Format all step results for LLM context"""
        lines = []

        for step_result in results.completed_steps:
            lines.append(f"- {step_result.step_id}:")
            lines.append(f"  Output: {json.dumps(step_result.output, indent=4)}")

        return "\n".join(lines) if lines else "No previous steps"

    def _fix_placeholders_in_json(self, content: str) -> str:
        """
        Fix unquoted placeholders in JSON content by wrapping them in quotes.
        Handles patterns like {{step_0.result}} and converts them to "{{step_0.result}}"
        when they appear unquoted in JSON.

        This prevents JSON parsing errors when LLM generates placeholders without quotes
        in contexts where strings are expected (e.g., in arrays or as object values).

        Args:
            content: Raw JSON string that may contain unquoted placeholders

        Returns:
            Fixed JSON string with all placeholders properly quoted
        """
        # Pattern to match unquoted placeholders in JSON
        # Matches: {{...}} when NOT already inside quotes
        # Uses negative lookbehind (?<!") and negative lookahead (?!") to ensure
        # the placeholder is not already quoted
        pattern = r'(?<!")(\{\{[^}]+\}\})(?!")'

        def replace_match(match):
            placeholder = match.group(1)
            return f'"{placeholder}"'

        fixed = re.sub(pattern, replace_match, content)
        return fixed

    def _normalize_dependencies(self, deps: Any) -> list[str]:
        """
        Normalize dependencies to list of strings.
        Handles various input types from LLM:
        - None or empty -> []
        - Integer -> [] (treat as "no dependencies")
        - String -> [string]
        - List of integers -> convert to list of strings
        - List of strings -> return as-is
        """
        if deps is None or deps == [] or deps == "":
            return []

        # Single integer (e.g., 0) - treat as no dependencies
        if isinstance(deps, int):
            print(f"[Planner]   Warning: Got integer dependency {deps}, treating as no dependencies")
            return []

        # Single string - wrap in list
        if isinstance(deps, str):
            return [deps]

        # List - normalize each element
        if isinstance(deps, list):
            normalized = []
            for dep in deps:
                if isinstance(dep, str):
                    normalized.append(dep)
                elif isinstance(dep, int):
                    # Convert integer to step_id format (0-indexed)
                    # LLM returns 0-based index (0 means step_0, 1 means step_1, etc.)
                    step_id = f"step_{dep}"
                    normalized.append(step_id)
                    print(f"[Planner]   Info: Converted integer dependency {dep} to '{step_id}'")
                else:
                    print(f"[Planner]   Warning: Unknown dependency type {type(dep)}: {dep}")
            return normalized

        # Unknown type - return empty
        print(f"[Planner]   Warning: Unknown dependencies type {type(deps)}: {deps}, treating as no dependencies")
        return []

    def _format_tools_for_prompt(self) -> str:
        """Format available tools for prompt"""
        lines = []
        for tool in self.settings.available_tools:
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

    def _format_tools_detailed(self) -> str:
        """Format available tools in detailed JSON format for prompt, including FastMCP outputSchema"""
        lines = []
        for tool in self.settings.available_tools:
            tool_dict = {
                "name": tool.name,
                "description": tool.description
            }
            if tool.input_schema:
                tool_dict["input_schema"] = tool.input_schema
            # Include outputSchema from FastMCP if available
            if tool.output_schema:
                tool_dict["output_schema"] = tool.output_schema
            lines.append("    " + json.dumps(tool_dict, indent=4).replace("\n", "\n    "))
        return ",\n".join(lines)

    def _format_context(self, context: Optional[ContextBundle]) -> str:
        """Format context for prompt"""
        if not context:
            return "No additional context"

        lines = []
        if context.conversation_history:
            lines.append("Conversation history:")
            for msg in context.conversation_history[-5:]:  # Last 5 messages
                lines.append(f"  - {msg}")

        if context.additional_context:
            # Handle previous_execution_results - structured data from previous requests
            previous_results = context.additional_context.get("previous_execution_results", [])
            if previous_results:
                lines.append("")
                lines.append("🔴" * 30)
                lines.append("🔴 CRITICAL: PREVIOUS EXECUTION RESULTS - YOU MUST USE THESE FOR FOLLOW-UP REQUESTS! 🔴")
                lines.append("🔴" * 30)
                lines.append("")

                for i, result in enumerate(previous_results):
                    lines.append(f"━━━ [Previous Request {i+1}]: \"{result.get('request', 'Unknown')}\" ━━━")
                    lines.append(f"[Timestamp]: {result.get('timestamp', 'Unknown')}")
                    lines.append(f"[Structured Results - USE THESE VALUES]:")
                    # Pretty print the results data
                    results_data = result.get("results", {})
                    if isinstance(results_data, dict):
                        lines.append(json.dumps(results_data, indent=2, ensure_ascii=False))
                    else:
                        lines.append(str(results_data))
                    lines.append("")

                lines.append("🔴" * 30)
                lines.append("")
                lines.append("🚨 MANDATORY FOLLOW-UP HANDLING RULES:")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("When user says ANY of these (in any language):")
                lines.append("  • '첫번째', '첫 번째', 'first', 'the first one'")
                lines.append("  • '두번째', '두 번째', 'second', 'the second one'")
                lines.append("  • '그것', '그거', 'that one', 'it'")
                lines.append("  • '틀어줘', '재생해줘', 'play', 'play it'")
                lines.append("  • '방금', '아까', 'just now', 'earlier'")
                lines.append("")
                lines.append("You MUST:")
                lines.append("1. Look at PREVIOUS EXECUTION RESULTS above")
                lines.append("2. Extract the ACTUAL values (URLs, IDs, titles, etc.)")
                lines.append("3. Use those values DIRECTLY in your tool call")
                lines.append("4. NEVER respond with 'What song?' or ask for clarification!")
                lines.append("")
                lines.append("Example: If previous results have videos: [{id: 'abc123', ...}]")
                lines.append("  User: '첫번째 틀어줘' (play the first one)")
                lines.append("  ✅ CORRECT: Call play_audio with url='https://youtube.com/watch?v=abc123'")
                lines.append("  ❌ WRONG: Ask 'Which song do you want to play?'")
                lines.append("  ❌ WRONG: Return direct_response asking for clarification")
                lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                lines.append("")

            # Handle other context (excluding internal fields)
            other_context = {k: v for k, v in context.additional_context.items()
                           if k not in ["recent_results", "recent_plan_id", "recent_request", "previous_execution_results"]}

            if other_context:
                lines.append("Additional context:")
                for key, value in other_context.items():
                    lines.append(f"  - {key}: {value}")

        return "\n".join(lines) if lines else "No additional context"

    async def _format_recent_execution_results(self, context: Optional[ContextBundle]) -> str:
        """Format recent execution results from previous plans"""
        if not context or not context.additional_context:
            return ""

        try:
            # Check if recent results are already in the context (loaded by Orchestrator)
            recent_results = context.additional_context.get("recent_results")
            recent_request = context.additional_context.get("recent_request")

            if not recent_results:
                return ""

            lines = [
                "Recent execution results (from previous request):",
                f"  Previous request: {recent_request}",
                "  Available data from previous execution:"
            ]

            for result in recent_results:
                if result.get("status") == "success":
                    # Format the output for readability
                    output_preview = str(result.get("output", ""))[:300]  # First 300 chars
                    if len(str(result.get("output", ""))) > 300:
                        output_preview += "..."
                    lines.append(f"    - {result.get('description', 'Unknown')}: {output_preview}")

            return "\n".join(lines)
        except Exception as e:
            print(f"[Planner] Error formatting recent execution results: {e}")
            return ""

    def _get_placeholder_instructions(self, prompt_type: str = "initial") -> str:
        """
        Get placeholder instructions based on LLM provider

        Args:
            prompt_type: Type of prompt ("initial" or "decision")

        Returns:
            Placeholder instruction text appropriate for the LLM provider

        Note:
            Future enhancement: This will be replaced with database/UI-managed prompts.
            For now, we use provider-specific hardcoded instructions.
        """
        provider = self.settings.llm_provider.lower()

        # Anthropic models work well with simple, concise instructions
        if provider == "anthropic":
            return self._get_anthropic_placeholder_instructions(prompt_type)
        # OpenRouter and other providers benefit from more explicit guidance
        else:
            return self._get_enhanced_placeholder_instructions(prompt_type)

    def _get_anthropic_placeholder_instructions(self, prompt_type: str) -> str:
        """
        Get simple placeholder instructions for Anthropic models

        Anthropic models (Claude) understand instructions well with minimal examples.
        Keep it concise to avoid over-specification.
        """
        if prompt_type == "initial":
            return """PLACEHOLDER SYNTAX FOR REFERENCING PREVIOUS STEPS:
IMPORTANT: Always use DOUBLE curly braces {{{{ }}}} for placeholders!

- To reference a previous step's entire output: use {{{{step_N}}}} or {{{{step_N.result}}}}
  Example: {{"numbers": [{{{{step_0.result}}}}, 150]}}
  NOTE: Steps are 0-indexed (step_0 is the first step, step_1 is the second, etc.)

- To reference a specific field: use {{{{step_N.field_name}}}}
  Example: {{"event_id": {{{{step_0.id}}}}}}

- To access nested fields: use {{{{step_N.field.nested_field}}}}
  Example: {{"title": {{{{step_0.event.title}}}}}}

- To access array elements: use {{{{step_N.array_field.INDEX}}}} (dot notation)
  Example: {{"event_id": {{{{step_0.events.0.id}}}}}}
  Example: {{"recipient": {{{{step_1.events.0.attendees.0}}}}}}
  NOTE: Array indices use dot notation (events.0.id) NOT bracket notation (events[0].id)"""
        else:  # decision
            return """PLACEHOLDER SYNTAX FOR NEXT STEPS (when needed):
- To reference previous step output: {{{{step_N}}}} or {{{{step_N.field_name}}}}
- To access array elements: {{{{step_N.array.0.id}}}} (use dot notation)
- NOTE: Steps are 0-indexed (step_0 is first step, step_1 is second, etc.)
- But prefer using actual values from the results when possible!"""

    def _get_enhanced_placeholder_instructions(self, prompt_type: str) -> str:
        """
        Get enhanced placeholder instructions for OpenRouter and other providers

        These models need more explicit guidance with positive/negative examples
        to avoid generating placeholders in incorrect formats.
        """
        if prompt_type == "initial":
            return """PLACEHOLDER SYNTAX FOR REFERENCING PREVIOUS STEPS:
CRITICAL: Placeholders MUST be STRING values wrapped in DOUBLE curly braces {{{{ }}}}

✅ CORRECT FORMAT (placeholders as strings):
- To reference a previous step's entire output: use {{{{step_N}}}} or {{{{step_N.result}}}}
  Example: {{"numbers": ["{{{{step_0.result}}}}", 150]}}
  Example: {{"value": "{{{{step_0}}}}"}}
  NOTE: Steps are 0-indexed (step_0 is the first step, step_1 is the second, etc.)

- To reference a specific field: use {{{{step_N.field_name}}}}
  Example: {{"event_id": "{{{{step_0.id}}}}"}}
  Example: {{"title": "{{{{step_1.name}}}}"}}

- To access nested fields: use {{{{step_N.field.nested_field}}}}
  Example: {{"title": "{{{{step_0.event.title}}}}"}}

- To access array elements: use {{{{step_N.array_field.INDEX}}}} (dot notation)
  Example: {{"event_id": "{{{{step_0.events.0.id}}}}"}}
  Example: {{"recipient": "{{{{step_1.events.0.attendees.0}}}}"}}
  NOTE: Array indices use dot notation (events.0.id) NOT bracket notation (events[0].id)

❌ FORBIDDEN FORMATS (will cause errors):
- NEVER use dict/object format: {{"numbers": [{{"step_0.result": ""}}, 150]}} ❌ WRONG!
- NEVER use placeholder key: {{"numbers": [{{"placeholder": "step_0"}}, 150]}} ❌ WRONG!
- NEVER use ref key: {{"value": {{"ref": "step_0"}}}} ❌ WRONG!
- Placeholders MUST be quoted strings, NOT objects or dicts

✅ ALWAYS use this format: "{{{{step_N.field}}}}" (quoted string with double braces)"""
        else:  # decision
            return """PLACEHOLDER SYNTAX FOR NEXT STEPS (when needed):
CRITICAL: Placeholders MUST be STRING values wrapped in DOUBLE curly braces {{{{ }}}}

✅ CORRECT FORMAT:
- Reference step output: {{"value": "{{{{step_N}}}}"}} or {{"id": "{{{{step_N.field_name}}}}"}}
- Array elements: {{"event_id": "{{{{step_N.array.0.id}}}}"}} (use dot notation)
- Example: {{"numbers": ["{{{{step_0.result}}}}", 150]}}
- NOTE: Steps are 0-indexed (step_0 is first step, step_1 is second, etc.)

❌ FORBIDDEN FORMATS:
- NEVER: {{"value": {{"step_0": ""}}}} ❌
- NEVER: {{"value": {{"placeholder": "step_0"}}}} ❌
- NEVER: {{"value": {{"ref": "step_0.result"}}}} ❌
- Placeholders MUST be quoted strings: "{{{{step_N}}}}" ✅

Prefer using actual values from results when possible!"""

    def _get_initial_plan_prompt(self, state: State) -> str:
        """
        Get initial planning prompt based on provider

        Args:
            state: Current state

        Returns:
            Prompt string appropriate for the LLM provider
        """
        provider = self.settings.llm_provider.lower()

        # Use enhanced prompt for OpenRouter
        if provider == "openrouter":
            return self._get_openrouter_initial_plan_prompt(state)
        else:
            return self._get_standard_initial_plan_prompt(state)

    def _get_standard_initial_plan_prompt(self, state: State) -> str:
        """Standard initial planning prompt"""
        tools_list_detailed = self._format_tools_detailed()
        context_str = self._format_context(state.context)
        recent_results_str = ""  # Will be populated by async method if needed

        # Get current date and time
        current_datetime = datetime.now()
        today_str = current_datetime.strftime("%Y-%m-%d (%A)")
        current_time_str = current_datetime.strftime("%H:%M:%S")

        return f"""You are an AI assistant that creates execution plans.

🚨 CRITICAL RULE - TOOL USAGE DECISION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You must decide whether to use tools or respond directly based on the user's request.

✅ USE TOOLS (create execution plan) when:
- The request requires taking actions (send email, create calendar event, search data, etc.)
- You need to retrieve external information (emails, contacts, news, weather, etc.)
- Calculations or data processing is needed
- Any operation that requires one of the available tools

✅ RESPOND DIRECTLY (use direct_response) when:
- Meta questions about yourself (e.g., "What LLM are you?", "What can you do?", "Who made you?")
- General knowledge questions that don't require tool execution
- Conversational queries that don't need external data
- Questions about capabilities or limitations
- No suitable tool exists for the request

❌ FORBIDDEN BEHAVIORS:
- Do NOT use inappropriate tools just to force tool usage
- Do NOT create execution plans when direct response is more appropriate
- Do NOT respond directly when tools are clearly needed
- Do NOT guess or make up tool names

Examples:
• User: "What's 150 + 250?"
  ✅ GOOD: Create plan with calculator tool to add(150, 250)

• User: "Send email to John"
  ✅ GOOD: Create plan: Step 0: lookup_contact("John"), Step 1: send_email(...)

• User: "What LLM model are you?"
  ✅ GOOD: {{"type": "direct_response", "message": "I am Claude 3.5 Sonnet..."}}

• User: "What tools do you have access to?"
  ✅ GOOD: {{"type": "direct_response", "message": "I have access to email tools, calendar management..."}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT CONTEXT:
- Today's date: {today_str}
- Current time: {current_time_str}
- When interpreting time references (e.g., "this week", "next week", "tomorrow", "last week"), use today's date as the reference point.

Available tools (you MUST use these exact tool names):
{tools_list_detailed}

User request: {state.request_text}

Context:
{context_str}

CRITICAL: You MUST use ONLY the exact tool names listed above. DO NOT create variations or guess tool names.

🔴🔴🔴 CRITICAL: FOLLOW-UP REQUESTS - MUST USE TOOLS, NEVER direct_response! 🔴🔴🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If the user's request references previous results in ANY way:
  • Korean: "첫번째", "두번째", "그것", "그거", "틀어줘", "재생해", "방금", "아까"
  • English: "first", "second", "that one", "it", "play it", "the one", "just now"

You MUST:
1. Check the PREVIOUS EXECUTION RESULTS section in the Context above
2. Extract the ACTUAL values (IDs, URLs, titles, etc.) from those results
3. Create an execution plan with the appropriate tool using those real values
4. NEVER return direct_response asking for clarification!

🚨 ABSOLUTELY FORBIDDEN for follow-up requests:
❌ Returning direct_response with "어떤 노래를 틀어드릴까요?" (Which song?)
❌ Returning direct_response asking for more information
❌ Returning direct_response saying you don't know which item
❌ Any response that doesn't use a tool when previous results exist

✅ CORRECT BEHAVIOR for follow-up requests:
- Previous results show: videos: [{{id: "abc123", title: "Song A"}}, {{id: "xyz789", title: "Song B"}}]
- User says: "첫번째 틀어줘" or "play the first song"
- ✅ CORRECT: Create execution plan with play_audio tool using url="https://youtube.com/watch?v=abc123"

Example execution plan for "첫번째 틀어줘":
[
  {{
    "tool_name": "play_audio",
    "input": {{"url": "https://youtube.com/watch?v=abc123"}},
    "description": "Play the first song from previous search results",
    "dependencies": []
  }}
]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESPONSE FORMAT - Choose ONE of the following:

OPTION 1: If tools are needed, create a step-by-step execution plan.
Return a JSON array of steps. Each step should specify:
1. tool_name: which tool to use
2. input: parameters for the tool
3. description: what this step does
4. dependencies: which previous step IDs this depends on (empty list if none)

OPTION 2: ONLY use direct_response when ALL of these conditions are met:
  ✓ Meta questions about yourself (e.g., "What LLM are you?")
  ✓ General knowledge that doesn't require tools
  ✓ NO previous execution results in context
  ✓ User is NOT referencing previous results (no "첫번째", "first", "그것", etc.)

🚨 NEVER use direct_response if:
  ✗ Previous execution results exist in context
  ✗ User says "첫번째", "두번째", "first", "second", "그것", "that one"
  ✗ User says "틀어줘", "재생해", "play", "play it"
  ✗ User references any item from a previous search/query

Return a JSON object with this format:
{{
  "type": "direct_response",
  "message": "Your direct answer to the user's question"
}}

{self._get_placeholder_instructions(prompt_type="initial")}

CRITICAL - USING TOOL OUTPUT SCHEMAS:
Each tool definition above includes an "output_schema" field showing:
- Example output structure
- Key fields you can reference in placeholders

When creating placeholders:
1. Check the tool's "output_schema" -> "key_fields" for available field names
2. Use the ACTUAL field names from the schema (e.g., if schema shows "articles", use {{{{step_X.articles}}}})
3. Refer to the "example" output to understand the structure
4. If a tool has no output_schema, use generic patterns like {{{{step_X.result}}}} or {{{{step_X}}}}

Example:
- Tool: search_latest_news
- Output schema: {{"key_fields": ["articles", "count"]}}
- Correct placeholder: {{{{step_0.articles}}}}
- Wrong placeholder: {{{{step_0.news}}}} ❌

FORMAT EXAMPLES:

For execution plan (array of steps):
[
  {{
    "tool_name": "tool_name",
    "input": {{"param": "value"}},
    "description": "description of this step",
    "dependencies": []
  }}
]

For direct response (ONLY when no previous results exist and no references to previous items):
{{
  "type": "direct_response",
  "message": "Your answer here"
}}

🔴 CRITICAL FOLLOW-UP EXAMPLE:
If previous results show: videos: [{{id: "sDY7FUbYvkg", title: "Song A"}}]
And user says: "첫번째 틀어줘" or "play the first one"
✅ CORRECT - Use tool:
[
  {{
    "tool_name": "play_audio",
    "input": {{"url": "https://youtube.com/watch?v=sDY7FUbYvkg"}},
    "description": "Play the first song from previous search results",
    "dependencies": []
  }}
]
❌ WRONG - Never do this:
{{"type": "direct_response", "message": "어떤 노래를 틀어드릴까요?"}}

Return ONLY the JSON (either execution plan array OR direct response object), no other text.
"""

    def _get_openrouter_initial_plan_prompt(self, state: State) -> str:
        """Enhanced initial planning prompt for OpenRouter (OSS 20b models)"""
        tools_list_detailed = self._format_tools_detailed()
        context_str = self._format_context(state.context)

        # Get current date and time
        current_datetime = datetime.now()
        today_str = current_datetime.strftime("%Y-%m-%d (%A)")
        current_time_str = current_datetime.strftime("%H:%M:%S")

        return f"""You are an AI assistant. Your task is to decide whether to create an execution plan using tools or respond directly.

⚠️ ABSOLUTELY CRITICAL - TOOL USAGE DECISION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DECIDE BASED ON THE USER'S REQUEST:

✅ USE TOOLS (create execution plan) when:
- Actions needed: send email, create calendar event, search data, etc.
- External information needed: emails, contacts, news, weather, etc.
- Calculations or data processing required

✅ RESPOND DIRECTLY when:
- Meta questions about yourself (e.g., "What LLM are you?", "What can you do?")
- General knowledge questions without tool requirements
- No suitable tool exists for the request
- DO NOT force inappropriate tool usage!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONTEXT:
- Today's date: {today_str}
- Current time: {current_time_str}
- User request: {state.request_text}

AVAILABLE TOOLS (use these exact names):
{tools_list_detailed}

⚠️ MANDATORY RESPONSE FORMAT - Choose ONE:

OPTION 1: If tools are needed, return a JSON ARRAY of steps:
[
  {{
    "tool_name": "exact_tool_name_from_list_above",
    "input": {{ "param1": "value1", "param2": "value2" }},
    "description": "what this step does",
    "dependencies": []
  }}
]

OPTION 2: ONLY use direct_response when ALL conditions are met:
  ✓ Meta questions about yourself (e.g., "What LLM are you?")
  ✓ NO previous execution results in context
  ✓ User is NOT referencing previous results

🚨 NEVER use direct_response if:
  ✗ Previous execution results exist in context
  ✗ User says "첫번째", "두번째", "first", "second", "그것"
  ✗ User says "틀어줘", "재생해", "play"

{{
  "type": "direct_response",
  "message": "Your direct answer here"
}}

⚠️ EXAMPLES:

Example 1 - User asks: "123 곱하기 456을 계산해줘" (Calculate 123 × 456)
CORRECT RESPONSE:
[
  {{
    "tool_name": "multiply",
    "input": {{ "numbers": [123, 456] }},
    "description": "Multiply 123 by 456",
    "dependencies": []
  }}
]

Example 2 - User asks: "What is 50 + 75?"
CORRECT RESPONSE:
[
  {{
    "tool_name": "add",
    "input": {{ "numbers": [50, 75] }},
    "description": "Add 50 and 75",
    "dependencies": []
  }}
]

Example 3 - User asks: "Send email to John"
CORRECT RESPONSE:
[
  {{
    "tool_name": "lookup_contact",
    "input": {{ "query": "John" }},
    "description": "Find John's email address",
    "dependencies": []
  }},
  {{
    "tool_name": "send_email",
    "input": {{
      "to": "{{{{step_0.contact.email}}}}",
      "subject": "Hello",
      "body": "Email content"
    }},
    "description": "Send email to John",
    "dependencies": [0]
  }}
]

Example 4 - User asks: "너는 무슨 LLM이니?" (What LLM are you?)
CORRECT RESPONSE:
{{
  "type": "direct_response",
  "message": "저는 Claude 3.5 Sonnet 모델입니다. Anthropic이 개발한 대화형 AI 어시스턴트입니다."
}}

Example 5 - CRITICAL! User asks: "첫번째 틀어줘" (play the first one)
When PREVIOUS EXECUTION RESULTS shows: videos: [{{id: "abc123", title: "Song A"}}]
CORRECT RESPONSE - USE TOOL:
[
  {{
    "tool_name": "play_audio",
    "input": {{ "url": "https://youtube.com/watch?v=abc123" }},
    "description": "Play the first song from previous search results",
    "dependencies": []
  }}
]
❌ WRONG for Example 5:
{{
  "type": "direct_response",
  "message": "어떤 노래를 틀어드릴까요?"
}}

❌ WRONG - DO NOT DO THIS:
- Returning empty array: []  ← WRONG!
- Using inappropriate tools to force tool usage  ← WRONG!
- Responding with text instead of JSON  ← WRONG!

✅ RIGHT - DO THIS:
- Return JSON array when tools are needed  ← CORRECT!
- Return direct_response object when no tools are needed  ← CORRECT!
- Use the exact tool names from the list above  ← CORRECT!

⚠️ IMPORTANT - CHECK TOOL OUTPUT SCHEMAS:
Each tool definition includes "output_schema" showing available fields.
When referencing outputs in placeholders:
1. Check the tool's "output_schema" -> "key_fields"
2. Use ACTUAL field names (e.g., if key_fields shows "articles", use "articles" NOT "news")

Example:
- search_latest_news has key_fields: ["articles", "count"]
- Use {{{{step_0.articles}}}} NOT {{{{step_0.news}}}}

🔴🔴🔴 CRITICAL: FOLLOW-UP REQUESTS - MUST USE TOOLS! 🔴🔴🔴
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If user references previous results in ANY way:
  • Korean: "첫번째", "두번째", "그것", "틀어줘", "재생해"
  • English: "first", "second", "that one", "play it"

You MUST:
1. Check PREVIOUS EXECUTION RESULTS in Context section
2. Extract ACTUAL values (IDs, URLs, etc.)
3. Create execution plan with tool - NEVER direct_response!

🚨 FORBIDDEN:
❌ direct_response asking "어떤 노래?" (Which song?)
❌ direct_response asking for clarification
❌ Any response without tool when previous results exist

✅ CORRECT for "첫번째 틀어줘":
- Previous: videos: [{{id: "abc123", title: "Song A"}}]
- Create execution plan:
[
  {{
    "tool_name": "play_audio",
    "input": {{"url": "https://youtube.com/watch?v=abc123"}},
    "description": "Play the first song",
    "dependencies": []
  }}
]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOUR TASK:
1. Read the user's request: "{state.request_text}"
2. Decide: Does this require tools or can you respond directly?
3. If tools needed: Create a JSON array of steps
4. If no tools needed: Create a direct_response object
5. When referencing outputs, check output_schema for correct field names
6. Return ONLY the JSON (array or object)

NOW: Create your response.
Remember: Start with [ for tool execution plans, or {{ for direct responses!
"""

    def _get_decision_prompt(self, state: State, results: AggregatedGroupResults) -> str:
        """
        Get decision prompt based on provider

        Args:
            state: Current state
            results: Execution results

        Returns:
            Prompt string appropriate for the LLM provider
        """
        provider = self.settings.llm_provider.lower()

        # Use enhanced prompt for OpenRouter and other providers
        if provider == "openrouter":
            return self._get_openrouter_decision_prompt(state, results)
        else:
            return self._get_standard_decision_prompt(state, results)

    def _get_standard_decision_prompt(self, state: State, results: AggregatedGroupResults) -> str:
        """Standard decision prompt for Anthropic and other providers"""
        results_summary = self._format_results(results, state.plan)
        context_str = self._format_context(state.context)
        tools_list_detailed = self._format_tools_detailed()

        # Get current date and time
        current_datetime = datetime.now()
        today_str = current_datetime.strftime("%Y-%m-%d (%A)")
        current_time_str = current_datetime.strftime("%H:%M:%S")

        return f"""You are an AI assistant making STEP-BY-STEP decisions about task execution.

🚨 CRITICAL RULE - USE TOOLS FOR ADDITIONAL WORK:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
If the user's request is NOT fully satisfied by the executed steps, you MUST create nextSteps with tools.
DO NOT return "final" with a direct answer unless tools have already retrieved/computed the information.

❌ FORBIDDEN: Returning "final" with information you computed or inferred yourself
✅ REQUIRED: If more work is needed, return "nextSteps" with tool executions

Examples:
• Executed: calculator add(100, 200) → Result: 300
  User asked: "What's 100 + 200?"
  ✅ CORRECT: Return "final" with the result 300 (tool was executed)

• Executed: list_events → No relevant events found
  User asked: "Update the Project Meeting event"
  ❌ BAD: Return "final" saying "No event found"
  ✅ GOOD: Return "final" stating the event doesn't exist (tool confirmed this)

• Executed: lookup_contact("John") → Found: john@example.com
  User asked: "Send email to John about the meeting"
  ❌ BAD: Return "final" without sending email
  ✅ GOOD: Return "nextSteps" with send_email tool
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT CONTEXT:
- Today's date: {today_str}
- Current time: {current_time_str}
- When interpreting time references (e.g., "this week", "next week", "tomorrow", "last week"), use today's date as the reference point.

IMPORTANT: All planned steps have been executed. Now you need to decide if the task is complete or if additional steps are needed.

Original request: {state.request_text}

Context:
{context_str}

Available tools (you MUST use these exact tool names):
{tools_list_detailed}

CRITICAL: You MUST use ONLY the exact tool names listed above. DO NOT create variations or guess tool names.

Execution results (all steps have been executed):
{results_summary}

ANALYZING STEP RESULTS:
- Look at the actual data returned by each completed step
- If a step returned a list of items (e.g., calendar events), you can:
  * Check if the desired item exists in the list
  * Create a new step to process specific items based on their properties
  * Use the actual IDs, titles, or other fields from the results
- You do NOT need to rely only on placeholder syntax like {{{{step_0.events.0.id}}}}
- Instead, you can examine the step output and create intelligent next steps

CRITICAL - HANDLING EMPTY OR NULL RESULTS:
- ALWAYS check if previous step results are empty, null, or contain no data
- If a step returned an empty list [], null, or no items:
  * DO NOT create follow-up steps that depend on that data
  * DO NOT use empty values as input to subsequent steps (e.g., don't pass "" to search queries)
  * Instead, either:
    a) Skip the dependent steps and mark task as complete with appropriate message
    b) Return "needsHuman" if user input is needed to proceed
    c) Adjust the plan to handle the empty case gracefully
- Examples:
  * If list_events returns no events, DON'T create a search_issues step with empty meeting summary
  * If search_issues returns no issues, DON'T try to process non-existent issue data
  * If a required item is not found, DON'T proceed with placeholder or empty values

DECISION OPTIONS:
1. "final" - Task is complete, return final response to user
2. "nextSteps" - More steps needed based on the results you analyzed
   - Create new steps dynamically using the actual data from previous steps
   - You can reference specific values you found in the step outputs
   - Each new step should have: tool_name, input, description, dependencies
3. "needsHuman" - Requires human intervention (missing info, ambiguous results, etc.)
4. "failed" - Task failed and cannot continue

{self._get_placeholder_instructions(prompt_type="decision")}

🚨 CRITICAL JSON FORMAT REQUIREMENTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. You MUST return a valid JSON OBJECT (not an array, not a string, not empty)
2. The JSON MUST have "type", "reason", and "payload" fields
3. NEVER return: [], {{}}, "", null, or any other format
4. If unsure, default to "final" type with appropriate message
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 CRITICAL - ALWAYS INCLUDE ACTUAL DATA IN FINAL RESPONSES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When returning "final" type, you MUST include the ACTUAL step output data in payload.data!

❌ WRONG - Generic success message without data:
{{{{
  "type": "final",
  "payload": {{{{
    "message": "Task completed successfully"  ← No actual data!
  }}}}
}}}}

✅ CORRECT - Include actual results in data field:
{{{{
  "type": "final",
  "payload": {{{{
    "message": "Found 1 critical issue",
    "data": {{{{
      "issues": [...actual issue objects from step output...]
    }}}}
  }}}}
}}}}

RULE: The user needs to SEE the actual results (issues, events, calculation results, etc.)
Copy the relevant data from the step outputs into payload.data!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CORRECT RESPONSE EXAMPLES:

Example 1 - Task completed (multiplication was performed):
{{{{
  "type": "final",
  "reason": "User asked for multiplication of 123 and 456. The multiply tool successfully computed the result as 56088.",
  "payload": {{{{
    "message": "계산이 완료되었습니다. 123 × 456 = 56088",
    "data": 56088
  }}}}
}}}}

Example 2 - Task completed (Jira issues found):
{{{{
  "type": "final",
  "reason": "User asked for critical Jira issues. The search_issues tool found 1 critical issue.",
  "payload": {{{{
    "message": "Critical 이슈 1건을 찾았습니다.",
    "data": {{{{
      "count": 1,
      "issues": [
        {{{{
          "key": "PROJ-6",
          "summary": "Fix memory leak in background worker",
          "priority": "Critical",
          "status": "Open"
        }}}}
      ]
    }}}}
  }}}}
}}}}

Example 3 - Task completed (calendar events listed):
{{{{
  "type": "final",
  "reason": "User asked for this week's events. The list_events tool returned 3 events.",
  "payload": {{{{
    "message": "이번 주 일정 3건을 찾았습니다.",
    "data": {{{{
      "events": [
        {{{{"id": "evt_1", "title": "Team Meeting", "start": "2025-11-22T10:00:00"}}}},
        {{{{"id": "evt_2", "title": "Project Review", "start": "2025-11-23T14:00:00"}}}},
        {{{{"id": "evt_3", "title": "Client Call", "start": "2025-11-24T15:00:00"}}}}
      ]
    }}}}
  }}}}
}}}}

Example 4 - Need additional steps (email needs to be sent):
{{{{
  "type": "nextSteps",
  "reason": "Contact was found, but email hasn't been sent yet",
  "payload": {{{{
    "steps": [
      {{{{
        "tool_name": "send_email",
        "input": {{{{
          "to": "john@example.com",
          "subject": "Meeting",
          "body": "Meeting details..."
        }}}},
        "description": "Send email to John",
        "dependencies": []
      }}}}
    ]
  }}}}
}}}}

Example 3 - Need human input:
{{{{
  "type": "needsHuman",
  "reason": "Multiple contacts found with name 'John', need user to specify which one",
  "payload": {{{{
    "question": "I found 3 contacts named John. Which one did you mean: John Smith, John Doe, or John Park?"
  }}}}
}}}}

Example 4 - Task failed:
{{{{
  "type": "failed",
  "reason": "API returned authentication error and cannot proceed",
  "payload": {{{{
    "error": "Authentication failed. Please check your credentials."
  }}}}
}}}}

❌ INVALID RESPONSES (DO NOT DO THIS):
- []
- {{{{}}}}
- ""
- {{{{"steps": []}}}}
- null
- Any response without "type", "reason", and "payload" fields

NOW, analyze the execution results above and return your decision as a valid JSON object:
"""

    def _get_openrouter_decision_prompt(self, state: State, results: AggregatedGroupResults) -> str:
        """Enhanced decision prompt for OpenRouter (OSS 20b models)"""
        results_summary = self._format_results(results, state.plan)
        context_str = self._format_context(state.context)
        tools_list_detailed = self._format_tools_detailed()

        # Get current date and time
        current_datetime = datetime.now()
        today_str = current_datetime.strftime("%Y-%m-%d (%A)")
        current_time_str = current_datetime.strftime("%H:%M:%S")

        return f"""You are an AI assistant. Your task is to analyze the execution results and return a JSON decision.

⚠️ ABSOLUTELY CRITICAL - READ THIS FIRST:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR RESPONSE MUST BE A JSON OBJECT WITH EXACTLY THIS STRUCTURE:
{{
  "type": "final" OR "nextSteps" OR "needsHuman" OR "failed",
  "reason": "explanation here",
  "payload": {{ ... }}
}}

DO NOT wrap your response in ANY other fields like "final_output", "response", "decision", etc.
DO NOT return an empty object {{}}, empty array [], or null.
ONLY return the JSON structure shown above. Nothing else.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONTEXT INFORMATION:
- Today's date: {today_str}
- Current time: {current_time_str}
- Original user request: {state.request_text}

EXECUTION RESULTS:
{results_summary}

YOUR TASK:
1. Read the user's original request: "{state.request_text}"
2. Check what steps were executed and their results
3. Decide if the task is complete or needs more steps

DECISION RULES:
• If all work is done → return type="final"
• If more steps needed → return type="nextSteps"
• If need user input → return type="needsHuman"
• If task failed → return type="failed"

⚠️ MANDATORY JSON FORMAT - COPY THIS EXACTLY:

If task is complete:
{{
  "type": "final",
  "reason": "explain what was done",
  "payload": {{
    "message": "user-friendly message here",
    "data": result_data_here
  }}
}}

If need more steps:
{{
  "type": "nextSteps",
  "reason": "explain why more steps needed",
  "payload": {{
    "steps": [
      {{
        "tool_name": "exact_tool_name",
        "input": {{ "param": "value" }},
        "description": "what this step does",
        "dependencies": []
      }}
    ]
  }}
}}

⚠️ CRITICAL - INCLUDE ACTUAL DATA:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When type="final", you MUST copy the actual step output data into payload.data!
Users need to SEE the actual results (issues, events, numbers, etc.)

❌ WRONG:
{{ "type": "final", "payload": {{ "message": "Success" }} }}  ← No data!

✅ CORRECT:
{{ "type": "final", "payload": {{ "message": "Found issues", "data": {{...actual results...}} }} }}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ EXAMPLES OF CORRECT RESPONSES:

Example 1 - Multiplication task completed:
{{
  "type": "final",
  "reason": "The multiply tool successfully computed 123 × 456 = 56088",
  "payload": {{
    "message": "계산 완료: 123 × 456 = 56088",
    "data": 56088
  }}
}}

Example 2 - Jira issues found:
{{
  "type": "final",
  "reason": "Found 1 critical Jira issue",
  "payload": {{
    "message": "Critical 이슈 1건 발견",
    "data": {{
      "count": 1,
      "issues": [
        {{ "key": "PROJ-6", "summary": "Fix memory leak", "priority": "Critical" }}
      ]
    }}
  }}
}}

Example 3 - Events listed:
{{
  "type": "final",
  "reason": "Found 3 events this week",
  "payload": {{
    "message": "이번 주 일정 3건",
    "data": {{
      "events": [
        {{ "id": "evt_1", "title": "Meeting" }},
        {{ "id": "evt_2", "title": "Review" }}
      ]
    }}
  }}
}}

Example 4 - Need to do more work:
{{
  "type": "nextSteps",
  "reason": "User asked to multiply numbers but no tool was executed yet",
  "payload": {{
    "steps": [
      {{
        "tool_name": "multiply",
        "input": {{ "numbers": [123, 456] }},
        "description": "Multiply 123 and 456",
        "dependencies": []
      }}
    ]
  }}
}}

❌ WRONG - DO NOT DO THIS:
- {{ "final_output": {{ "type": "final", ... }} }}  ← WRONG! Extra wrapper
- []  ← WRONG! Empty array
- {{}}  ← WRONG! Empty object
- {{ "steps": [] }}  ← WRONG! Missing type and reason

✅ RIGHT - DO THIS:
- {{ "type": "final", "reason": "...", "payload": {{...}} }}  ← CORRECT!

NOW: Analyze the execution results above and return your JSON decision.
Remember: Your response must start with {{ "type": not with anything else!
"""

    def _format_results(self, results: AggregatedGroupResults, plan: Optional[Plan]) -> str:
        """Format results for prompt"""
        lines = [
            f"Total steps: {results.total_steps}",
            f"Completed: {len(results.completed_steps)}",
            f"Failed: {len(results.failed_steps)}",
            f"Success rate: {results.success_rate:.1%}",
            "",
            "Completed steps:"
        ]

        for step_result in results.completed_steps:
            lines.append(f"  - {step_result.step_id}: {step_result.output}")

        if results.failed_steps:
            lines.append("")
            lines.append("Failed steps:")
            for step_result in results.failed_steps:
                lines.append(f"  - {step_result.step_id}: {step_result.error}")

        # Add pending steps (not yet executed)
        if plan:
            completed_step_ids = {step.step_id for step in results.completed_steps}
            failed_step_ids = {step.step_id for step in results.failed_steps}
            pending_steps = [
                step for step in plan.steps
                if step.step_id not in completed_step_ids and step.step_id not in failed_step_ids
            ]

            if pending_steps:
                lines.append("")
                lines.append("Pending steps (already planned, not yet executed):")
                for step in pending_steps:
                    lines.append(f"  - {step.step_id}: {step.description} (tool: {step.tool_name})")

        return "\n".join(lines)
