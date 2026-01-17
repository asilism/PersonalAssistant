"""
MCP Agent Wrapper - Wraps MCP servers as independent agents
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from orchestration.mcp_executor import MCPExecutor
from orchestration.types import Step, StepResult
from orchestration.placeholder_resolver import PlaceholderResolver
from .md_communicator import MDCommunicator


class MCPAgentWrapper:
    """
    MCP Agent Wrapper - Wraps an MCP server as an independent agent

    Responsibilities:
    1. Monitor task.md file for new assignments
    2. Execute tasks using MCP tools
    3. Write results to result.md
    4. Handle errors and retries
    """

    def __init__(
        self,
        agent_name: str,
        mcp_executor: MCPExecutor,
        md_communicator: MDCommunicator,
        placeholder_resolver: Optional[PlaceholderResolver] = None,
        poll_interval: float = 1.0
    ):
        """
        Initialize MCP Agent Wrapper

        Args:
            agent_name: Name of this agent (e.g., 'browser', 'filesystem')
            mcp_executor: MCP executor for calling MCP tools
            md_communicator: MD file communication manager
            placeholder_resolver: Resolver for cross-task placeholders (optional)
            poll_interval: How often to check for new tasks (seconds)
        """
        self.agent_name = agent_name
        self.mcp_executor = mcp_executor
        self.md_comm = md_communicator
        self.resolver = placeholder_resolver  # Shared resolver for cross-task references
        self.poll_interval = poll_interval

        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._current_task_id: Optional[str] = None

        print(f"[MCPAgentWrapper:{agent_name}] Initialized with{'out' if not placeholder_resolver else ''} placeholder resolver")

    async def start_monitoring(self):
        """Start monitoring for tasks"""
        if self._running:
            print(f"[MCPAgentWrapper:{self.agent_name}] Already monitoring")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        print(f"[MCPAgentWrapper:{self.agent_name}] Started monitoring")

    async def stop_monitoring(self):
        """Stop monitoring for tasks"""
        if not self._running:
            return

        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        print(f"[MCPAgentWrapper:{self.agent_name}] Stopped monitoring")

    async def _monitor_loop(self):
        """Main monitoring loop"""
        print(f"[MCPAgentWrapper:{self.agent_name}] Entering monitor loop")

        while self._running:
            try:
                # Check for new task
                task_data = await self.md_comm.read_task(self.agent_name)

                if task_data and task_data.get('status') == 'pending':
                    task_id = task_data.get('task_id')

                    # Avoid re-executing same task
                    if task_id != self._current_task_id:
                        print(f"[MCPAgentWrapper:{self.agent_name}] New task detected: {task_id}")
                        self._current_task_id = task_id

                        # Update status to in_progress
                        await self.md_comm.update_task_status(self.agent_name, 'in_progress')

                        # Execute task
                        result_data = await self.execute_task(task_data)

                        # Write result
                        await self.md_comm.write_result(self.agent_name, result_data)

                        # Update task status to completed/failed
                        final_status = result_data.get('status', 'failed')
                        await self.md_comm.update_task_status(self.agent_name, final_status)

                        print(f"[MCPAgentWrapper:{self.agent_name}] Task {task_id} completed with status: {final_status}")

                # Sleep before next check
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                print(f"[MCPAgentWrapper:{self.agent_name}] Monitor loop cancelled")
                break
            except Exception as e:
                print(f"[MCPAgentWrapper:{self.agent_name}] Error in monitor loop: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(self.poll_interval)

    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task by calling MCP tools

        Args:
            task_data: Task data from task.md

        Returns:
            Result data to write to result.md
        """
        task_id = task_data.get('task_id', 'unknown')
        tool_calls = task_data.get('tool_calls', [])

        print(f"[MCPAgentWrapper:{self.agent_name}] Executing task {task_id} with {len(tool_calls)} tool calls")

        results = []
        errors = []
        all_success = True

        for i, call in enumerate(tool_calls):
            tool_name = call.get('tool')
            params = call.get('params', {})

            try:
                # Create Step object for MCP executor
                step = Step(
                    step_id=f"{task_id}_call_{i+1}",
                    tool_name=tool_name,
                    input=params,
                    description=f"Execute {tool_name} for task {task_id}"
                )

                # Resolve placeholders if resolver is available
                if self.resolver:
                    print(f"[MCPAgentWrapper:{self.agent_name}] Resolving placeholders for {tool_name}")
                    resolved_step = self.resolver.resolve_step_input(step)
                    print(f"[MCPAgentWrapper:{self.agent_name}] Resolved params: {resolved_step.input}")
                else:
                    resolved_step = step
                    print(f"[MCPAgentWrapper:{self.agent_name}] Calling tool {tool_name} with params: {params}")

                # Execute via MCP executor
                step_result: StepResult = await self.mcp_executor.execute_step(resolved_step)

                # Record result
                if step_result.status == "success":
                    results.append({
                        'tool': tool_name,
                        'output': step_result.output
                    })
                    print(f"[MCPAgentWrapper:{self.agent_name}] Tool {tool_name} succeeded")

                    # Register successful step output for future placeholder resolution
                    if self.resolver and step_result.output is not None:
                        self.resolver.register_step_result(step.step_id, step_result.output)
                        print(f"[MCPAgentWrapper:{self.agent_name}] Registered result for {step.step_id}")
                else:
                    all_success = False
                    error_msg = step_result.error or "Unknown error"
                    errors.append(f"{tool_name}: {error_msg}")
                    results.append({
                        'tool': tool_name,
                        'output': {'error': error_msg}
                    })
                    print(f"[MCPAgentWrapper:{self.agent_name}] Tool {tool_name} failed: {error_msg}")

            except Exception as e:
                all_success = False
                error_msg = str(e)
                errors.append(f"{tool_name}: {error_msg}")
                results.append({
                    'tool': tool_name,
                    'output': {'error': error_msg}
                })
                print(f"[MCPAgentWrapper:{self.agent_name}] Exception executing {tool_name}: {e}")
                import traceback
                traceback.print_exc()

        # Build result data
        status = "completed" if all_success else "failed"
        summary = self._build_summary(task_data, results, all_success)

        result_data = {
            'task_id': task_id,
            'status': status,
            'executed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'results': results,
            'summary': summary,
            'errors': "\n".join(errors) if errors else ""
        }

        return result_data

    async def execute_single_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """
        Execute a single MCP tool (utility method)

        Args:
            tool_name: Name of the tool
            params: Tool parameters

        Returns:
            Tool output
        """
        step = Step(
            step_id=f"manual_{tool_name}_{datetime.now().timestamp()}",
            tool_name=tool_name,
            input=params,
            description=f"Manual execution of {tool_name}"
        )

        step_result = await self.mcp_executor.execute_step(step)

        if step_result.status == "success":
            return step_result.output
        else:
            raise Exception(f"Tool {tool_name} failed: {step_result.error}")

    def _build_summary(
        self,
        task_data: Dict[str, Any],
        results: List[Dict[str, Any]],
        all_success: bool
    ) -> str:
        """Build a human-readable summary of task execution"""
        description = task_data.get('description', 'No description')
        num_tools = len(results)
        num_succeeded = sum(1 for r in results if 'error' not in r.get('output', {}))

        if all_success:
            summary = f"Successfully completed task: {description}. Executed {num_tools} tool call(s)."
        else:
            summary = f"Task partially completed: {description}. {num_succeeded}/{num_tools} tool call(s) succeeded."

        # Add key results if available
        key_results = []
        for result in results:
            output = result.get('output', {})
            if isinstance(output, dict):
                # Extract interesting fields
                if 'result' in output:
                    key_results.append(str(output['result'])[:100])
                elif 'message' in output:
                    key_results.append(str(output['message'])[:100])

        if key_results:
            summary += f" Key results: {', '.join(key_results[:3])}"

        return summary

    def is_monitoring(self) -> bool:
        """Check if agent is currently monitoring"""
        return self._running


