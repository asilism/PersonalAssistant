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

from .md_communicator import MDCommunicator
from .supervisor import SupervisorAgent
from .agent_wrapper import MCPAgentWrapper, AgentPool


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

        # Config loader
        self.config_loader = ConfigLoader()

        print(f"[ManusCoordinator] Initialized for {user_id}@{tenant}")

    async def run(
        self,
        request: str,
        session_id: Optional[str] = None,
        max_iterations: int = 3,
        max_wait_time: int = 60
    ) -> Dict[str, Any]:
        """
        Execute a user request using Manus-style multi-agent system

        Args:
            request: User request text
            session_id: Optional session ID (generates new if not provided)
            max_iterations: Maximum replanning iterations on failure
            max_wait_time: Maximum time to wait for agents (seconds)

        Returns:
            Dictionary with:
                - success: bool
                - message: str
                - results: dict (agent results)
                - final_response: str
                - session_id: str
        """
        # Initialize session
        await self._initialize_session(session_id)

        print(f"[ManusCoordinator] Processing request: {request[:100]}...")

        try:
            # Step 1: Supervisor analyzes request
            print("[ManusCoordinator] Step 1: Analyzing request")
            analysis = await self.supervisor.analyze_request(request)

            # Step 2: Supervisor creates execution plan
            print("[ManusCoordinator] Step 2: Creating execution plan")
            plan_data = await self.supervisor.create_plan(request, analysis)

            if 'error' in plan_data:
                return {
                    'success': False,
                    'message': f"Planning failed: {plan_data['error']}",
                    'results': {},
                    'session_id': self.session_id
                }

            # Write plan to plan.md
            await self.md_comm.write_plan({
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
            })

            # Step 3: Start agent monitoring
            print("[ManusCoordinator] Step 3: Starting agent pool")
            await self.agent_pool.start_all()

            # Step 4: Assign tasks to agents
            print("[ManusCoordinator] Step 4: Assigning tasks to agents")
            await self.supervisor.assign_tasks(plan_data)

            # Step 5: Monitor progress and wait for completion
            print("[ManusCoordinator] Step 5: Monitoring agent progress")
            completed, results = await self._wait_for_completion(
                plan_data,
                max_wait_time=max_wait_time
            )

            # Step 6: Handle failures and replanning
            if not completed:
                print("[ManusCoordinator] Some tasks failed, considering replanning...")
                # TODO: Implement replanning logic
                # For now, just collect whatever results we have

            # Step 7: Supervisor synthesizes final response
            print("[ManusCoordinator] Step 7: Synthesizing final response")
            final_response = await self.supervisor.synthesize_final_response(
                request, plan_data, results
            )

            # Update plan with final results
            await self.md_comm.write_plan({
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
                'results': final_response
            })

            # Stop agents
            await self.agent_pool.stop_all()

            return {
                'success': completed,
                'message': 'Request completed' if completed else 'Request partially completed',
                'results': results,
                'final_response': final_response,
                'session_id': self.session_id,
                'workspace_path': str(self.workspace_path)
            }

        except Exception as e:
            print(f"[ManusCoordinator] Error during execution: {e}")
            import traceback
            traceback.print_exc()

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

        # Create supervisor
        self.supervisor = SupervisorAgent(
            settings=self.settings,
            md_communicator=self.md_comm,
            available_agents=agent_tools
        )

        # Create agent pool with wrappers
        self.agent_pool = AgentPool()

        for agent_name in agent_tools.keys():
            agent_wrapper = MCPAgentWrapper(
                agent_name=agent_name,
                mcp_executor=self.mcp_executor,
                md_communicator=self.md_comm,
                poll_interval=0.5  # Check every 0.5 seconds
            )
            self.agent_pool.add_agent(agent_wrapper)

        print(f"[ManusCoordinator] Session initialized with {len(agent_tools)} agents")

    async def _wait_for_completion(
        self,
        plan_data: Dict[str, Any],
        max_wait_time: int = 60,
        check_interval: float = 1.0
    ) -> tuple[bool, Dict[str, Any]]:
        """
        Wait for all agents to complete their tasks

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
