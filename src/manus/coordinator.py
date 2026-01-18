"""
Manus Coordinator - Main orchestrator for Manus-style multi-agent system
"""

import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from orchestration.mcp_executor import MCPExecutor
from orchestration.config import ConfigLoader
from orchestration.types import OrchestrationSettings, ToolDefinition
from orchestration.placeholder_resolver import PlaceholderResolver
from orchestration.event_emitter import get_event_emitter

from .md_communicator import MDCommunicator
from .supervisor import SupervisorAgent
from .agent_wrapper import MCPAgentWrapper, AgentPool
from .retry_history import RetryHistory


class ManusCoordinator:
    """
    Manus Coordinator - Top-level orchestrator for the Manus system

    Workflow:
    1. Initialize session workspace
    2. Create supervisor agent
    3. Create MCP agent wrappers
    4. Supervisor analyzes request and creates plan
    5. Supervisor assigns tasks to agents (via MD files)
    6. Agents execute tasks concurrently
    7. Supervisor monitors progress and collects results
    8. Supervisor synthesizes final response
    """

    def __init__(
        self,
        user_id: str = "test_user",
        tenant: str = "test_tenant",
        workspace_base_path: Optional[Path] = None
    ):
        """
        Initialize Manus Coordinator

        Args:
            user_id: User identifier
            tenant: Tenant identifier
            workspace_base_path: Base path for workspaces (default: workspaces/)
        """
        self.user_id = user_id
        self.tenant = tenant

        # Workspace management
        if workspace_base_path is None:
            workspace_base_path = Path(__file__).parent.parent.parent / "workspaces"
        self.workspace_base_path = Path(workspace_base_path)
        self.workspace_base_path.mkdir(parents=True, exist_ok=True)

        # Session-specific components (initialized in run)
        self.session_id: Optional[str] = None
        self.workspace_path: Optional[Path] = None
        self.md_comm: Optional[MDCommunicator] = None
        self.supervisor: Optional[SupervisorAgent] = None
        self.agent_pool: Optional[AgentPool] = None
        self.mcp_executor: Optional[MCPExecutor] = None
        self.settings: Optional[OrchestrationSettings] = None
        self.placeholder_resolver: Optional[PlaceholderResolver] = None

        # Event emitter for real-time updates
        self.event_emitter = get_event_emitter()

        # Config loader
        self.config_loader = ConfigLoader()

        print(f"[ManusCoordinator] Initialized for {user_id}@{tenant}")

    async def run(
        self,
        request: str,
        session_id: Optional[str] = None,
        max_retries: int = 3,
        max_wait_time: int = 60
    ) -> Dict[str, Any]:
        """
        Execute a user request using Manus-style multi-agent system with automatic retry

        Args:
            request: User request text
            session_id: Optional session ID (generates new if not provided)
            max_retries: Maximum number of retries on failure (default: 3)
            max_wait_time: Maximum time to wait for agents (seconds)

        Returns:
            Dictionary with:
                - success: bool
                - message: str
                - results: dict (agent results)
                - final_response: str
                - session_id: str
                - retry_count: int (number of retries performed)
        """
        # Initialize session
        await self._initialize_session(session_id)

        print(f"[ManusCoordinator] Processing request: {request[:100]}...")

        # Emit execution started event
        await self.event_emitter.emit_execution_started(
            trace_id=self.session_id,
            session_id=self.session_id,
            request_text=request,
            user_id=self.user_id,
            tenant=self.tenant
        )

        try:
            # Step 1: Supervisor analyzes request
            print("[ManusCoordinator] Step 1: Analyzing request")
            await self.event_emitter.emit_step_started(
                trace_id=self.session_id,
                step_name="analyze_request",
                message="Analyzing request and identifying required capabilities"
            )
            analysis = await self.supervisor.analyze_request(request)
            await self.event_emitter.emit_step_completed(
                trace_id=self.session_id,
                step_name="analyze_request",
                message="Request analysis completed",
                result={"analysis": analysis}
            )

            # Step 2: Supervisor creates execution plan
            print("[ManusCoordinator] Step 2: Creating execution plan")
            await self.event_emitter.emit_step_started(
                trace_id=self.session_id,
                step_name="create_plan",
                message="Creating execution plan with task breakdown"
            )
            plan_data = await self.supervisor.create_plan(request, analysis)

            if 'error' not in plan_data:
                await self.event_emitter.emit_step_completed(
                    trace_id=self.session_id,
                    step_name="create_plan",
                    message=f"Execution plan created with {len(plan_data.get('tasks', []))} tasks",
                    result={"task_count": len(plan_data.get('tasks', []))}
                )

            if 'error' in plan_data:
                return {
                    'success': False,
                    'message': f"Planning failed: {plan_data['error']}",
                    'results': {},
                    'session_id': self.session_id
                }

            # Write initial plan to plan.md
            plan_content = {
                'request': request,
                'analysis': analysis,
                'tasks': plan_data.get('tasks', []),
                'progress': {
                    'total': len(plan_data.get('tasks', [])),
                    'completed': 0,
                    'in_progress': 0,
                    'pending': len(plan_data.get('tasks', [])),
                    'failed': 0
                }
            }
            await self.md_comm.write_plan(plan_content)

            # Emit plan created/updated event
            await self.event_emitter.emit_plan_created(
                trace_id=self.session_id,
                plan_id=self.session_id,
                steps=plan_data.get('tasks', []),
                total_steps=len(plan_data.get('tasks', []))
            )

            # Step 3: Start agent monitoring
            print("[ManusCoordinator] Step 3: Starting agent pool")
            await self.event_emitter.emit_step_started(
                trace_id=self.session_id,
                step_name="start_agents",
                message="Starting agent pool for task execution"
            )
            await self.agent_pool.start_all()
            await self.event_emitter.emit_step_completed(
                trace_id=self.session_id,
                step_name="start_agents",
                message=f"Agent pool started with {len(self.agent_pool.agents)} agents"
            )

            # Initialize retry tracking
            retry_history = RetryHistory()
            completed = False
            results = {}
            retry_count = 0
            completed_tasks = {}  # Cache for successfully completed tasks: {task_id: result}

            # Step 4: Retry loop
            for attempt in range(max_retries + 1):  # 0, 1, 2, 3 (total 4 attempts)
                if attempt > 0:
                    retry_count = attempt
                    print(f"\n[ManusCoordinator] 🔄 Retry attempt {attempt}/{max_retries}")

                # Execute tasks in dependency order
                attempt_label = f"Attempt {attempt + 1}/{max_retries + 1}"
                print(f"[ManusCoordinator] Step 4: Executing tasks ({attempt_label})")
                await self.event_emitter.emit_step_started(
                    trace_id=self.session_id,
                    step_name="execute_tasks",
                    message=f"Executing tasks in dependency order ({attempt_label})"
                )
                completed, results = await self._execute_tasks_with_dependencies(
                    plan_data,
                    max_wait_time=max_wait_time,
                    completed_tasks=completed_tasks
                )

                # Check if all tasks completed successfully
                if completed:
                    print(f"[ManusCoordinator] ✅ All tasks completed successfully!")
                    await self.event_emitter.emit_step_completed(
                        trace_id=self.session_id,
                        step_name="execute_tasks",
                        message="All tasks completed successfully",
                        result={"status": "success", "task_count": len(results)}
                    )
                    break

                # Collect failed tasks and errors
                print(f"[ManusCoordinator] ⚠️  Some tasks failed")
                failed_task_ids = []
                error_info = {}

                for agent_name, result in results.items():
                    if result.get('status') == 'failed':
                        task_id = result.get('task_id', agent_name)
                        error = result.get('errors', 'Unknown error')

                        failed_task_ids.append(task_id)
                        error_info[task_id] = error

                        print(f"[ManusCoordinator]   ❌ Task {task_id}: {error[:100]}...")

                        # Classify error type
                        error_type = self._classify_error_type(error)

                        if error_type == 'non_retryable':
                            print(f"[ManusCoordinator] 🛑 Task {task_id} has NON-RETRYABLE error - retry won't help")
                            print(f"[ManusCoordinator] 🛑 Error type: Environmental/system issue")
                            print(f"[ManusCoordinator] 💡 Suggestion: Check system requirements or use alternative approach")

                            # Build failure response
                            final_response = await self.supervisor.synthesize_final_response(
                                request, plan_data, results
                            )

                            await self.agent_pool.stop_all()

                            return {
                                'success': False,
                                'message': f'Task {task_id} failed with non-retryable error: {error[:200]}',
                                'results': results,
                                'final_response': final_response,
                                'session_id': self.session_id,
                                'workspace_path': str(self.workspace_path),
                                'retry_count': retry_count,
                                'failure_reason': 'non_retryable_error'
                            }

                        # Check for duplicate errors
                        if retry_history.is_duplicate_error(task_id, error):
                            print(f"[ManusCoordinator] 🛑 Task {task_id} has DUPLICATE error - same error as previous attempt")
                            print(f"[ManusCoordinator] 🛑 Stopping retries to prevent infinite loop")

                            # Build failure response
                            final_response = await self.supervisor.synthesize_final_response(
                                request, plan_data, results
                            )

                            await self.agent_pool.stop_all()

                            return {
                                'success': False,
                                'message': f'Task {task_id} failed with duplicate error after {attempt + 1} attempts',
                                'results': results,
                                'final_response': final_response,
                                'session_id': self.session_id,
                                'workspace_path': str(self.workspace_path),
                                'retry_count': retry_count,
                                'failure_reason': 'duplicate_error'
                            }

                        # Record this attempt in history
                        task_tool_calls = None
                        for task in plan_data.get('tasks', []):
                            if task.get('task_id') == task_id:
                                task_tool_calls = task.get('tool_calls', [])
                                break

                        retry_history.add_attempt(task_id, error, plan_data, task_tool_calls)

                # Check if we've exhausted retries
                if attempt >= max_retries:
                    print(f"[ManusCoordinator] 🛑 Maximum retries ({max_retries}) reached")
                    break

                # Step 5: Replan with error history
                print(f"[ManusCoordinator] Step 5: Replanning failed tasks with history awareness")
                print(f"[ManusCoordinator] Failed tasks: {failed_task_ids}")

                await self.event_emitter.emit_step_started(
                    trace_id=self.session_id,
                    step_name="replan",
                    message=f"Replanning {len(failed_task_ids)} failed tasks with error history"
                )

                new_plan = await self.supervisor.replan(
                    original_request=request,
                    original_plan=plan_data,
                    failed_tasks=failed_task_ids,
                    error_info=error_info,
                    retry_history=retry_history,
                    completed_tasks=completed_tasks
                )

                if 'error' in new_plan:
                    print(f"[ManusCoordinator] ⚠️  Replanning failed: {new_plan['error']}")
                    await self.event_emitter.emit_step_failed(
                        trace_id=self.session_id,
                        step_name="replan",
                        error=new_plan['error']
                    )
                    break

                # Update plan for next iteration
                plan_data = new_plan
                print(f"[ManusCoordinator] 📝 New plan created with {len(new_plan.get('tasks', []))} tasks")

                await self.event_emitter.emit_step_completed(
                    trace_id=self.session_id,
                    step_name="replan",
                    message=f"New plan created with {len(new_plan.get('tasks', []))} tasks",
                    result={"task_count": len(new_plan.get('tasks', []))}
                )

                # Debug: Log replanned tasks details
                for i, task in enumerate(new_plan.get('tasks', [])):
                    print(f"[ManusCoordinator]   Replanned Task {i+1}: {task.get('task_id')}")
                    for j, call in enumerate(task.get('tool_calls', [])):
                        print(f"[ManusCoordinator]     Call {j+1}: {call.get('tool')} - params: {list(call.get('params', {}).keys())}")
                        # Log parameter values for debugging (truncated)
                        for param_name, param_value in call.get('params', {}).items():
                            if isinstance(param_value, str) and len(param_value) > 100:
                                print(f"[ManusCoordinator]       {param_name}: {param_value[:100]}...")
                            else:
                                print(f"[ManusCoordinator]       {param_name}: {param_value}")

                # Update plan.md with retry information
                retry_plan_content = {
                    'request': request,
                    'analysis': analysis,
                    'tasks': plan_data.get('tasks', []),
                    'progress': {
                        'total': len(plan_data.get('tasks', [])),
                        'completed': 0,
                        'in_progress': 0,
                        'pending': len(plan_data.get('tasks', [])),
                        'failed': 0
                    },
                    'retry_attempt': attempt + 1
                }
                await self.md_comm.write_plan(retry_plan_content)

                # Emit plan updated event
                await self.event_emitter.emit_plan_updated(
                    trace_id=self.session_id,
                    plan_data=retry_plan_content
                )

            # Step 6: Supervisor synthesizes final response
            print("[ManusCoordinator] Step 6: Synthesizing final response")
            await self.event_emitter.emit_step_started(
                trace_id=self.session_id,
                step_name="synthesize_response",
                message="Synthesizing final response from agent results"
            )
            final_response = await self.supervisor.synthesize_final_response(
                request, plan_data, results
            )
            await self.event_emitter.emit_step_completed(
                trace_id=self.session_id,
                step_name="synthesize_response",
                message="Final response synthesized"
            )

            # Update plan with final results
            final_plan_content = {
                'request': request,
                'analysis': analysis,
                'tasks': plan_data.get('tasks', []),
                'progress': {
                    'total': len(plan_data.get('tasks', [])),
                    'completed': sum(1 for r in results.values() if r.get('status') == 'completed'),
                    'in_progress': 0,
                    'pending': 0,
                    'failed': sum(1 for r in results.values() if r.get('status') == 'failed')
                },
                'results': final_response,
                'retry_count': retry_count
            }
            await self.md_comm.write_plan(final_plan_content)

            # Emit final plan updated event
            await self.event_emitter.emit_plan_updated(
                trace_id=self.session_id,
                plan_data=final_plan_content
            )

            # Stop agents
            await self.agent_pool.stop_all()

            success_message = 'Request completed'
            if retry_count > 0:
                success_message += f' after {retry_count} retry attempts'
            elif not completed:
                success_message = 'Request partially completed'

            # Emit execution completed event
            await self.event_emitter.emit_execution_completed(
                trace_id=self.session_id,
                message=success_message,
                data={
                    "results": results,
                    "final_response": final_response,
                    "workspace_path": str(self.workspace_path),
                    "retry_count": retry_count,
                    "success": completed
                }
            )

            return {
                'success': completed,
                'message': success_message,
                'results': results,
                'final_response': final_response,
                'session_id': self.session_id,
                'workspace_path': str(self.workspace_path),
                'retry_count': retry_count
            }

        except Exception as e:
            print(f"[ManusCoordinator] Error during execution: {e}")
            import traceback
            traceback.print_exc()

            # Emit execution error event
            await self.event_emitter.emit_execution_error(
                trace_id=self.session_id,
                error=str(e),
                error_type=type(e).__name__
            )

            # Stop agents on error
            if self.agent_pool:
                await self.agent_pool.stop_all()

            return {
                'success': False,
                'message': f"Execution failed: {str(e)}",
                'results': {},
                'session_id': self.session_id,
                'error': str(e)
            }

    async def _initialize_session(self, session_id: Optional[str] = None):
        """Initialize a session with workspace and agents"""
        # Generate session ID if not provided
        if session_id is None:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        self.session_id = session_id
        self.workspace_path = self.workspace_base_path / session_id

        print(f"[ManusCoordinator] Initializing session: {session_id}")
        print(f"[ManusCoordinator] Workspace: {self.workspace_path}")

        # Create MD communicator
        self.md_comm = MDCommunicator(self.workspace_path)
        await self.md_comm.initialize()

        # Load settings
        self.settings = await self.config_loader.get_settings(self.user_id, self.tenant)

        # Initialize MCP executor
        self.mcp_executor = MCPExecutor(self.user_id, self.tenant)
        await self.mcp_executor.initialize_servers()

        # Discover available tools
        available_tools = await self.mcp_executor.discover_tools()
        print(f"[ManusCoordinator] Discovered {len(available_tools)} tools from MCP servers")

        # Group tools by agent (based on tool-server mapping)
        tool_server_map = self.mcp_executor.get_tool_server_map()
        agent_tools: Dict[str, List[ToolDefinition]] = {}

        for tool in available_tools:
            server_name = tool_server_map.get(tool.name)
            if server_name:
                if server_name not in agent_tools:
                    agent_tools[server_name] = []
                agent_tools[server_name].append(tool)

        print(f"[ManusCoordinator] Organized tools into {len(agent_tools)} agents")

        # Create shared placeholder resolver for cross-task references
        self.placeholder_resolver = PlaceholderResolver()
        print("[ManusCoordinator] Created shared PlaceholderResolver for cross-task references")

        # Create supervisor
        self.supervisor = SupervisorAgent(
            settings=self.settings,
            md_communicator=self.md_comm,
            available_agents=agent_tools
        )

        # Create agent pool with wrappers (all sharing the same resolver)
        self.agent_pool = AgentPool()

        for agent_name in agent_tools.keys():
            agent_wrapper = MCPAgentWrapper(
                agent_name=agent_name,
                mcp_executor=self.mcp_executor,
                md_communicator=self.md_comm,
                placeholder_resolver=self.placeholder_resolver,  # Shared resolver!
                poll_interval=0.5  # Check every 0.5 seconds
            )
            self.agent_pool.add_agent(agent_wrapper)

        print(f"[ManusCoordinator] Session initialized with {len(agent_tools)} agents (shared resolver)")

    async def _execute_tasks_with_dependencies(
        self,
        plan_data: Dict[str, Any],
        max_wait_time: int = 60,
        completed_tasks: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Execute tasks in dependency order, skipping already completed tasks

        Args:
            plan_data: Plan data with tasks
            max_wait_time: Maximum time to wait per task (seconds)
            completed_tasks: Dict of already completed tasks {task_id: result}

        Returns:
            Tuple of (all_completed, results)
        """
        if completed_tasks is None:
            completed_tasks = {}
        tasks = plan_data.get('tasks', [])
        if not tasks:
            return True, {}

        # Sort tasks by dependencies (topological sort)
        sorted_tasks = self._topological_sort_tasks(tasks)

        print(f"[ManusCoordinator] Executing {len(sorted_tasks)} tasks in dependency order")
        for i, task in enumerate(sorted_tasks):
            print(f"  {i+1}. {task['task_id']} (agent: {task.get('agent')}, deps: {task.get('dependencies', [])})")

        all_results = {}
        all_success = True

        for task in sorted_tasks:
            task_id = task['task_id']
            agent_name = task.get('agent')

            if not agent_name:
                print(f"[ManusCoordinator] Warning: Task {task_id} has no agent assigned, skipping")
                all_success = False
                continue

            # Check if this task was already completed successfully in a previous attempt
            if task_id in completed_tasks:
                cached_result = completed_tasks[task_id]
                all_results[agent_name] = cached_result
                print(f"\n[ManusCoordinator] ⚡ Task {task_id} already completed - using cached result")
                print(f"[ManusCoordinator]    Status: {cached_result.get('status')}")
                continue

            print(f"\n[ManusCoordinator] === Assigning task {task_id} to agent {agent_name} ===")

            # Clear any previous task files for this agent to avoid stale task detection
            await self.md_comm.clear_agent_task(agent_name)

            # Assign this task to its agent
            await self.supervisor.assign_tasks({'tasks': [task]})

            # Wait for this specific agent to complete
            completed, result = await self._wait_for_agent(
                agent_name,
                task_id,
                max_wait_time=max_wait_time
            )

            if completed and result:
                all_results[agent_name] = result
                # Cache this successful result for future retries
                completed_tasks[task_id] = result
                print(f"[ManusCoordinator] ✓ Task {task_id} completed successfully (cached for retries)")
            else:
                all_success = False
                if result:
                    all_results[agent_name] = result
                print(f"[ManusCoordinator] ✗ Task {task_id} failed or timed out")

        return all_success, all_results

    def _topological_sort_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort tasks in dependency order using topological sort

        Args:
            tasks: List of task dictionaries

        Returns:
            Sorted list of tasks
        """
        # Build task ID to task mapping
        task_map = {task['task_id']: task for task in tasks}

        # Build dependency graph
        in_degree = {task['task_id']: 0 for task in tasks}
        adjacency = {task['task_id']: [] for task in tasks}

        for task in tasks:
            task_id = task['task_id']
            dependencies = task.get('dependencies', [])
            in_degree[task_id] = len(dependencies)

            for dep in dependencies:
                if dep in adjacency:
                    adjacency[dep].append(task_id)

        # Kahn's algorithm for topological sort
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        sorted_task_ids = []

        while queue:
            current = queue.pop(0)
            sorted_task_ids.append(current)

            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(sorted_task_ids) != len(tasks):
            print("[ManusCoordinator] Warning: Circular dependency detected in tasks!")
            # Return original order as fallback
            return tasks

        # Convert task IDs back to task objects
        return [task_map[task_id] for task_id in sorted_task_ids]

    async def _wait_for_agent(
        self,
        agent_name: str,
        task_id: str,
        max_wait_time: int = 60,
        check_interval: float = 0.5
    ) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Wait for a specific agent to complete its current task

        Args:
            agent_name: Name of the agent
            task_id: Task ID being executed
            max_wait_time: Maximum time to wait (seconds)
            check_interval: How often to check progress (seconds)

        Returns:
            Tuple of (completed, result)
        """
        elapsed = 0.0

        while elapsed < max_wait_time:
            # Check if agent has result
            result = await self.md_comm.read_result(agent_name)

            if result and result.get('task_id') == task_id:
                status = result.get('status')
                if status in ('completed', 'failed'):
                    return status == 'completed', result

            # Wait before next check
            await asyncio.sleep(check_interval)
            elapsed += check_interval

        # Timeout
        print(f"[ManusCoordinator] Timeout waiting for agent {agent_name} (task {task_id})")
        result = await self.md_comm.read_result(agent_name)
        return False, result

    async def _wait_for_completion(
        self,
        plan_data: Dict[str, Any],
        max_wait_time: int = 60,
        check_interval: float = 1.0
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Wait for all agents to complete their tasks (legacy method)

        Args:
            plan_data: Plan data with tasks
            max_wait_time: Maximum time to wait (seconds)
            check_interval: How often to check progress (seconds)

        Returns:
            Tuple of (all_completed, results)
        """
        tasks = plan_data.get('tasks', [])
        num_tasks = len(tasks)

        if num_tasks == 0:
            return True, {}

        # Build expected agents set
        expected_agents = set(task.get('agent') for task in tasks)

        print(f"[ManusCoordinator] Waiting for {len(expected_agents)} agents to complete {num_tasks} tasks")
        print(f"[ManusCoordinator] Expected agents: {expected_agents}")

        elapsed = 0.0
        while elapsed < max_wait_time:
            # Check progress
            agent_statuses = await self.supervisor.monitor_progress()

            # Count completed/failed
            completed_count = sum(1 for status in agent_statuses.values() if status in ('completed', 'failed'))

            print(f"[ManusCoordinator] Progress: {completed_count}/{len(expected_agents)} agents finished (elapsed: {elapsed:.1f}s)")

            # Check if all expected agents have completed
            if all(agent_statuses.get(agent) in ('completed', 'failed') for agent in expected_agents):
                print("[ManusCoordinator] All agents finished!")
                results = await self.supervisor.collect_results()

                # Check if all succeeded
                all_success = all(
                    results.get(agent, {}).get('status') == 'completed'
                    for agent in expected_agents
                )

                return all_success, results

            # Wait before next check
            await asyncio.sleep(check_interval)
            elapsed += check_interval

        # Timeout - collect whatever results we have
        print(f"[ManusCoordinator] Timeout after {max_wait_time}s - collecting partial results")
        results = await self.supervisor.collect_results()

        return False, results

    async def cleanup(self):
        """Cleanup resources"""
        if self.agent_pool:
            await self.agent_pool.stop_all()

        if self.mcp_executor:
            await self.mcp_executor.cleanup()

        print(f"[ManusCoordinator] Cleanup completed")

    def _classify_error_type(self, error_message: str) -> str:
        """
        Classify error type to determine if retry is worthwhile

        Args:
            error_message: Error message from failed task

        Returns:
            'non_retryable' if error indicates retry won't help,
            'retryable' otherwise
        """
        error_lower = error_message.lower()

        # Non-retryable errors (environmental/system issues)
        non_retryable_patterns = [
            'no suitable media player found',
            'please install mpv or vlc',
            'no mcp server found for tool',
            'tool not found',
            'agent not found',
            'permission denied',
            'not authorized',
        ]

        for pattern in non_retryable_patterns:
            if pattern in error_lower:
                return 'non_retryable'

        # Default: assume retryable (network issues, timeouts, etc.)
        return 'retryable'

    # ========== Utility Methods ==========

    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information"""
        return {
            'session_id': self.session_id,
            'workspace_path': str(self.workspace_path) if self.workspace_path else None,
            'user_id': self.user_id,
            'tenant': self.tenant,
            'agents': self.agent_pool.list_agents() if self.agent_pool else []
        }

    async def get_plan_status(self) -> Optional[Dict[str, Any]]:
        """Get current plan status from plan.md"""
        if not self.md_comm:
            return None

        return await self.md_comm.read_plan()

    async def get_agent_statuses(self) -> Dict[str, str]:
        """Get status of all agents"""
        if not self.supervisor:
            return {}

        return await self.supervisor.monitor_progress()
