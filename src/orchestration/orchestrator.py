"""
Orchestrator - Main orchestration class using LangGraph
"""

import json
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .types import (
    State,
    StateType,
    TraceContext,
    ContextBundle,
    FinalSummary,
)
from .config import ConfigLoader
from .tracker import TaskTracker
from .planner import Planner
from .dispatcher import TaskDispatcher
from .listener import ResultListener
from .event_emitter import get_event_emitter


class OrchestrationState(TypedDict):
    """
    State for LangGraph - using TypedDict for LangGraph compatibility
    We'll convert to/from our Pydantic State model
    """
    type: str
    session_id: str
    user_id: str
    tenant: str
    request_text: str
    trace_id: str
    context: Optional[dict]
    plan: Optional[dict]
    plan_state: Optional[str]
    results: Optional[dict]
    error: Optional[str]
    final_payload: Optional[dict]
    retry_counts: dict


class Orchestrator:
    """
    Orchestrator - LangGraph-based state machine for task orchestration
    """

    def __init__(self, user_id: str, tenant: str, preloaded_mcp_tools: list = None, preloaded_tool_server_map: dict = None):
        self.user_id = user_id
        self.tenant = tenant
        self.preloaded_mcp_tools = preloaded_mcp_tools or []
        self.preloaded_tool_server_map = preloaded_tool_server_map or {}

        # Initialize components
        self.config_loader = ConfigLoader()
        self.tracker = TaskTracker()
        self.listener = ResultListener(self.tracker)
        self.event_emitter = get_event_emitter()

        # LangGraph checkpointer will be initialized in _initialize (SQLite-based for persistence)
        self.checkpointer = None
        self._db_conn = None  # aiosqlite connection
        self._checkpointer_initialized = False

        # Settings and planner will be initialized on first run
        self.settings = None
        self.planner = None
        self.dispatcher = None
        self.mcp_executor = None

        # Build the graph
        self.graph = None

    async def _initialize(self):
        """Initialize settings and components"""
        # Initialize SQLite checkpointer for persistent state
        if not self._checkpointer_initialized:
            checkpoint_path = Path(__file__).parent.parent.parent / "data" / "checkpoints.db"
            checkpoint_path.parent.mkdir(exist_ok=True)
            # Use aiosqlite directly for cleaner connection management
            self._db_conn = await aiosqlite.connect(str(checkpoint_path))
            self.checkpointer = AsyncSqliteSaver(self._db_conn)
            self._checkpointer_initialized = True
            print(f"[Orchestrator] Initialized SQLite checkpointer at {checkpoint_path}")

        if not self.settings:
            # Initialize MCP executor and discover tools
            from .mcp_executor import MCPExecutor

            self.mcp_executor = MCPExecutor(user_id=self.user_id, tenant=self.tenant)

            # Use preloaded tools if available, otherwise discover
            if self.preloaded_mcp_tools and self.preloaded_tool_server_map:
                print(f"[Orchestrator] Using {len(self.preloaded_mcp_tools)} preloaded MCP tools")
                mcp_tools = self.preloaded_mcp_tools
                # Initialize servers for execution and set preloaded tool-server mapping
                await self.mcp_executor.initialize_servers()
                self.mcp_executor.set_tool_server_map(self.preloaded_tool_server_map)
                print(f"[Orchestrator] Set preloaded tool-server map with {len(self.preloaded_tool_server_map)} mappings")
            else:
                print(f"[Orchestrator] No preloaded tools or map, discovering now...")
                await self.mcp_executor.initialize_servers()
                mcp_tools = await self.mcp_executor.discover_tools()
                print(f"[Orchestrator] Discovered {len(mcp_tools)} MCP tools")

            # Get settings with MCP tools
            self.settings = await self.config_loader.get_settings(
                self.user_id, self.tenant, mcp_tools=mcp_tools
            )
            self.planner = Planner(self.settings, self.tracker)
            self.dispatcher = TaskDispatcher(self.tracker, self.mcp_executor)

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine"""

        # Create workflow
        workflow = StateGraph(OrchestrationState)

        # Add nodes
        workflow.add_node("planning", self._plan_node)
        workflow.add_node("dispatch", self._dispatch_node)
        workflow.add_node("decide", self._decide_node)
        workflow.add_node("finalize", self._finalize_node)
        workflow.add_node("error_handler", self._error_node)

        # Set entry point
        workflow.set_entry_point("planning")

        # Add edges
        workflow.add_conditional_edges(
            "planning",
            self._route_after_plan,
            {
                "dispatch": "dispatch",
                "finalize": "finalize",
                "error_handler": "error_handler"
            }
        )

        workflow.add_conditional_edges(
            "dispatch",
            self._route_after_dispatch,
            {
                "decide": "decide",
                "error_handler": "error_handler"
            }
        )

        workflow.add_conditional_edges(
            "decide",
            self._route_after_decide,
            {
                "dispatch": "dispatch",
                "finalize": "finalize",
                "error_handler": "error_handler",
                "end": END
            }
        )

        workflow.add_edge("finalize", END)
        workflow.add_edge("error_handler", END)

        return workflow.compile(checkpointer=self.checkpointer)

    async def _plan_node(self, state: OrchestrationState) -> OrchestrationState:
        """Planning node"""
        print(f"[Orchestrator] === Planning Node ===")
        print(f"[Orchestrator] Session: {state.get('session_id')}")
        print(f"[Orchestrator] Request: {state.get('request_text', '')[:100]}...")

        trace_id = state.get('trace_id', '')

        # Emit node entered event
        await self.event_emitter.emit_node_entered(
            trace_id=trace_id,
            node_name="planning",
            state_type=state.get('type', '')
        )

        try:
            # Convert to Pydantic State
            pydantic_state = self._to_pydantic_state(state)
            pydantic_state.type = StateType.PLAN_OR_DECIDE

            # Run planner
            result_state = await self.planner.invoke(pydantic_state)

            print(f"[Orchestrator] Planning completed, next state: {result_state.type}")

            # Emit node exited event
            await self.event_emitter.emit_node_exited(
                trace_id=trace_id,
                node_name="planning",
                next_state_type=result_state.type.value
            )

            # Convert back
            return self._from_pydantic_state(result_state)
        except Exception as e:
            print(f"[Orchestrator] ERROR in planning node: {str(e)}")
            import traceback
            print(f"[Orchestrator] Traceback:\n{traceback.format_exc()}")

            # Emit error event
            await self.event_emitter.emit_execution_error(
                trace_id=trace_id,
                error=str(e),
                error_type="PlanningNodeError"
            )

            state["type"] = StateType.ERROR.value
            state["error"] = f"Planning node failed: {str(e)}"
            return state

    async def _dispatch_node(self, state: OrchestrationState) -> OrchestrationState:
        """Dispatch node"""
        print(f"[Orchestrator] === Dispatch Node ===")
        plan_id = state.get("plan", {}).get("plan_id") if state.get("plan") else "N/A"
        print(f"[Orchestrator] Plan ID: {plan_id}")

        trace_id = state.get('trace_id', '')

        # Emit node entered event
        await self.event_emitter.emit_node_entered(
            trace_id=trace_id,
            node_name="dispatch",
            state_type=state.get('type', '')
        )

        try:
            # Convert to Pydantic State
            pydantic_state = self._to_pydantic_state(state)

            # Run dispatcher
            result_state = await self.dispatcher.invoke(pydantic_state)

            print(f"[Orchestrator] Dispatch completed, next state: {result_state.type}")

            # Emit node exited event
            await self.event_emitter.emit_node_exited(
                trace_id=trace_id,
                node_name="dispatch",
                next_state_type=result_state.type.value
            )

            # Convert back
            return self._from_pydantic_state(result_state)
        except Exception as e:
            print(f"[Orchestrator] ERROR in dispatch node: {str(e)}")
            import traceback
            print(f"[Orchestrator] Traceback:\n{traceback.format_exc()}")

            # Emit error event
            await self.event_emitter.emit_execution_error(
                trace_id=trace_id,
                error=str(e),
                error_type="DispatchNodeError"
            )

            state["type"] = StateType.ERROR.value
            state["error"] = f"Dispatch node failed: {str(e)}"
            return state

    async def _decide_node(self, state: OrchestrationState) -> OrchestrationState:
        """Decision node"""
        print(f"[Orchestrator] === Decide Node ===")
        results = state.get("results", {})
        if results:
            print(f"[Orchestrator] Completed steps: {results.get('completed_steps', [])}")
            print(f"[Orchestrator] Failed steps: {results.get('failed_steps', [])}")

        trace_id = state.get('trace_id', '')

        # Emit node entered event
        await self.event_emitter.emit_node_entered(
            trace_id=trace_id,
            node_name="decide",
            state_type=state.get('type', '')
        )

        try:
            # Convert to Pydantic State
            pydantic_state = self._to_pydantic_state(state)
            pydantic_state.type = StateType.PLAN_OR_DECIDE

            # Run planner for decision
            result_state = await self.planner.invoke(pydantic_state)

            print(f"[Orchestrator] Decision completed, next state: {result_state.type}")

            # Emit node exited event
            await self.event_emitter.emit_node_exited(
                trace_id=trace_id,
                node_name="decide",
                next_state_type=result_state.type.value
            )

            # Convert back
            return self._from_pydantic_state(result_state)
        except Exception as e:
            print(f"[Orchestrator] ERROR in decide node: {str(e)}")
            import traceback
            print(f"[Orchestrator] Traceback:\n{traceback.format_exc()}")

            # Emit error event
            await self.event_emitter.emit_execution_error(
                trace_id=trace_id,
                error=str(e),
                error_type="DecideNodeError"
            )

            state["type"] = StateType.ERROR.value
            state["error"] = f"Decide node failed: {str(e)}"
            return state

    async def _finalize_node(self, state: OrchestrationState) -> OrchestrationState:
        """Finalization node"""
        print(f"[Orchestrator] === Finalize Node ===")
        payload = state.get("final_payload", {})
        print(f"[Orchestrator] Final payload: {payload}")

        # Only set to FINAL if not already a terminal state (e.g., HUMAN_IN_THE_LOOP)
        current_type = state.get("type")
        if current_type != StateType.HUMAN_IN_THE_LOOP.value:
            state["type"] = StateType.FINAL.value

        return state

    async def _error_node(self, state: OrchestrationState) -> OrchestrationState:
        """Error node"""
        error_msg = state.get('error') or 'Unknown error occurred'
        print(f"[Orchestrator] === Error Node ===")
        print(f"[Orchestrator] ERROR: {error_msg}")
        print(f"[Orchestrator] State at error:")
        print(f"[Orchestrator]   - Session: {state.get('session_id')}")
        print(f"[Orchestrator]   - Request: {state.get('request_text', '')[:100]}")
        print(f"[Orchestrator]   - Plan ID: {state.get('plan', {}).get('plan_id') if state.get('plan') else 'N/A'}")

        # Ensure error message is always set in state
        state["error"] = error_msg
        state["type"] = StateType.ERROR.value
        return state

    def _route_after_plan(self, state: OrchestrationState) -> str:
        """Route after planning"""
        state_type = state.get("type", "")

        if state_type == StateType.DISPATCH.value:
            return "dispatch"
        elif state_type == StateType.FINAL.value:
            return "finalize"
        elif state_type == StateType.ERROR.value:
            return "error_handler"
        else:
            # Unknown state type - set error and route to error_handler
            if not state.get("error"):
                state["error"] = f"Unexpected state type after planning: {state_type}"
            return "error_handler"

    def _route_after_dispatch(self, state: OrchestrationState) -> str:
        """Route after dispatch"""
        state_type = state.get("type", "")

        if state_type == StateType.PLAN_OR_DECIDE.value:
            return "decide"
        elif state_type == StateType.ERROR.value:
            return "error_handler"
        else:
            # Unknown state type - set error and route to error_handler
            if not state.get("error"):
                state["error"] = f"Unexpected state type after dispatch: {state_type}"
            return "error_handler"

    def _route_after_decide(self, state: OrchestrationState) -> str:
        """Route after decision"""
        state_type = state.get("type", "")

        if state_type == StateType.DISPATCH.value:
            return "dispatch"
        elif state_type == StateType.FINAL.value:
            return "finalize"
        elif state_type == StateType.ERROR.value:
            return "error_handler"
        elif state_type == StateType.HUMAN_IN_THE_LOOP.value:
            # Treat as finalize to return response to user
            print(f"[Orchestrator] Routing HUMAN_IN_THE_LOOP to finalize")
            return "finalize"
        else:
            # Unknown state type - set error and route to error_handler
            if not state.get("error"):
                state["error"] = f"Unexpected state type after decision: {state_type}"
            return "error_handler"

    def _to_pydantic_state(self, state: OrchestrationState) -> State:
        """Convert OrchestrationState to Pydantic State"""
        from .types import State, StateType, TraceContext, ContextBundle, Plan, AggregatedGroupResults, PlanState

        # Build trace context
        trace = TraceContext(trace_id=state["trace_id"])

        # Build context
        context = None
        if state.get("context"):
            context = ContextBundle(**state["context"])

        # Build plan
        plan = None
        if state.get("plan"):
            plan = Plan(**state["plan"])

        # Build results
        results = None
        if state.get("results"):
            results = AggregatedGroupResults(**state["results"])

        # Build plan state
        plan_state = None
        if state.get("plan_state"):
            plan_state = PlanState(state["plan_state"])

        return State(
            type=StateType(state["type"]),
            session_id=state["session_id"],
            user_id=state["user_id"],
            tenant=state["tenant"],
            request_text=state["request_text"],
            trace=trace,
            context=context,
            plan=plan,
            plan_state=plan_state,
            results=results,
            error=state.get("error"),
            final_payload=state.get("final_payload"),
            retry_counts=state.get("retry_counts", {})
        )

    def _from_pydantic_state(self, state: State) -> OrchestrationState:
        """Convert Pydantic State to OrchestrationState"""
        return {
            "type": state.type.value,
            "session_id": state.session_id,
            "user_id": state.user_id,
            "tenant": state.tenant,
            "request_text": state.request_text,
            "trace_id": state.trace.trace_id,
            "context": state.context.model_dump() if state.context else None,
            "plan": state.plan.model_dump() if state.plan else None,
            "plan_state": state.plan_state.value if state.plan_state else None,
            "results": state.results.model_dump() if state.results else None,
            "error": state.error,
            "final_payload": state.final_payload,
            "retry_counts": state.retry_counts
        }

    def _extract_recent_results(self, chat_history: list) -> str:
        """Extract recent execution results from chat history"""
        # Look for the most recent assistant message with execution results
        for msg in reversed(chat_history):
            if msg.role == "assistant":
                # Return the most recent assistant response
                # This could contain calendar events, emails, etc.
                return msg.content
        return ""

    async def run(self, session_id: str, request_text: str, trace_id: Optional[str] = None) -> dict:
        """
        Run the orchestrator with a user request
        """
        # Initialize if needed
        await self._initialize()

        # Build graph if needed
        if not self.graph:
            self.graph = self._build_graph()

        # Set up session workspace for file operations
        workspace_base = Path(__file__).parent.parent.parent / "workspaces"
        workspace_path = workspace_base / session_id
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Configure MCP executor to use session workspace
        if self.mcp_executor:
            self.mcp_executor.set_workspace(session_id, str(workspace_path))
            print(f"[Orchestrator] Configured workspace for session {session_id}: {workspace_path}")

        # Generate trace ID if not provided
        if not trace_id:
            import uuid
            trace_id = str(uuid.uuid4())

        # Save user message to chat history
        print(f"[Orchestrator] About to save user message - session_id={session_id}, user_id={self.user_id}, tenant={self.tenant}")
        await self.tracker.save_user_message(
            session_id=session_id,
            user_id=self.user_id,
            tenant=self.tenant,
            content=request_text
        )
        print(f"[Orchestrator] User message saved successfully")

        # Load chat history for context (last 10 messages)
        chat_history = await self.tracker.load_chat_history(
            session_id=session_id,
            limit=10
        )

        # Format chat history for context
        conversation_history = []
        for msg in chat_history:
            conversation_history.append(f"{msg.role}: {msg.content}")

        # Load recent execution results (structured tool outputs from previous requests)
        recent_execution_results = await self.tracker.load_recent_execution_results(
            session_id=session_id,
            limit=3  # Last 3 execution results
        )

        # Format execution results for context
        formatted_execution_results = []
        for exec_result in recent_execution_results:
            try:
                results_data = json.loads(exec_result.results_json)
                formatted_execution_results.append({
                    "request": exec_result.request_text,
                    "results": results_data,
                    "timestamp": exec_result.created_at
                })
            except json.JSONDecodeError:
                pass  # Skip malformed results

        # Extract recent results for context (legacy - from chat history text)
        recent_results = self._extract_recent_results(chat_history)

        # Configure thread_id for checkpointing (use session_id as thread_id)
        thread_config = {"configurable": {"thread_id": session_id}}

        # Check if there's a previous state (HITL scenario)
        previous_state = None
        try:
            # Get the latest state from checkpointer
            state_snapshot = await self.graph.aget_state(thread_config)
            if state_snapshot and state_snapshot.values:
                previous_state = state_snapshot.values
                print(f"[Orchestrator] Found previous state for session {session_id}")
                print(f"[Orchestrator] Previous state type: {previous_state.get('type')}")
                print(f"[Orchestrator] Previous plan: {previous_state.get('plan', {}).get('plan_id') if previous_state.get('plan') else 'None'}")
        except Exception as e:
            print(f"[Orchestrator] No previous state found or error retrieving it: {e}")

        # Determine initial state based on whether this is a HITL response
        if previous_state and previous_state.get("type") == StateType.HUMAN_IN_THE_LOOP.value:
            # This is a HITL response - resume from previous state
            print(f"[Orchestrator] HITL response detected - resuming from previous state")

            # Update the previous state with new request text (HITL response)
            initial_state = previous_state.copy()
            initial_state["request_text"] = request_text  # Update with HITL response
            initial_state["trace_id"] = trace_id  # Update trace_id for new execution
            initial_state["type"] = StateType.PLAN_OR_DECIDE.value  # Resume execution

            # Update context with conversation history
            if initial_state.get("context"):
                initial_state["context"]["conversation_history"] = conversation_history
            else:
                initial_state["context"] = {
                    "session_id": session_id,
                    "conversation_history": conversation_history,
                    "additional_context": {}
                }

            # Add HITL response to context for planner to use
            if "additional_context" not in initial_state["context"]:
                initial_state["context"]["additional_context"] = {}
            initial_state["context"]["additional_context"]["hitl_response"] = request_text

            # Check if there's a failed step to retry
            failed_step_id = previous_state.get("final_payload", {}).get("failed_step_id")
            if failed_step_id:
                print(f"[Orchestrator] HITL retry: Removing failed step {failed_step_id} from results to allow retry")

                # Remove the failed step from results to allow it to be retried
                if initial_state.get("results"):
                    results = initial_state["results"]
                    if "failed_steps" in results:
                        # Filter out the failed step
                        results["failed_steps"] = [
                            step for step in results["failed_steps"]
                            if step.get("step_id") != failed_step_id
                        ]
                        print(f"[Orchestrator] Removed {failed_step_id} from failed_steps")

                # Reset retry count for this step
                if "retry_counts" in initial_state:
                    if failed_step_id in initial_state["retry_counts"]:
                        del initial_state["retry_counts"][failed_step_id]
                        print(f"[Orchestrator] Reset retry count for {failed_step_id}")

            print(f"[Orchestrator] Resuming with plan: {initial_state.get('plan', {}).get('plan_id') if initial_state.get('plan') else 'None'}")
        else:
            # New request - create initial state
            print(f"[Orchestrator] New request - creating initial state")
            print(f"[Orchestrator] Loaded {len(formatted_execution_results)} previous execution results for context")
            initial_state: OrchestrationState = {
                "type": StateType.INIT.value,
                "session_id": session_id,
                "user_id": self.user_id,
                "tenant": self.tenant,
                "request_text": request_text,
                "trace_id": trace_id,
                "context": {
                    "session_id": session_id,
                    "conversation_history": conversation_history,
                    "additional_context": {
                        "recent_results": recent_results,
                        "previous_execution_results": formatted_execution_results  # Structured results from previous requests
                    }
                },
                "plan": None,  # Will be created by planner or restored from checkpoint
                "plan_state": None,
                "results": None,
                "error": None,
                "final_payload": None,
                "retry_counts": {}  # Initialize retry tracking
            }

        # Run the graph
        start_time = datetime.now()

        # Emit execution started event
        await self.event_emitter.emit_execution_started(
            trace_id=trace_id,
            session_id=session_id,
            request_text=request_text,
            user_id=self.user_id,
            tenant=self.tenant
        )

        try:
            # Invoke the graph with thread config for checkpointing
            final_state = await self.graph.ainvoke(initial_state, config=thread_config)

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # Build response and save assistant message
            if final_state.get("type") == StateType.FINAL.value:
                payload = final_state.get("final_payload", {})
                response_message = payload.get("message", "Task completed successfully")
                result_data = payload.get("data")
                data_type = payload.get("data_type")  # For frontend formatting

                # Save assistant response to chat history
                await self.tracker.save_assistant_message(
                    session_id=session_id,
                    user_id=self.user_id,
                    tenant=self.tenant,
                    content=response_message
                )

                # Save structured execution results for future context
                if result_data is not None:
                    try:
                        results_json = json.dumps(result_data, default=str, ensure_ascii=False)
                        await self.tracker.save_execution_result(
                            session_id=session_id,
                            user_id=self.user_id,
                            tenant=self.tenant,
                            request_text=request_text,
                            results_json=results_json
                        )
                        print(f"[Orchestrator] Saved structured execution results for future context")
                    except Exception as e:
                        print(f"[Orchestrator] Warning: Failed to save execution results: {e}")

                # Emit execution completed event
                await self.event_emitter.emit_execution_completed(
                    trace_id=trace_id,
                    success=True,
                    message=response_message,
                    execution_time=execution_time,
                    results=result_data,
                    data_type=data_type
                )

                return {
                    "success": True,
                    "message": response_message,
                    "results": result_data,
                    "execution_time": execution_time,
                    "plan_id": final_state.get("plan", {}).get("plan_id") if final_state.get("plan") else None,
                    "plan": final_state.get("plan")  # Include full plan for analysis
                }
            elif final_state.get("type") == StateType.HUMAN_IN_THE_LOOP.value:
                # Human input required - LangGraph checkpoint will preserve state
                payload = final_state.get("final_payload", {})
                # Support both "message" and "question" keys for backward compatibility
                message = payload.get("message") or payload.get("question", "추가 정보가 필요합니다.")

                # Save assistant response to chat history
                await self.tracker.save_assistant_message(
                    session_id=session_id,
                    user_id=self.user_id,
                    tenant=self.tenant,
                    content=message
                )

                # Emit execution completed event (requires human input)
                await self.event_emitter.emit_execution_completed(
                    trace_id=trace_id,
                    success=False,
                    message=f"Requires human input: {message}",
                    execution_time=execution_time
                )

                return {
                    "success": False,
                    "message": message,
                    "requires_input": True,
                    "missing_param": payload.get("missing_param"),
                    "failed_step_id": payload.get("failed_step_id"),
                    "execution_time": execution_time,
                    "plan_id": final_state.get("plan", {}).get("plan_id") if final_state.get("plan") else None
                }
            elif final_state.get("type") == StateType.ERROR.value:
                error_message = final_state.get("error") or "Unknown error occurred"

                # Save error message to chat history
                await self.tracker.save_assistant_message(
                    session_id=session_id,
                    user_id=self.user_id,
                    tenant=self.tenant,
                    content=f"Error: {error_message}"
                )

                # Emit execution error event
                await self.event_emitter.emit_execution_error(
                    trace_id=trace_id,
                    error=error_message,
                    error_type="ExecutionError"
                )

                return {
                    "success": False,
                    "message": error_message,
                    "execution_time": execution_time
                }
            else:
                incomplete_message = "Execution incomplete"

                # Save incomplete message to chat history
                await self.tracker.save_assistant_message(
                    session_id=session_id,
                    user_id=self.user_id,
                    tenant=self.tenant,
                    content=incomplete_message
                )

                return {
                    "success": False,
                    "message": incomplete_message,
                    "execution_time": execution_time
                }

        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            print(f"[Orchestrator] CRITICAL ERROR: Orchestration failed")
            print(f"[Orchestrator] Exception type: {type(e).__name__}")
            print(f"[Orchestrator] Exception message: {str(e)}")
            import traceback
            print(f"[Orchestrator] Traceback:\n{traceback.format_exc()}")

            return {
                "success": False,
                "message": f"Orchestration failed: {str(e)}",
                "execution_time": execution_time
            }

    async def cleanup(self):
        """Cleanup resources including checkpointer connection"""
        if self._checkpointer_initialized and self._db_conn:
            try:
                await self._db_conn.close()
                self._checkpointer_initialized = False
                self.checkpointer = None
                self._db_conn = None
                print("[Orchestrator] Closed SQLite checkpointer connection")
            except Exception as e:
                print(f"[Orchestrator] Error closing checkpointer: {e}")
