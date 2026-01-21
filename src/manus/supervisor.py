"""
Supervisor Agent - Plans and coordinates multi-agent tasks
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from orchestration.llm_client import create_llm_client, LLMClient
from orchestration.types import OrchestrationSettings, ToolDefinition
from orchestration.event_emitter import get_event_emitter
from .md_communicator import MDCommunicator


class SupervisorAgent:
    """
    Supervisor Agent - Main coordinator for Manus-style multi-agent system

    Responsibilities:
    1. Analyze user requests
    2. Create execution plans
    3. Assign tasks to specialized agents
    4. Monitor progress
    5. Collect and synthesize results
    """

    def __init__(
        self,
        settings: OrchestrationSettings,
        md_communicator: MDCommunicator,
        available_agents: Dict[str, List[ToolDefinition]]
    ):
        """
        Initialize Supervisor Agent

        Args:
            settings: Orchestration settings (LLM config, etc.)
            md_communicator: MD file communication manager
            available_agents: Dict mapping agent names to their available tools
        """
        self.settings = settings
        self.md_comm = md_communicator
        self.available_agents = available_agents

        # Create LLM client
        self.llm_client: LLMClient = create_llm_client(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            provider=settings.llm_provider,
            base_url=settings.llm_base_url
        )

        print(f"[SupervisorAgent] Initialized with {len(available_agents)} agents")
        print(f"[SupervisorAgent] Using LLM: {settings.llm_provider}/{settings.llm_model}")

    async def analyze_request(self, request: str, session_id: Optional[str] = None) -> str:
        """
        Analyze user request and generate high-level understanding

        Args:
            request: User request text
            session_id: Optional session ID for event streaming

        Returns:
            Analysis text
        """
        prompt = f"""Analyze the following user request and provide a high-level understanding of what needs to be done.

User Request: {request}

Provide a brief analysis (2-3 sentences) covering:
1. What is the user trying to accomplish?
2. What are the key steps needed?
3. What domains/tools might be involved?

