"""
Agent Memory & Learning System.

Implements persistent memory capabilities for agents:
- Episodic Memory: remembers past task executions & outcomes
- Semantic Memory: stores learned patterns & best practices
- Working Memory: short-term context for current task
- Performance Analytics: tracks agent effectiveness over time
- Adaptive Learning: auto-tunes agent parameters based on outcomes

Uses Redis as the backing store for cross-session persistence.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Memory Records
# ---------------------------------------------------------------------------

@dataclass
class EpisodicMemory:
    """A single episodic memory — one task execution."""
    memory_id: str
    agent_id: str
    task_type: str
    input_summary: str
    output_summary: str
    success: bool
    quality_score: float  # 0.0 - 1.0
    duration_s: float
    cost_usd: float
    model_used: str
    timestamp: float = field(default_factory=time.time)
    feedback: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SemanticPattern:
    """A learned pattern — generalized from episodic memories."""
    pattern_id: str
    task_type: str
    description: str
    conditions: dict  # When this pattern applies
    strategy: dict  # What to do
    success_rate: float
    sample_count: int
    last_updated: float = field(default_factory=time.time)


@dataclass
class WorkingMemory:
    """Short-term memory for a single pipeline execution."""
    pipeline_id: str
    entries: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    ttl: float = 3600.0  # 1 hour default

    def store(self, key: str, value: Any):
        self.entries[key] = {"value": value, "stored_at": time.time()}

    def recall(self, key: str, default: Any = None) -> Any:
        entry = self.entries.get(key)
        if entry is None:
            return default
        return entry["value"]

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


@dataclass
class PerformanceProfile:
    """Aggregated performance statistics for an agent."""
    agent_id: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_cost_usd: float = 0.0
    avg_quality_score: float = 0.0
    avg_duration_s: float = 0.0
    task_type_scores: dict[str, float] = field(default_factory=dict)
    model_performance: dict[str, dict] = field(default_factory=dict)  # model -> {success_rate, avg_quality}
    trend: str = "stable"  # improving, stable, degrading
    _recent_scores: list[float] = field(default_factory=list, repr=False)


# ---------------------------------------------------------------------------
# Memory Store
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    Centralized memory system for all agents.

    Features:
    - Episodic memory with similarity search
    - Semantic pattern extraction
    - Performance tracking & analytics
    - Redis-backed persistence
    - Automatic memory consolidation
    """

    def __init__(self, redis_url: str | None = None):
        from config import settings
        self._redis_url = redis_url or settings.memory_redis_url
        self._redis = None
        self._episodic: dict[str, list[EpisodicMemory]] = defaultdict(list)
        self._semantic: dict[str, list[SemanticPattern]] = defaultdict(list)
        self._working: dict[str, WorkingMemory] = {}
        self._profiles: dict[str, PerformanceProfile] = {}
        self._initialized = False

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception:
                log.warning("memory.redis_unavailable", url=self._redis_url)
                self._redis = None
        return self._redis

    async def initialize(self):
        """Load persistent memories from Redis."""
        if self._initialized:
            return
        redis = await self._get_redis()
        if redis:
            try:
                # Load performance profiles
                profiles_raw = await redis.get("memory:profiles")
                if profiles_raw:
                    for agent_id, data in json.loads(profiles_raw).items():
                        self._profiles[agent_id] = PerformanceProfile(
                            agent_id=agent_id, **{k: v for k, v in data.items() if k != "agent_id"}
                        )

                # Load recent episodic memories (last 1000 per agent)
                agent_ids = await redis.smembers("memory:agents")
                for aid in (agent_ids or []):
                    raw = await redis.lrange(f"memory:episodic:{aid}", 0, 999)
                    for item in raw:
                        mem = json.loads(item)
                        self._episodic[aid].append(EpisodicMemory(**mem))

                log.info("memory.loaded", agents=len(self._profiles))
            except Exception as exc:
                log.warning("memory.load_failed", error=str(exc))

        self._initialized = True

    async def _persist_profile(self, agent_id: str):
        """Persist a performance profile to Redis."""
        redis = await self._get_redis()
        if redis:
            try:
                profiles_data = {
                    aid: {
                        "total_tasks": p.total_tasks,
                        "successful_tasks": p.successful_tasks,
                        "failed_tasks": p.failed_tasks,
                        "total_cost_usd": p.total_cost_usd,
                        "avg_quality_score": p.avg_quality_score,
                        "avg_duration_s": p.avg_duration_s,
                        "task_type_scores": p.task_type_scores,
                        "model_performance": p.model_performance,
                        "trend": p.trend,
                    }
                    for aid, p in self._profiles.items()
                }
                await redis.set("memory:profiles", json.dumps(profiles_data))
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Episodic Memory
    # -----------------------------------------------------------------------

    async def record_episode(self, memory: EpisodicMemory):
        """Record a task execution episode."""
        self._episodic[memory.agent_id].append(memory)

        # Persist to Redis
        redis = await self._get_redis()
        if redis:
            try:
                await redis.lpush(
                    f"memory:episodic:{memory.agent_id}",
                    json.dumps({
                        "memory_id": memory.memory_id,
                        "agent_id": memory.agent_id,
                        "task_type": memory.task_type,
                        "input_summary": memory.input_summary,
                        "output_summary": memory.output_summary,
                        "success": memory.success,
                        "quality_score": memory.quality_score,
                        "duration_s": memory.duration_s,
                        "cost_usd": memory.cost_usd,
                        "model_used": memory.model_used,
                        "timestamp": memory.timestamp,
                        "feedback": memory.feedback,
                        "metadata": memory.metadata,
                    }),
                )
                await redis.ltrim(f"memory:episodic:{memory.agent_id}", 0, 4999)
                await redis.sadd("memory:agents", memory.agent_id)
            except Exception:
                pass

        # Update performance profile
        await self._update_profile(memory)

    async def recall_similar(
        self,
        agent_id: str,
        task_type: str,
        input_keywords: list[str] | None = None,
        limit: int = 5,
        min_quality: float = 0.7,
    ) -> list[EpisodicMemory]:
        """Recall similar past episodes for context-aware decisions."""
        episodes = self._episodic.get(agent_id, [])

        # Filter by task type and quality
        relevant = [
            ep for ep in episodes
            if ep.task_type == task_type and ep.quality_score >= min_quality
        ]

        if input_keywords:
            # Score by keyword overlap
            def keyword_score(ep: EpisodicMemory) -> float:
                text = f"{ep.input_summary} {ep.output_summary}".lower()
                matches = sum(1 for kw in input_keywords if kw.lower() in text)
                return matches / max(len(input_keywords), 1)

            relevant.sort(key=keyword_score, reverse=True)
        else:
            # Sort by recency
            relevant.sort(key=lambda ep: ep.timestamp, reverse=True)

        return relevant[:limit]

    # -----------------------------------------------------------------------
    # Working Memory
    # -----------------------------------------------------------------------

    def create_working_memory(self, pipeline_id: str) -> WorkingMemory:
        """Create a new working memory scope for a pipeline execution."""
        wm = WorkingMemory(pipeline_id=pipeline_id)
        self._working[pipeline_id] = wm
        return wm

    def get_working_memory(self, pipeline_id: str) -> WorkingMemory | None:
        wm = self._working.get(pipeline_id)
        if wm and wm.is_expired():
            del self._working[pipeline_id]
            return None
        return wm

    def cleanup_working_memories(self):
        """Remove expired working memories."""
        expired = [pid for pid, wm in self._working.items() if wm.is_expired()]
        for pid in expired:
            del self._working[pid]

    # -----------------------------------------------------------------------
    # Performance Analytics
    # -----------------------------------------------------------------------

    async def _update_profile(self, memory: EpisodicMemory):
        """Update agent performance profile from a new episode."""
        agent_id = memory.agent_id
        if agent_id not in self._profiles:
            self._profiles[agent_id] = PerformanceProfile(agent_id=agent_id)

        profile = self._profiles[agent_id]
        profile.total_tasks += 1

        if memory.success:
            profile.successful_tasks += 1
        else:
            profile.failed_tasks += 1

        profile.total_cost_usd += memory.cost_usd

        # Exponential moving average
        alpha = 0.2
        profile.avg_quality_score = (
            alpha * memory.quality_score + (1 - alpha) * profile.avg_quality_score
            if profile.total_tasks > 1 else memory.quality_score
        )
        profile.avg_duration_s = (
            alpha * memory.duration_s + (1 - alpha) * profile.avg_duration_s
            if profile.total_tasks > 1 else memory.duration_s
        )

        # Task type scores
        current = profile.task_type_scores.get(memory.task_type, 0.5)
        profile.task_type_scores[memory.task_type] = (
            alpha * memory.quality_score + (1 - alpha) * current
        )

        # Model performance tracking
        model = memory.model_used
        if model not in profile.model_performance:
            profile.model_performance[model] = {"success_rate": 1.0, "avg_quality": memory.quality_score, "count": 0}
        mp = profile.model_performance[model]
        mp["count"] += 1
        mp["success_rate"] = alpha * (1.0 if memory.success else 0.0) + (1 - alpha) * mp["success_rate"]
        mp["avg_quality"] = alpha * memory.quality_score + (1 - alpha) * mp["avg_quality"]

        # Trend detection
        profile._recent_scores.append(memory.quality_score)
        if len(profile._recent_scores) > 20:
            profile._recent_scores = profile._recent_scores[-20:]

        if len(profile._recent_scores) >= 10:
            first_half = sum(profile._recent_scores[:10]) / 10
            second_half = sum(profile._recent_scores[10:]) / len(profile._recent_scores[10:])
            diff = second_half - first_half
            if diff > 0.05:
                profile.trend = "improving"
            elif diff < -0.05:
                profile.trend = "degrading"
            else:
                profile.trend = "stable"

        await self._persist_profile(agent_id)

    def get_profile(self, agent_id: str) -> PerformanceProfile | None:
        return self._profiles.get(agent_id)

    def get_all_profiles(self) -> dict[str, PerformanceProfile]:
        return dict(self._profiles)

    def get_best_model_for_task(self, agent_id: str, task_type: str) -> str | None:
        """Recommend the best model based on historical performance."""
        profile = self._profiles.get(agent_id)
        if not profile or not profile.model_performance:
            return None

        best_model = None
        best_score = -1.0
        for model, stats in profile.model_performance.items():
            score = stats["avg_quality"] * stats["success_rate"]
            if score > best_score and stats["count"] >= 3:
                best_score = score
                best_model = model
        return best_model

    # -----------------------------------------------------------------------
    # Semantic Pattern Extraction
    # -----------------------------------------------------------------------

    async def extract_patterns(self, agent_id: str, task_type: str, min_samples: int = 10) -> list[SemanticPattern]:
        """
        Analyze episodic memories to extract reusable patterns.

        This is a simplified version — a production system would use
        clustering or LLM-based pattern extraction.
        """
        episodes = [
            ep for ep in self._episodic.get(agent_id, [])
            if ep.task_type == task_type
        ]

        if len(episodes) < min_samples:
            return []

        # Group successful vs failed episodes
        successful = [ep for ep in episodes if ep.success and ep.quality_score >= 0.8]
        failed = [ep for ep in episodes if not ep.success or ep.quality_score < 0.5]

        patterns = []

        if successful:
            # Extract "what works" pattern
            avg_quality = sum(ep.quality_score for ep in successful) / len(successful)
            avg_duration = sum(ep.duration_s for ep in successful) / len(successful)
            models_used = defaultdict(int)
            for ep in successful:
                models_used[ep.model_used] += 1
            best_model = max(models_used, key=models_used.get) if models_used else "unknown"

            patterns.append(SemanticPattern(
                pattern_id=f"success_{agent_id}_{task_type}",
                task_type=task_type,
                description=f"Successful pattern for {task_type}: avg quality {avg_quality:.2f}",
                conditions={"task_type": task_type},
                strategy={
                    "recommended_model": best_model,
                    "expected_duration_s": avg_duration,
                    "expected_quality": avg_quality,
                    "sample_outputs": [ep.output_summary for ep in successful[:3]],
                },
                success_rate=len(successful) / max(len(episodes), 1),
                sample_count=len(successful),
            ))

        if failed:
            # Extract "what to avoid" pattern
            common_issues = defaultdict(int)
            for ep in failed:
                if ep.feedback:
                    common_issues[ep.feedback] += 1

            patterns.append(SemanticPattern(
                pattern_id=f"failure_{agent_id}_{task_type}",
                task_type=task_type,
                description=f"Failure pattern for {task_type}: {len(failed)} failures",
                conditions={"task_type": task_type, "failure_mode": True},
                strategy={
                    "common_issues": dict(common_issues),
                    "avoidance_tips": [f"Avoid: {issue}" for issue in list(common_issues.keys())[:5]],
                },
                success_rate=0.0,
                sample_count=len(failed),
            ))

        self._semantic[agent_id] = patterns
        return patterns

    def get_patterns(self, agent_id: str, task_type: str | None = None) -> list[SemanticPattern]:
        """Get learned patterns for an agent."""
        patterns = self._semantic.get(agent_id, [])
        if task_type:
            patterns = [p for p in patterns if p.task_type == task_type]
        return patterns

    # -----------------------------------------------------------------------
    # Adaptive Parameter Tuning
    # -----------------------------------------------------------------------

    def recommend_parameters(self, agent_id: str, task_type: str) -> dict:
        """
        Recommend agent parameters based on historical performance.

        Returns suggested model, temperature, max_tokens, and retry count.
        """
        profile = self._profiles.get(agent_id)
        if not profile:
            return {}

        recommendations = {}

        # Best model recommendation
        best_model = self.get_best_model_for_task(agent_id, task_type)
        if best_model:
            recommendations["model"] = best_model

        # Retry count based on failure rate
        success_rate = profile.successful_tasks / max(profile.total_tasks, 1)
        if success_rate < 0.7:
            recommendations["max_retries"] = 4
        elif success_rate < 0.9:
            recommendations["max_retries"] = 3
        else:
            recommendations["max_retries"] = 2

        # Timeout based on historical duration
        if profile.avg_duration_s > 0:
            recommendations["timeout"] = max(30, profile.avg_duration_s * 3)

        return recommendations


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_memory_store: MemoryStore | None = None


def get_memory_store(redis_url: str | None = None) -> MemoryStore:
    """Get the global memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore(redis_url)
    return _memory_store
