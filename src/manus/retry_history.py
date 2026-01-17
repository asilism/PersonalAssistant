"""
Retry History Tracker - Prevents duplicate error attempts
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime


class RetryHistory:
    """
    Track retry history for tasks to prevent duplicate error attempts

    This class maintains a history of failed task attempts, including:
    - Error messages and normalized signatures
    - Plan data that was used
    - Timestamps for each attempt

    It can detect duplicate errors by normalizing error messages
    (removing UUIDs, numbers, timestamps) to prevent infinite retry loops
    where the same error keeps occurring.
    """

    def __init__(self):
        """Initialize empty retry history"""
        # task_id -> list of attempt records
        self.task_histories: Dict[str, List[Dict[str, Any]]] = {}

    def add_attempt(
        self,
        task_id: str,
        error: str,
        plan_data: Dict[str, Any],
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """
        Record a failed attempt for a task

        Args:
            task_id: ID of the failed task
            error: Error message from the failure
            plan_data: The plan data that was attempted
            tool_calls: Optional list of tool calls that were attempted

        Returns:
            Attempt number for this task
        """
        if task_id not in self.task_histories:
            self.task_histories[task_id] = []

        error_signature = self._normalize_error(error)
        attempt_number = len(self.task_histories[task_id]) + 1

        attempt_record = {
            'attempt_number': attempt_number,
            'error': error,
            'error_signature': error_signature,
            'plan_data': plan_data,
            'tool_calls': tool_calls,
            'timestamp': datetime.now().isoformat()
        }

        self.task_histories[task_id].append(attempt_record)

        return attempt_number

    def is_duplicate_error(self, task_id: str, error: str) -> bool:
        """
        Check if this error has occurred before for this task

        Uses normalized error signatures to detect duplicates.
        This prevents retry loops where the same error keeps happening.

        Args:
            task_id: ID of the task
            error: Error message to check

        Returns:
            True if this exact error has occurred before, False otherwise
        """
        if task_id not in self.task_histories:
            return False

        error_signature = self._normalize_error(error)

        for attempt in self.task_histories[task_id]:
            if attempt['error_signature'] == error_signature:
                return True

        return False

    def get_history(self, task_id: str) -> List[Dict[str, Any]]:
        """
        Get all attempt records for a specific task

        Args:
            task_id: ID of the task

        Returns:
            List of attempt records (empty if task has no history)
        """
        return self.task_histories.get(task_id, [])

    def get_all_histories(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get complete history for all tasks

        Returns:
            Dictionary mapping task IDs to their attempt lists
        """
        return self.task_histories

    def get_attempt_count(self, task_id: str) -> int:
        """
        Get number of attempts for a task

        Args:
            task_id: ID of the task

        Returns:
            Number of attempts (0 if no history)
        """
        return len(self.task_histories.get(task_id, []))

    def format_history_for_prompt(self, task_id: str) -> str:
        """
        Format task history as readable text for LLM prompts

        Args:
            task_id: ID of the task

        Returns:
            Formatted history string
        """
        history = self.get_history(task_id)

        if not history:
            return f"Task {task_id}: No previous attempts"

        lines = [f"Task {task_id} - Previous Attempts:"]

        for attempt in history:
            attempt_num = attempt['attempt_number']
            timestamp = attempt['timestamp']
            error = attempt['error']
            tool_calls = attempt.get('tool_calls', [])

            lines.append(f"\n  Attempt {attempt_num} (at {timestamp}):")
            lines.append(f"    Error: {error}")

            if tool_calls:
                lines.append(f"    Tool calls attempted:")
                for i, call in enumerate(tool_calls):
                    tool_name = call.get('tool', 'UNKNOWN')
                    params = call.get('params', {})
                    lines.append(f"      {i+1}. {tool_name}")
                    lines.append(f"         Parameters: {list(params.keys())}")

            # Check if this is a duplicate of previous attempt
            if attempt_num > 1:
                prev_signature = history[attempt_num - 2]['error_signature']
                curr_signature = attempt['error_signature']
                if prev_signature == curr_signature:
                    lines.append(f"    ⚠️  DUPLICATE ERROR - Same as attempt {attempt_num - 1}")

        return "\n".join(lines)

    def _normalize_error(self, error: str) -> str:
        """
        Normalize error message for comparison

        This removes variable parts of error messages:
        - UUIDs (replaced with 'UUID')
        - Numbers (replaced with 'N')
        - Timestamps (replaced with 'TIMESTAMP')
        - Extra whitespace

        This allows us to detect when the "same" error is happening
        even if some details vary.

        Args:
            error: Raw error message

        Returns:
            Normalized error signature
        """
        # Remove UUIDs (8-4-4-4-12 format)
        normalized = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            'UUID',
            error,
            flags=re.IGNORECASE
        )

        # Remove hex IDs (common in error messages)
        normalized = re.sub(r'\b[0-9a-f]{8,}\b', 'HEXID', normalized, flags=re.IGNORECASE)

        # Remove numbers (but keep them in words like "task_1")
        normalized = re.sub(r'(?<![a-zA-Z_])\d+(?![a-zA-Z_])', 'N', normalized)

        # Remove ISO timestamps
        normalized = re.sub(
            r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?',
            'TIMESTAMP',
            normalized
        )

        # Remove file paths (keep only the error part)
        normalized = re.sub(r'/[\w/.-]+\.py', 'FILE.py', normalized)

        # Normalize whitespace
        normalized = ' '.join(normalized.split())

        # Lowercase for case-insensitive comparison
        normalized = normalized.lower().strip()

        return normalized

    def clear_history(self, task_id: Optional[str] = None):
        """
        Clear retry history

        Args:
            task_id: If provided, clear only this task's history.
                    If None, clear all history.
        """
        if task_id is None:
            self.task_histories.clear()
        elif task_id in self.task_histories:
            del self.task_histories[task_id]
