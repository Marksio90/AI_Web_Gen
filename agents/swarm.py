"""
Swarm Intelligence & Multi-Agent Consensus Engine.

Implements collective decision-making algorithms:
- Weighted Voting Ensemble (multiple agents vote on decisions)
- Debate Protocol (agents argue for/against, judge decides)
- Iterative Refinement Swarm (agents improve each other's work)
- Specialist Router (routes tasks to best-suited agent)
- Tournament Selection (competitive agent selection)

This module enables emergent intelligence from agent collaboration.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Core Types
# ---------------------------------------------------------------------------

class ConsensusStrategy(str, Enum):
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_VOTE = "weighted_vote"
    BEST_OF_N = "best_of_n"
    DEBATE = "debate"
    ITERATIVE_REFINEMENT = "iterative_refinement"
    TOURNAMENT = "tournament"


@dataclass
class AgentVote:
    """A single agent's vote or proposal."""
    agent_id: str
    agent_name: str
    proposal: Any
    confidence: float  # 0.0 - 1.0
    reasoning: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SwarmDecision:
    """The result of a swarm consensus process."""
    strategy: ConsensusStrategy
    winner: Any
    votes: list[AgentVote]
    confidence: float
    rounds: int
    duration_s: float
    dissent_ratio: float  # How much disagreement (0=unanimous, 1=total discord)
    metadata: dict = field(default_factory=dict)


@dataclass
class SpecialistProfile:
    """Describes an agent's area of expertise for routing."""
    agent_id: str
    agent_name: str
    specialties: list[str]
    performance_scores: dict[str, float] = field(default_factory=dict)  # task_type -> score
    total_tasks: int = 0
    success_rate: float = 1.0
    avg_latency_s: float = 0.0
    cost_per_task: float = 0.0


# ---------------------------------------------------------------------------
# Voting Ensemble
# ---------------------------------------------------------------------------

