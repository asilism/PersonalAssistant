"""
Manus-style multi-agent system

This module implements a Manus-inspired architecture where:
1. A Supervisor agent plans and coordinates tasks
2. Specialized MCP agents execute tasks independently
3. Communication happens via Markdown files
4. Agents collaborate asynchronously
"""

from .md_communicator import MDCommunicator
from .supervisor import SupervisorAgent
from .agent_wrapper import MCPAgentWrapper
from .coordinator import ManusCoordinator

__all__ = [
    'MDCommunicator',
    'SupervisorAgent',
    'MCPAgentWrapper',
    'ManusCoordinator',
]
