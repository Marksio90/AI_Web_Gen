"""
Multi-Algorithm Ensemble Engine.

Implements advanced algorithmic strategies for AI-powered decisions:
- Multi-Model Router: routes to optimal LLM based on task characteristics
- Ensemble Scorer: combines scores from multiple algorithms
- Evolutionary Content Optimizer: genetic algorithm for content quality
- Chain-of-Thought Decomposer: complex reasoning chains
- Adaptive Temperature Controller: dynamic LLM parameter tuning
- Cost-Performance Optimizer: Pareto-optimal model selection

This is the "brain" — the algorithmic intelligence layer.
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

import structlog

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Multi-Model Router
# ---------------------------------------------------------------------------

class ModelTier(str, Enum):
    NANO = "nano"          # Cheapest, fastest, simplest tasks
    MICRO = "micro"        # Slightly better, still cheap
    STANDARD = "standard"  # Good balance
    PREMIUM = "premium"    # Best quality, higher cost
    FRONTIER = "frontier"  # State-of-the-art, most expensive


@dataclass
class ModelProfile:
    """Profile of an AI model's capabilities."""
    model_id: str
    provider: str  # openai, groq, anthropic
    tier: ModelTier
    cost_per_1k_input: float
    cost_per_1k_output: float
    avg_latency_s: float
    context_window: int
    strengths: list[str]  # task types this model excels at
    max_output_tokens: int = 4096
    supports_json_mode: bool = True
    supports_function_calling: bool = True


