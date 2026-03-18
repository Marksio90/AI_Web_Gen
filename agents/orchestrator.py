"""
Advanced DAG-based Agent Orchestrator Engine.

Implements a Directed Acyclic Graph execution engine for multi-agent workflows
with dynamic routing, parallel execution, conditional branching, checkpointing,
circuit breakers, and real-time telemetry.

This is the heart of the platform — the "nervous system" connecting all agents.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Node & Edge Definitions
# ---------------------------------------------------------------------------

class NodeStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"
    CIRCUIT_OPEN = "circuit_open"


class EdgeCondition(str, Enum):
    ALWAYS = "always"
    ON_SUCCESS = "on_success"
    ON_FAILURE = "on_failure"
    CONDITIONAL = "conditional"


@dataclass
class CircuitBreaker:
    """Circuit breaker pattern for agent resilience."""
    failure_threshold: int = 3
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 1

    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _state: str = field(default="closed", repr=False)  # closed, open, half_open
    _half_open_calls: int = field(default=0, repr=False)

    def record_success(self):
        self._failure_count = 0
        self._state = "closed"
        self._half_open_calls = 0

    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"

    def can_execute(self) -> bool:
        if self._state == "closed":
            return True
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = "half_open"
                self._half_open_calls = 0
                return True
            return False
        # half_open
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False

    @property
    def state(self) -> str:
        # Re-evaluate on read
        if self._state == "open" and time.monotonic() - self._last_failure_time >= self.recovery_timeout:
            self._state = "half_open"
        return self._state


@dataclass
class DAGNode:
    """A single node in the execution DAG."""
    id: str
    name: str
    execute_fn: Callable[..., Coroutine]
    max_retries: int = 2
    retry_delay: float = 2.0
    timeout: float = 120.0
    priority: int = 0  # Higher = execute first among ready nodes
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    retry_count: int = 0
    execution_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


@dataclass
class DAGEdge:
    """Directed edge between two nodes with optional condition."""
    source: str  # node ID
    target: str  # node ID
    condition: EdgeCondition = EdgeCondition.ON_SUCCESS
    condition_fn: Optional[Callable[[Any], bool]] = None


@dataclass
class Checkpoint:
    """Serializable pipeline checkpoint for resumption."""
    pipeline_id: str
    timestamp: float
    node_states: dict[str, dict]  # node_id -> {status, result, error}
    context: dict[str, Any]
    completed_nodes: list[str]


# ---------------------------------------------------------------------------
# DAG Builder
# ---------------------------------------------------------------------------

class DAGBuilder:
    """Fluent API for constructing execution DAGs."""

    def __init__(self, name: str = "pipeline"):
        self.name = name
        self._nodes: dict[str, DAGNode] = {}
        self._edges: list[DAGEdge] = []

    def add_node(
        self,
        node_id: str,
        name: str,
        execute_fn: Callable,
        max_retries: int = 2,
        timeout: float = 120.0,
        priority: int = 0,
    ) -> "DAGBuilder":
        self._nodes[node_id] = DAGNode(
            id=node_id,
            name=name,
            execute_fn=execute_fn,
            max_retries=max_retries,
            timeout=timeout,
            priority=priority,
        )
        return self

    def add_edge(
        self,
        source: str,
        target: str,
        condition: EdgeCondition = EdgeCondition.ON_SUCCESS,
        condition_fn: Optional[Callable] = None,
    ) -> "DAGBuilder":
        self._edges.append(DAGEdge(source, target, condition, condition_fn))
        return self

    def chain(self, *node_ids: str) -> "DAGBuilder":
        """Chain nodes in sequence: A -> B -> C."""
        for i in range(len(node_ids) - 1):
            self.add_edge(node_ids[i], node_ids[i + 1])
        return self

    def fan_out(self, source: str, *targets: str) -> "DAGBuilder":
        """Fan out from one node to multiple parallel targets."""
        for t in targets:
            self.add_edge(source, t)
        return self

    def fan_in(self, *sources: str, target: str) -> "DAGBuilder":
        """Fan in from multiple nodes to a single target (barrier sync)."""
        for s in sources:
            self.add_edge(s, target)
        return self

    def conditional(
        self,
        source: str,
        target: str,
        condition_fn: Callable[[Any], bool],
    ) -> "DAGBuilder":
        """Add conditional edge — target only executes if condition_fn(source_result) is True."""
        self.add_edge(source, target, EdgeCondition.CONDITIONAL, condition_fn)
        return self

    def on_failure(self, source: str, fallback: str) -> "DAGBuilder":
        """Add fallback edge — executes when source fails."""
        self.add_edge(source, fallback, EdgeCondition.ON_FAILURE)
        return self

    def build(self) -> "ExecutionDAG":
        return ExecutionDAG(self.name, dict(self._nodes), list(self._edges))


# ---------------------------------------------------------------------------
# Execution Engine
# ---------------------------------------------------------------------------

class ExecutionDAG:
    """
    High-performance DAG execution engine with:
    - Topological parallel execution
    - Circuit breaker pattern
    - Checkpointing & resumption
    - Real-time telemetry events
    - Dynamic routing
    """

    def __init__(self, name: str, nodes: dict[str, DAGNode], edges: list[DAGEdge]):
        self.name = name
        self.nodes = nodes
        self.edges = edges
        self.pipeline_id = uuid.uuid4().hex
        self.context: dict[str, Any] = {}
        self._event_handlers: list[Callable] = []
        self._checkpoints: list[Checkpoint] = []

        # Build adjacency structures
        self._successors: dict[str, list[DAGEdge]] = defaultdict(list)
        self._predecessors: dict[str, list[DAGEdge]] = defaultdict(list)
        for edge in edges:
            self._successors[edge.source].append(edge)
            self._predecessors[edge.target].append(edge)

    def on_event(self, handler: Callable):
        """Register an event handler for telemetry."""
        self._event_handlers.append(handler)

    async def _emit_event(self, event_type: str, node_id: str, data: dict | None = None):
        event = {
            "pipeline_id": self.pipeline_id,
            "event": event_type,
            "node_id": node_id,
            "timestamp": time.time(),
            "data": data or {},
        }
        for handler in self._event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                pass

    def _get_root_nodes(self) -> list[str]:
        """Find nodes with no incoming edges."""
        targets = {e.target for e in self.edges}
        return [nid for nid in self.nodes if nid not in targets]

    def _is_node_ready(self, node_id: str) -> bool:
        """Check if all predecessor conditions are met."""
        predecessors = self._predecessors.get(node_id, [])
        if not predecessors:
            return True

        for edge in predecessors:
            source_node = self.nodes[edge.source]
            if edge.condition == EdgeCondition.ALWAYS:
                if source_node.status not in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED):
                    return False
            elif edge.condition == EdgeCondition.ON_SUCCESS:
                if source_node.status != NodeStatus.COMPLETED:
                    return False
            elif edge.condition == EdgeCondition.ON_FAILURE:
                if source_node.status != NodeStatus.FAILED:
                    return False
            elif edge.condition == EdgeCondition.CONDITIONAL:
                if source_node.status != NodeStatus.COMPLETED:
                    return False
                if edge.condition_fn and not edge.condition_fn(source_node.result):
                    return False
        return True

    def _should_skip(self, node_id: str) -> bool:
        """Determine if a node should be skipped (e.g., conditional edge not met)."""
        predecessors = self._predecessors.get(node_id, [])
        if not predecessors:
            return False

        # If ALL incoming edges have unmet conditions, skip
        all_unmet = True
        for edge in predecessors:
            source_node = self.nodes[edge.source]
            if edge.condition == EdgeCondition.ON_SUCCESS and source_node.status == NodeStatus.COMPLETED:
                all_unmet = False
            elif edge.condition == EdgeCondition.ON_FAILURE and source_node.status == NodeStatus.FAILED:
                all_unmet = False
            elif edge.condition == EdgeCondition.CONDITIONAL:
                if source_node.status == NodeStatus.COMPLETED:
                    if edge.condition_fn and edge.condition_fn(source_node.result):
                        all_unmet = False
            elif edge.condition == EdgeCondition.ALWAYS:
                if source_node.status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED):
                    all_unmet = False

        return all_unmet

    async def _execute_node(self, node: DAGNode) -> Any:
        """Execute a single node with retry, circuit breaker, and timeout."""
        if not node.circuit_breaker.can_execute():
            node.status = NodeStatus.CIRCUIT_OPEN
            node.error = f"Circuit breaker open for {node.name}"
            await self._emit_event("circuit_open", node.id)
            raise RuntimeError(node.error)

        node.status = NodeStatus.RUNNING
        node.start_time = time.monotonic()
        await self._emit_event("node_started", node.id, {"name": node.name})

        last_exc = None
        for attempt in range(node.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    node.execute_fn(self.context),
                    timeout=node.timeout,
                )
                node.result = result
                node.status = NodeStatus.COMPLETED
                node.end_time = time.monotonic()
                node.circuit_breaker.record_success()

                # Store result in shared context
                self.context[f"result:{node.id}"] = result

                await self._emit_event("node_completed", node.id, {
                    "duration_s": round(node.end_time - node.start_time, 3),
                    "attempt": attempt + 1,
                })
                return result

            except asyncio.TimeoutError:
                last_exc = TimeoutError(f"Node {node.name} timed out after {node.timeout}s")
                node.retry_count = attempt + 1
                if attempt < node.max_retries:
                    node.status = NodeStatus.RETRYING
                    await self._emit_event("node_retrying", node.id, {
                        "attempt": attempt + 1,
                        "reason": "timeout",
                    })
                    await asyncio.sleep(node.retry_delay * (2 ** attempt))

            except Exception as exc:
                last_exc = exc
                node.retry_count = attempt + 1
                if attempt < node.max_retries:
                    node.status = NodeStatus.RETRYING
                    await self._emit_event("node_retrying", node.id, {
                        "attempt": attempt + 1,
                        "reason": str(exc),
                    })
                    await asyncio.sleep(node.retry_delay * (2 ** attempt))

        # All retries exhausted
        node.status = NodeStatus.FAILED
        node.error = str(last_exc)
        node.end_time = time.monotonic()
        node.circuit_breaker.record_failure()

        await self._emit_event("node_failed", node.id, {
            "error": str(last_exc),
            "attempts": node.retry_count,
            "duration_s": round(node.end_time - node.start_time, 3),
        })
        raise last_exc

    def create_checkpoint(self) -> Checkpoint:
        """Create a serializable checkpoint of current execution state."""
        cp = Checkpoint(
            pipeline_id=self.pipeline_id,
            timestamp=time.time(),
            node_states={
                nid: {
                    "status": node.status.value,
                    "result": node.result if node.status == NodeStatus.COMPLETED else None,
                    "error": node.error,
                }
                for nid, node in self.nodes.items()
            },
            context={k: v for k, v in self.context.items() if not callable(v)},
            completed_nodes=[
                nid for nid, node in self.nodes.items()
                if node.status == NodeStatus.COMPLETED
            ],
        )
        self._checkpoints.append(cp)
        return cp

    def restore_checkpoint(self, checkpoint: Checkpoint):
        """Restore execution state from a checkpoint."""
        self.context.update(checkpoint.context)
        for nid, state in checkpoint.node_states.items():
            if nid in self.nodes:
                self.nodes[nid].status = NodeStatus(state["status"])
                self.nodes[nid].result = state.get("result")
                self.nodes[nid].error = state.get("error")

    async def execute(
        self,
        initial_context: dict[str, Any] | None = None,
        max_parallelism: int = 10,
    ) -> dict[str, Any]:
        """
        Execute the DAG with maximum parallelism.

        Uses a wave-based execution model:
        1. Find all ready nodes (dependencies met)
        2. Execute them in parallel (up to max_parallelism)
        3. After completion, find new ready nodes
        4. Repeat until no more nodes can run
        """
        if initial_context:
            self.context.update(initial_context)

        semaphore = asyncio.Semaphore(max_parallelism)
        start_time = time.monotonic()

        await self._emit_event("pipeline_started", "__root__", {
            "pipeline": self.name,
            "total_nodes": len(self.nodes),
        })

        completed = set()
        failed = set()
        skipped = set()

        while True:
            # Find all nodes ready to execute
            ready = []
            for nid, node in self.nodes.items():
                if node.status in (NodeStatus.PENDING, NodeStatus.QUEUED):
                    if nid in completed or nid in failed or nid in skipped:
                        continue
                    if self._should_skip(nid):
                        node.status = NodeStatus.SKIPPED
                        skipped.add(nid)
                        await self._emit_event("node_skipped", nid)
                        continue
                    if self._is_node_ready(nid):
                        ready.append(node)

            if not ready:
                # Check if we're truly done or deadlocked
                running = [n for n in self.nodes.values() if n.status == NodeStatus.RUNNING]
                if not running:
                    break
                # Wait for running tasks to complete
                await asyncio.sleep(0.1)
                continue

            # Sort by priority (higher first)
            ready.sort(key=lambda n: n.priority, reverse=True)

            # Execute ready nodes in parallel
            async def _run_with_sem(node: DAGNode):
                async with semaphore:
                    try:
                        await self._execute_node(node)
                        completed.add(node.id)
                    except Exception:
                        failed.add(node.id)

            tasks = [asyncio.create_task(_run_with_sem(n)) for n in ready]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Checkpoint after each wave
            self.create_checkpoint()

        duration = time.monotonic() - start_time

        await self._emit_event("pipeline_completed", "__root__", {
            "duration_s": round(duration, 3),
            "completed": len(completed),
            "failed": len(failed),
            "skipped": len(skipped),
        })

        return {
            "pipeline_id": self.pipeline_id,
            "duration_s": round(duration, 3),
            "nodes": {
                nid: {
                    "status": node.status.value,
                    "result": node.result,
                    "error": node.error,
                    "duration_s": round(node.end_time - node.start_time, 3)
                    if node.start_time and node.end_time else None,
                }
                for nid, node in self.nodes.items()
            },
            "context": self.context,
        }


# ---------------------------------------------------------------------------
# Pipeline Templates
# ---------------------------------------------------------------------------

class PipelineTemplate:
    """Pre-built DAG templates for common workflows."""

    @staticmethod
    def linear(*steps: tuple[str, str, Callable]) -> DAGBuilder:
        """Create a simple linear pipeline: step1 -> step2 -> step3."""
        builder = DAGBuilder("linear")
        ids = []
        for step_id, name, fn in steps:
            builder.add_node(step_id, name, fn)
            ids.append(step_id)
        builder.chain(*ids)
        return builder

    @staticmethod
    def map_reduce(
        scatter_id: str,
        scatter_fn: Callable,
        worker_specs: list[tuple[str, str, Callable]],
        gather_id: str,
        gather_fn: Callable,
    ) -> DAGBuilder:
        """Create a scatter-gather (map-reduce) pipeline."""
        builder = DAGBuilder("map_reduce")
        builder.add_node(scatter_id, "Scatter", scatter_fn)

        worker_ids = []
        for wid, name, fn in worker_specs:
            builder.add_node(wid, name, fn)
            worker_ids.append(wid)

        builder.add_node(gather_id, "Gather", gather_fn)
        builder.fan_out(scatter_id, *worker_ids)
        builder.fan_in(*worker_ids, target=gather_id)
        return builder

    @staticmethod
    def with_fallback(
        primary_id: str,
        primary_fn: Callable,
        fallback_id: str,
        fallback_fn: Callable,
        continue_id: str,
        continue_fn: Callable,
    ) -> DAGBuilder:
        """Create a pipeline with automatic fallback on failure."""
        builder = DAGBuilder("with_fallback")
        builder.add_node(primary_id, "Primary", primary_fn)
        builder.add_node(fallback_id, "Fallback", fallback_fn)
        builder.add_node(continue_id, "Continue", continue_fn)
        builder.on_failure(primary_id, fallback_id)
        builder.add_edge(primary_id, continue_id, EdgeCondition.ON_SUCCESS)
        builder.add_edge(fallback_id, continue_id, EdgeCondition.ON_SUCCESS)
        return builder
