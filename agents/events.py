"""
Event Bus & Real-Time Streaming System.

Implements a pub/sub event system for:
- Pipeline execution telemetry
- Real-time progress streaming to frontend
- Agent communication
- Metric collection
- Audit trail

Supports both in-process and Redis-backed pub/sub.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable, Coroutine

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------

class EventCategory(str, Enum):
    PIPELINE = "pipeline"
    AGENT = "agent"
    SWARM = "swarm"
    MEMORY = "memory"
    ALGORITHM = "algorithm"
    SYSTEM = "system"
    METRIC = "metric"


@dataclass
class Event:
    """A single event in the system."""
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    category: EventCategory = EventCategory.SYSTEM
    event_type: str = ""
    source: str = ""  # agent_id or component name
    pipeline_id: str = ""
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)
    severity: str = "info"  # debug, info, warning, error, critical

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "category": self.category.value,
            "event_type": self.event_type,
            "source": self.source,
            "pipeline_id": self.pipeline_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "severity": self.severity,
        }

    def to_sse(self) -> str:
        """Format as Server-Sent Event."""
        return f"event: {self.event_type}\ndata: {json.dumps(self.to_dict(), default=str)}\n\n"


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

class EventBus:
    """
    In-process event bus with async pub/sub.

    Features:
    - Topic-based subscription
    - Wildcard subscriptions
    - Event buffering for late subscribers
    - Async iterator interface for streaming
    - Redis pub/sub bridge for multi-instance
    """

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._wildcard_subscribers: list[asyncio.Queue] = []
        self._event_history: list[Event] = []
        self._max_history: int = 10000
        self._redis_bridge: _RedisBridge | None = None

    async def enable_redis_bridge(self, redis_url: str = "redis://redis:6379/2"):
        """Enable Redis pub/sub for cross-instance event propagation."""
        self._redis_bridge = _RedisBridge(redis_url, self)
        await self._redis_bridge.start()

    async def publish(self, event: Event):
        """Publish an event to all relevant subscribers."""
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Deliver to topic subscribers
        topic = f"{event.category.value}:{event.event_type}"
        for queue in self._subscribers.get(topic, []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Deliver to category subscribers
        for queue in self._subscribers.get(event.category.value, []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Deliver to wildcard subscribers
        for queue in self._wildcard_subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

        # Bridge to Redis
        if self._redis_bridge:
            await self._redis_bridge.publish(event)

    async def subscribe(
        self,
        topic: str | None = None,
        pipeline_id: str | None = None,
        buffer_size: int = 1000,
    ) -> AsyncIterator[Event]:
        """
        Subscribe to events. Yields events as they arrive.

        Args:
            topic: Specific topic (e.g., "pipeline:node_completed") or category (e.g., "pipeline")
            pipeline_id: Filter events for a specific pipeline
            buffer_size: Maximum events to buffer
        """
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=buffer_size)

        if topic is None:
            self._wildcard_subscribers.append(queue)
        else:
            self._subscribers[topic].append(queue)

        try:
            while True:
                event = await queue.get()
                if pipeline_id and event.pipeline_id != pipeline_id:
                    continue
                yield event
        finally:
            # Cleanup
            if topic is None:
                self._wildcard_subscribers.remove(queue)
            else:
                self._subscribers[topic].remove(queue)

    def get_history(
        self,
        category: EventCategory | None = None,
        pipeline_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Get recent event history with optional filters."""
        events = self._event_history
        if category:
            events = [e for e in events if e.category == category]
        if pipeline_id:
            events = [e for e in events if e.pipeline_id == pipeline_id]
        return events[-limit:]

    async def stream_sse(
        self,
        pipeline_id: str | None = None,
        categories: list[EventCategory] | None = None,
    ) -> AsyncIterator[str]:
        """Stream events as Server-Sent Events (SSE) format."""
        async for event in self.subscribe(pipeline_id=pipeline_id):
            if categories and event.category not in categories:
                continue
            yield event.to_sse()


class _RedisBridge:
    """Bridge between local event bus and Redis pub/sub."""

    CHANNEL = "ai_web_gen:events"

    def __init__(self, redis_url: str, event_bus: EventBus):
        self._redis_url = redis_url
        self._event_bus = event_bus
        self._redis = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None

    async def start(self):
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
            self._pubsub = self._redis.pubsub()
            await self._pubsub.subscribe(self.CHANNEL)
            self._listener_task = asyncio.create_task(self._listen())
            log.info("event_bridge.started")
        except Exception as exc:
            log.warning("event_bridge.start_failed", error=str(exc))

    async def publish(self, event: Event):
        if self._redis:
            try:
                await self._redis.publish(self.CHANNEL, json.dumps(event.to_dict(), default=str))
            except Exception:
                pass

    async def _listen(self):
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    event = Event(
                        event_id=data.get("event_id", ""),
                        category=EventCategory(data.get("category", "system")),
                        event_type=data.get("event_type", ""),
                        source=data.get("source", ""),
                        pipeline_id=data.get("pipeline_id", ""),
                        timestamp=data.get("timestamp", time.time()),
                        data=data.get("data", {}),
                        severity=data.get("severity", "info"),
                    )
                    # Republish locally (without bridging back to Redis)
                    old_bridge = self._event_bus._redis_bridge
                    self._event_bus._redis_bridge = None
                    await self._event_bus.publish(event)
                    self._event_bus._redis_bridge = old_bridge
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error("event_bridge.listener_error", error=str(exc))


# ---------------------------------------------------------------------------
# Metric Collector
# ---------------------------------------------------------------------------

class MetricCollector:
    """
    Collects and aggregates metrics from events.

    Provides real-time dashboarding data:
    - Pipeline throughput
    - Agent latencies
    - Success/failure rates
    - Cost tracking
    - Quality score distributions
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._collection_task: asyncio.Task | None = None

    async def start_collecting(self):
        """Start background metric collection from event bus."""
        self._collection_task = asyncio.create_task(self._collect_loop())

    async def _collect_loop(self):
        try:
            async for event in self._event_bus.subscribe():
                self._process_event(event)
        except asyncio.CancelledError:
            pass

    def _process_event(self, event: Event):
        """Extract metrics from an event."""
        if event.event_type == "node_completed":
            agent = event.data.get("name", "unknown")
            duration = event.data.get("duration_s", 0)
            self._counters[f"agent.{agent}.completed"] += 1
            self._histograms[f"agent.{agent}.duration_s"].append(duration)

        elif event.event_type == "node_failed":
            agent = event.data.get("name", "unknown")
            self._counters[f"agent.{agent}.failed"] += 1

        elif event.event_type == "pipeline_completed":
            duration = event.data.get("duration_s", 0)
            self._counters["pipeline.completed"] += 1
            self._histograms["pipeline.duration_s"].append(duration)

        elif event.event_type == "pipeline_started":
            self._counters["pipeline.started"] += 1

    def get_metrics(self) -> dict:
        """Get current metric snapshot."""
        metrics = {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {},
        }

        for name, values in self._histograms.items():
            if values:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                metrics["histograms"][name] = {
                    "count": n,
                    "min": sorted_vals[0],
                    "max": sorted_vals[-1],
                    "mean": sum(sorted_vals) / n,
                    "p50": sorted_vals[n // 2],
                    "p95": sorted_vals[int(n * 0.95)] if n >= 20 else sorted_vals[-1],
                    "p99": sorted_vals[int(n * 0.99)] if n >= 100 else sorted_vals[-1],
                }

        return metrics


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
