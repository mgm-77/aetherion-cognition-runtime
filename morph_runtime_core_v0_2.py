"""
MORPH Runtime Core v0.2
Adds Route Memory on top of the v0.1.1 ideas.

Main additions:
- RouteMemoryRecord
- RouteMemoryEngine
- historical retrieval of prior route patterns
- runtime updates after each run
- demo with two consecutive runs to show historical adaptation

This is still a prototype/simulator, not a real model runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple
import re
import json


class TaskType(str, Enum):
    SIMPLE = "simple"
    RETRIEVAL = "retrieval"
    CODING = "coding"
    MATH = "math"
    LONG_CONTEXT = "long_context"
    VERIFICATION_HEAVY = "verification_heavy"


class Difficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    CRITICAL = "critical"


@dataclass
class BudgetProfile:
    max_depth: int = 3
    verification_threshold: int = 2
    max_hot_items: int = 3
    max_warm_items: int = 3
    force_cold_tail: bool = True


@dataclass
class ContextItem:
    item_id: str
    text: str
    priority: float = 0.0
    dependencies: List[str] = field(default_factory=list)


@dataclass
class MemoryTiles:
    hot: List[ContextItem] = field(default_factory=list)
    warm: List[ContextItem] = field(default_factory=list)
    cold: List[ContextItem] = field(default_factory=list)
    latent_summary: List[str] = field(default_factory=list)


@dataclass
class RouteMemoryRecord:
    task_type: str
    run_count: int = 0
    avg_depth: float = 0.0
    verification_rate: float = 0.0
    preferred_hot_items: Dict[str, int] = field(default_factory=dict)
    preferred_modules: Dict[str, int] = field(default_factory=dict)


@dataclass
class RuntimeState:
    prompt: str
    task_type: TaskType
    budget: BudgetProfile
    active_modules: List[str] = field(default_factory=list)
    memory: MemoryTiles = field(default_factory=MemoryTiles)
    trace: List[Dict] = field(default_factory=list)
    verification_armed: bool = False
    historical_route_used: bool = False
    historical_record_snapshot: Optional[Dict] = None

    def log(self, event: str, **payload: object) -> None:
        self.trace.append({"event": event, **payload})


class PromptClassifier:
    CODING_HINTS = {
        "code": 2.0,
        "python": 2.0,
        "javascript": 2.0,
        "bug": 1.8,
        "function": 1.7,
        "class": 1.7,
        "compile": 1.8,
        "script": 1.6,
        "api": 1.4,
        "refactor": 2.0,
        "debug": 2.0,
        "stack trace": 2.2,
    }

    MATH_HINTS = {
        "prove": 2.0,
        "lemma": 1.8,
        "theorem": 1.8,
        "equation": 1.6,
        "integral": 1.6,
        "derivative": 1.6,
        "conjecture": 2.0,
        "prime": 1.3,
        "matrix": 1.3,
        "rk(": 2.0,
        "arithmetic progression": 2.0,
        "contradiction": 1.7,
    }

    RETRIEVAL_HINTS = {
        "find": 1.7,
        "search": 1.7,
        "look up": 1.7,
        "extract": 1.7,
        "retrieve": 1.7,
        "from the document": 1.8,
        "from the file": 1.8,
        "compare these": 1.6,
    }

    VERIFICATION_HINTS = {
        "verify": 2.0,
        "check carefully": 2.2,
        "double-check": 2.2,
        "validate": 2.0,
        "audit": 2.0,
        "be certain": 1.8,
        "prove rigorously": 2.2,
    }

    SIMPLE_HINTS = {
        "summary": 1.4,
        "short": 1.0,
        "friendly": 1.0,
        "brief": 1.0,
        "simple": 1.0,
        "overview": 1.1,
    }

    @classmethod
    def _score_category(cls, text: str, weighted_hints: Dict[str, float]) -> float:
        score = 0.0
        for hint, weight in weighted_hints.items():
            if hint in text:
                score += weight
        return score

    @classmethod
    def classify(cls, prompt: str, context_items: List[ContextItem]) -> TaskType:
        lower = prompt.lower()

        if len(prompt) > 1200 or len(context_items) > 12:
            return TaskType.LONG_CONTEXT

        scores = {
            TaskType.SIMPLE: cls._score_category(lower, cls.SIMPLE_HINTS),
            TaskType.RETRIEVAL: cls._score_category(lower, cls.RETRIEVAL_HINTS),
            TaskType.CODING: cls._score_category(lower, cls.CODING_HINTS),
            TaskType.MATH: cls._score_category(lower, cls.MATH_HINTS),
            TaskType.VERIFICATION_HEAVY: cls._score_category(lower, cls.VERIFICATION_HINTS),
        }

        scores[TaskType.LONG_CONTEXT] = 2.2 if ("long context" in lower or "unified architecture summary" in lower) else 0.0

        if ("short" in lower or "friendly" in lower or "summary" in lower) and scores[TaskType.CODING] < 2.5:
            scores[TaskType.SIMPLE] += 1.2

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        if best_score < 1.5:
            return TaskType.SIMPLE
        return best_type


class TokenDifficultyEstimator:
    CRITICAL_PATTERNS = [
        r"\btherefore\b",
        r"\bprove\b",
        r"\bcontradiction\b",
        r"=",
        r"->",
        r"\bif and only if\b",
        r"\bmust\b",
        r"\bcritical\b",
        r"\bunsafe\b",
        r"\bdelete\b",
        r"\bvalidate\b",
        r"\bverify\b",
    ]

    NORMAL_PATTERNS = [
        r"\bdefine\b",
        r"\bexplain\b",
        r"\bbecause\b",
        r"\bbranch\b",
        r"\bmodule\b",
        r"\bmemory\b",
        r"\bsummary\b",
        r"\barchitecture\b",
    ]

    @classmethod
    def estimate(cls, chunk: str, task_type: TaskType) -> Difficulty:
        lower = chunk.lower()

        if task_type in {TaskType.MATH, TaskType.VERIFICATION_HEAVY}:
            for pat in cls.CRITICAL_PATTERNS:
                if re.search(pat, lower):
                    return Difficulty.CRITICAL

        for pat in cls.CRITICAL_PATTERNS:
            if re.search(pat, lower):
                return Difficulty.CRITICAL

        for pat in cls.NORMAL_PATTERNS:
            if re.search(pat, lower):
                return Difficulty.NORMAL

        if len(chunk.strip()) < 20:
            return Difficulty.EASY

        return Difficulty.NORMAL


class DepthGovernor:
    TASK_BASE_DEPTH = {
        TaskType.SIMPLE: 1,
        TaskType.RETRIEVAL: 1,
        TaskType.CODING: 2,
        TaskType.MATH: 2,
        TaskType.LONG_CONTEXT: 2,
        TaskType.VERIFICATION_HEAVY: 2,
    }

    DIFFICULTY_BOOST = {
        Difficulty.EASY: 0,
        Difficulty.NORMAL: 0,
        Difficulty.CRITICAL: 1,
    }

    @classmethod
    def choose_depth(
        cls,
        difficulty: Difficulty,
        task_type: TaskType,
        budget: BudgetProfile,
        historical_record: Optional[RouteMemoryRecord] = None,
    ) -> int:
        depth = cls.TASK_BASE_DEPTH[task_type] + cls.DIFFICULTY_BOOST[difficulty]

        # Historical adaptation:
        # if prior average depth was consistently > 1.5 on this task type,
        # allow a slight upward preference.
        if historical_record and historical_record.run_count >= 1 and historical_record.avg_depth > 1.5:
            depth += 0 if difficulty == Difficulty.EASY else 0.2

        return max(1, min(int(round(depth)), budget.max_depth))


class MemoryTileManager:
    TASK_KEYWORDS = {
        TaskType.SIMPLE: ["summary", "friendly", "overview"],
        TaskType.RETRIEVAL: ["find", "compare", "extract", "retrieve", "activation pack", "flux"],
        TaskType.CODING: ["code", "debug", "class", "function", "runtime"],
        TaskType.MATH: ["prove", "contradiction", "theorem", "lemma", "mathematics", "equation"],
        TaskType.LONG_CONTEXT: ["long context", "memory", "summary", "reactivation", "architecture"],
        TaskType.VERIFICATION_HEAVY: ["verify", "validate", "critical", "safe", "check"],
    }

    @staticmethod
    def build_tiles(
        prompt: str,
        context_items: List[ContextItem],
        task_type: TaskType,
        budget: BudgetProfile,
        historical_record: Optional[RouteMemoryRecord] = None,
    ) -> MemoryTiles:
        prompt_lower = prompt.lower()
        task_keywords = MemoryTileManager.TASK_KEYWORDS.get(task_type, [])

        scored: List[Tuple[float, ContextItem]] = []
        for item in context_items:
            score = item.priority
            text_lower = item.text.lower()
            item_id_lower = item.item_id.lower()

            overlap = sum(1 for w in prompt_lower.split() if len(w) > 3 and w in text_lower)
            score += overlap * 0.18

            if item_id_lower in prompt_lower:
                score += 1.2

            keyword_hits = sum(1 for kw in task_keywords if kw in text_lower or kw in item_id_lower)
            score += keyword_hits * 0.35

            if task_type in {TaskType.MATH, TaskType.VERIFICATION_HEAVY} and "activation pack" in text_lower:
                score -= 0.15

            # Historical route memory boost
            if historical_record and item_id_lower in historical_record.preferred_hot_items:
                score += min(0.6, 0.12 * historical_record.preferred_hot_items[item_id_lower])

            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        ordered_items = [item for _, item in scored]

        hot = ordered_items[: budget.max_hot_items]
        warm = ordered_items[budget.max_hot_items : budget.max_hot_items + budget.max_warm_items]
        cold = ordered_items[budget.max_hot_items + budget.max_warm_items :]

        if budget.force_cold_tail and len(ordered_items) > 4 and not cold:
            if warm:
                cold = [warm.pop()]
            elif hot:
                cold = [hot.pop()]

        latent_summary = [
            MemoryTileManager._make_summary(item.text)
            for item in cold[: min(5, len(cold))]
        ]

        return MemoryTiles(hot=hot, warm=warm, cold=cold, latent_summary=latent_summary)

    @staticmethod
    def _make_summary(text: str, max_len: int = 100) -> str:
        text = " ".join(text.strip().split())
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."


class ReactivationGate:
    @staticmethod
    def maybe_reactivate(query: str, memory: MemoryTiles) -> Optional[ContextItem]:
        q = query.lower()

        for item in memory.warm:
            if any(token in item.text.lower() for token in q.split() if len(token) > 4):
                return item

        for item in memory.cold:
            summary = MemoryTileManager._make_summary(item.text).lower()
            if any(token in summary for token in q.split() if len(token) > 5):
                return item

        return None


class VerificationTrigger:
    @staticmethod
    def should_verify(
        task_type: TaskType,
        difficulty: Difficulty,
        chosen_depth: int,
        budget: BudgetProfile,
        chunk: str,
        historical_record: Optional[RouteMemoryRecord] = None,
    ) -> bool:
        if task_type == TaskType.VERIFICATION_HEAVY:
            return True
        if difficulty == Difficulty.CRITICAL and chosen_depth >= budget.verification_threshold:
            return True
        if task_type == TaskType.MATH and any(sym in chunk.lower() for sym in ["=", "therefore", "implies", "contradiction"]):
            return True

        # Historical pressure: if this route often used verification, allow slight carryover
        if historical_record and historical_record.verification_rate > 0.7 and task_type in {TaskType.MATH, TaskType.CODING}:
            if difficulty == Difficulty.NORMAL:
                return True

        return False


class RouteMemoryEngine:
    def __init__(self) -> None:
        self.records: Dict[str, RouteMemoryRecord] = {}

    def retrieve(self, task_type: TaskType) -> Optional[RouteMemoryRecord]:
        return self.records.get(task_type.value)

    def update(
        self,
        task_type: TaskType,
        chosen_depths: List[int],
        verification_armed: bool,
        hot_items: List[str],
        active_modules: List[str],
    ) -> None:
        key = task_type.value
        record = self.records.get(key)
        if record is None:
            record = RouteMemoryRecord(task_type=key)
            self.records[key] = record

        record.run_count += 1

        avg_depth_this_run = sum(chosen_depths) / max(1, len(chosen_depths))
        record.avg_depth = (
            ((record.avg_depth * (record.run_count - 1)) + avg_depth_this_run) / record.run_count
        )

        verify_num = 1.0 if verification_armed else 0.0
        record.verification_rate = (
            ((record.verification_rate * (record.run_count - 1)) + verify_num) / record.run_count
        )

        for item in hot_items:
            record.preferred_hot_items[item] = record.preferred_hot_items.get(item, 0) + 1

        for mod in active_modules:
            record.preferred_modules[mod] = record.preferred_modules.get(mod, 0) + 1

    def export(self) -> Dict[str, Dict]:
        return {k: asdict(v) for k, v in self.records.items()}


class MorphRuntimeCoreV02:
    def __init__(self, budget: Optional[BudgetProfile] = None, route_memory: Optional[RouteMemoryEngine] = None) -> None:
        self.budget = budget or BudgetProfile()
        self.route_memory = route_memory or RouteMemoryEngine()

    def run(self, prompt: str, context_items: List[ContextItem]) -> RuntimeState:
        task_type = PromptClassifier.classify(prompt, context_items)
        historical_record = self.route_memory.retrieve(task_type)

        state = RuntimeState(prompt=prompt, task_type=task_type, budget=self.budget)
        state.historical_route_used = historical_record is not None
        state.historical_record_snapshot = asdict(historical_record) if historical_record else None

        state.log(
            "task_classified",
            task_type=task_type.value,
            historical_route_used=state.historical_route_used,
        )

        state.memory = MemoryTileManager.build_tiles(
            prompt, context_items, task_type, self.budget, historical_record
        )
        state.log(
            "memory_tiled",
            hot=[x.item_id for x in state.memory.hot],
            warm=[x.item_id for x in state.memory.warm],
            cold=[x.item_id for x in state.memory.cold],
            latent_summary_count=len(state.memory.latent_summary),
        )

        state.active_modules = [
            "PromptClassifier",
            "TokenDifficultyEstimator",
            "DepthGovernor",
            "MemoryTileManager",
            "RouteMemoryEngine",
        ]

        chunks = self._make_chunks(prompt)
        chosen_depths: List[int] = []

        for idx, chunk in enumerate(chunks):
            difficulty = TokenDifficultyEstimator.estimate(chunk, task_type)
            depth = DepthGovernor.choose_depth(difficulty, task_type, self.budget, historical_record)
            chosen_depths.append(depth)

            verify = VerificationTrigger.should_verify(
                task_type, difficulty, depth, self.budget, chunk, historical_record
            )

            state.log(
                "chunk_processed",
                chunk_index=idx,
                chunk=chunk,
                difficulty=difficulty.value,
                chosen_depth=depth,
                verify=verify,
            )

            if verify:
                state.verification_armed = True
                if "VerificationTrigger" not in state.active_modules:
                    state.active_modules.append("VerificationTrigger")

            reactivated = ReactivationGate.maybe_reactivate(chunk, state.memory)
            if reactivated:
                if reactivated not in state.memory.hot:
                    state.memory.hot.append(reactivated)
                state.log(
                    "reactivation",
                    chunk_index=idx,
                    reactivated_item=reactivated.item_id,
                )
                if "ReactivationGate" not in state.active_modules:
                    state.active_modules.append("ReactivationGate")

        self.route_memory.update(
            task_type=task_type,
            chosen_depths=chosen_depths,
            verification_armed=state.verification_armed,
            hot_items=[x.item_id for x in state.memory.hot],
            active_modules=state.active_modules,
        )

        state.log(
            "route_memory_updated",
            task_type=task_type.value,
            record=self.route_memory.export().get(task_type.value, {}),
        )

        state.log(
            "runtime_complete",
            active_modules=state.active_modules,
            verification_armed=state.verification_armed,
        )
        return state

    @staticmethod
    def _make_chunks(prompt: str, chunk_size: int = 120) -> List[str]:
        text = " ".join(prompt.strip().split())
        if not text:
            return [""]
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def demo() -> None:
    context = [
        ContextItem(
            item_id="beal_method",
            text="Reusable Beal method using structural reduction, local valuations, and Lucas or Lehmer compression.",
            priority=0.8,
        ),
        ContextItem(
            item_id="morph_v05",
            text="MORPH v0.5 defines the Cognitive Fabric Runtime with route memory, residues, and unified orchestration.",
            priority=0.95,
        ),
        ContextItem(
            item_id="morph_v07",
            text="MORPH v0.7 adds multi-scale scheduling with immediate, short, medium, and deep horizons.",
            priority=0.85,
        ),
        ContextItem(
            item_id="math_simulator",
            text="The quantum super-research mathematics simulator includes branch atlas, verification stack, and discovery engine.",
            priority=0.9,
        ),
        ContextItem(
            item_id="activation_pack",
            text="The activation pack reactivates the simulator ecosystem in a new chat with manual rearm and canonical sources.",
            priority=0.7,
        ),
        ContextItem(
            item_id="flux_programming",
            text="Flux programming means loss minimization through living continuity, selective activation, and injection instead of full restart.",
            priority=0.88,
        ),
        ContextItem(
            item_id="long_context_notes",
            text=("Long context often needs memory tiles, reactivation gates, summaries, and selective hot-region promotion. " * 8),
            priority=0.6,
        ),
    ]

    route_memory = RouteMemoryEngine()
    runtime = MorphRuntimeCoreV02(route_memory=route_memory)

    prompt = "Prove why a structural contradiction route may be stronger than brute-force checking in a mathematics simulator."

    print("=== MORPH Runtime Core v0.2 Demo / Run 1 ===")
    result1 = runtime.run(prompt, context)
    print(f"Task type: {result1.task_type.value}")
    print(f"Historical route used: {result1.historical_route_used}")
    print(f"Hot memory: {[x.item_id for x in result1.memory.hot]}")
    print(f"Verification armed: {result1.verification_armed}")

    print("\n=== MORPH Runtime Core v0.2 Demo / Run 2 ===")
    result2 = runtime.run(prompt, context)
    print(f"Task type: {result2.task_type.value}")
    print(f"Historical route used: {result2.historical_route_used}")
    print(f"Historical record snapshot: {json.dumps(result2.historical_record_snapshot, indent=2)}")
    print(f"Hot memory: {[x.item_id for x in result2.memory.hot]}")
    print(f"Verification armed: {result2.verification_armed}")

    print("\n=== Route Memory Export ===")
    print(json.dumps(route_memory.export(), indent=2))


if __name__ == "__main__":
    demo()