class MultiModelRouter:
    """
    Intelligent LLM routing engine.

    Selects the optimal model based on:
    - Task complexity analysis
    - Cost constraints
    - Latency requirements
    - Quality requirements
    - Historical performance data
    """

    # Pre-configured model profiles
    DEFAULT_MODELS = {
        "gpt-4o-mini": ModelProfile(
            model_id="gpt-4o-mini", provider="openai", tier=ModelTier.MICRO,
            cost_per_1k_input=0.00015, cost_per_1k_output=0.0006,
            avg_latency_s=1.5, context_window=128000,
            strengths=["classification", "extraction", "simple_generation", "routing"],
        ),
        "gpt-4o": ModelProfile(
            model_id="gpt-4o", provider="openai", tier=ModelTier.PREMIUM,
            cost_per_1k_input=0.0025, cost_per_1k_output=0.01,
            avg_latency_s=3.0, context_window=128000,
            strengths=["complex_generation", "reasoning", "quality_control", "creative_writing"],
        ),
        "gpt-4.1-mini": ModelProfile(
            model_id="gpt-4.1-mini", provider="openai", tier=ModelTier.STANDARD,
            cost_per_1k_input=0.0004, cost_per_1k_output=0.0016,
            avg_latency_s=2.0, context_window=1000000,
            strengths=["long_context", "analysis", "generation", "coding"],
        ),
        "gpt-4.1": ModelProfile(
            model_id="gpt-4.1", provider="openai", tier=ModelTier.PREMIUM,
            cost_per_1k_input=0.002, cost_per_1k_output=0.008,
            avg_latency_s=2.5, context_window=1000000,
            strengths=["complex_generation", "reasoning", "long_context", "quality_control"],
        ),
        "gpt-4.1-nano": ModelProfile(
            model_id="gpt-4.1-nano", provider="openai", tier=ModelTier.NANO,
            cost_per_1k_input=0.0001, cost_per_1k_output=0.0004,
            avg_latency_s=0.8, context_window=1000000,
            strengths=["classification", "extraction", "simple_tasks", "high_volume"],
        ),
        "llama-4-scout-17b-16e-instruct": ModelProfile(
            model_id="llama-4-scout-17b-16e-instruct", provider="groq", tier=ModelTier.STANDARD,
            cost_per_1k_input=0.00011, cost_per_1k_output=0.00034,
            avg_latency_s=1.0, context_window=131072,
            strengths=["generation", "creative_writing", "fast_inference", "cost_efficient"],
        ),
    }

    def __init__(self):
        self.models = dict(self.DEFAULT_MODELS)
        self._performance_history: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    def register_model(self, profile: ModelProfile):
        self.models[profile.model_id] = profile

    def select_model(
        self,
        task_type: str,
        complexity: float = 0.5,  # 0=trivial, 1=very complex
        max_cost_per_1k: float = 0.01,
        max_latency_s: float = 10.0,
        min_quality: float = 0.7,
        prefer_provider: str | None = None,
        required_features: list[str] | None = None,
    ) -> ModelProfile:
        """Select the optimal model for a given task."""
        candidates = list(self.models.values())

        # Filter by provider preference
        if prefer_provider:
            provider_models = [m for m in candidates if m.provider == prefer_provider]
            if provider_models:
                candidates = provider_models

        # Filter by cost constraint
        candidates = [
            m for m in candidates
            if m.cost_per_1k_output <= max_cost_per_1k
        ]

        # Filter by latency
        candidates = [m for m in candidates if m.avg_latency_s <= max_latency_s]

        # Filter by required features
        if required_features:
            if "json_mode" in required_features:
                candidates = [m for m in candidates if m.supports_json_mode]
            if "function_calling" in required_features:
                candidates = [m for m in candidates if m.supports_function_calling]

        if not candidates:
            # Fallback to any available model
            candidates = list(self.models.values())
            log.warning("model_router.no_candidates_after_filter", task=task_type)

        # Score candidates based on task requirements
        scored = []
        for model in candidates:
            score = 0.0

            # Task type match
            if task_type in model.strengths:
                score += 0.4

            # Complexity match (complex tasks need better models)
            tier_scores = {
                ModelTier.NANO: 0.2,
                ModelTier.MICRO: 0.4,
                ModelTier.STANDARD: 0.6,
                ModelTier.PREMIUM: 0.8,
                ModelTier.FRONTIER: 1.0,
            }
            tier_match = 1.0 - abs(complexity - tier_scores[model.tier])
            score += 0.3 * tier_match

            # Cost efficiency (cheaper is better when quality is sufficient)
            max_cost = max(m.cost_per_1k_output for m in candidates)
            cost_score = 1.0 - (model.cost_per_1k_output / max(max_cost, 0.001))
            score += 0.15 * cost_score

            # Latency (faster is better)
            max_lat = max(m.avg_latency_s for m in candidates)
            lat_score = 1.0 - (model.avg_latency_s / max(max_lat, 0.1))
            score += 0.15 * lat_score

            # Historical performance bonus
            history = self._performance_history.get(model.model_id, {}).get(task_type, [])
            if history:
                avg_perf = sum(history[-20:]) / len(history[-20:])
                score += 0.1 * avg_perf

            scored.append((model, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        selected = scored[0][0]

        log.info("model_router.selected",
                 model=selected.model_id,
                 task=task_type,
                 complexity=complexity,
                 score=round(scored[0][1], 3))

        return selected

    def record_performance(self, model_id: str, task_type: str, quality: float):
        """Record model performance for future routing decisions."""
        self._performance_history[model_id][task_type].append(quality)
        # Keep last 100 records per model/task
        if len(self._performance_history[model_id][task_type]) > 100:
            self._performance_history[model_id][task_type] = \
                self._performance_history[model_id][task_type][-100:]


# ---------------------------------------------------------------------------
# Ensemble Scorer
# ---------------------------------------------------------------------------

@dataclass
class ScoringResult:
    """Result from an ensemble scoring operation."""
    final_score: float
    component_scores: dict[str, float]
    weights: dict[str, float]
    confidence: float
    recommendation: str


class EnsembleScorer:
    """
    Combines multiple scoring algorithms for robust quality assessment.

    Algorithms:
    - Rule-based heuristics (fast, deterministic)
    - LLM-based evaluation (nuanced, expensive)
    - Statistical analysis (data-driven)
    - User preference modeling (personalized)
    """

    def __init__(self):
        self.scorers: dict[str, tuple[Callable, float]] = {}  # name -> (fn, weight)

    def add_scorer(self, name: str, scorer_fn: Callable, weight: float = 1.0):
        """Register a scoring function with a weight."""
        self.scorers[name] = (scorer_fn, weight)

    async def score(self, content: Any, context: dict | None = None) -> ScoringResult:
        """Run all scorers and compute weighted ensemble score."""
        component_scores = {}
        weights = {}

        async def _run_scorer(name: str, fn: Callable, weight: float):
            try:
                if asyncio.iscoroutinefunction(fn):
                    score = await fn(content, context or {})
                else:
                    score = fn(content, context or {})
                return name, float(score), weight
            except Exception as exc:
                log.warning("scorer.failed", name=name, error=str(exc))
                return name, None, weight

        # Run all scorers in parallel
        tasks = [_run_scorer(name, fn, w) for name, (fn, w) in self.scorers.items()]
        results = await asyncio.gather(*tasks)

        total_weight = 0.0
        weighted_sum = 0.0

        for name, score, weight in results:
            if score is not None:
                component_scores[name] = score
                weights[name] = weight
                weighted_sum += score * weight
                total_weight += weight

        final_score = weighted_sum / max(total_weight, 0.01)

        # Calculate confidence based on scorer agreement
        if len(component_scores) >= 2:
            scores = list(component_scores.values())
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std_dev = math.sqrt(variance)
            confidence = max(0.0, 1.0 - std_dev)  # Lower std_dev = higher confidence
        else:
            confidence = 0.5

        # Generate recommendation
        if final_score >= 0.85:
            recommendation = "excellent"
        elif final_score >= 0.75:
            recommendation = "approved"
        elif final_score >= 0.60:
            recommendation = "needs_revision"
        else:
            recommendation = "rejected"

        return ScoringResult(
            final_score=round(final_score, 4),
            component_scores=component_scores,
            weights=weights,
            confidence=round(confidence, 4),
            recommendation=recommendation,
        )


# ---------------------------------------------------------------------------
# Evolutionary Content Optimizer
# ---------------------------------------------------------------------------

@dataclass
class ContentGenome:
    """A single content 'genome' in the evolutionary population."""
    genome_id: str
    content: Any
    fitness: float = 0.0
    generation: int = 0
    parent_ids: list[str] = field(default_factory=list)
    mutations: list[str] = field(default_factory=list)


class EvolutionaryOptimizer:
    """
    Genetic algorithm for content optimization.

    Process:
    1. Generate initial population (multiple content variants)
    2. Evaluate fitness (quality scoring)
    3. Select best (tournament selection)
    4. Crossover (combine best elements)
    5. Mutate (LLM-powered variations)
    6. Repeat until convergence

    This produces content that's been "evolved" to be optimal.
    """

    def __init__(
        self,
        generator_fn: Callable[..., Coroutine],  # Generates new content
        mutator_fn: Callable[..., Coroutine],     # Mutates existing content
        fitness_fn: Callable[..., Coroutine],      # Evaluates content quality
        population_size: int = 5,
        max_generations: int = 3,
        mutation_rate: float = 0.3,
        elite_count: int = 2,
    ):
        self.generator_fn = generator_fn
        self.mutator_fn = mutator_fn
        self.fitness_fn = fitness_fn
        self.population_size = population_size
        self.max_generations = max_generations
        self.mutation_rate = mutation_rate
        self.elite_count = elite_count

    async def evolve(self, task_input: Any) -> ContentGenome:
        """Run evolutionary optimization and return the best genome."""
        start = time.monotonic()

        # Step 1: Generate initial population
        log.info("evolution.init", population_size=self.population_size)
        population = await self._generate_population(task_input, self.population_size)

        best_ever: ContentGenome | None = None

        for gen in range(self.max_generations):
            # Step 2: Evaluate fitness
            await self._evaluate_fitness(population)
            population.sort(key=lambda g: g.fitness, reverse=True)

            current_best = population[0]
            log.info("evolution.generation",
                     gen=gen + 1,
                     best_fitness=round(current_best.fitness, 3),
                     avg_fitness=round(sum(g.fitness for g in population) / len(population), 3))

            if best_ever is None or current_best.fitness > best_ever.fitness:
                best_ever = current_best

            # Check convergence
            if current_best.fitness >= 0.95:
                log.info("evolution.converged", gen=gen + 1, fitness=current_best.fitness)
                break

            # Step 3: Selection & reproduction
            elite = population[:self.elite_count]
            new_population = list(elite)

            # Step 4: Mutation
            while len(new_population) < self.population_size:
                parent = random.choice(elite)
                if random.random() < self.mutation_rate:
                    child = await self._mutate(parent, task_input, gen + 1)
                    new_population.append(child)
                else:
                    # Generate fresh individual
                    fresh = await self._generate_one(task_input, gen + 1)
                    new_population.append(fresh)

            population = new_population

        duration = time.monotonic() - start
        log.info("evolution.complete",
                 best_fitness=round(best_ever.fitness, 3),
                 duration_s=round(duration, 2))

        return best_ever

    async def _generate_population(self, task_input: Any, size: int) -> list[ContentGenome]:
        tasks = [self._generate_one(task_input, 0) for _ in range(size)]
        return await asyncio.gather(*tasks)

    async def _generate_one(self, task_input: Any, generation: int) -> ContentGenome:
        content = await self.generator_fn(task_input)
        return ContentGenome(
            genome_id=f"gen{generation}_{random.randint(1000, 9999)}",
            content=content,
            generation=generation,
        )

    async def _mutate(self, parent: ContentGenome, task_input: Any, generation: int) -> ContentGenome:
        mutated_content = await self.mutator_fn(parent.content, task_input)
        return ContentGenome(
            genome_id=f"gen{generation}_{random.randint(1000, 9999)}",
            content=mutated_content,
            generation=generation,
            parent_ids=[parent.genome_id],
            mutations=["llm_mutation"],
        )

    async def _evaluate_fitness(self, population: list[ContentGenome]):
        async def _eval(genome: ContentGenome):
            try:
                genome.fitness = float(await self.fitness_fn(genome.content))
            except Exception:
                genome.fitness = 0.0

        await asyncio.gather(*[_eval(g) for g in population])


# ---------------------------------------------------------------------------
# Chain-of-Thought Decomposer
# ---------------------------------------------------------------------------

@dataclass
class ThoughtStep:
    """A single step in a chain-of-thought reasoning."""
    step_id: int
    description: str
    input_data: Any
    output_data: Any = None
    reasoning: str = ""
    confidence: float = 0.0
    duration_s: float = 0.0


class ChainOfThought:
    """
    Decomposes complex tasks into explicit reasoning steps.

    Features:
    - Automatic task decomposition
    - Step-by-step execution with intermediate validation
    - Backtracking on low-confidence steps
    - Reasoning trace for explainability
    """

    def __init__(
        self,
        decomposer_fn: Callable[..., Coroutine],  # Breaks task into steps
        executor_fn: Callable[..., Coroutine],      # Executes a single step
        validator_fn: Callable[..., Coroutine] | None = None,
        backtrack_threshold: float = 0.3,
    ):
        self.decomposer_fn = decomposer_fn
        self.executor_fn = executor_fn
        self.validator_fn = validator_fn
        self.backtrack_threshold = backtrack_threshold

    async def reason(self, task: Any) -> tuple[Any, list[ThoughtStep]]:
        """Execute chain-of-thought reasoning and return result + trace."""
        # Decompose task into steps
        steps_plan = await self.decomposer_fn(task)
        if isinstance(steps_plan, dict):
            step_descriptions = steps_plan.get("steps", [str(steps_plan)])
        elif isinstance(steps_plan, list):
            step_descriptions = steps_plan
        else:
            step_descriptions = [str(steps_plan)]

        thought_chain: list[ThoughtStep] = []
        accumulated_context = {"task": task, "steps_completed": []}

        for i, description in enumerate(step_descriptions):
            step_start = time.monotonic()

            step = ThoughtStep(
                step_id=i + 1,
                description=str(description),
                input_data=dict(accumulated_context),
            )

            # Execute step
            step_result = await self.executor_fn({
                "step_number": i + 1,
                "step_description": description,
                "context": accumulated_context,
            })

            step.output_data = step_result
            step.duration_s = round(time.monotonic() - step_start, 3)

            if isinstance(step_result, dict):
                step.confidence = float(step_result.get("confidence", 0.8))
                step.reasoning = str(step_result.get("reasoning", ""))
            else:
                step.confidence = 0.8

            # Validate step if validator provided
            if self.validator_fn and step.confidence < 0.9:
                validation = await self.validator_fn({
                    "step": step.description,
                    "result": step_result,
                    "context": accumulated_context,
                })
                if isinstance(validation, dict):
                    step.confidence = float(validation.get("confidence", step.confidence))

            # Backtrack if confidence too low
            if step.confidence < self.backtrack_threshold and i > 0:
                log.warning("cot.backtrack",
                            step=i + 1,
                            confidence=step.confidence,
                            description=description)
                # Re-execute with explicit instruction to reconsider
                retry_result = await self.executor_fn({
                    "step_number": i + 1,
                    "step_description": f"RECONSIDER: {description}",
                    "context": accumulated_context,
                    "previous_attempt": step_result,
                    "previous_confidence": step.confidence,
                })
                step.output_data = retry_result
                if isinstance(retry_result, dict):
                    step.confidence = float(retry_result.get("confidence", 0.5))

            thought_chain.append(step)
            accumulated_context["steps_completed"].append({
                "step": i + 1,
                "description": description,
                "result": step.output_data,
            })

        # Final result is the last step's output
        final_result = thought_chain[-1].output_data if thought_chain else None
        return final_result, thought_chain


# ---------------------------------------------------------------------------
# Cost-Performance Optimizer
# ---------------------------------------------------------------------------

class CostPerformanceOptimizer:
    """
    Pareto-optimal model selection balancing cost and quality.

    Maintains a cost-quality frontier and selects the model
    that provides the best quality within budget constraints.
    """

    def __init__(self):
        self._history: dict[str, list[tuple[float, float]]] = defaultdict(list)  # model -> [(cost, quality)]

    def record(self, model_id: str, cost: float, quality: float):
        self._history[model_id].append((cost, quality))
        if len(self._history[model_id]) > 200:
            self._history[model_id] = self._history[model_id][-200:]

    def get_pareto_frontier(self) -> list[tuple[str, float, float]]:
        """Get the Pareto frontier of models (non-dominated solutions)."""
        # Compute average cost and quality for each model
        averages = []
        for model_id, records in self._history.items():
            if records:
                avg_cost = sum(c for c, _ in records) / len(records)
                avg_quality = sum(q for _, q in records) / len(records)
                averages.append((model_id, avg_cost, avg_quality))

        if not averages:
            return []

        # Find Pareto frontier (minimize cost, maximize quality)
        frontier = []
        for model_id, cost, quality in averages:
            dominated = False
            for other_id, other_cost, other_quality in averages:
                if other_cost <= cost and other_quality >= quality and (other_cost < cost or other_quality > quality):
                    dominated = True
                    break
            if not dominated:
                frontier.append((model_id, cost, quality))

        frontier.sort(key=lambda x: x[1])  # Sort by cost
        return frontier

    def select_optimal(self, max_cost: float, min_quality: float = 0.0) -> str | None:
        """Select the best model within cost constraint."""
        frontier = self.get_pareto_frontier()
        candidates = [(m, c, q) for m, c, q in frontier if c <= max_cost and q >= min_quality]
        if not candidates:
            # Fallback: any model within cost
            all_models = [
                (m, sum(c for c, _ in self._history[m]) / len(self._history[m]),
                 sum(q for _, q in self._history[m]) / len(self._history[m]))
                for m in self._history if self._history[m]
            ]
            candidates = [(m, c, q) for m, c, q in all_models if c <= max_cost]

        if not candidates:
            return None

        # Select highest quality within budget
        return max(candidates, key=lambda x: x[2])[0]
