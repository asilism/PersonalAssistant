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

    async def analyze_request(self, request: str) -> str:
        """
        Analyze user request and generate high-level understanding

        Args:
            request: User request text

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
            analysis = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            return analysis.strip()
        except Exception as e:
            print(f"[SupervisorAgent] Error during analysis: {e}")
            return f"Error analyzing request: {str(e)}"

    async def create_plan(self, request: str, analysis: str) -> Dict[str, Any]:
        """
        Create execution plan with task breakdown

        Args:
            request: User request text
            analysis: Analysis from analyze_request()

        Returns:
            Plan dictionary with tasks
        """
        # Build dynamic tool documentation
        tool_schemas_doc = self._build_tool_schemas_documentation()
        placeholder_rules = self._format_placeholder_rules()

        prompt = f"""You are a supervisor agent coordinating multiple specialized agents.

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
"""

        try:
            print("[SupervisorAgent] Generating execution plan...")
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096
            )

            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()

            # Parse JSON
            plan_data = json.loads(response)

            # Assign task IDs if not present
            for i, task in enumerate(plan_data.get('tasks', [])):
                if 'task_id' not in task:
                    task['task_id'] = f"task_{i+1}_{uuid.uuid4().hex[:8]}"
                if 'status' not in task:
                    task['status'] = 'pending'

            print(f"[SupervisorAgent] Plan created with {len(plan_data.get('tasks', []))} tasks")
            return plan_data

        except json.JSONDecodeError as e:
            print(f"[SupervisorAgent] JSON parsing error: {e}")
            print(f"[SupervisorAgent] Raw response: {response[:500]}")
            # Fallback: return empty plan
            return {
                "tasks": [],
                "execution_strategy": "sequential",
                "estimated_steps": 0,
                "error": f"Failed to parse plan: {str(e)}"
            }
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
            plan_data: Execution plan
            results: Collected results from agents

        Returns:
            Final response text
        """
        # Build results summary
        results_summary = self._format_results_summary(results)

        prompt = f"""You are a supervisor agent. You coordinated multiple specialized agents to complete a user's request.

Original Request: {request}

Results from Agents:
{results_summary}

Please synthesize a clear, concise final response to the user that:
1. Confirms what was accomplished
2. Provides key information/results
3. Mentions any issues or limitations

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
            return f"Tasks completed. Results:\n{results_summary}"

    async def replan(
        self,
        original_request: str,
        original_plan: Dict[str, Any],
        failed_tasks: List[str],
        error_info: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Create a new plan to handle failed tasks

        Args:
            original_request: Original user request
            original_plan: Original plan data
            failed_tasks: List of failed task IDs
            error_info: Dictionary mapping task IDs to error messages

        Returns:
            New plan dictionary
        """
        error_summary = "\n".join([
            f"- Task {task_id}: {error_info.get(task_id, 'Unknown error')}"
            for task_id in failed_tasks
        ])

        prompt = f"""You are a supervisor agent. Some tasks failed during execution and need replanning.

Original Request: {original_request}

Failed Tasks:
{error_summary}

Original Plan:
{json.dumps(original_plan, indent=2)}

Create a new plan to complete the request, taking into account the failures.
You can:
1. Retry failed tasks with different parameters
2. Use alternative tools/agents
3. Break down tasks differently
4. Adjust the strategy

Return the same JSON structure as before.
"""

        try:
            response = await self.llm_client.generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096
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
                        for field_name, field_info in output_props.items():
                            field_type = field_info.get('type', 'any')
                            field_desc = field_info.get('description', '')
                            doc_lines.append(f"  - `{field_name}`: {field_type}")
                            if field_desc:
                                doc_lines.append(f"    {field_desc}")
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
   - Check the "Output Fields" section for each tool
   - If output is nested, use dot notation: `{{task_id.results.0.name}}`
   - Array indexing: `{{task_id.items.0}}` for first item

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

    def _build_agent_capabilities_summary(self) -> str:
        """Build a formatted summary of agent capabilities (legacy - kept for compatibility)"""
        summary_lines = []

        for agent_name, tools in self.available_agents.items():
            tool_names = [tool.name for tool in tools]
            summary_lines.append(f"**{agent_name}**: {', '.join(tool_names)}")

        return "\n".join(summary_lines)

    def _format_results_summary(self, results: Dict[str, Any]) -> str:
        """Format results dictionary as readable text"""
        if not results:
            return "No results available."

        summary_lines = []

        for agent_name, result_data in results.items():
            status = result_data.get('status', 'unknown')
            summary = result_data.get('summary', '')
            errors = result_data.get('errors', '')

            summary_lines.append(f"**{agent_name}**:")
            summary_lines.append(f"  Status: {status}")
            if summary:
                summary_lines.append(f"  Summary: {summary}")
            if errors:
                summary_lines.append(f"  Errors: {errors}")
            summary_lines.append("")

        return "\n".join(summary_lines)