class VotingEnsemble:
    """
    Multiple agents vote on a decision, with optional weighting.

    Supports:
    - Equal-weight majority voting
    - Performance-weighted voting
    - Confidence-weighted voting
    - Quorum requirements
    """

    def __init__(
        self,
        agents: list[tuple[str, str, Callable[..., Coroutine]]],  # (id, name, fn)
        weights: dict[str, float] | None = None,
        quorum: float = 0.5,  # Minimum fraction of agents that must vote
    ):
        self.agents = agents
        self.weights = weights or {a[0]: 1.0 for a in agents}
        self.quorum = quorum

    async def vote(
        self,
        prompt: Any,
        timeout: float = 60.0,
        strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED_VOTE,
    ) -> SwarmDecision:
        """Collect votes from all agents and determine consensus."""
        start = time.monotonic()

        async def _get_vote(agent_id: str, agent_name: str, fn: Callable) -> AgentVote | None:
            try:
                result = await asyncio.wait_for(fn(prompt), timeout=timeout)
                if isinstance(result, dict):
                    return AgentVote(
                        agent_id=agent_id,
                        agent_name=agent_name,
                        proposal=result.get("proposal", result),
                        confidence=float(result.get("confidence", 0.8)),
                        reasoning=str(result.get("reasoning", "")),
                    )
                return AgentVote(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    proposal=result,
                    confidence=0.8,
                )
            except Exception as exc:
                log.warning("vote.failed", agent=agent_name, error=str(exc))
                return None

        # Collect all votes concurrently
        tasks = [_get_vote(aid, name, fn) for aid, name, fn in self.agents]
        raw_votes = await asyncio.gather(*tasks)
        votes = [v for v in raw_votes if v is not None]

        if len(votes) < len(self.agents) * self.quorum:
            raise RuntimeError(
                f"Quorum not reached: {len(votes)}/{len(self.agents)} "
                f"(need {self.quorum * 100}%)"
            )

        # Determine winner based on strategy
        if strategy == ConsensusStrategy.WEIGHTED_VOTE:
            winner, confidence, dissent = self._weighted_vote(votes)
        elif strategy == ConsensusStrategy.BEST_OF_N:
            winner, confidence, dissent = self._best_of_n(votes)
        else:
            winner, confidence, dissent = self._majority_vote(votes)

        duration = time.monotonic() - start
        return SwarmDecision(
            strategy=strategy,
            winner=winner,
            votes=votes,
            confidence=confidence,
            rounds=1,
            duration_s=round(duration, 3),
            dissent_ratio=dissent,
        )

    def _weighted_vote(self, votes: list[AgentVote]) -> tuple[Any, float, float]:
        """Weighted voting with confidence and agent weights."""
        score_map: dict[str, float] = {}
        proposal_map: dict[str, Any] = {}

        for vote in votes:
            key = self._proposal_key(vote.proposal)
            weight = self.weights.get(vote.agent_id, 1.0) * vote.confidence
            score_map[key] = score_map.get(key, 0) + weight
            proposal_map[key] = vote.proposal

        total_weight = sum(score_map.values())
        best_key = max(score_map, key=score_map.get)
        confidence = score_map[best_key] / total_weight if total_weight else 0
        dissent = 1.0 - confidence

        return proposal_map[best_key], confidence, dissent

    def _majority_vote(self, votes: list[AgentVote]) -> tuple[Any, float, float]:
        """Simple majority voting."""
        count_map: dict[str, int] = {}
        proposal_map: dict[str, Any] = {}

        for vote in votes:
            key = self._proposal_key(vote.proposal)
            count_map[key] = count_map.get(key, 0) + 1
            proposal_map[key] = vote.proposal

        best_key = max(count_map, key=count_map.get)
        confidence = count_map[best_key] / len(votes)
        dissent = 1.0 - confidence

        return proposal_map[best_key], confidence, dissent

    def _best_of_n(self, votes: list[AgentVote]) -> tuple[Any, float, float]:
        """Select the highest-confidence proposal."""
        best = max(votes, key=lambda v: v.confidence * self.weights.get(v.agent_id, 1.0))
        avg_confidence = sum(v.confidence for v in votes) / len(votes)
        dissent = 1.0 - avg_confidence
        return best.proposal, best.confidence, dissent

    @staticmethod
    def _proposal_key(proposal: Any) -> str:
        """Generate a hashable key from a proposal."""
        if isinstance(proposal, (str, int, float, bool)):
            return str(proposal)
        return hashlib.md5(json.dumps(proposal, sort_keys=True, default=str).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Debate Protocol
# ---------------------------------------------------------------------------

class DebateProtocol:
    """
    Structured debate between agents with a judge.

    Process:
    1. Proponent presents initial argument
    2. Opponent critiques
    3. Proponent rebuts
    4. Judge evaluates and decides

    This mirrors adversarial ML / Constitutional AI approaches.
    """

    def __init__(
        self,
        proponent_fn: Callable[..., Coroutine],
        opponent_fn: Callable[..., Coroutine],
        judge_fn: Callable[..., Coroutine],
        max_rounds: int = 3,
    ):
        self.proponent_fn = proponent_fn
        self.opponent_fn = opponent_fn
        self.judge_fn = judge_fn
        self.max_rounds = max_rounds

    async def debate(self, topic: str, context: dict | None = None) -> SwarmDecision:
        """Run a structured debate and return the judge's decision."""
        start = time.monotonic()
        votes = []
        debate_transcript = []

        for round_num in range(1, self.max_rounds + 1):
            # Proponent argues
            prop_input = {
                "topic": topic,
                "context": context or {},
                "round": round_num,
                "previous_debate": debate_transcript,
                "role": "proponent",
            }
            prop_result = await self.proponent_fn(prop_input)
            debate_transcript.append({"round": round_num, "role": "proponent", "argument": prop_result})

            votes.append(AgentVote(
                agent_id="proponent",
                agent_name="Proponent",
                proposal=prop_result,
                confidence=0.8,
                reasoning=f"Round {round_num} argument",
            ))

            # Opponent critiques
            opp_input = {
                "topic": topic,
                "context": context or {},
                "round": round_num,
                "previous_debate": debate_transcript,
                "role": "opponent",
                "proponent_argument": prop_result,
            }
            opp_result = await self.opponent_fn(opp_input)
            debate_transcript.append({"round": round_num, "role": "opponent", "argument": opp_result})

            votes.append(AgentVote(
                agent_id="opponent",
                agent_name="Opponent",
                proposal=opp_result,
                confidence=0.7,
                reasoning=f"Round {round_num} critique",
            ))

        # Judge evaluates the full debate
        judge_input = {
            "topic": topic,
            "context": context or {},
            "full_debate": debate_transcript,
            "role": "judge",
        }
        verdict = await self.judge_fn(judge_input)

        duration = time.monotonic() - start
        return SwarmDecision(
            strategy=ConsensusStrategy.DEBATE,
            winner=verdict,
            votes=votes,
            confidence=float(verdict.get("confidence", 0.85)) if isinstance(verdict, dict) else 0.85,
            rounds=self.max_rounds,
            duration_s=round(duration, 3),
            dissent_ratio=0.0,
            metadata={"transcript": debate_transcript},
        )


# ---------------------------------------------------------------------------
# Iterative Refinement Swarm
# ---------------------------------------------------------------------------

class IterativeRefinementSwarm:
    """
    Agents take turns improving each other's output.

    Process:
    1. Agent A produces initial draft
    2. Agent B reviews & improves
    3. Agent C reviews & improves
    4. Repeat until convergence or max rounds

    Models the "pair programming" / "code review" paradigm.
    """

    def __init__(
        self,
        agents: list[tuple[str, str, Callable[..., Coroutine]]],
        convergence_threshold: float = 0.95,
        max_rounds: int = 3,
    ):
        self.agents = agents
        self.convergence_threshold = convergence_threshold
        self.max_rounds = max_rounds

    async def refine(self, initial_input: Any) -> SwarmDecision:
        """Run iterative refinement until convergence."""
        start = time.monotonic()
        current_output = initial_input
        votes = []
        prev_score = 0.0

        for round_num in range(1, self.max_rounds + 1):
            for agent_id, agent_name, fn in self.agents:
                refinement_input = {
                    "current_version": current_output,
                    "round": round_num,
                    "agent_role": agent_name,
                    "instruction": "Review and improve the current version. "
                                   "Return the improved version with a quality score (0-1).",
                }
                result = await fn(refinement_input)

                score = float(result.get("score", 0.8)) if isinstance(result, dict) else 0.8
                improved = result.get("improved", result) if isinstance(result, dict) else result

                votes.append(AgentVote(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    proposal=improved,
                    confidence=score,
                    reasoning=f"Round {round_num} refinement",
                ))

                current_output = improved

                # Check convergence
                if score >= self.convergence_threshold:
                    log.info("swarm.converged", round=round_num, agent=agent_name, score=score)
                    break

                if abs(score - prev_score) < 0.02 and round_num > 1:
                    log.info("swarm.plateau", round=round_num, score=score)
                    break

                prev_score = score
            else:
                continue
            break

        duration = time.monotonic() - start
        final_confidence = votes[-1].confidence if votes else 0.0

        return SwarmDecision(
            strategy=ConsensusStrategy.ITERATIVE_REFINEMENT,
            winner=current_output,
            votes=votes,
            confidence=final_confidence,
            rounds=round_num,
            duration_s=round(duration, 3),
            dissent_ratio=1.0 - final_confidence,
        )


# ---------------------------------------------------------------------------
# Specialist Router
# ---------------------------------------------------------------------------

class SpecialistRouter:
    """
    Intelligent task routing based on agent expertise profiles.

    Features:
    - Skill-based routing
    - Performance-based routing (send to agent with best track record)
    - Load-aware routing
    - Cost-optimized routing
    """

    def __init__(self):
        self.specialists: dict[str, SpecialistProfile] = {}
        self._active_tasks: dict[str, int] = {}  # agent_id -> active count

    def register(self, profile: SpecialistProfile):
        """Register a specialist agent."""
        self.specialists[profile.agent_id] = profile
        self._active_tasks.setdefault(profile.agent_id, 0)

    def route(
        self,
        task_type: str,
        optimize_for: str = "performance",  # performance, cost, latency
        exclude: set[str] | None = None,
    ) -> SpecialistProfile | None:
        """Route a task to the best specialist."""
        exclude = exclude or set()
        candidates = [
            s for s in self.specialists.values()
            if task_type in s.specialties and s.agent_id not in exclude
        ]

        if not candidates:
            # Fallback to any agent
            candidates = [
                s for s in self.specialists.values()
                if s.agent_id not in exclude
            ]

        if not candidates:
            return None

        if optimize_for == "performance":
            return max(candidates, key=lambda s: s.performance_scores.get(task_type, s.success_rate))
        elif optimize_for == "cost":
            return min(candidates, key=lambda s: s.cost_per_task)
        elif optimize_for == "latency":
            return min(candidates, key=lambda s: s.avg_latency_s)
        elif optimize_for == "load":
            return min(candidates, key=lambda s: self._active_tasks.get(s.agent_id, 0))
        return candidates[0]

    def update_stats(
        self,
        agent_id: str,
        task_type: str,
        success: bool,
        latency_s: float,
        cost: float = 0.0,
    ):
        """Update performance statistics for a specialist."""
        if agent_id not in self.specialists:
            return

        profile = self.specialists[agent_id]
        profile.total_tasks += 1

        # Exponential moving average for scores
        alpha = 0.3
        current_score = profile.performance_scores.get(task_type, 0.5)
        new_score = 1.0 if success else 0.0
        profile.performance_scores[task_type] = alpha * new_score + (1 - alpha) * current_score

        # Update success rate (EMA)
        profile.success_rate = alpha * (1.0 if success else 0.0) + (1 - alpha) * profile.success_rate

        # Update latency (EMA)
        profile.avg_latency_s = alpha * latency_s + (1 - alpha) * profile.avg_latency_s

        # Update cost (EMA)
        if cost > 0:
            profile.cost_per_task = alpha * cost + (1 - alpha) * profile.cost_per_task


# ---------------------------------------------------------------------------
# Tournament Selection
# ---------------------------------------------------------------------------

class TournamentSelection:
    """
    Competitive tournament between agents.

    Process:
    1. All agents produce output for the same task
    2. Each output is scored by a judge agent
    3. Best output wins (optionally with elimination rounds)

    Models competitive evolution / genetic algorithm selection.
    """

    def __init__(
        self,
        competitors: list[tuple[str, str, Callable[..., Coroutine]]],
        judge_fn: Callable[..., Coroutine],
    ):
        self.competitors = competitors
        self.judge_fn = judge_fn

    async def run_tournament(
        self,
        task: Any,
        rounds: int = 1,
    ) -> SwarmDecision:
        """Run a tournament and select the best output."""
        start = time.monotonic()
        votes = []

        # All competitors produce output
        async def _compete(agent_id: str, agent_name: str, fn: Callable) -> AgentVote:
            try:
                result = await fn(task)
                return AgentVote(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    proposal=result,
                    confidence=0.0,  # Will be scored by judge
                )
            except Exception as exc:
                return AgentVote(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    proposal=None,
                    confidence=0.0,
                    reasoning=f"Failed: {exc}",
                )

        tasks = [_compete(aid, name, fn) for aid, name, fn in self.competitors]
        raw_votes = await asyncio.gather(*tasks)
        valid_votes = [v for v in raw_votes if v.proposal is not None]

        if not valid_votes:
            raise RuntimeError("All competitors failed")

        # Judge scores all entries
        judge_input = {
            "task": task,
            "entries": [
                {"agent": v.agent_name, "output": v.proposal}
                for v in valid_votes
            ],
        }
        scores = await self.judge_fn(judge_input)

        # Apply scores
        if isinstance(scores, dict) and "rankings" in scores:
            for ranking in scores["rankings"]:
                for v in valid_votes:
                    if v.agent_name == ranking.get("agent"):
                        v.confidence = float(ranking.get("score", 0))
                        v.reasoning = ranking.get("reasoning", "")
        elif isinstance(scores, list):
            for i, score_val in enumerate(scores):
                if i < len(valid_votes):
                    valid_votes[i].confidence = float(score_val) if isinstance(score_val, (int, float)) else 0.5

        votes = sorted(valid_votes, key=lambda v: v.confidence, reverse=True)
        winner = votes[0]

        duration = time.monotonic() - start
        return SwarmDecision(
            strategy=ConsensusStrategy.TOURNAMENT,
            winner=winner.proposal,
            votes=votes,
            confidence=winner.confidence,
            rounds=rounds,
            duration_s=round(duration, 3),
            dissent_ratio=1.0 - (winner.confidence / max(sum(v.confidence for v in votes), 0.01)),
        )