class AgentPool:
    """
    Agent Pool - Manages multiple MCP Agent Wrappers

    Allows starting/stopping all agents at once
    """

    def __init__(self):
        self.agents: Dict[str, MCPAgentWrapper] = {}

    def add_agent(self, agent: MCPAgentWrapper):
        """Add an agent to the pool"""
        self.agents[agent.agent_name] = agent
        print(f"[AgentPool] Added agent: {agent.agent_name}")

    async def start_all(self):
        """Start monitoring on all agents"""
        print(f"[AgentPool] Starting {len(self.agents)} agents")

        tasks = [agent.start_monitoring() for agent in self.agents.values()]
        await asyncio.gather(*tasks)

        print(f"[AgentPool] All agents started")

    async def stop_all(self):
        """Stop monitoring on all agents"""
        print(f"[AgentPool] Stopping {len(self.agents)} agents")

        tasks = [agent.stop_monitoring() for agent in self.agents.values()]
        await asyncio.gather(*tasks)

        print(f"[AgentPool] All agents stopped")

    def get_agent(self, agent_name: str) -> Optional[MCPAgentWrapper]:
        """Get an agent by name"""
        return self.agents.get(agent_name)

    def list_agents(self) -> List[str]:
        """List all agent names"""
        return list(self.agents.keys())

    async def get_all_statuses(self) -> Dict[str, bool]:
        """Get monitoring status for all agents"""
        return {
            name: agent.is_monitoring()
            for name, agent in self.agents.items()
        }
