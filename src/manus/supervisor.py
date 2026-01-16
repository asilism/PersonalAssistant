"""
Supervisor Agent - Plans and coordinates multi-agent tasks
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from ..orchestration.llm_client import create_llm_client, LLMClient
from ..orchestration.types import OrchestrationSettings, ToolDefinition
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
        # Build agent capabilities summary
        agent_capabilities = self._build_agent_capabilities_summary()

        prompt = f"""You are a supervisor agent coordinating multiple specialized agents.

User Request: {request}

Analysis: {analysis}

Available Agents and Their Capabilities:
{agent_capabilities}

Create an execution plan by breaking down the request into tasks for specialized agents.

Requirements:
1. Each task should be assigned to ONE specific agent
2. Tasks should be atomic and focused
3. Specify tool calls for each task
4. Identify dependencies between tasks
5. Set priority (high/medium/low)

Return a JSON object with this structure:
{{
  "tasks": [
    {{
      "task_id": "unique_id",
      "name": "Task name",
      "agent": "agent_name",
      "description": "What needs to be done",
      "priority": "high|medium|low",
      "dependencies": ["task_id1", "task_id2"],
      "tool_calls": [
        {{
          "tool": "tool_name",
          "params": {{}}
        }}
      ]
    }}
  ],
  "execution_strategy": "sequential|parallel|mixed",
  "estimated_steps": 3
}}

IMPORTANT: Return ONLY valid JSON, no markdown code blocks or explanations.
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

    def _build_agent_capabilities_summary(self) -> str:
        """Build a formatted summary of agent capabilities"""
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
