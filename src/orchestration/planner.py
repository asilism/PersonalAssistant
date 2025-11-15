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

        # Determine LLM provider
        llm_provider = os.getenv("LLM_PROVIDER", "anthropic")

        # Create LLM client
        self.llm_client: LLMClient = create_llm_client(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            provider=llm_provider,
            base_url=settings.llm_base_url
        )

        print(f"[Planner] Using {llm_provider} with model {settings.llm_model}")

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

        # Build prompt for LLM
        tools_description = self._format_tools_for_prompt()
        tools_list_detailed = self._format_tools_detailed()
        context_str = self._format_context(state.context)

        # Get recent execution results from previous plans (loaded by Orchestrator in state.context)
        recent_results_str = await self._format_recent_execution_results(state.context)

        # Get current date and time
        current_datetime = datetime.now()
        today_str = current_datetime.strftime("%Y-%m-%d (%A)")
        current_time_str = current_datetime.strftime("%H:%M:%S")

        prompt = f"""You are an AI assistant that creates execution plans.

IMPORTANT CONTEXT:
- Today's date: {today_str}
- Current time: {current_time_str}
- When interpreting time references (e.g., "this week", "next week", "tomorrow", "last week"), use today's date as the reference point.

Available tools (you MUST use these exact tool names):
{tools_list_detailed}

User request: {state.request_text}

Context:
{context_str}

{recent_results_str if recent_results_str else ""}

CRITICAL: You MUST use ONLY the exact tool names listed above. DO NOT create variations or guess tool names (e.g., if the tool is "update_event", do NOT use "update_calendar_event").

IMPORTANT: If the user is asking about what tools you have, what you can do, or requesting a list of available capabilities, you should provide the list of available tools instead of creating an execution plan.

For tool listing requests, return a JSON response in this format:
{{
  "type": "tool_list_request",
  "tools": [
{tools_list_detailed}
  ]
}}

Otherwise, create a step-by-step execution plan to fulfill the user's request.
For each step, specify:
1. tool_name: which tool to use
2. input: parameters for the tool
3. description: what this step does
4. dependencies: which previous step IDs this depends on (empty list if none)

PLACEHOLDER SYNTAX FOR REFERENCING PREVIOUS STEPS:
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
  NOTE: Array indices use dot notation (events.0.id) NOT bracket notation (events[0].id)

IMPORTANT: FILTERING AND SEARCHING IN ARRAYS
- When the user asks for a specific item (e.g., "update Project Review event"), DO NOT blindly use index 0
- Instead, describe what you're looking for using a descriptive placeholder
- The system will resolve it intelligently based on the actual data
- Examples:
  * BAD:  {{"event_id": {{{{step_0.events.0.id}}}}}}  // Always picks first event
  * GOOD: {{"event_id": "{{{{event_id_where_title_is_Project_Review}}}}"}}  // Describes what to find
  * GOOD: Use a descriptive placeholder that indicates filtering criteria
- If you need to find a specific item, create a placeholder that describes the search condition

- Dependencies are specified as integers (0 for first step, 1 for second step, etc.)
  Example: "dependencies": [0] means this step depends on step_0 (the first step)
  Example: "dependencies": [0, 1] means this step depends on step_0 and step_1

CRITICAL RULES FOR EMAIL ADDRESSES AND CONTACT INFORMATION:
- NEVER fabricate or guess email addresses (e.g., DO NOT create "name@example.com" or "username@domain.com")
- NEVER use placeholder domains like @example.com, @test.com, @sample.com
- If the user provides only a name (e.g., "send email to John") without an email address:
  * DO NOT guess the email address
  * Instead, use a placeholder like "{{"contact_email"}}" in the input
  * The system will ask the user for the correct email address
- Only use actual email addresses that:
  * Were explicitly provided by the user in their request
  * Are available in the provided context
  * Are retrieved from a contact lookup tool (if available)
- If you don't have a valid email address, use a template variable placeholder like "{{"recipient_email"}}" instead

CRITICAL RULES FOR REUSING PREVIOUS EXECUTION RESULTS:
- ALWAYS check the "Recent execution results" section above for data from previous requests
- If the current user request requires data that was ALREADY retrieved in a recent execution:
  * DO NOT create a new step to fetch the same data again
  * Instead, assume the data is available from the recent execution
  * Directly use the data in your plan (you can reference it in step descriptions)
- Examples:
  * Previous request: "Search for Jira issues with status Done"
  * Current request: "Send those issues by email"
  * GOOD: Skip the search step, directly create email step with the issue data
  * BAD: Search for issues again, then send email
- Only re-fetch data if:
  * The user explicitly asks for updated/fresh data
  * The previous data is clearly outdated or irrelevant
  * The search criteria have changed
- When reusing data, mention in the step description that you're using data from the previous request

Return your plan as a JSON array of steps. Each step should have this format:
{{
  "tool_name": "tool_name",
  "input": {{"param": "value"}},
  "description": "description of this step",
  "dependencies": []
}}

Return ONLY the JSON (either tool list or execution plan), no other text.
"""

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
            response_data = json.loads(content)

            # Check if this is a tool list request
            if isinstance(response_data, dict) and response_data.get("type") == "tool_list_request":
                print(f"[Planner] Detected tool list request")
                tools_info = response_data.get("tools", [])

                # Format tools information for user
                tools_message = "Here are the tools I have access to:\n\n"
                for i, tool in enumerate(self.settings.available_tools, 1):
                    tools_message += f"{i}. **{tool.name}**: {tool.description}\n"
                    if tool.input_schema and tool.input_schema.get('properties'):
                        tools_message += "   Parameters:\n"
                        properties = tool.input_schema['properties']
                        required = tool.input_schema.get('required', [])
                        for prop_name, prop_details in properties.items():
                            req_marker = " (required)" if prop_name in required else " (optional)"
                            prop_desc = prop_details.get('description', prop_details.get('type', ''))
                            tools_message += f"   - {prop_name}{req_marker}: {prop_desc}\n"
                    tools_message += "\n"

                # Return as final response
                state.type = StateType.FINAL
                state.final_payload = {
                    "message": tools_message,
                    "data": {
                        "tool_count": len(self.settings.available_tools),
                        "tools": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "input_schema": tool.input_schema
                            }
                            for tool in self.settings.available_tools
                        ]
                    }
                }
                return state

            # Otherwise, treat as execution plan
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

        # Build prompt for decision
        results_summary = self._format_results(results, state.plan)
        context_str = self._format_context(state.context)
        tools_list_detailed = self._format_tools_detailed()

        # Get current date and time
        current_datetime = datetime.now()
        today_str = current_datetime.strftime("%Y-%m-%d (%A)")
        current_time_str = current_datetime.strftime("%H:%M:%S")

        prompt = f"""You are an AI assistant making STEP-BY-STEP decisions about task execution.

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

DECISION OPTIONS:
1. "final" - Task is complete, return final response to user
2. "nextSteps" - More steps needed based on the results you analyzed
   - Create new steps dynamically using the actual data from previous steps
   - You can reference specific values you found in the step outputs
   - Each new step should have: tool_name, input, description, dependencies
3. "needsHuman" - Requires human intervention (missing info, ambiguous results, etc.)
4. "failed" - Task failed and cannot continue

PLACEHOLDER SYNTAX FOR NEXT STEPS (when needed):
- To reference previous step output: {{{{step_N}}}} or {{{{step_N.field_name}}}}
- To access array elements: {{{{step_N.array.0.id}}}} (use dot notation)
- NOTE: Steps are 0-indexed (step_0 is first step, step_1 is second, etc.)
- But prefer using actual values from the results when possible!

Return your decision as JSON:
{{
  "type": "final|nextSteps|needsHuman|failed",
  "reason": "explanation of your analysis and decision",
  "payload": {{
    // For "final": {{"message": "success message to user", "data": <optional result data>}}
    // For "nextSteps": {{"steps": [
    //   {{
    //     "tool_name": "tool_name",
    //     "input": {{"param": "value or {{{{placeholder}}}}"}},
    //     "description": "what this step does",
    //     "dependencies": [0, 1]  // indices of steps this depends on
    //   }}
    // ]}}
    // For "needsHuman": {{"question": "what to ask the user"}}
    // For "failed": {{"error": "error description"}}
  }}
}}

Return ONLY the JSON, no other text.
"""

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
            decision_data = json.loads(content)
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
        # Build prompt for LLM
        prompt = f"""You are helping resolve placeholders in a task execution step.

MOST RECENT STEP EXECUTED:
- Step ID: {latest_result.step_id}
- Tool: {latest_result.tool_name if hasattr(latest_result, 'tool_name') else 'unknown'}
- Output: {json.dumps(latest_result.output, indent=2)}

ALL COMPLETED STEPS (for reference):
{self._format_all_step_results(all_results)}

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

CRITICAL INSTRUCTIONS FOR ARRAY PLACEHOLDERS:
- When you see {{{{step_X.array.0.field}}}}, DO NOT always pick index 0
- Instead, analyze the step description and previous context to find the RIGHT item
- Example: If step description is "Update Project Review event" and step_0 returned:
  * events: [{{"id": "event_1", "title": "Team Meeting"}}, {{"id": "event_2", "title": "Project Review"}}]
  * The placeholder {{{{step_0.events.0.id}}}} should resolve to "event_2" (not "event_1")
  * Because the description mentions "Project Review"

IMPORTANT:
- If a placeholder describes a filter or search (e.g., "event where title='X'"), find the matching item
- Use the step description as a guide for which item to select from arrays
- Extract the exact field value requested (e.g., if placeholder asks for "id", return just the id)
- Preserve all non-placeholder values as-is
- If you cannot resolve a placeholder, keep it as-is and explain in reasoning

Return ONLY valid JSON in this format:
{{
  "resolved_input": {{
    // The complete input dict with all placeholders resolved
    // Example: {{"event_id": "event_2", "updates": {{"end": "2024-03-20T16:00:00"}}}}
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

            data = json.loads(content)

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
        """Format available tools in detailed JSON format for prompt"""
        lines = []
        for tool in self.settings.available_tools:
            tool_dict = {
                "name": tool.name,
                "description": tool.description
            }
            if tool.input_schema:
                tool_dict["input_schema"] = tool.input_schema
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
            # Handle recent_results separately for better formatting
            recent_results = context.additional_context.get("recent_results")
            other_context = {k: v for k, v in context.additional_context.items()
                           if k not in ["recent_results", "recent_plan_id", "recent_request"]}

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
