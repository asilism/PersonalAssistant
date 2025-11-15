"""
Planner - Plans task execution using LLM
"""

import json
import uuid
import os
from typing import Optional, Any
from anthropic import Anthropic

from .types import (
    State,
    StateType,
    Plan,
    Step,
    Decision,
    OrchestrationSettings,
    ContextBundle,
    AggregatedGroupResults,
    PlanState
)
from .llm_client import create_llm_client, LLMClient
from .validators import extract_missing_params
from .event_emitter import get_event_emitter


class Planner:
    """Planner - Uses LLM to create execution plans"""

    def __init__(self, settings: OrchestrationSettings):
        self.settings = settings
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

        prompt = f"""You are an AI assistant that creates execution plans.

Available tools:
{tools_description}

User request: {state.request_text}

Context:
{context_str}

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

        # Check if any steps have exceeded max retries
        max_retries = self.settings.max_retries  # Default is 3 from types.py
        steps_exceeded_retries = []

        for failed_step in results.failed_steps:
            step_id = failed_step.step_id
            retry_count = state.retry_counts.get(step_id, 0)

            print(f"[Planner] Step {step_id} failure count: {retry_count + 1}/{max_retries}")

            if retry_count >= max_retries:
                steps_exceeded_retries.append(step_id)
                print(f"[Planner] Step {step_id} has exceeded max retries ({max_retries})")

        # If any steps exceeded retries, fail the task
        if steps_exceeded_retries:
            error_msg = f"Task failed: The following steps exceeded maximum retry limit ({max_retries}): {', '.join(steps_exceeded_retries)}"
            print(f"[Planner] {error_msg}")
            state.type = StateType.ERROR
            state.error = error_msg
            return state

        # Increment retry counts for failed steps
        for failed_step in results.failed_steps:
            step_id = failed_step.step_id
            state.retry_counts[step_id] = state.retry_counts.get(step_id, 0) + 1
            print(f"[Planner] Incremented retry count for {step_id}: {state.retry_counts[step_id]}")

        # Build prompt for decision
        results_summary = self._format_results(results)

        prompt = f"""You are an AI assistant making decisions about task execution.

Original request: {state.request_text}

Execution results so far:
{results_summary}

Decide what to do next:
1. "final" - task is complete, return final response
2. "nextSteps" - more steps needed, provide them
3. "needsHuman" - requires human intervention
4. "failed" - task failed and cannot continue

Return your decision as JSON:
{{
  "type": "final|nextSteps|needsHuman|failed",
  "reason": "explanation",
  "payload": {{
    // For "final": {{"message": "success message", "data": ...}}
    // For "nextSteps": {{"steps": [...]}} (same format as initial planning)
    // For "needsHuman": {{"question": "what to ask user"}}
    // For "failed": {{"error": "error message"}}
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
                        # New step - generate new ID
                        step_id = f"step_{len(state.plan.steps) + i + 1}"
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
                    # Convert integer to step_id format (1-indexed)
                    # LLM returns 0-based index, but step_ids start from 1
                    step_id = f"step_{dep + 1}"
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
            lines.append("Additional context:")
            for key, value in context.additional_context.items():
                lines.append(f"  - {key}: {value}")

        return "\n".join(lines) if lines else "No additional context"

    def _format_results(self, results: AggregatedGroupResults) -> str:
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

        return "\n".join(lines)
