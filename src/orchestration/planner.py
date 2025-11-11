"""
Planner - Plans task execution using LLM
"""

import json
import uuid
import os
from typing import Optional
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


class Planner:
    """Planner - Uses LLM to create execution plans"""

    def __init__(self, settings: OrchestrationSettings):
        self.settings = settings

        # Determine LLM provider
        llm_provider = os.getenv("LLM_PROVIDER", "anthropic")

        # Create LLM client
        self.llm_client: LLMClient = create_llm_client(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            provider=llm_provider
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
        context_str = self._format_context(state.context)

        prompt = f"""You are an AI assistant that creates execution plans.

Available tools:
{tools_description}

User request: {state.request_text}

Context:
{context_str}

Create a step-by-step execution plan to fulfill the user's request.
For each step, specify:
1. tool_name: which tool to use
2. input: parameters for the tool
3. description: what this step does
4. dependencies: which previous step IDs this depends on (empty list if none)

Return your plan as a JSON array of steps. Each step should have this format:
{{
  "tool_name": "tool_name",
  "input": {{"param": "value"}},
  "description": "description of this step",
  "dependencies": []
}}

Return ONLY the JSON array, no other text.
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
            steps_data = json.loads(content)
            print(f"[Planner] Successfully parsed {len(steps_data)} steps")

            # Create plan
            plan_id = str(uuid.uuid4())
            steps = []
            dependencies = {}

            for i, step_data in enumerate(steps_data):
                step_id = f"step_{i+1}"
                print(f"[Planner] Processing step {i+1}/{len(steps_data)}: {step_data.get('description', 'N/A')}")

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

        results = state.results
        if not results:
            # No results yet, shouldn't happen
            print(f"[Planner] ERROR: No results available for decision")
            state.type = StateType.ERROR
            state.error = "No results available for decision"
            return state

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
                state.type = StateType.FINAL
                state.final_payload = decision_data["payload"]
                return state

            elif decision_type == "nextSteps":
                # Add more steps to plan
                print(f"[Planner] Decision: Next steps required")
                next_steps_data = decision_data["payload"].get("steps", [])
                print(f"[Planner] Processing {len(next_steps_data)} next steps...")

                # Validate and normalize next steps
                for i, step_data in enumerate(next_steps_data):
                    print(f"[Planner]   Validating next step {i+1}: {step_data.get('description', 'N/A')}")
                    raw_deps = step_data.get("dependencies", [])
                    normalized_deps = self._normalize_dependencies(raw_deps)
                    step_data["dependencies"] = normalized_deps
                    print(f"[Planner]   Dependencies normalized: {raw_deps} -> {normalized_deps}")

                # For simplicity, we'll transition to DISPATCH
                # In production, you'd add steps to the existing plan
                state.type = StateType.DISPATCH
                return state

            elif decision_type == "needsHuman":
                # Needs human input
                print(f"[Planner] Decision: Human intervention required")
                state.type = StateType.HUMAN_IN_THE_LOOP
                state.final_payload = decision_data["payload"]
                return state

            elif decision_type == "failed":
                # Failed
                print(f"[Planner] Decision: Task failed")
                error_msg = decision_data["payload"].get("error", "Task failed")
                print(f"[Planner] Error: {error_msg}")
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
                    # Convert integer to step_id format
                    normalized.append(f"step_{dep}")
                    print(f"[Planner]   Warning: Converted integer dependency {dep} to 'step_{dep}'")
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
