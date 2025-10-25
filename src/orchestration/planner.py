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

        print(f"\n{'='*80}")
        print(f"[Planner] Creating initial plan")
        print(f"[Planner] User request: {state.request_text}")
        print(f"[Planner] Available tools: {len(self.settings.available_tools)}")
        print(f"\n[Planner] Prompt sent to LLM:")
        print(f"{'-'*80}")
        print(prompt)
        print(f"{'-'*80}\n")

        try:
            # Call LLM
            content = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096
            )
            content = content.strip()

            print(f"[Planner] Raw LLM response:")
            print(f"{'-'*80}")
            print(content)
            print(f"{'-'*80}\n")

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            print(f"[Planner] Cleaned response (after removing markdown):")
            print(f"{'-'*80}")
            print(content)
            print(f"{'-'*80}\n")

            steps_data = json.loads(content)
            print(f"[Planner] Parsed {len(steps_data)} steps from LLM response")

            # Create plan
            plan_id = str(uuid.uuid4())
            steps = []
            dependencies = {}

            for i, step_data in enumerate(steps_data):
                step_id = f"step_{i+1}"

                # Convert dependencies to strings if they are integers
                raw_dependencies = step_data.get("dependencies", [])
                str_dependencies = []
                for dep in raw_dependencies:
                    if isinstance(dep, int):
                        # Convert integer index to step_id
                        str_dependencies.append(f"step_{dep+1}")
                    elif isinstance(dep, str):
                        str_dependencies.append(dep)
                    else:
                        print(f"[Planner] WARNING: Unknown dependency type {type(dep)}: {dep}")

                print(f"[Planner] Step {i+1}:")
                print(f"  - Tool: {step_data['tool_name']}")
                print(f"  - Description: {step_data['description']}")
                print(f"  - Input: {step_data['input']}")
                print(f"  - Dependencies (raw): {raw_dependencies}")
                print(f"  - Dependencies (converted): {str_dependencies}")

                step = Step(
                    step_id=step_id,
                    tool_name=step_data["tool_name"],
                    input=step_data["input"],
                    description=step_data["description"],
                    dependencies=str_dependencies
                )
                steps.append(step)
                dependencies[step_id] = step.dependencies

            plan = Plan(
                plan_id=plan_id,
                steps=steps,
                dependencies=dependencies
            )

            print(f"\n[Planner] ✓ Plan created successfully:")
            print(f"  - Plan ID: {plan_id}")
            print(f"  - Total steps: {len(steps)}")
            print(f"{'='*80}\n")

            # Update state
            state.plan = plan
            state.plan_state = PlanState.PENDING
            state.type = StateType.DISPATCH

            return state

        except json.JSONDecodeError as e:
            # JSON parsing failed
            error_msg = f"Failed to parse LLM response as JSON: {str(e)}"
            print(f"\n[Planner] ✗ ERROR: {error_msg}")
            print(f"[Planner] Response that failed to parse:")
            print(f"{'-'*80}")
            print(content if 'content' in locals() else 'No content available')
            print(f"{'-'*80}\n")
            state.type = StateType.ERROR
            state.error = f"Planning failed: {error_msg}"
            return state
        except Exception as e:
            # Planning failed
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"\n[Planner] ✗ ERROR: {error_msg}")
            import traceback
            print(f"[Planner] Traceback:")
            print(traceback.format_exc())
            print(f"{'='*80}\n")
            state.type = StateType.ERROR
            state.error = f"Planning failed: {error_msg}"
            return state

    async def _decide_next(self, state: State) -> State:
        """Decide next action based on current results"""

        results = state.results
        if not results:
            # No results yet, shouldn't happen
            print(f"\n[Planner] ✗ ERROR: No results available for decision")
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

        print(f"\n{'='*80}")
        print(f"[Planner] Deciding next action")
        print(f"[Planner] Original request: {state.request_text}")
        print(f"[Planner] Execution results:")
        print(f"  - Total steps: {results.total_steps}")
        print(f"  - Completed: {len(results.completed_steps)}")
        print(f"  - Failed: {len(results.failed_steps)}")
        print(f"  - Success rate: {results.success_rate:.1%}")
        print(f"\n[Planner] Prompt sent to LLM:")
        print(f"{'-'*80}")
        print(prompt)
        print(f"{'-'*80}\n")

        try:
            content = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096
            )
            content = content.strip()

            print(f"[Planner] Raw LLM response:")
            print(f"{'-'*80}")
            print(content)
            print(f"{'-'*80}\n")

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            print(f"[Planner] Cleaned response (after removing markdown):")
            print(f"{'-'*80}")
            print(content)
            print(f"{'-'*80}\n")

            decision_data = json.loads(content)
            decision_type = decision_data["type"]
            decision_reason = decision_data.get("reason", "No reason provided")

            print(f"[Planner] Decision made:")
            print(f"  - Type: {decision_type}")
            print(f"  - Reason: {decision_reason}")

            if decision_type == "final":
                # Task complete
                print(f"[Planner] ✓ Task complete - transitioning to FINAL state")
                print(f"{'='*80}\n")
                state.type = StateType.FINAL
                state.final_payload = decision_data["payload"]
                return state

            elif decision_type == "nextSteps":
                # Add more steps to plan
                # For simplicity, we'll transition to HUMAN_IN_THE_LOOP
                # In production, you'd add steps to the existing plan
                print(f"[Planner] → More steps needed - transitioning to DISPATCH state")
                print(f"{'='*80}\n")
                state.type = StateType.DISPATCH
                return state

            elif decision_type == "needsHuman":
                # Needs human input
                print(f"[Planner] ⚠ Human intervention required - transitioning to HUMAN_IN_THE_LOOP state")
                print(f"{'='*80}\n")
                state.type = StateType.HUMAN_IN_THE_LOOP
                state.final_payload = decision_data["payload"]
                return state

            elif decision_type == "failed":
                # Failed
                error_msg = decision_data["payload"].get("error", "Task failed")
                print(f"[Planner] ✗ Task failed - transitioning to ERROR state")
                print(f"[Planner] Error: {error_msg}")
                print(f"{'='*80}\n")
                state.type = StateType.ERROR
                state.error = error_msg
                return state

            else:
                print(f"[Planner] ✗ Unknown decision type: {decision_type}")
                print(f"{'='*80}\n")
                state.type = StateType.ERROR
                state.error = f"Unknown decision type: {decision_type}"
                return state

        except json.JSONDecodeError as e:
            # JSON parsing failed
            error_msg = f"Failed to parse LLM response as JSON: {str(e)}"
            print(f"\n[Planner] ✗ ERROR: {error_msg}")
            print(f"[Planner] Response that failed to parse:")
            print(f"{'-'*80}")
            print(content if 'content' in locals() else 'No content available')
            print(f"{'-'*80}")
            print(f"{'='*80}\n")
            state.type = StateType.ERROR
            state.error = f"Decision making failed: {error_msg}"
            return state
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"\n[Planner] ✗ ERROR: {error_msg}")
            import traceback
            print(f"[Planner] Traceback:")
            print(traceback.format_exc())
            print(f"{'='*80}\n")
            state.type = StateType.ERROR
            state.error = f"Decision making failed: {error_msg}"
            return state

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
