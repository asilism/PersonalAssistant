"""
Orchestrator - Main orchestration class using LangGraph
"""

from datetime import datetime
from typing import Annotated, Optional, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

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

    def __init__(self, user_id: str, tenant: str, preloaded_mcp_tools: list = None):
        self.user_id = user_id
        self.tenant = tenant
        self.preloaded_mcp_tools = preloaded_mcp_tools or []

        # Initialize components
        self.config_loader = ConfigLoader()
        self.tracker = TaskTracker()
        self.listener = ResultListener(self.tracker)
        self.event_emitter = get_event_emitter()

        # Settings and planner will be initialized on first run
        self.settings = None
        self.planner = None
        self.dispatcher = None
        self.mcp_executor = None

        # Build the graph
        self.graph = None

    async def _initialize(self):
        """Initialize settings and components"""
        if not self.settings:
            # Initialize MCP executor and discover tools
            from .mcp_executor import MCPExecutor

            self.mcp_executor = MCPExecutor()

            # Use preloaded tools if available, otherwise discover
            if self.preloaded_mcp_tools:
                print(f"[Orchestrator] Using {len(self.preloaded_mcp_tools)} preloaded MCP tools")
                mcp_tools = self.preloaded_mcp_tools
                # Still initialize servers for execution
                await self.mcp_executor.initialize_servers()
            else:
                print(f"[Orchestrator] No preloaded tools, discovering now...")
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

        return workflow.compile()

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
        error_msg = state.get('error', 'Unknown error')
        print(f"[Orchestrator] === Error Node ===")
        print(f"[Orchestrator] ERROR: {error_msg}")
        print(f"[Orchestrator] State at error:")
        print(f"[Orchestrator]   - Session: {state.get('session_id')}")
        print(f"[Orchestrator]   - Request: {state.get('request_text', '')[:100]}")
        print(f"[Orchestrator]   - Plan ID: {state.get('plan', {}).get('plan_id') if state.get('plan') else 'N/A'}")

        state["type"] = StateType.ERROR.value
        return state

    def _route_after_plan(self, state: OrchestrationState) -> str:
        """Route after planning"""
        state_type = state.get("type", "")

        if state_type == StateType.DISPATCH.value:
            return "dispatch"
        elif state_type == StateType.ERROR.value:
            return "error_handler"
        else:
            return "error_handler"

    def _route_after_dispatch(self, state: OrchestrationState) -> str:
        """Route after dispatch"""
        state_type = state.get("type", "")

        if state_type == StateType.PLAN_OR_DECIDE.value:
            return "decide"
        elif state_type == StateType.ERROR.value:
            return "error_handler"
        else:
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

    async def run(self, session_id: str, request_text: str, trace_id: Optional[str] = None) -> dict:
        """
        Run the orchestrator with a user request
        """
        # Initialize if needed
        await self._initialize()

        # Build graph if needed
        if not self.graph:
            self.graph = self._build_graph()

        # Generate trace ID if not provided
        if not trace_id:
            import uuid
            trace_id = str(uuid.uuid4())

        # Save user message to chat history
        await self.tracker.save_user_message(
            session_id=session_id,
            user_id=self.user_id,
            tenant=self.tenant,
            content=request_text
        )

        # Load chat history for context (last 10 messages)
        chat_history = await self.tracker.load_chat_history(
            session_id=session_id,
            limit=10
        )

        # Format chat history for context
        conversation_history = []
        for msg in chat_history:
            conversation_history.append(f"{msg.role}: {msg.content}")

        # Load recent execution results for context
        additional_context = {}
        try:
            recent_history = await self.tracker.get_history(session_id, self.user_id)
            if recent_history.recent_plans:
                # Get the most recent plan (regardless of status) to reuse successful step results
                # This is important for HITL scenarios where the plan is not yet completed
                # but has already executed some steps successfully
                most_recent = recent_history.recent_plans[-1]
                recent_results = self.tracker.get_step_results(most_recent.plan_id)
                if recent_results:
                    # Filter for successful results only
                    successful_results = [r for r in recent_results if r.status == "success"]
                    if successful_results:
                        # Store recent results in additional context
                        additional_context["recent_plan_id"] = most_recent.plan_id
                        additional_context["recent_request"] = most_recent.request_text
                        additional_context["recent_results"] = [
                            {
                                "step_id": r.step_id,
                                "description": r.description,
                                "output": r.output,
                                "status": r.status
                            }
                            for r in successful_results
                        ]
        except Exception as e:
            print(f"[Orchestrator] Warning: Could not load recent execution results: {e}")

        # Initial state
        initial_state: OrchestrationState = {
            "type": StateType.INIT.value,
            "session_id": session_id,
            "user_id": self.user_id,
            "tenant": self.tenant,
            "request_text": request_text,
            "trace_id": trace_id,
            "context": {"session_id": session_id, "conversation_history": conversation_history, "additional_context": additional_context},
            "plan": None,
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
            # Invoke the graph
            final_state = await self.graph.ainvoke(initial_state)

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            # Build response and save assistant message
            if final_state.get("type") == StateType.FINAL.value:
                payload = final_state.get("final_payload", {})
                response_message = payload.get("message", "Task completed successfully")

                # Save assistant response to chat history
                await self.tracker.save_assistant_message(
                    session_id=session_id,
                    user_id=self.user_id,
                    tenant=self.tenant,
                    content=response_message
                )

                # Emit execution completed event
                await self.event_emitter.emit_execution_completed(
                    trace_id=trace_id,
                    success=True,
                    message=response_message,
                    execution_time=execution_time,
                    results=payload.get("data")
                )

                return {
                    "success": True,
                    "message": response_message,
                    "results": payload.get("data"),
                    "execution_time": execution_time,
                    "plan_id": final_state.get("plan", {}).get("plan_id") if final_state.get("plan") else None,
                    "plan": final_state.get("plan")  # Include full plan for analysis
                }
            elif final_state.get("type") == StateType.HUMAN_IN_THE_LOOP.value:
                # Human input required
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
                error_message = final_state.get("error", "Unknown error")

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