Analysis:"""

        try:
            # Get event emitter if session_id provided
            event_emitter = get_event_emitter() if session_id else None

            # Stream the response with real-time progress
            content = ""
            async for chunk in self.llm_client.generate_stream(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            ):
                content += chunk

                # Emit real-time progress
                if event_emitter:
                    await event_emitter.emit_plan_generation_progress(
                        trace_id=session_id,
                        content=content,
                        is_complete=False,
                        step="analyze_request"
                    )

            analysis = content.strip()

            # Emit final progress
            if event_emitter:
                await event_emitter.emit_plan_generation_progress(
                    trace_id=session_id,
                    content=analysis,
                    is_complete=True,
                    step="analyze_request"
                )

            return analysis
        except Exception as e:
            print(f"[SupervisorAgent] Error during analysis: {e}")
            return f"Error analyzing request: {str(e)}"

    async def create_plan(self, request: str, analysis: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create execution plan with task breakdown

        Args:
            request: User request text
            analysis: Analysis from analyze_request()
            session_id: Optional session ID for event streaming

        Returns:
            Plan dictionary with tasks
        """
        # Build dynamic tool documentation
        tool_schemas_doc = self._build_tool_schemas_documentation()
        placeholder_rules = self._format_placeholder_rules()

        # Get current date/time for date calculations in planning
        now = datetime.now()
        current_datetime = now.strftime("%Y-%m-%d %H:%M:%S")
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")
        current_year = now.year
        current_month = now.month
        current_day = now.day

        prompt = f"""You are a supervisor agent coordinating multiple specialized agents.

CURRENT DATETIME: {current_datetime}
- Date: {current_date}
- Time: {current_time}
- Year: {current_year}, Month: {current_month}, Day: {current_day}

User Request: {request}

Analysis: {analysis}

{tool_schemas_doc}

{placeholder_rules}

Create an execution plan by breaking down the request into tasks for specialized agents.

Requirements:
1. Each task should be assigned to ONE specific agent
2. Tasks should be atomic and focused
3. Specify tool calls with EXACT parameter names from the tool's input schema
4. Use placeholders ({{{{task_id.field}}}}) to reference outputs from previous tasks
5. Identify dependencies between tasks (tasks with placeholders MUST list the referenced tasks in dependencies)
6. Set priority (high/medium/low)

Return a JSON object with this structure:
{{
  "tasks": [
    {{
      "task_id": "task_1_description",
      "name": "Task name",
      "agent": "agent_name",
      "description": "What needs to be done",
      "priority": "high|medium|low",
      "dependencies": [],
      "tool_calls": [
        {{
          "tool": "tool_name",
          "params": {{
            "param_name": "value or {{{{task_X.field}}}}"
          }}
        }}
      ]
    }},
    {{
      "task_id": "task_2_description",
      "name": "Task using previous result",
      "agent": "agent_name",
      "description": "Task that depends on task_1",
      "priority": "medium",
      "dependencies": ["task_1_description"],
      "tool_calls": [
        {{
          "tool": "another_tool",
          "params": {{
            "input_field": "{{{{task_1_description_call_1.output_field}}}}"
          }}
        }}
      ]
    }}
  ],
  "execution_strategy": "sequential|parallel|mixed",
  "estimated_steps": 2
}}

CRITICAL RULES:
1. Use DOUBLE curly braces for placeholders: {{{{task_id.field}}}}
2. Match parameter names EXACTLY to the tool's input schema
3. Use output field names from the previous task's output schema
4. Always add dependencies when using placeholders
5. Return ONLY valid JSON, no markdown code blocks or explanations
6. For date/time calculations:
   - You have CURRENT DATETIME above - use it to calculate dates directly
   - Calculate date strings yourself and put them directly in parameters
   - Example: If today is 2026-01-21 and user wants "this month", use start="2026-01-01", end="2026-01-31"
   - Example: If today is 2026-01-21 and user wants "this week", use start="2026-01-21", end="2026-01-28"
   - NEVER use shell commands (date, tr, awk, sed) - they don't work cross-platform
   - If you absolutely need to run code, use Python with appropriate tools
   - But preferably: Just calculate dates yourself and include them as literal strings in parameters
"""

        try:
            print("[SupervisorAgent] Generating execution plan...")

            # Get event emitter if session_id provided
            event_emitter = get_event_emitter() if session_id else None

            # Retry loop for JSON parsing errors
            max_retries = 2
            last_error = None

            for attempt in range(max_retries + 1):
                if attempt > 0:
                    print(f"[SupervisorAgent] Retry attempt {attempt}/{max_retries} due to JSON parsing error")
                    # Add error feedback to prompt
                    retry_prompt = prompt + f"""

PREVIOUS ATTEMPT FAILED:
The previous response had a JSON parsing error: {last_error}

Please ensure you return ONLY valid JSON with:
- All property names in double quotes
- No extra text or comments before/after property names
- Proper comma separation between properties
- No trailing commas

Return ONLY the JSON object, nothing else."""
                    current_prompt = retry_prompt
                else:
                    current_prompt = prompt

                # Stream the response with real-time progress updates
                content = ""
                async for chunk in self.llm_client.generate_stream(
                    messages=[{"role": "user", "content": current_prompt}],
                    max_tokens=8192
                ):
                    content += chunk

                    # Emit real-time progress for every chunk (token-level streaming)
                    if event_emitter:
                        await event_emitter.emit_plan_generation_progress(
                            trace_id=session_id,
                            content=content,
                            is_complete=False,
                            step="create_plan"
                        )

                response = content.strip()

                # Emit final progress event
                if event_emitter:
                    await event_emitter.emit_plan_generation_progress(
                        trace_id=session_id,
                        content=response,
                        is_complete=True,
                        step="create_plan"
                    )

                # Clean response
                response = response.strip()
                if response.startswith("```"):
                    response = response.split("```")[1]
                    if response.startswith("json"):
                        response = response[4:]
                    response = response.strip()

                # Try to parse JSON
                try:
                    plan_data = json.loads(response)
                    # Success! Break out of retry loop
                    break
                except json.JSONDecodeError as e:
                    last_error = str(e)
                    print(f"[SupervisorAgent] JSON parsing error (attempt {attempt + 1}): {e}")
                    print(f"[SupervisorAgent] Raw response (first 500 chars): {response[:500]}")

                    if attempt == max_retries:
                        # Final attempt failed, log full response and return error
                        print(f"[SupervisorAgent] All retry attempts exhausted")
                        print(f"[SupervisorAgent] Full response: {response}")
                        return {
                            "tasks": [],
                            "execution_strategy": "sequential",
                            "estimated_steps": 0,
                            "error": f"Failed to parse plan after {max_retries + 1} attempts: {str(e)}"
                        }
                    # Continue to next retry attempt

            # Assign task IDs if not present
            for i, task in enumerate(plan_data.get('tasks', [])):
                if 'task_id' not in task:
                    task['task_id'] = f"task_{i+1}_{uuid.uuid4().hex[:8]}"
                if 'status' not in task:
                    task['status'] = 'pending'

            # Validate and fix plan
            plan_data = self._validate_and_fix_plan(plan_data)

            print(f"[SupervisorAgent] Plan created with {len(plan_data.get('tasks', []))} tasks")

            # Debug: Log plan details
            for i, task in enumerate(plan_data.get('tasks', [])):
                print(f"[SupervisorAgent] Task {i+1}: {task.get('task_id')}")
                print(f"  Agent: {task.get('agent')}")
                print(f"  Tool calls: {len(task.get('tool_calls', []))}")
                for j, call in enumerate(task.get('tool_calls', [])):
                    tool_name = call.get('tool', 'MISSING')
                    print(f"    Call {j+1}: tool='{tool_name}' params={list(call.get('params', {}).keys())}")

            return plan_data

        except Exception as e:
            print(f"[SupervisorAgent] Error creating plan: {e}")
            return {
                "tasks": [],
                "execution_strategy": "sequential",
                "estimated_steps": 0,
                "error": str(e)
            }

    async def assign_tasks(self, plan_data: Dict[str, Any]) -> None:
        """
        Assign tasks to agents by writing to their task.md files

        Args:
            plan_data: Plan dictionary from create_plan()
        """
        tasks = plan_data.get('tasks', [])

        for task in tasks:
            agent_name = task.get('agent')
            if not agent_name:
                print(f"[SupervisorAgent] Warning: Task {task.get('task_id')} has no agent assigned")
                continue

            # Build task data for MD file
            task_data = {
                'task_id': task['task_id'],
                'assigned_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'description': task.get('description', ''),
                'tool_calls': task.get('tool_calls', []),
                'status': 'pending'
            }

            # Write task to agent's task.md
            await self.md_comm.write_task(agent_name, task_data)

        print(f"[SupervisorAgent] Assigned {len(tasks)} tasks to agents")

    async def monitor_progress(self) -> Dict[str, str]:
        """
        Monitor progress by checking result.md files for all agents

        Returns:
            Dictionary mapping agent names to their task status
        """
        agent_statuses = {}
        agents_with_tasks = await self.md_comm.list_agents_with_tasks()

        for agent_name in agents_with_tasks:
            # Check if result exists
            result_data = await self.md_comm.read_result(agent_name)

            if result_data:
                agent_statuses[agent_name] = result_data.get('status', 'unknown')
            else:
                # No result yet, check task status
                task_data = await self.md_comm.read_task(agent_name)
                if task_data:
                    agent_statuses[agent_name] = task_data.get('status', 'pending')
                else:
                    agent_statuses[agent_name] = 'no_task'

        return agent_statuses

    async def collect_results(self) -> Dict[str, Any]:
        """
        Collect results from all agents

        Returns:
            Dictionary with collected results
        """
        results = {}
        agents_with_tasks = await self.md_comm.list_agents_with_tasks()

        for agent_name in agents_with_tasks:
            result_data = await self.md_comm.read_result(agent_name)
            if result_data:
                results[agent_name] = result_data

        return results

    async def collect_tasks_and_results(self) -> Dict[str, Dict[str, Any]]:
        """
        Collect both tasks and results from all agents

        Returns:
            Dictionary with agent_name -> {'task': task_data, 'result': result_data}
        """
        collected = {}
        agents_with_tasks = await self.md_comm.list_agents_with_tasks()

        for agent_name in agents_with_tasks:
            task_data = await self.md_comm.read_task(agent_name)
            result_data = await self.md_comm.read_result(agent_name)

            collected[agent_name] = {
                'task': task_data,
                'result': result_data
            }

        return collected

    async def synthesize_final_response(
        self,
        request: str,
        plan_data: Dict[str, Any],
        results: Dict[str, Any]
    ) -> str:
        """
        Synthesize final response from collected results

        Args:
            request: Original user request
            plan_data: Execution plan (CRITICAL: contains the intended response strategy)
            results: Collected results from agents

        Returns:
            Final response text
        """
        # Collect both tasks and results for full context
        tasks_and_results = await self.collect_tasks_and_results()

        # Build comprehensive summary with task assignments AND results
        full_summary = self._format_tasks_and_results_summary(tasks_and_results)

        # Format the original plan for context
        plan_summary = self._format_plan_summary(plan_data)

        # Get current date and time to provide temporal context
        now = datetime.now()
        current_datetime = now.strftime("%Y-%m-%d %H:%M:%S")
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")

        prompt = f"""You are a supervisor agent. You coordinated multiple specialized agents to complete a user's request.

CURRENT DATETIME: {current_datetime}
- Current Date: {current_date}
- Current Time: {current_time}

Original User Request: {request}

ORIGINAL EXECUTION PLAN (YOUR INTENDED STRATEGY):
{plan_summary}

Tasks Assigned and Execution Results:
{full_summary}

Please synthesize a clear, concise final response to the user that:
1. FOLLOWS THE ORIGINAL PLAN'S INTENT - If the plan intended to filter, summarize, or format data in a specific way, do that in your response
2. Confirms what was accomplished based on the ACTUAL task assignments and results
3. Provides key information/results using the ACTUAL data from tool outputs
4. Uses accurate dates, times, and other details from the actual tool outputs (not made-up dates)
5. When referring to time periods (e.g., "this week", "this month"), use the CURRENT DATETIME provided above
6. Applies any filtering, formatting, or processing that was described in the original plan
7. Mentions any issues or limitations if present

CRITICAL: The original plan describes the INTENT of how to present results to the user. For example:
- If the plan says "fetch all events then show only this month", filter the results to this month even if the tool returned all events
- If the plan says "summarize", provide a summary not full details
- If the plan says "list top 5", show only 5 items even if more are available

Base your response on:
1. The INTENT described in the original plan
2. The actual task descriptions and tool parameters
3. The actual tool outputs

Do not make up or guess any information, especially dates and times.

Final Response:"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000
            )
            return response.strip()
        except Exception as e:
            print(f"[SupervisorAgent] Error synthesizing response: {e}")
            # Fallback: return raw results
            return f"Tasks completed. Full details:\n{full_summary}"

    async def replan(
        self,
        original_request: str,
        original_plan: Dict[str, Any],
        failed_tasks: List[str],
        error_info: Dict[str, str],
        retry_history: Optional[Any] = None,
        completed_tasks: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new plan to handle failed tasks with awareness of previous attempts

        Args:
            original_request: Original user request
            original_plan: Original plan data
            failed_tasks: List of failed task IDs
            error_info: Dictionary mapping task IDs to error messages
            retry_history: RetryHistory object with previous attempt information
            completed_tasks: Dict of already completed tasks {task_id: result}

        Returns:
            New plan dictionary with improved strategy
        """
        if completed_tasks is None:
            completed_tasks = {}
        # Build error summary
        error_summary = "\n".join([
            f"- Task {task_id}: {error_info.get(task_id, 'Unknown error')}"
            for task_id in failed_tasks
        ])

        # Build history summary if available
        history_section = ""
        if retry_history:
            history_lines = ["\n## Previous Attempt History\n"]

            for task_id in failed_tasks:
                task_history = retry_history.format_history_for_prompt(task_id)
                if task_history:
                    history_lines.append(task_history)
                    history_lines.append("")  # Blank line

            if len(history_lines) > 1:  # More than just header
                history_section = "\n".join(history_lines)

        # Build completed tasks summary
        completed_section = ""
        if completed_tasks:
            completed_lines = ["\n## ✅ Already Completed Tasks (DO NOT RE-EXECUTE)\n"]
            completed_lines.append("These tasks have ALREADY been completed successfully in a previous attempt.")
            completed_lines.append("You can reference their outputs using placeholders, but DO NOT include them in your new plan.\n")

            for task_id, result in completed_tasks.items():
                completed_lines.append(f"**Task: {task_id}**")
                completed_lines.append(f"  Status: {result.get('status', 'completed')}")
                if 'summary' in result:
                    completed_lines.append(f"  Summary: {result['summary'][:200]}")
                completed_lines.append("")

            completed_section = "\n".join(completed_lines)

        # Build comprehensive replanning prompt
        prompt = f"""You are a supervisor agent. Some tasks failed during execution and need intelligent replanning.

## Original Request
{original_request}

## Current Failures
{error_summary}
{completed_section}
{history_section}
## Original Plan
{json.dumps(original_plan, indent=2)}

## Your Mission
Analyze WHY the tasks failed and create a NEW plan that addresses the root causes.

## ⚠️ CRITICAL: Avoid Infinite Retry Loops ⚠️

If your new plan causes the SAME error again, the system will STOP retrying immediately.
You MUST create a plan that is FUNDAMENTALLY DIFFERENT from what failed.

## Critical Replanning Rules

1. **DO NOT REPEAT FAILED APPROACHES**
   - If you see duplicate errors in the history, the approach is fundamentally wrong
   - You MUST try a completely different strategy
   - Check parameter TYPES carefully - this is the #1 cause of duplicate errors

2. **Common Error Patterns and Solutions**

   **Type Mismatch Errors** (e.g., "Input should be a valid string" but got dict):
   ⚠️ **CRITICAL**: NEVER pass a dict/object placeholder to a string parameter!

   Examples of WRONG approaches:
   ❌ `{{"content": "{{{{task_1_call_1}}}}"}}`  - Passes whole dict to string param
   ❌ `{{"data": "{{{{task_1_call_1.location}}}}"}}`  - Passes nested dict to string param
   ❌ `{{"text": "{{{{task_1_call_1}}}}"}}`  - Any dict to any string param is WRONG

   Correct Solutions (pick ONE):
   ✅ **Extract specific field**: `{{"content": "Temperature: {{{{task_1_call_1.current.temperature}}}}"}}`
   ✅ **Extract multiple fields**: `{{"content": "Seoul weather: {{{{task_1_call_1.current.temperature}}}}, {{{{task_1_call_1.current.condition}}}}"}}`
   ✅ **Use array index**: `{{"name": "{{{{task_1_call_1.results.0.name}}}}"}}`

   🔧 **If you need the full dict as string**:
   The system will automatically convert dicts to JSON strings when needed.
   However, it's better to extract only what you need!

   **Missing Parameter Errors**:
   - ✅ Check tool schema and add ALL required parameters
   - ✅ Use placeholders to pass data from previous tasks

   **Wrong Tool Selection**:
   - ✅ Review available tools and pick the correct one
   - ✅ Check tool descriptions and parameter schemas

   **Placeholder Resolution Errors** (e.g., "Field 'xyz' not found"):
   ⚠️ **CRITICAL**: The field you're trying to access is probably NESTED inside an object!

   Common mistake - trying to access nested fields at top level:
   ❌ `{{{{task_1_call_1.field}}}}` - WRONG if 'field' is inside a parent object

   Solution - check the tool's Output Fields section:
   - Look for "⚠️ NESTED OBJECT" warnings
   - The warning shows EXACTLY how to access the field
   - Use the full path shown in the schema

   Example - If you see in Output Fields:
   ```
   - result: object
     ⚠️ NESTED OBJECT - Access fields using: result.field_name
       - result.field: string
   ```

   Then use: ✅ `{{{{task_1_call_1.result.field}}}}`
   NOT:       ❌ `{{{{task_1_call_1.field}}}}`

   **ALWAYS** check the tool's Output Fields section for the exact structure!
   If you see "⚠️ NESTED OBJECT" warning, you MUST use the full path shown!

   **Data Format Errors**:
   - ✅ Add intermediate processing step
   - ✅ Transform data structure before using it
   - ✅ Use different output fields from previous task

3. **Replanning Strategies** (Try in order)

   Strategy A - **Fix Parameters**:
   - Correct parameter types (add JSON conversion if needed)
   - Fix parameter names to match tool schema exactly
   - Add missing required parameters

   Strategy B - **Add Intermediate Step**:
   - Insert data transformation task between steps
   - Example: Extract specific fields, format data, convert types

   Strategy C - **Different Tool**:
   - Use alternative tool that accepts the data format you have
   - Switch to a tool with more flexible parameters

   Strategy D - **Break Down Task**:
   - Split complex task into smaller atomic steps
   - Each step does one simple thing

4. **Verification Checklist Before Submitting Plan**

   For EACH tool call, verify:

   ✓ **Type Check**: Does parameter type match schema?
     - If schema says "string", value MUST be string or field access
     - If schema says "number", value MUST be number
     - If schema says "object", value CAN be dict placeholder

   ✓ **Required Params**: Are ALL required parameters provided?
     - Check tool's input schema
     - Missing params = guaranteed failure

   ✓ **Placeholder Validity**: Do placeholders reference real output fields?
     - Check previous task's output schema
     - Use correct field names and paths

   ✓ **Dependencies**: Are dependencies correctly specified?
     - If using {{task_X}}, must have "task_X" in dependencies array

5. **What Success Looks Like**
   - Parameter types match tool schema EXACTLY
   - All required parameters are provided
   - Placeholders reference valid output fields
   - Dependencies are correctly specified

## Output Format
Return the same JSON structure as the original plan:
{{
  "tasks": [...],
  "execution_strategy": "sequential|parallel|mixed",
  "estimated_steps": N
}}

**IMPORTANT**: Return ONLY valid JSON, no markdown code blocks or explanations.
**REMEMBER**: The new plan MUST be different from what failed before!
"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192
            )

            # Clean and parse
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()

            new_plan = json.loads(response)

            # Assign task IDs
            for i, task in enumerate(new_plan.get('tasks', [])):
                if 'task_id' not in task:
                    task['task_id'] = f"task_retry_{i+1}_{uuid.uuid4().hex[:8]}"
                if 'status' not in task:
                    task['status'] = 'pending'

            return new_plan

        except json.JSONDecodeError as e:
            print(f"[SupervisorAgent] JSON parsing error during replan: {e}")
            print(f"[SupervisorAgent] Raw response (first 1000 chars): {response[:1000]}")
            print(f"[SupervisorAgent] Response length: {len(response)} characters")
            print(f"[SupervisorAgent] Full response: {response}")
            return {
                "tasks": [],
                "execution_strategy": "sequential",
                "error": f"Failed to parse replanned tasks: {str(e)}"
            }
        except Exception as e:
            print(f"[SupervisorAgent] Error during replan: {e}")
            return {
                "tasks": [],
                "execution_strategy": "sequential",
                "error": str(e)
            }

    # ========== Helper Methods ==========

    def _build_tool_schemas_documentation(self) -> str:
        """
        Build comprehensive tool documentation with input/output schemas

        This method dynamically generates documentation for ALL available tools,
        ensuring any MCP server addition is automatically included.

        Returns:
            Formatted documentation string for LLM prompt
        """
        doc_lines = ["## Available Tools and Their Schemas\n"]

        for agent_name, tools in self.available_agents.items():
            doc_lines.append(f"### Agent: {agent_name}\n")

            for tool in tools:
                doc_lines.append(f"**Tool: {tool.name}**")
                doc_lines.append(f"Description: {tool.description}")

                # Input Schema
                if tool.input_schema:
                    doc_lines.append("\nInput Parameters:")
                    properties = tool.input_schema.get('properties', {})
                    required = tool.input_schema.get('required', [])

                    for param_name, param_info in properties.items():
                        param_type = param_info.get('type', 'any')
                        param_desc = param_info.get('description', '')
                        is_required = param_name in required

                        req_marker = " (REQUIRED)" if is_required else " (optional)"
                        doc_lines.append(f"  - `{param_name}`: {param_type}{req_marker}")
                        if param_desc:
                            doc_lines.append(f"    {param_desc}")
                else:
                    doc_lines.append("\nInput Parameters: (no schema available)")

                # Output Schema
                if tool.output_schema:
                    doc_lines.append("\nOutput Fields:")
                    output_props = tool.output_schema.get('properties', {})

                    if output_props:
                        self._append_schema_fields(doc_lines, output_props, indent=1)
                    else:
                        # Output schema exists but no properties defined
                        # Try to infer structure from example or type
                        output_type = tool.output_schema.get('type', 'object')
                        doc_lines.append(f"  - Returns: {output_type}")
                else:
                    doc_lines.append("\nOutput Fields: (no schema available - check tool documentation)")

                # Add example usage
                example = self._generate_example_from_schema(tool)
                if example:
                    doc_lines.append(f"\nExample Usage:")
                    doc_lines.append(f"```json")
                    doc_lines.append(json.dumps(example, indent=2))
                    doc_lines.append(f"```")

                doc_lines.append("")  # Blank line between tools

            doc_lines.append("")  # Blank line between agents

        return "\n".join(doc_lines)

    def _format_placeholder_rules(self) -> str:
        """
        Format placeholder usage rules

        Returns:
            Formatted rules string for LLM prompt
        """
        return """## Placeholder Reference Rules

