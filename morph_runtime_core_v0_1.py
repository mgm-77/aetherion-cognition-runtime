
"""
MORPH Runtime Core v0.1
Prototype implementation of:
- PromptClassifier
- TokenDifficultyEstimator
- DepthGovernor
- MemoryTileManager
- ReactivationGate
- VerificationTrigger

This is a simulator/prototype of the runtime logic, not a real model runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    max_hot_items: int = 4
    max_warm_items: int = 6


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
class RuntimeState:
    prompt: str
    task_type: TaskType
    budget: BudgetProfile
    active_modules: List[str] = field(default_factory=list)
    memory: MemoryTiles = field(default_factory=MemoryTiles)
    trace: List[Dict] = field(default_factory=list)
    verification_armed: bool = False

    def log(self, event: str, **payload: object) -> None:
        self.trace.append({"event": event, **payload})


class PromptClassifier:
    """Very small heuristic classifier for the first buildable core."""

    CODING_HINTS = [
        "code", "python", "javascript", "bug", "function", "class", "runtime",
        "compile", "script", "api", "refactor", "debug"
    ]
    MATH_HINTS = [
        "prove", "lemma", "theorem", "equation", "integral", "derivative",
        "conjecture", "prime", "matrix", "rk(", "arithmetic progression"
    ]
    RETRIEVAL_HINTS = [
        "find", "search", "look up", "extract", "retrieve", "from the document",
        "from the file", "compare these"
    ]
    VERIFICATION_HINTS = [
        "verify", "check carefully", "double-check", "validate", "audit",
        "be certain", "prove rigorously"
    ]

    @classmethod
    def classify(cls, prompt: str, context_items: List[ContextItem]) -> TaskType:
        lower = prompt.lower()

        if len(prompt) > 1200 or len(context_items) > 12:
            return TaskType.LONG_CONTEXT

        if any(h in lower for h in cls.VERIFICATION_HINTS):
            return TaskType.VERIFICATION_HEAVY

        if any(h in lower for h in cls.CODING_HINTS):
            return TaskType.CODING

        if any(h in lower for h in cls.MATH_HINTS):
            return TaskType.MATH

        if any(h in lower for h in cls.RETRIEVAL_HINTS):
            return TaskType.RETRIEVAL

        return TaskType.SIMPLE


class TokenDifficultyEstimator:
    """Heuristic token/chunk difficulty estimator."""

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
    ]

    NORMAL_PATTERNS = [
        r"\bdefine\b",
        r"\bexplain\b",
        r"\bbecause\b",
        r"\bbranch\b",
        r"\bmodule\b",
        r"\bmemory\b",
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
    """Maps difficulty and task type to an execution depth."""

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
    ) -> int:
        depth = cls.TASK_BASE_DEPTH[task_type] + cls.DIFFICULTY_BOOST[difficulty]
        return max(1, min(depth, budget.max_depth))


class MemoryTileManager:
    """Splits context into hot / warm / cold / latent summary zones."""

    @staticmethod
    def build_tiles(
        prompt: str,
        context_items: List[ContextItem],
        budget: BudgetProfile,
    ) -> MemoryTiles:
        prompt_lower = prompt.lower()

        scored: List[Tuple[float, ContextItem]] = []
        for item in context_items:
            score = item.priority
            text_lower = item.text.lower()

            overlap = sum(1 for w in prompt_lower.split() if len(w) > 3 and w in text_lower)
            score += overlap * 0.2
            if item.item_id.lower() in prompt_lower:
                score += 1.0

            scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        ordered_items = [item for _, item in scored]

        hot = ordered_items[: budget.max_hot_items]
        warm = ordered_items[budget.max_hot_items : budget.max_hot_items + budget.max_warm_items]
        cold = ordered_items[budget.max_hot_items + budget.max_warm_items :]

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
    """Reactivates warm/cold items selectively by summary anchors or dependency links."""

    @staticmethod
    def maybe_reactivate(
        query: str,
        memory: MemoryTiles,
    ) -> Optional[ContextItem]:
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
    """Arms extra checking for risky situations."""

    @staticmethod
    def should_verify(
        task_type: TaskType,
        difficulty: Difficulty,
        chosen_depth: int,
        budget: BudgetProfile,
        chunk: str,
    ) -> bool:
        if task_type == TaskType.VERIFICATION_HEAVY:
            return True
        if difficulty == Difficulty.CRITICAL and chosen_depth >= budget.verification_threshold:
            return True
        if task_type == TaskType.MATH and any(sym in chunk for sym in ["=", "therefore", "implies"]):
            return True
        return False


class MorphRuntimeCoreV01:
    """Main prototype runtime."""

    def __init__(self, budget: Optional[BudgetProfile] = None) -> None:
        self.budget = budget or BudgetProfile()

    def run(self, prompt: str, context_items: List[ContextItem]) -> RuntimeState:
        task_type = PromptClassifier.classify(prompt, context_items)
        state = RuntimeState(prompt=prompt, task_type=task_type, budget=self.budget)
        state.log("task_classified", task_type=task_type.value)

        state.memory = MemoryTileManager.build_tiles(prompt, context_items, self.budget)
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
        ]

        chunks = self._make_chunks(prompt)
        for idx, chunk in enumerate(chunks):
            difficulty = TokenDifficultyEstimator.estimate(chunk, task_type)
            depth = DepthGovernor.choose_depth(difficulty, task_type, self.budget)
            verify = VerificationTrigger.should_verify(
                task_type, difficulty, depth, self.budget, chunk
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
            text="Reusable Beal method using structural reduction, local valuations, and Lucas/Lehmer compression.",
            priority=0.8,
        ),
        ContextItem(
            item_id="morph_v05",
            text="MORPH v0.5 defines the Cognitive Fabric Runtime with route memory, residues, and unified orchestration.",
            priority=0.9,
        ),
        ContextItem(
            item_id="morph_v07",
            text="MORPH v0.7 adds multi-scale scheduling with immediate, short, medium, and deep horizons.",
            priority=0.7,
        ),
        ContextItem(
            item_id="math_simulator",
            text="The quantum super-research mathematics simulator includes branch atlas, verification stack, and discovery engine.",
            priority=0.85,
        ),
    ]

    prompt = (
        "Write a runtime architecture note that explains how MORPH v0.5 and v0.7 "
        "support a mathematics simulator, verify the critical transition points, "
        "and reactivate the right memory if the branch structure becomes important."
    )

    runtime = MorphRuntimeCoreV01()
    result = runtime.run(prompt, context)

    print("=== MORPH Runtime Core v0.1 Demo ===")
    print(f"Task type: {result.task_type.value}")
    print(f"Active modules: {result.active_modules}")
    print(f"Verification armed: {result.verification_armed}")
    print("Hot memory:", [x.item_id for x in result.memory.hot])
    print("Warm memory:", [x.item_id for x in result.memory.warm])
    print("Cold memory:", [x.item_id for x in result.memory.cold])
    print("\nTrace:")
    print(json.dumps(result.trace, indent=2))


if __name__ == "__main__":
    demo()
