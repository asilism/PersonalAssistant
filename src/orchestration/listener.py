"""
ResultListener - Listens for and processes results
"""

from .types import StepResult
from .tracker import TaskTracker


class ResultListener:
    """ResultListener - Processes step results"""

    def __init__(self, tracker: TaskTracker):
        self.tracker = tracker

    async def on_result_received(self, result: StepResult) -> None:
        """
        Called when a step result is received
        In the current implementation, results are already tracked by TaskDispatcher
        This is here for extensibility (e.g., publishing to message queue, webhooks, etc.)
        """
        # Log result
        print(f"[ResultListener] Received result for step {result.step_id}: {result.status}")

        # Could publish to message queue, trigger webhooks, etc.
        # For now, just a placeholder

    async def start_consuming(self) -> None:
        """
        Start consuming results from message queue
        In the current implementation (direct MCP execution), this is not needed
        This would be used if results came from an async message queue
        """
        # Placeholder for message queue consumption
        print("[ResultListener] Ready to consume results")