When a task needs to use the output from a previous task:

1. **Syntax**: Use DOUBLE curly braces: `{{task_id.field}}`
   - ✅ Correct: `{{"city": "{{task_1_search_call_1.name}}"}}`
   - ❌ Wrong: `{{"city": "{result_of_task_1.city_id}"}}`

2. **Task ID Format**: Use the exact task_id from the previous task + "_call_N"
   - If task has task_id="task_1_search", the step_id will be "task_1_search_call_1"
   - Reference it as: `{{task_1_search_call_1.field_name}}`

3. **Field Names**: Use EXACT field names from the output schema
   - Check the "Output Fields" section for each tool - it shows the COMPLETE structure
   - If output is nested, use dot notation: `{{task_id.parent.child}}`
   - Array indexing: `{{task_id.items.0}}` for first item

   **CRITICAL - Accessing Nested Fields**:
   When you see nested objects in the output schema, you MUST use the full path!

   Look for the "⚠️ NESTED OBJECT" warning in output fields. It tells you exactly how to access nested fields.

   Example - If the Output Fields section shows:
   ```
   - success: boolean
   - data: object
     ⚠️ NESTED OBJECT - Access fields using: data.field_name
       - data.name: string
       - data.value: number
       - data.metadata: object
         ⚠️ NESTED OBJECT - Access fields using: data.metadata.field_name
           - data.metadata.created_at: string
   ```

   ❌ WRONG: `{{task_1_call_1.name}}` - name is inside 'data' object!
   ❌ WRONG: `{{task_1_call_1.value}}` - value is inside 'data' object!
   ❌ WRONG: `{{task_1_call_1.created_at}}` - created_at is inside 'data.metadata'!

   ✅ CORRECT: `{{task_1_call_1.data.name}}` - Full path through parent object
   ✅ CORRECT: `{{task_1_call_1.data.value}}` - Full path through parent object
   ✅ CORRECT: `{{task_1_call_1.data.metadata.created_at}}` - Full path through all parent objects

