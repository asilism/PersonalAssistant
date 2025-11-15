"""
Event Emitter for execution log streaming
"""

import asyncio
import json
from datetime import datetime
from typing import Optional, AsyncGenerator, Any
from collections import defaultdict

from .types import ExecutionEvent, ExecutionEventType


class ExecutionEventEmitter:
    """
    Event emitter for streaming execution logs in real-time
    Uses async queues to emit events to multiple subscribers
    """

    def __init__(self):
        # Store queues per trace_id
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, trace_id: str) -> asyncio.Queue:
        """
        Subscribe to events for a specific trace_id
        Returns a queue that will receive events
        """
        async with self._lock:
            queue = asyncio.Queue()
            self._subscribers[trace_id].append(queue)
            return queue

    async def unsubscribe(self, trace_id: str, queue: asyncio.Queue):
        """
        Unsubscribe from events for a specific trace_id
        """
        async with self._lock:
            if trace_id in self._subscribers:
                if queue in self._subscribers[trace_id]:
                    self._subscribers[trace_id].remove(queue)
                # Clean up empty subscriber lists
                if not self._subscribers[trace_id]:
                    del self._subscribers[trace_id]

    async def emit(self, event: ExecutionEvent):
        """
        Emit an event to all subscribers of the trace_id
        """
        trace_id = event.trace_id
        async with self._lock:
            if trace_id in self._subscribers:
                # Put event in all subscriber queues
                for queue in self._subscribers[trace_id]:
                    try:
                        await queue.put(event)
                    except Exception as e:
                        print(f"[EventEmitter] Error putting event in queue: {e}")

    async def emit_execution_started(
        self,
        trace_id: str,
        session_id: str,
        request_text: str,
        user_id: str,
        tenant: str
    ):
        """Emit execution started event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_STARTED,
            trace_id=trace_id,
            message=f"Execution started for request: {request_text[:100]}...",
            data={
                "session_id": session_id,
                "request_text": request_text,
                "user_id": user_id,
                "tenant": tenant
            }
        )
        await self.emit(event)

    async def emit_plan_created(
        self,
        trace_id: str,
        plan_id: str,
        steps: list[dict],
        total_steps: int
    ):
        """Emit plan created event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.PLAN_CREATED,
            trace_id=trace_id,
            message=f"Plan created with {total_steps} steps",
            data={
                "plan_id": plan_id,
                "steps": steps,
                "total_steps": total_steps
            }
        )
        await self.emit(event)

    async def emit_step_started(
        self,
        trace_id: str,
        plan_id: str,
        step_id: str,
        step_description: str,
        tool_name: str,
        tool_input: Optional[dict[str, Any]] = None
    ):
        """Emit step started event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.STEP_STARTED,
            trace_id=trace_id,
            message=f"Starting step: {step_description}",
            data={
                "plan_id": plan_id,
                "step_id": step_id,
                "step_description": step_description,
                "tool_name": tool_name,
                "tool_input": tool_input or {}
            }
        )
        await self.emit(event)

    async def emit_step_completed(
        self,
        trace_id: str,
        plan_id: str,
        step_id: str,
        step_description: str,
        output: Any,
        duration: float
    ):
        """Emit step completed event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.STEP_COMPLETED,
            trace_id=trace_id,
            message=f"Completed step: {step_description} (took {duration:.2f}ms)",
            data={
                "plan_id": plan_id,
                "step_id": step_id,
                "step_description": step_description,
                "output": output,
                "duration": duration
            }
        )
        await self.emit(event)

    async def emit_step_failed(
        self,
        trace_id: str,
        plan_id: str,
        step_id: str,
        step_description: str,
        error: str,
        duration: float
    ):
        """Emit step failed event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.STEP_FAILED,
            trace_id=trace_id,
            message=f"Failed step: {step_description} - Error: {error}",
            data={
                "plan_id": plan_id,
                "step_id": step_id,
                "step_description": step_description,
                "error": error,
                "duration": duration
            }
        )
        await self.emit(event)

    async def emit_decision_made(
        self,
        trace_id: str,
        decision_type: str,
        reason: str,
        next_action: Optional[str] = None
    ):
        """Emit decision made event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.DECISION_MADE,
            trace_id=trace_id,
            message=f"Decision: {decision_type} - {reason}",
            data={
                "decision_type": decision_type,
                "reason": reason,
                "next_action": next_action
            }
        )
        await self.emit(event)

    async def emit_node_entered(
        self,
        trace_id: str,
        node_name: str,
        state_type: str
    ):
        """Emit node entered event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.NODE_ENTERED,
            trace_id=trace_id,
            message=f"Entering node: {node_name}",
            data={
                "node_name": node_name,
                "state_type": state_type
            }
        )
        await self.emit(event)

    async def emit_node_exited(
        self,
        trace_id: str,
        node_name: str,
        next_state_type: str
    ):
        """Emit node exited event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.NODE_EXITED,
            trace_id=trace_id,
            message=f"Exiting node: {node_name} -> next state: {next_state_type}",
            data={
                "node_name": node_name,
                "next_state_type": next_state_type
            }
        )
        await self.emit(event)

    async def emit_execution_completed(
        self,
        trace_id: str,
        success: bool,
        message: str,
        execution_time: float
    ):
        """Emit execution completed event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_COMPLETED,
            trace_id=trace_id,
            message=f"Execution completed: {message}",
            data={
                "success": success,
                "message": message,
                "execution_time": execution_time
            }
        )
        await self.emit(event)

    async def emit_execution_error(
        self,
        trace_id: str,
        error: str,
        error_type: Optional[str] = None
    ):
        """Emit execution error event"""
        event = ExecutionEvent(
            event_type=ExecutionEventType.EXECUTION_ERROR,
            trace_id=trace_id,
            message=f"Execution error: {error}",
            data={
                "error": error,
                "error_type": error_type
            }
        )
        await self.emit(event)

    async def stream_events(self, trace_id: str) -> AsyncGenerator[str, None]:
        """
        Stream events for a specific trace_id as Server-Sent Events
        This is a generator that yields SSE formatted strings
        """
        queue = await self.subscribe(trace_id)

        try:
            while True:
                # Wait for next event with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Format as SSE
                    event_data = {
                        "event_type": event.event_type.value,
                        "trace_id": event.trace_id,
                        "timestamp": event.timestamp.isoformat(),
                        "message": event.message,
                        "data": event.data
                    }

                    # SSE format: data: {json}\n\n
                    sse_message = f"data: {json.dumps(event_data)}\n\n"
                    yield sse_message

                    # If this is a completion or error event, send done signal and break
                    if event.event_type in [
                        ExecutionEventType.EXECUTION_COMPLETED,
                        ExecutionEventType.EXECUTION_ERROR
                    ]:
                        # Send a final done signal
                        yield "data: {\"done\": true}\n\n"
                        break

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield ": keepalive\n\n"

        except Exception as e:
            print(f"[EventEmitter] Error in stream_events: {e}")
            # Send error event
            error_data = {
                "event_type": "stream_error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

        finally:
            # Unsubscribe when done
            await self.unsubscribe(trace_id, queue)


# Global event emitter instance
_global_emitter: Optional[ExecutionEventEmitter] = None


def get_event_emitter() -> ExecutionEventEmitter:
    """Get or create global event emitter instance"""
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = ExecutionEventEmitter()
    return _global_emitter
