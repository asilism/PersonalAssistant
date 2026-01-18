"""
MD Communicator - Handles Markdown file-based communication between agents
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
import aiofiles
from aiofiles import os as aio_os


class MDCommunicator:
    """
    MDCommunicator - Manages reading/writing markdown files for agent communication

    Features:
    - Async file I/O
    - File locking for concurrent access
    - Structured MD parsing/writing
    - File change monitoring
    """

    def __init__(self, workspace_path: Path):
        """
        Initialize MD Communicator

        Args:
            workspace_path: Path to workspace directory (e.g., workspaces/{session_id})
        """
        self.workspace_path = Path(workspace_path)
        self.plan_file = self.workspace_path / "plan.md"
        self.tasks_dir = self.workspace_path / "tasks"
        self.logs_dir = self.workspace_path / "logs"

        # File locks
        self._locks: Dict[str, asyncio.Lock] = {}

    async def initialize(self):
        """Create workspace directory structure"""
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        print(f"[MDCommunicator] Initialized workspace at {self.workspace_path}")

    def _get_lock(self, file_path: str) -> asyncio.Lock:
        """Get or create lock for a file"""
        if file_path not in self._locks:
            self._locks[file_path] = asyncio.Lock()
        return self._locks[file_path]

    async def write_plan(self, plan_data: Dict[str, Any]) -> None:
        """
        Write execution plan to plan.md

        Args:
            plan_data: Dictionary containing:
                - request: User request
                - analysis: Supervisor's analysis
                - tasks: List of tasks
                - progress: Progress summary
                - results: Final results (optional)
        """
        lock = self._get_lock(str(self.plan_file))
        async with lock:
            content = self._format_plan_md(plan_data)
            async with aiofiles.open(self.plan_file, 'w', encoding='utf-8') as f:
                await f.write(content)
        print(f"[MDCommunicator] Plan written to {self.plan_file}")

    async def read_plan(self) -> Optional[Dict[str, Any]]:
        """
        Read execution plan from plan.md

        Returns:
            Dictionary with plan data or None if file doesn't exist
        """
        if not self.plan_file.exists():
            return None

        lock = self._get_lock(str(self.plan_file))
        async with lock:
            async with aiofiles.open(self.plan_file, 'r', encoding='utf-8') as f:
                content = await f.read()

        return self._parse_plan_md(content)

    async def write_task(self, agent_name: str, task_data: Dict[str, Any]) -> None:
        """
        Write task assignment to tasks/{agent}/task.md

        Args:
            agent_name: Name of the agent
            task_data: Dictionary containing:
                - task_id: Unique task ID
                - description: Task description
                - tool_calls: List of tool calls
                - status: Task status
        """
        agent_dir = self.tasks_dir / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)

        task_file = agent_dir / "task.md"
        lock = self._get_lock(str(task_file))

        async with lock:
            content = self._format_task_md(task_data)
            async with aiofiles.open(task_file, 'w', encoding='utf-8') as f:
                await f.write(content)

        print(f"[MDCommunicator] Task written to {task_file}")

    async def read_task(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Read task assignment from tasks/{agent}/task.md

        Args:
            agent_name: Name of the agent

        Returns:
            Dictionary with task data or None if file doesn't exist
        """
        task_file = self.tasks_dir / agent_name / "task.md"
        if not task_file.exists():
            return None

        lock = self._get_lock(str(task_file))
        async with lock:
            async with aiofiles.open(task_file, 'r', encoding='utf-8') as f:
                content = await f.read()

        return self._parse_task_md(content)

    async def write_result(self, agent_name: str, result_data: Dict[str, Any]) -> None:
        """
        Write task result to tasks/{agent}/result.md

        Args:
            agent_name: Name of the agent
            result_data: Dictionary containing:
                - task_id: Task ID
                - status: Execution status
                - results: List of tool call results
                - summary: Summary text
                - errors: Error messages (optional)
        """
        agent_dir = self.tasks_dir / agent_name
        agent_dir.mkdir(parents=True, exist_ok=True)

        result_file = agent_dir / "result.md"
        lock = self._get_lock(str(result_file))

        async with lock:
            content = self._format_result_md(result_data)
            async with aiofiles.open(result_file, 'w', encoding='utf-8') as f:
                await f.write(content)

        print(f"[MDCommunicator] Result written to {result_file}")

    async def read_result(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """
        Read task result from tasks/{agent}/result.md

        Args:
            agent_name: Name of the agent

        Returns:
            Dictionary with result data or None if file doesn't exist
        """
        result_file = self.tasks_dir / agent_name / "result.md"
        if not result_file.exists():
            return None

        lock = self._get_lock(str(result_file))
        async with lock:
            async with aiofiles.open(result_file, 'r', encoding='utf-8') as f:
                content = await f.read()

        return self._parse_result_md(content)

    async def update_task_status(self, agent_name: str, status: str) -> None:
        """
        Update task status in task.md file

        Args:
            agent_name: Name of the agent
            status: New status (pending, in_progress, completed, failed)
        """
        task_data = await self.read_task(agent_name)
        if task_data:
            task_data['status'] = status
            await self.write_task(agent_name, task_data)

    async def list_agents_with_tasks(self) -> List[str]:
        """
        List all agents that have task assignments

        Returns:
            List of agent names
        """
        if not self.tasks_dir.exists():
            return []

        agents = []
        for agent_dir in self.tasks_dir.iterdir():
            if agent_dir.is_dir() and (agent_dir / "task.md").exists():
                agents.append(agent_dir.name)

        return agents

    async def clear_agent_task(self, agent_name: str) -> None:
        """
        Clear task and result files for an agent

        Args:
            agent_name: Name of the agent
        """
        agent_dir = self.tasks_dir / agent_name
        if agent_dir.exists():
            task_file = agent_dir / "task.md"
            result_file = agent_dir / "result.md"

            # Use async file deletion with retry logic for Windows file locking
            await self._safe_delete_file(task_file)
            await self._safe_delete_file(result_file)

            print(f"[MDCommunicator] Cleared task files for {agent_name}")

    async def _safe_delete_file(self, file_path: Path, max_retries: int = 5) -> None:
        """
        Safely delete a file with retry logic for Windows file locking issues

        Args:
            file_path: Path to file to delete
            max_retries: Maximum number of retry attempts (default: 5)
        """
        if not file_path.exists():
            return

        # Get lock for this file
        lock = self._get_lock(str(file_path))

        for attempt in range(max_retries):
            try:
                async with lock:
                    # Double-check file still exists
                    if file_path.exists():
                        # Use async file removal
                        await aio_os.remove(str(file_path))
                        return
                    else:
                        return  # Already deleted
            except PermissionError as e:
                if attempt < max_retries - 1:
                    # Wait with exponential backoff before retry
                    wait_time = 0.1 * (2 ** attempt)  # 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                    print(f"[MDCommunicator] File locked: {file_path.name}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    # Last attempt failed - log warning but don't crash
                    print(f"[MDCommunicator] Warning: Could not delete {file_path.name} after {max_retries} attempts: {e}")
                    print(f"[MDCommunicator] File may be locked by another process. Continuing anyway...")
            except Exception as e:
                # Other errors - log and continue
                print(f"[MDCommunicator] Warning: Error deleting {file_path.name}: {e}")
                return

    # ========== MD Formatting Methods ==========

    def _format_plan_md(self, plan_data: Dict[str, Any]) -> str:
        """Format plan data as Markdown"""
        request = plan_data.get('request', '')
        analysis = plan_data.get('analysis', '')
        tasks = plan_data.get('tasks', [])
        progress = plan_data.get('progress', {})
        results = plan_data.get('results', '')

        md = f"""# Execution Plan

## Request
{request}

## Analysis
{analysis}

## Task Breakdown

"""
        # Add tasks with checkbox format
        for i, task in enumerate(tasks, 1):
            task_name = task.get('name', f'Task {i}')
            agent = task.get('agent', 'unknown')
            status = task.get('status', 'pending')
            priority = task.get('priority', 'medium')
            dependencies = task.get('dependencies', [])
            description = task.get('description', '')

            # Determine checkbox state based on status
            if status == 'completed':
                checkbox = '[x]'
            else:
                checkbox = '[ ]'

            # Add status emoji
            status_emoji = {
                'pending': '⏳',
                'in_progress': '🔄',
                'completed': '✅',
                'failed': '❌'
            }.get(status, '📝')

            md += f"""### {checkbox} Task {i}: {task_name} {status_emoji}
- **Agent**: {agent}
- **Status**: {status}
- **Priority**: {priority}
- **Dependencies**: {json.dumps(dependencies)}
- **Description**: {description}

"""

        # Add progress
        md += f"""## Progress
- Total Tasks: {progress.get('total', len(tasks))}
- Completed: {progress.get('completed', 0)}
- In Progress: {progress.get('in_progress', 0)}
- Pending: {progress.get('pending', len(tasks))}
- Failed: {progress.get('failed', 0)}

"""

        # Add results if available
        if results:
            md += f"""## Results Summary
{results}
"""

        return md

    def _parse_plan_md(self, content: str) -> Dict[str, Any]:
        """Parse plan.md content into dictionary"""
        plan_data = {
            'request': '',
            'analysis': '',
            'tasks': [],
            'progress': {},
            'results': ''
        }

        # Extract request
        request_match = re.search(r'## Request\n(.*?)\n\n', content, re.DOTALL)
        if request_match:
            plan_data['request'] = request_match.group(1).strip()

        # Extract analysis
        analysis_match = re.search(r'## Analysis\n(.*?)\n\n', content, re.DOTALL)
        if analysis_match:
            plan_data['analysis'] = analysis_match.group(1).strip()

        # Extract tasks (with checkbox support)
        tasks_section = re.search(r'## Task Breakdown\n(.*?)## Progress', content, re.DOTALL)
        if tasks_section:
            # Updated regex to capture checkbox and emoji
            task_blocks = re.findall(r'### \[([ x])\] Task \d+: (.*?)\n(.*?)(?=###|##|\Z)', tasks_section.group(1), re.DOTALL)
            for checkbox, task_name, task_content in task_blocks:
                # Remove emoji from task name if present
                task_name_clean = re.sub(r'[⏳🔄✅❌📝]\s*$', '', task_name.strip())
                task = {'name': task_name_clean}

                # Parse task fields
                agent_match = re.search(r'- \*\*Agent\*\*: (.*)', task_content)
                status_match = re.search(r'- \*\*Status\*\*: (.*)', task_content)
                priority_match = re.search(r'- \*\*Priority\*\*: (.*)', task_content)
                deps_match = re.search(r'- \*\*Dependencies\*\*: (.*)', task_content)
                desc_match = re.search(r'- \*\*Description\*\*: (.*)', task_content)

                if agent_match:
                    task['agent'] = agent_match.group(1).strip()
                if status_match:
                    task['status'] = status_match.group(1).strip()
                if priority_match:
                    task['priority'] = priority_match.group(1).strip()
                if deps_match:
                    try:
                        task['dependencies'] = json.loads(deps_match.group(1).strip())
                    except:
                        task['dependencies'] = []
                if desc_match:
                    task['description'] = desc_match.group(1).strip()

                plan_data['tasks'].append(task)

        # Extract progress
        progress_section = re.search(r'## Progress\n(.*?)(?=##|\Z)', content, re.DOTALL)
        if progress_section:
            progress_text = progress_section.group(1)
            total_match = re.search(r'- Total Tasks: (\d+)', progress_text)
            completed_match = re.search(r'- Completed: (\d+)', progress_text)
            in_progress_match = re.search(r'- In Progress: (\d+)', progress_text)
            pending_match = re.search(r'- Pending: (\d+)', progress_text)
            failed_match = re.search(r'- Failed: (\d+)', progress_text)

            if total_match:
                plan_data['progress']['total'] = int(total_match.group(1))
            if completed_match:
                plan_data['progress']['completed'] = int(completed_match.group(1))
            if in_progress_match:
                plan_data['progress']['in_progress'] = int(in_progress_match.group(1))
            if pending_match:
                plan_data['progress']['pending'] = int(pending_match.group(1))
            if failed_match:
                plan_data['progress']['failed'] = int(failed_match.group(1))

        # Extract results
        results_match = re.search(r'## Results Summary\n(.*)', content, re.DOTALL)
        if results_match:
            plan_data['results'] = results_match.group(1).strip()

        return plan_data

    def _format_task_md(self, task_data: Dict[str, Any]) -> str:
        """Format task data as Markdown"""
        task_id = task_data.get('task_id', 'unknown')
        assigned_at = task_data.get('assigned_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        description = task_data.get('description', '')
        tool_calls = task_data.get('tool_calls', [])
        status = task_data.get('status', 'pending')

        md = f"""# Task Assignment

## Task ID
{task_id}

## Assigned At
{assigned_at}

## Description
{description}

## Tool Calls

"""
        # Add tool calls
        for i, call in enumerate(tool_calls, 1):
            tool_name = call.get('tool', 'unknown')
            params = call.get('params', {})

            md += f"""### Call {i}: {tool_name}
```json
{json.dumps(params, indent=2)}
```

"""

        md += f"""## Status
{status}
"""

        return md

    def _parse_task_md(self, content: str) -> Dict[str, Any]:
        """Parse task.md content into dictionary"""
        task_data = {
            'task_id': '',
            'assigned_at': '',
            'description': '',
            'tool_calls': [],
            'status': 'pending'
        }

        # Extract task ID
        task_id_match = re.search(r'## Task ID\n(.*?)\n', content)
        if task_id_match:
            task_data['task_id'] = task_id_match.group(1).strip()

        # Extract assigned at
        assigned_match = re.search(r'## Assigned At\n(.*?)\n', content)
        if assigned_match:
            task_data['assigned_at'] = assigned_match.group(1).strip()

        # Extract description
        desc_match = re.search(r'## Description\n(.*?)\n\n', content, re.DOTALL)
        if desc_match:
            task_data['description'] = desc_match.group(1).strip()

        # Extract tool calls
        tool_calls_section = re.search(r'## Tool Calls\n(.*?)## Status', content, re.DOTALL)
        if tool_calls_section:
            call_blocks = re.findall(r'### Call \d+: (.*?)\n```json\n(.*?)\n```', tool_calls_section.group(1), re.DOTALL)
            for tool_name, params_json in call_blocks:
                try:
                    params = json.loads(params_json)
                    task_data['tool_calls'].append({
                        'tool': tool_name.strip(),
                        'params': params
                    })
                except json.JSONDecodeError:
                    print(f"[MDCommunicator] Warning: Failed to parse params for {tool_name}")

        # Extract status
        status_match = re.search(r'## Status\n(.*?)(?:\n|$)', content)
        if status_match:
            task_data['status'] = status_match.group(1).strip()

        return task_data

    def _format_result_md(self, result_data: Dict[str, Any]) -> str:
        """Format result data as Markdown"""
        task_id = result_data.get('task_id', 'unknown')
        status = result_data.get('status', 'unknown')
        executed_at = result_data.get('executed_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        results = result_data.get('results', [])
        summary = result_data.get('summary', '')
        errors = result_data.get('errors', '')

        md = f"""# Task Result

## Task ID
{task_id}

## Status
{status}

## Executed At
{executed_at}

## Results

"""
        # Add results
        for i, result in enumerate(results, 1):
            tool_name = result.get('tool', 'unknown')
            output = result.get('output', {})

            md += f"""### Call {i}: {tool_name}
```json
{json.dumps(output, indent=2)}
```

"""

        md += f"""## Summary
{summary}

## Errors
{errors if errors else 'None'}
"""

        return md

    def _parse_result_md(self, content: str) -> Dict[str, Any]:
        """Parse result.md content into dictionary"""
        result_data = {
            'task_id': '',
            'status': '',
            'executed_at': '',
            'results': [],
            'summary': '',
            'errors': ''
        }

        # Extract task ID
        task_id_match = re.search(r'## Task ID\n(.*?)\n', content)
        if task_id_match:
            result_data['task_id'] = task_id_match.group(1).strip()

        # Extract status
        status_match = re.search(r'## Status\n(.*?)\n', content)
        if status_match:
            result_data['status'] = status_match.group(1).strip()

        # Extract executed at
        executed_match = re.search(r'## Executed At\n(.*?)\n', content)
        if executed_match:
            result_data['executed_at'] = executed_match.group(1).strip()

        # Extract results
        results_section = re.search(r'## Results\n(.*?)## Summary', content, re.DOTALL)
        if results_section:
            result_blocks = re.findall(r'### Call \d+: (.*?)\n```json\n(.*?)\n```', results_section.group(1), re.DOTALL)
            for tool_name, output_json in result_blocks:
                try:
                    output = json.loads(output_json)
                    result_data['results'].append({
                        'tool': tool_name.strip(),
                        'output': output
                    })
                except json.JSONDecodeError:
                    print(f"[MDCommunicator] Warning: Failed to parse output for {tool_name}")

        # Extract summary
        summary_match = re.search(r'## Summary\n(.*?)\n\n## Errors', content, re.DOTALL)
        if summary_match:
            result_data['summary'] = summary_match.group(1).strip()

        # Extract errors
        errors_match = re.search(r'## Errors\n(.*?)(?:\n|$)', content, re.DOTALL)
        if errors_match:
            errors_text = errors_match.group(1).strip()
            result_data['errors'] = errors_text if errors_text != 'None' else ''

        return result_data