4. **Dependencies**: ALWAYS list prerequisite tasks in the dependencies array
   - If task_2 uses `{{task_1_call_1.result}}`, add `"dependencies": ["task_1"]`

5. **Common Patterns**:
   - Search then use result: search_city → get_weather
     ```json
     {
       "task_id": "task_2_weather",
       "dependencies": ["task_1_search"],
       "tool_calls": [{
         "tool": "get_current_weather",
         "params": {
           "city": "{{task_1_search_call_1.results.0.name}}"
         }
       }]
     }
     ```
   - Get item then update it: get_event → update_event
   - List items then process each: list_files → read_file
"""

    def _append_schema_fields(
        self,
        doc_lines: List[str],
        properties: Dict[str, Any],
        indent: int = 1,
        prefix: str = ""
    ) -> None:
        """
        Recursively append schema fields to documentation with nested structure

        Args:
            doc_lines: List to append formatted field descriptions to
            properties: Schema properties dictionary
            indent: Current indentation level
            prefix: Field path prefix (e.g., "current." for nested fields)
        """
        indent_str = "  " * indent

        for field_name, field_info in properties.items():
            field_type = field_info.get('type', 'any')
            field_desc = field_info.get('description', '')
            full_field_name = f"{prefix}{field_name}"

            # Format the field line
            doc_lines.append(f"{indent_str}- `{full_field_name}`: {field_type}")
            if field_desc:
                doc_lines.append(f"{indent_str}  {field_desc}")

            # Recursively process nested objects
            if field_type == 'object':
                nested_props = field_info.get('properties', {})
                if nested_props:
                    # Add explicit note about nested object access
                    doc_lines.append(f"{indent_str}  ⚠️  NESTED OBJECT - Access fields using: {full_field_name}.field_name")
                    # Show nested fields with increased indentation
                    self._append_schema_fields(
                        doc_lines,
                        nested_props,
                        indent=indent + 1,
                        prefix=f"{full_field_name}."
                    )

            # Handle arrays with object items
            elif field_type == 'array':
                items_schema = field_info.get('items', {})
                if isinstance(items_schema, dict):
                    items_type = items_schema.get('type')
                    if items_type == 'object':
                        items_props = items_schema.get('properties', {})
                        if items_props:
                            doc_lines.append(f"{indent_str}  Array items have fields:")
                            self._append_schema_fields(
                                doc_lines,
                                items_props,
                                indent=indent + 2,
                                prefix=f"{full_field_name}.0."
                            )

    def _generate_example_from_schema(self, tool: ToolDefinition) -> Optional[Dict[str, Any]]:
        """
        Generate example tool call from schema

        Args:
            tool: Tool definition with schemas

        Returns:
            Example dictionary or None
        """
        if not tool.input_schema:
            return None

        properties = tool.input_schema.get('properties', {})
        required = tool.input_schema.get('required', [])

        if not properties:
            return None

        example = {
            "tool": tool.name,
            "params": {}
        }

        # Generate example values for required parameters
        for param_name in required:
            if param_name in properties:
                param_info = properties[param_name]
                example["params"][param_name] = self._generate_example_value(
                    param_name,
                    param_info
                )

        return example

    def _generate_example_value(self, param_name: str, param_info: dict) -> Any:
        """
        Generate example value based on parameter schema

        Args:
            param_name: Parameter name
            param_info: Parameter schema info

        Returns:
            Example value
        """
        param_type = param_info.get('type', 'string')
        param_desc = param_info.get('description', '').lower()

        # Type-based examples
        if param_type == 'string':
            # Context-aware examples
            if 'email' in param_name.lower() or 'email' in param_desc:
                return "user@example.com"
            elif 'city' in param_name.lower() or 'city' in param_desc:
                return "Seoul"
            elif 'date' in param_name.lower() or 'date' in param_desc:
                return "2024-01-01"
            elif 'url' in param_name.lower() or 'url' in param_desc:
                return "https://example.com"
            else:
                return f"example_{param_name}"
        elif param_type == 'number' or param_type == 'integer':
            return 123
        elif param_type == 'boolean':
            return True
        elif param_type == 'array':
            items_type = param_info.get('items', {}).get('type', 'string')
            if items_type == 'string':
                return ["item1", "item2"]
            else:
                return [1, 2, 3]
        elif param_type == 'object':
            return {}
        else:
            return f"<{param_type}>"

    def _validate_and_fix_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and fix plan data, especially tool names in tool_calls

        Args:
            plan_data: Plan data from LLM

        Returns:
            Fixed plan data
        """
        tasks = plan_data.get('tasks', [])

        for task_idx, task in enumerate(tasks):
            agent_name = task.get('agent')
            tool_calls = task.get('tool_calls', [])

            if not agent_name:
                print(f"[SupervisorAgent] WARNING: Task {task.get('task_id')} has no agent assigned")
                continue

            if not tool_calls:
                print(f"[SupervisorAgent] WARNING: Task {task.get('task_id')} has no tool calls")
                continue

            # Get available tools for this agent
            agent_tools = self.available_agents.get(agent_name, [])
            tool_names = [tool.name for tool in agent_tools]

            # Validate each tool call
            for call_idx, call in enumerate(tool_calls):
                tool_name = call.get('tool', '').strip()

                # Check if tool name is missing or empty
                if not tool_name:
                    print(f"[SupervisorAgent] ERROR: Task {task.get('task_id')} call {call_idx+1} has missing/empty tool name")

                    # Try to auto-fix if agent has only one tool
                    if len(tool_names) == 1:
                        fixed_tool_name = tool_names[0]
                        call['tool'] = fixed_tool_name
                        print(f"[SupervisorAgent] AUTO-FIX: Set tool name to '{fixed_tool_name}' (only tool for agent '{agent_name}')")
                    else:
                        print(f"[SupervisorAgent] ERROR: Cannot auto-fix - agent '{agent_name}' has {len(tool_names)} tools: {tool_names}")
                        print(f"[SupervisorAgent] LLM must specify which tool to use!")
                        # Set to first tool as fallback
                        if tool_names:
                            call['tool'] = tool_names[0]
                            print(f"[SupervisorAgent] FALLBACK: Using first available tool '{tool_names[0]}'")

                # Check if tool name is valid for this agent
                elif tool_name not in tool_names:
                    print(f"[SupervisorAgent] WARNING: Task {task.get('task_id')} references unknown tool '{tool_name}'")
                    print(f"[SupervisorAgent] Available tools for agent '{agent_name}': {tool_names}")

                    # Try to find a close match
                    for available_tool in tool_names:
                        if tool_name.lower() in available_tool.lower() or available_tool.lower() in tool_name.lower():
                            print(f"[SupervisorAgent] AUTO-FIX: Changing '{tool_name}' to '{available_tool}'")
                            call['tool'] = available_tool
                            break

        return plan_data

    def _build_agent_capabilities_summary(self) -> str:
        """Build a formatted summary of agent capabilities (legacy - kept for compatibility)"""
        summary_lines = []

        for agent_name, tools in self.available_agents.items():
            tool_names = [tool.name for tool in tools]
            summary_lines.append(f"**{agent_name}**: {', '.join(tool_names)}")

        return "\n".join(summary_lines)

    def _format_results_summary(self, results: Dict[str, Any]) -> str:
        """Format results dictionary as readable text (legacy method for backward compatibility)"""
        if not results:
            return "No results available."

        summary_lines = []

        for agent_name, result_data in results.items():
            status = result_data.get('status', 'unknown')
            summary = result_data.get('summary', '')
            errors = result_data.get('errors', '')
            actual_results = result_data.get('results', [])

            summary_lines.append(f"**{agent_name}**:")
            summary_lines.append(f"  Status: {status}")
            if summary:
                summary_lines.append(f"  Summary: {summary}")

            # Include actual tool results so LLM can see the detailed data
            if actual_results:
                summary_lines.append(f"  Detailed Results:")
                for i, result_item in enumerate(actual_results, 1):
                    tool_name = result_item.get('tool', 'unknown')
                    tool_output = result_item.get('output', {})

                    summary_lines.append(f"    [{i}] Tool: {tool_name}")
                    # Format the output in a readable way
                    import json
                    try:
                        output_str = json.dumps(tool_output, indent=6, ensure_ascii=False)
                        summary_lines.append(f"    Output:")
                        for line in output_str.split('\n'):
                            summary_lines.append(f"      {line}")
                    except (TypeError, ValueError):
                        summary_lines.append(f"      {tool_output}")

            if errors:
                summary_lines.append(f"  Errors: {errors}")
            summary_lines.append("")

        return "\n".join(summary_lines)

    def _format_tasks_and_results_summary(self, collected: Dict[str, Dict[str, Any]]) -> str:
        """
        Format tasks and results together for better context

        Args:
            collected: Dictionary with agent_name -> {'task': task_data, 'result': result_data}

        Returns:
            Formatted string with task assignments and results
        """
        if not collected:
            return "No tasks or results available."

        import json
        summary_lines = []

        for agent_name, data in collected.items():
            task_data = data.get('task') or {}
            result_data = data.get('result') or {}

            summary_lines.append(f"**Agent: {agent_name}**")
            summary_lines.append("")

            # Task information
            task_description = task_data.get('description', '')
            tool_calls = task_data.get('tool_calls', [])

            if task_description or tool_calls:
                summary_lines.append(f"  Task Assignment:")
                if task_description:
                    summary_lines.append(f"    Description: {task_description}")
                if tool_calls:
                    summary_lines.append(f"    Requested Tool Calls:")
                    for i, call in enumerate(tool_calls, 1):
                        tool_name = call.get('tool', 'unknown')
                        params = call.get('params', {})
                        summary_lines.append(f"      [{i}] {tool_name}")
                        try:
                            params_str = json.dumps(params, indent=8, ensure_ascii=False)
                            summary_lines.append(f"        Parameters:")
                            for line in params_str.split('\n'):
                                summary_lines.append(f"          {line}")
                        except (TypeError, ValueError):
                            summary_lines.append(f"          {params}")
                summary_lines.append("")

            # Result information
            status = result_data.get('status', 'unknown')
            summary = result_data.get('summary', '')
            errors = result_data.get('errors', '')
            actual_results = result_data.get('results', [])

            summary_lines.append(f"  Execution Result:")
            summary_lines.append(f"    Status: {status}")
            if summary:
                summary_lines.append(f"    Summary: {summary}")

            # Include actual tool results with the detailed output
            if actual_results:
                summary_lines.append(f"    Actual Tool Outputs:")
                for i, result_item in enumerate(actual_results, 1):
                    tool_name = result_item.get('tool', 'unknown')
                    tool_output = result_item.get('output', {})

                    summary_lines.append(f"      [{i}] Tool: {tool_name}")
                    try:
                        output_str = json.dumps(tool_output, indent=10, ensure_ascii=False)
                        summary_lines.append(f"        Output:")
                        for line in output_str.split('\n'):
                            summary_lines.append(f"          {line}")
                    except (TypeError, ValueError):
                        summary_lines.append(f"          {tool_output}")

            if errors:
                summary_lines.append(f"    Errors: {errors}")

            summary_lines.append("")
            summary_lines.append("---")
            summary_lines.append("")

        return "\n".join(summary_lines)

    def _format_plan_summary(self, plan_data: Dict[str, Any]) -> str:
        """
        Format the execution plan to show the original intent

        Args:
            plan_data: The execution plan dictionary

        Returns:
            Formatted string showing the plan's intent
        """
        if not plan_data:
            return "No plan available."

        import json
        summary_lines = []

        # Overall strategy
        strategy = plan_data.get('execution_strategy', 'unknown')
        estimated_steps = plan_data.get('estimated_steps', 0)

        summary_lines.append(f"Execution Strategy: {strategy}")
        summary_lines.append(f"Estimated Steps: {estimated_steps}")
        summary_lines.append("")

        # Task breakdown with intent
        tasks = plan_data.get('tasks', [])
        if tasks:
            summary_lines.append("Planned Tasks (showing the original intent):")
            summary_lines.append("")

            for i, task in enumerate(tasks, 1):
                task_id = task.get('task_id', 'unknown')
                name = task.get('name', 'Unnamed task')
                description = task.get('description', '')
                agent = task.get('agent', 'unknown')
                dependencies = task.get('dependencies', [])
                priority = task.get('priority', 'medium')

                summary_lines.append(f"  Task {i}: {name}")
                summary_lines.append(f"    ID: {task_id}")
                summary_lines.append(f"    Agent: {agent}")
                summary_lines.append(f"    Priority: {priority}")

                if description:
                    summary_lines.append(f"    Intent/Description: {description}")

                if dependencies:
                    summary_lines.append(f"    Dependencies: {', '.join(dependencies)}")

                # Show tool calls to understand what was planned
                tool_calls = task.get('tool_calls', [])
                if tool_calls:
                    summary_lines.append(f"    Planned Tool Calls:")
                    for j, call in enumerate(tool_calls, 1):
                        tool_name = call.get('tool', 'unknown')
                        params = call.get('params', {})
                        summary_lines.append(f"      [{j}] {tool_name}")
                        # Show key parameters to understand intent
                        if params:
                            try:
                                params_str = json.dumps(params, indent=10, ensure_ascii=False)
                                summary_lines.append(f"        Params:")
                                for line in params_str.split('\n'):
                                    summary_lines.append(f"          {line}")
                            except (TypeError, ValueError):
                                summary_lines.append(f"          {params}")

                summary_lines.append("")

        return "\n".join(summary_lines)
