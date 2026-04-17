"""
MORPH Runtime Core v0.5
Cognitive Fabric Runtime

This version unifies:
- task classification
- memory tiling
- route memory
- speculative routing
- persistent inference residue
- verification control
- reactivation

into one explicit fabric-level runtime.

Still a prototype/simulator, not a production runtime.
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


class FabricPhase(str, Enum):
    ORIENT = "orient"
    ROUTE_SELECTION = "route_selection"
    MEMORY_CONFIGURATION = "memory_configuration"
    EXECUTION = "execution"
    STABILIZATION = "stabilization"
    COMPLETE = "complete"


@dataclass
class BudgetProfile:
    max_depth: int = 3
    verification_threshold: int = 2
    max_hot_items: int = 3
    max_warm_items: int = 3
    force_cold_tail: bool = True
    max_candidate_routes: int = 3
    max_residue_bundles_per_task: int = 5


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
    preferred_route_names: Dict[str, int] = field(default_factory=dict)


@dataclass
class CandidateRoute:
    name: str
    depth_bias: float
    verification_bias: float
    reactivation_bias: float
    memory_focus: List[str] = field(default_factory=list)


@dataclass
class CandidateRouteScore:
    route_name: str
    score: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class ResidueBundle:
    task_type: str
    bundle_id: str
    route_name: str
    hot_items: List[str] = field(default_factory=list)
    active_modules: List[str] = field(default_factory=list)
    verification_armed: bool = False
    avg_depth: float = 0.0
    usage_count: int = 0


@dataclass
class FabricStateModel:
    task_type: Optional[str] = None
    phase: str = FabricPhase.ORIENT.value
    chosen_route: Optional[str] = None
    verification_armed: bool = False
    active_modules: List[str] = field(default_factory=list)
    health_score: float = 1.0
    historical_route_used: bool = False
    residue_bundle_count: int = 0
    depth_history: List[int] = field(default_factory=list)
    hot_memory_ids: List[str] = field(default_factory=list)
    warm_memory_ids: List[str] = field(default_factory=list)
    cold_memory_ids: List[str] = field(default_factory=list)


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
    candidate_routes: List[CandidateRoute] = field(default_factory=list)
    route_scores: List[CandidateRouteScore] = field(default_factory=list)
    chosen_route: Optional[str] = None
    residue_bundles_used: List[Dict] = field(default_factory=list)
    fabric_state: FabricStateModel = field(default_factory=FabricStateModel)

    def log(self, event: str, **payload: object) -> None:
        self.trace.append({"event": event, **payload})


class PromptClassifier:
    CODING_HINTS = {
        "code": 2.0, "python": 2.0, "javascript": 2.0, "bug": 1.8, "function": 1.7,
        "class": 1.7, "compile": 1.8, "script": 1.6, "api": 1.4, "refactor": 2.0,
        "debug": 2.0, "stack trace": 2.2,
    }
    MATH_HINTS = {
        "prove": 2.0, "lemma": 1.8, "theorem": 1.8, "equation": 1.6, "integral": 1.6,
        "derivative": 1.6, "conjecture": 2.0, "prime": 1.3, "matrix": 1.3, "rk(": 2.0,
        "arithmetic progression": 2.0, "contradiction": 1.7,
    }
    RETRIEVAL_HINTS = {
        "find": 1.7, "search": 1.7, "look up": 1.7, "extract": 1.7, "retrieve": 1.7,
        "from the document": 1.8, "from the file": 1.8, "compare these": 1.6,
    }
    VERIFICATION_HINTS = {
        "verify": 2.0, "check carefully": 2.2, "double-check": 2.2, "validate": 2.0,
        "audit": 2.0, "be certain": 1.8, "prove rigorously": 2.2,
    }
    SIMPLE_HINTS = {
        "summary": 1.4, "short": 1.0, "friendly": 1.0, "brief": 1.0, "simple": 1.0,
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
        if scores[best_type] < 1.5:
            return TaskType.SIMPLE
        return best_type


class TokenDifficultyEstimator:
    CRITICAL_PATTERNS = [
        r"\btherefore\b", r"\bprove\b", r"\bcontradiction\b", r"=", r"->",
        r"\bif and only if\b", r"\bmust\b", r"\bcritical\b", r"\bunsafe\b",
        r"\bdelete\b", r"\bvalidate\b", r"\bverify\b",
    ]
    NORMAL_PATTERNS = [
        r"\bdefine\b", r"\bexplain\b", r"\bbecause\b", r"\bbranch\b", r"\bmodule\b",
        r"\bmemory\b", r"\bsummary\b", r"\barchitecture\b",
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
        chosen_route_name: Optional[str] = None,
    ) -> None:
        key = task_type.value
        record = self.records.get(key)
        if record is None:
            record = RouteMemoryRecord(task_type=key)
            self.records[key] = record

        record.run_count += 1
        avg_depth_this_run = sum(chosen_depths) / max(1, len(chosen_depths))
        record.avg_depth = (((record.avg_depth * (record.run_count - 1)) + avg_depth_this_run) / record.run_count)
        verify_num = 1.0 if verification_armed else 0.0
        record.verification_rate = (((record.verification_rate * (record.run_count - 1)) + verify_num) / record.run_count)

        for item in hot_items:
            record.preferred_hot_items[item] = record.preferred_hot_items.get(item, 0) + 1
        for mod in active_modules:
            record.preferred_modules[mod] = record.preferred_modules.get(mod, 0) + 1
        if chosen_route_name:
            record.preferred_route_names[chosen_route_name] = record.preferred_route_names.get(chosen_route_name, 0) + 1

    def export(self) -> Dict[str, Dict]:
        return {k: asdict(v) for k, v in self.records.items()}


class ResidueRegistry:
    def __init__(self, max_bundles_per_task: int = 5) -> None:
        self.max_bundles_per_task = max_bundles_per_task
        self.registry: Dict[str, List[ResidueBundle]] = {}

    def retrieve(self, task_type: TaskType) -> List[ResidueBundle]:
        bundles = self.registry.get(task_type.value, [])
        for b in bundles:
            b.usage_count += 1
        return bundles[:]

    def store(
        self,
        task_type: TaskType,
        chosen_route_name: str,
        hot_items: List[str],
        active_modules: List[str],
        verification_armed: bool,
        avg_depth: float,
    ) -> None:
        key = task_type.value
        bundles = self.registry.setdefault(key, [])
        bundle_id = f"{key}_bundle_{len(bundles)+1}"
        bundle = ResidueBundle(
            task_type=key,
            bundle_id=bundle_id,
            route_name=chosen_route_name,
            hot_items=hot_items[:],
            active_modules=active_modules[:],
            verification_armed=verification_armed,
            avg_depth=avg_depth,
            usage_count=0,
        )
        bundles.append(bundle)
        if len(bundles) > self.max_bundles_per_task:
            bundles.pop(0)

    def export(self) -> Dict[str, List[Dict]]:
        return {k: [asdict(b) for b in v] for k, v in self.registry.items()}


class CandidateRouteGenerator:
    @staticmethod
    def generate(task_type: TaskType, historical_record: Optional[RouteMemoryRecord], budget: BudgetProfile) -> List[CandidateRoute]:
        if task_type == TaskType.MATH:
            routes = [
                CandidateRoute("math_deep_verify", 0.8, 1.0, 0.2, ["math_simulator", "beal_method"]),
                CandidateRoute("math_structural", 0.4, 0.8, 0.4, ["math_simulator", "morph_v05"]),
                CandidateRoute("math_contextual", 0.2, 0.4, 0.8, ["math_simulator", "long_context_notes"]),
            ]
        elif task_type == TaskType.CODING:
            routes = [
                CandidateRoute("coding_debug", 0.5, 0.4, 0.2, ["morph_v05", "flux_programming"]),
                CandidateRoute("coding_refactor", 0.3, 0.2, 0.1, ["morph_v05", "morph_v07"]),
                CandidateRoute("coding_verify", 0.6, 0.7, 0.1, ["morph_v05", "activation_pack"]),
            ]
        elif task_type == TaskType.RETRIEVAL:
            routes = [
                CandidateRoute("retrieval_targeted", 0.1, 0.1, 0.9, ["activation_pack", "flux_programming"]),
                CandidateRoute("retrieval_compare", 0.2, 0.2, 0.7, ["flux_programming", "morph_v05"]),
                CandidateRoute("retrieval_broad", 0.1, 0.0, 0.5, ["long_context_notes", "math_simulator"]),
            ]
        elif task_type == TaskType.LONG_CONTEXT:
            routes = [
                CandidateRoute("context_reactivation", 0.2, 0.2, 1.0, ["long_context_notes", "activation_pack"]),
                CandidateRoute("context_summary", 0.1, 0.1, 0.8, ["long_context_notes", "flux_programming"]),
                CandidateRoute("context_structure", 0.3, 0.2, 0.7, ["morph_v05", "math_simulator"]),
            ]
        elif task_type == TaskType.VERIFICATION_HEAVY:
            routes = [
                CandidateRoute("verify_strict", 0.5, 1.0, 0.2, ["morph_v05", "math_simulator"]),
                CandidateRoute("verify_balanced", 0.4, 0.8, 0.3, ["morph_v07", "flux_programming"]),
                CandidateRoute("verify_contextual", 0.3, 0.7, 0.6, ["activation_pack", "long_context_notes"]),
            ]
        else:
            routes = [
                CandidateRoute("simple_light", 0.0, 0.0, 0.1, ["morph_v05"]),
                CandidateRoute("simple_summary", 0.1, 0.0, 0.2, ["morph_v07", "flux_programming"]),
            ]

        if historical_record and historical_record.preferred_route_names:
            routes.sort(key=lambda r: historical_record.preferred_route_names.get(r.name, 0), reverse=True)

        return routes[: budget.max_candidate_routes]


class BranchScoringLayer:
    @staticmethod
    def score_all(
        routes: List[CandidateRoute],
        task_type: TaskType,
        historical_record: Optional[RouteMemoryRecord],
        residue_bundles: List[ResidueBundle],
    ) -> List[CandidateRouteScore]:
        results: List[CandidateRouteScore] = []

        residue_route_counts: Dict[str, int] = {}
        residue_hot_items: Dict[str, int] = {}
        for b in residue_bundles:
            residue_route_counts[b.route_name] = residue_route_counts.get(b.route_name, 0) + 1
            for item in b.hot_items:
                residue_hot_items[item] = residue_hot_items.get(item, 0) + 1

        for route in routes:
            score = 0.0
            reasons: List[str] = []

            score += route.depth_bias * 0.8
            score += route.verification_bias * 1.0
            score += route.reactivation_bias * 0.7

            if task_type == TaskType.MATH and "math" in route.name:
                score += 0.8
                reasons.append("math_route_match")
            if task_type == TaskType.RETRIEVAL and "retrieval" in route.name:
                score += 0.8
                reasons.append("retrieval_route_match")
            if task_type == TaskType.LONG_CONTEXT and "context" in route.name:
                score += 0.8
                reasons.append("context_route_match")
            if task_type == TaskType.VERIFICATION_HEAVY and "verify" in route.name:
                score += 0.8
                reasons.append("verify_route_match")

            if historical_record and route.name in historical_record.preferred_route_names:
                hist = historical_record.preferred_route_names[route.name]
                score += min(1.0, hist * 0.2)
                reasons.append("historical_preference")

            if route.name in residue_route_counts:
                score += min(0.8, residue_route_counts[route.name] * 0.2)
                reasons.append("residue_route_support")

            memory_overlap = sum(1 for item in route.memory_focus if item in residue_hot_items)
            if memory_overlap > 0:
                score += min(0.6, memory_overlap * 0.2)
                reasons.append("residue_memory_overlap")

            results.append(CandidateRouteScore(route.name, round(score, 3), reasons))

        results.sort(key=lambda x: x.score, reverse=True)
        return results


class EarlyCollapseController:
    @staticmethod
    def select(scores: List[CandidateRouteScore], routes: List[CandidateRoute]) -> CandidateRoute:
        top = scores[0]
        for route in routes:
            if route.name == top.route_name:
                return route
        return routes[0]


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
        chosen_route: Optional[CandidateRoute] = None,
        residue_bundles: Optional[List[ResidueBundle]] = None,
    ) -> MemoryTiles:
        prompt_lower = prompt.lower()
        task_keywords = MemoryTileManager.TASK_KEYWORDS.get(task_type, [])
        residue_hot_counts: Dict[str, int] = {}

        if residue_bundles:
            for b in residue_bundles:
                for item in b.hot_items:
                    residue_hot_counts[item] = residue_hot_counts.get(item, 0) + 1

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

            if historical_record and item_id_lower in historical_record.preferred_hot_items:
                score += min(0.6, 0.12 * historical_record.preferred_hot_items[item_id_lower])

            if chosen_route and item_id_lower in [x.lower() for x in chosen_route.memory_focus]:
                score += 0.7

            if item_id_lower in residue_hot_counts:
                score += min(0.8, residue_hot_counts[item_id_lower] * 0.15)

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

        latent_summary = [MemoryTileManager._make_summary(item.text) for item in cold[: min(5, len(cold))]]
        return MemoryTiles(hot=hot, warm=warm, cold=cold, latent_summary=latent_summary)

    @staticmethod
    def _make_summary(text: str, max_len: int = 100) -> str:
        text = " ".join(text.strip().split())
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."


class ReactivationGate:
    @staticmethod
    def maybe_reactivate(
        query: str,
        memory: MemoryTiles,
        chosen_route: Optional[CandidateRoute] = None,
        residue_bundles: Optional[List[ResidueBundle]] = None,
    ) -> Optional[ContextItem]:
        q = query.lower()
        route_focus = [x.lower() for x in chosen_route.memory_focus] if chosen_route else []
        residue_focus = set()
        if residue_bundles:
            for b in residue_bundles:
                residue_focus.update(x.lower() for x in b.hot_items)

        for item in memory.warm:
            if any(token in item.text.lower() for token in q.split() if len(token) > 4):
                return item
            if item.item_id.lower() in route_focus or item.item_id.lower() in residue_focus:
                return item

        for item in memory.cold:
            summary = MemoryTileManager._make_summary(item.text).lower()
            if any(token in summary for token in q.split() if len(token) > 5):
                return item
            if item.item_id.lower() in route_focus or item.item_id.lower() in residue_focus:
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
        chosen_route: Optional[CandidateRoute] = None,
        residue_bundles: Optional[List[ResidueBundle]] = None,
    ) -> bool:
        if task_type == TaskType.VERIFICATION_HEAVY:
            return True
        if difficulty == Difficulty.CRITICAL and chosen_depth >= budget.verification_threshold:
            return True
        if task_type == TaskType.MATH and any(sym in chunk.lower() for sym in ["=", "therefore", "implies", "contradiction"]):
            return True
        if historical_record and historical_record.verification_rate > 0.7 and task_type in {TaskType.MATH, TaskType.CODING}:
            if difficulty == Difficulty.NORMAL:
                return True
        if chosen_route and chosen_route.verification_bias > 0.5 and difficulty != Difficulty.EASY:
            return True
        if residue_bundles:
            residue_verify_rate = sum(1 for b in residue_bundles if b.verification_armed) / max(1, len(residue_bundles))
            if residue_verify_rate > 0.7 and difficulty != Difficulty.EASY:
                return True
        return False


class DepthGovernor:
    TASK_BASE_DEPTH = {
        TaskType.SIMPLE: 1, TaskType.RETRIEVAL: 1, TaskType.CODING: 2,
        TaskType.MATH: 2, TaskType.LONG_CONTEXT: 2, TaskType.VERIFICATION_HEAVY: 2,
    }
    DIFFICULTY_BOOST = {
        Difficulty.EASY: 0, Difficulty.NORMAL: 0, Difficulty.CRITICAL: 1,
    }

    @classmethod
    def choose_depth(
        cls,
        difficulty: Difficulty,
        task_type: TaskType,
        budget: BudgetProfile,
        historical_record: Optional[RouteMemoryRecord] = None,
        chosen_route: Optional[CandidateRoute] = None,
        residue_bundles: Optional[List[ResidueBundle]] = None,
    ) -> int:
        depth = cls.TASK_BASE_DEPTH[task_type] + cls.DIFFICULTY_BOOST[difficulty]

        if historical_record and historical_record.run_count >= 1 and historical_record.avg_depth > 1.5:
            depth += 0 if difficulty == Difficulty.EASY else 0.2
        if chosen_route:
            depth += chosen_route.depth_bias
        if residue_bundles:
            residue_depth = sum(b.avg_depth for b in residue_bundles) / max(1, len(residue_bundles))
            if residue_depth > 1.5:
                depth += 0.2

        return max(1, min(int(round(depth)), budget.max_depth))


class FabricAssemblyEngine:
    @staticmethod
    def build_fabric(
        prompt: str,
        context_items: List[ContextItem],
        budget: BudgetProfile,
        route_memory: RouteMemoryEngine,
        residue_registry: ResidueRegistry,
    ) -> Tuple[TaskType, Optional[RouteMemoryRecord], List[ResidueBundle], List[CandidateRoute], List[CandidateRouteScore], CandidateRoute]:
        task_type = PromptClassifier.classify(prompt, context_items)
        historical_record = route_memory.retrieve(task_type)
        residue_bundles = residue_registry.retrieve(task_type)
        candidate_routes = CandidateRouteGenerator.generate(task_type, historical_record, budget)
        route_scores = BranchScoringLayer.score_all(candidate_routes, task_type, historical_record, residue_bundles)
        chosen_route = EarlyCollapseController.select(route_scores, candidate_routes)
        return task_type, historical_record, residue_bundles, candidate_routes, route_scores, chosen_route


class FabricHealthMonitor:
    @staticmethod
    def evaluate(
        verification_armed: bool,
        chosen_depths: List[int],
        residue_bundle_count: int,
    ) -> float:
        avg_depth = sum(chosen_depths) / max(1, len(chosen_depths))
        score = 1.0
        if verification_armed:
            score -= 0.1
        if avg_depth > 2.5:
            score -= 0.1
        if residue_bundle_count > 2:
            score -= 0.05
        return max(0.5, round(score, 3))


class FabricOrchestrator:
    def __init__(
        self,
        budget: Optional[BudgetProfile] = None,
        route_memory: Optional[RouteMemoryEngine] = None,
        residue_registry: Optional[ResidueRegistry] = None,
    ) -> None:
        self.budget = budget or BudgetProfile()
        self.route_memory = route_memory or RouteMemoryEngine()
        self.residue_registry = residue_registry or ResidueRegistry(self.budget.max_residue_bundles_per_task)

    def run(self, prompt: str, context_items: List[ContextItem]) -> RuntimeState:
        task_type, historical_record, residue_bundles, candidate_routes, route_scores, chosen_route = FabricAssemblyEngine.build_fabric(
            prompt, context_items, self.budget, self.route_memory, self.residue_registry
        )

        state = RuntimeState(prompt=prompt, task_type=task_type, budget=self.budget)
        state.historical_route_used = historical_record is not None
        state.historical_record_snapshot = asdict(historical_record) if historical_record else None
        state.residue_bundles_used = [asdict(b) for b in residue_bundles]
        state.candidate_routes = candidate_routes
        state.route_scores = route_scores
        state.chosen_route = chosen_route.name

        state.fabric_state.task_type = task_type.value
        state.fabric_state.historical_route_used = state.historical_route_used
        state.fabric_state.residue_bundle_count = len(residue_bundles)

        state.log("fabric_phase", phase=FabricPhase.ORIENT.value)
        state.log("task_classified", task_type=task_type.value, historical_route_used=state.historical_route_used)

        state.fabric_state.phase = FabricPhase.ROUTE_SELECTION.value
        state.log("fabric_phase", phase=FabricPhase.ROUTE_SELECTION.value)
        state.log("residue_retrieved", bundle_count=len(residue_bundles), bundles=state.residue_bundles_used)
        state.log("candidate_routes_generated", routes=[asdict(r) for r in candidate_routes])
        state.log("route_scores", scores=[asdict(s) for s in route_scores])
        state.log("route_selected", chosen_route=chosen_route.name)

        state.fabric_state.phase = FabricPhase.MEMORY_CONFIGURATION.value
        state.log("fabric_phase", phase=FabricPhase.MEMORY_CONFIGURATION.value)
        state.memory = MemoryTileManager.build_tiles(
            prompt, context_items, task_type, self.budget, historical_record, chosen_route, residue_bundles
        )
        state.fabric_state.hot_memory_ids = [x.item_id for x in state.memory.hot]
        state.fabric_state.warm_memory_ids = [x.item_id for x in state.memory.warm]
        state.fabric_state.cold_memory_ids = [x.item_id for x in state.memory.cold]
        state.log(
            "memory_tiled",
            hot=state.fabric_state.hot_memory_ids,
            warm=state.fabric_state.warm_memory_ids,
            cold=state.fabric_state.cold_memory_ids,
            latent_summary_count=len(state.memory.latent_summary),
        )

        state.active_modules = [
            "FabricAssemblyEngine",
            "FabricOrchestrator",
            "FabricHealthMonitor",
            "PromptClassifier",
            "TokenDifficultyEstimator",
            "DepthGovernor",
            "MemoryTileManager",
            "RouteMemoryEngine",
            "ResidueRegistry",
            "CandidateRouteGenerator",
            "BranchScoringLayer",
            "EarlyCollapseController",
        ]
        state.fabric_state.active_modules = state.active_modules[:]
        state.fabric_state.chosen_route = chosen_route.name

        state.fabric_state.phase = FabricPhase.EXECUTION.value
        state.log("fabric_phase", phase=FabricPhase.EXECUTION.value)

        chunks = self._make_chunks(prompt)
        chosen_depths: List[int] = []

        for idx, chunk in enumerate(chunks):
            difficulty = TokenDifficultyEstimator.estimate(chunk, task_type)
            depth = DepthGovernor.choose_depth(difficulty, task_type, self.budget, historical_record, chosen_route, residue_bundles)
            chosen_depths.append(depth)
            state.fabric_state.depth_history.append(depth)

            verify = VerificationTrigger.should_verify(
                task_type, difficulty, depth, self.budget, chunk, historical_record, chosen_route, residue_bundles
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
                state.fabric_state.verification_armed = True
                if "VerificationTrigger" not in state.active_modules:
                    state.active_modules.append("VerificationTrigger")

            reactivated = ReactivationGate.maybe_reactivate(chunk, state.memory, chosen_route, residue_bundles)
            if reactivated:
                if reactivated not in state.memory.hot:
                    state.memory.hot.append(reactivated)
                state.log("reactivation", chunk_index=idx, reactivated_item=reactivated.item_id)
                if "ReactivationGate" not in state.active_modules:
                    state.active_modules.append("ReactivationGate")

        state.fabric_state.phase = FabricPhase.STABILIZATION.value
        state.log("fabric_phase", phase=FabricPhase.STABILIZATION.value)
        state.fabric_state.health_score = FabricHealthMonitor.evaluate(
            verification_armed=state.verification_armed,
            chosen_depths=chosen_depths,
            residue_bundle_count=len(residue_bundles),
        )
        state.log("fabric_health", health_score=state.fabric_state.health_score)

        avg_depth = sum(chosen_depths) / max(1, len(chosen_depths))

        self.route_memory.update(
            task_type=task_type,
            chosen_depths=chosen_depths,
            verification_armed=state.verification_armed,
            hot_items=[x.item_id for x in state.memory.hot],
            active_modules=state.active_modules,
            chosen_route_name=chosen_route.name,
        )

        self.residue_registry.store(
            task_type=task_type,
            chosen_route_name=chosen_route.name,
            hot_items=[x.item_id for x in state.memory.hot],
            active_modules=state.active_modules,
            verification_armed=state.verification_armed,
            avg_depth=avg_depth,
        )

        state.log("route_memory_updated", task_type=task_type.value, record=self.route_memory.export().get(task_type.value, {}))
        state.log("residue_stored", task_type=task_type.value, registry=self.residue_registry.export().get(task_type.value, []))

        state.fabric_state.phase = FabricPhase.COMPLETE.value
        state.log("fabric_phase", phase=FabricPhase.COMPLETE.value)
        state.log("runtime_complete", active_modules=state.active_modules, verification_armed=state.verification_armed)

        return state

    @staticmethod
    def _make_chunks(prompt: str, chunk_size: int = 120) -> List[str]:
        text = " ".join(prompt.strip().split())
        if not text:
            return [""]
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def demo() -> None:
    context = [
        ContextItem("beal_method", "Reusable Beal method using structural reduction, local valuations, and Lucas or Lehmer compression.", 0.8),
        ContextItem("morph_v05", "MORPH v0.5 defines the Cognitive Fabric Runtime with route memory, residues, and unified orchestration.", 0.95),
        ContextItem("morph_v07", "MORPH v0.7 adds multi-scale scheduling with immediate, short, medium, and deep horizons.", 0.85),
        ContextItem("math_simulator", "The quantum super-research mathematics simulator includes branch atlas, verification stack, and discovery engine.", 0.9),
        ContextItem("activation_pack", "The activation pack reactivates the simulator ecosystem in a new chat with manual rearm and canonical sources.", 0.7),
        ContextItem("flux_programming", "Flux programming means loss minimization through living continuity, selective activation, and injection instead of full restart.", 0.88),
        ContextItem("long_context_notes", ("Long context often needs memory tiles, reactivation gates, summaries, and selective hot-region promotion. " * 8), 0.6),
    ]

    route_memory = RouteMemoryEngine()
    residue_registry = ResidueRegistry()
    runtime = FabricOrchestrator(route_memory=route_memory, residue_registry=residue_registry)

    prompt = "Prove why a structural contradiction route may be stronger than brute-force checking in a mathematics simulator."

    print("=== MORPH Runtime Core v0.5 Demo / Run 1 ===")
    result1 = runtime.run(prompt, context)
    print(f"Task type: {result1.task_type.value}")
    print(f"Chosen route: {result1.chosen_route}")
    print(f"Fabric phase: {result1.fabric_state.phase}")
    print(f"Fabric health: {result1.fabric_state.health_score}")
    print(f"Residue bundles used: {len(result1.residue_bundles_used)}")
    print(f"Hot memory: {[x.item_id for x in result1.memory.hot]}")
    print(f"Verification armed: {result1.verification_armed}")

    print("\n=== MORPH Runtime Core v0.5 Demo / Run 2 ===")
    result2 = runtime.run(prompt, context)
    print(f"Task type: {result2.task_type.value}")
    print(f"Chosen route: {result2.chosen_route}")
    print(f"Fabric phase: {result2.fabric_state.phase}")
    print(f"Fabric health: {result2.fabric_state.health_score}")
    print(f"Historical route used: {result2.historical_route_used}")
    print(f"Residue bundles used: {len(result2.residue_bundles_used)}")
    print(f"Hot memory: {[x.item_id for x in result2.memory.hot]}")
    print(f"Verification armed: {result2.verification_armed}")

    print("\n=== Fabric State Snapshot ===")
    print(json.dumps(asdict(result2.fabric_state), indent=2))
    print("\n=== Route Memory Export ===")
    print(json.dumps(route_memory.export(), indent=2))
    print("\n=== Residue Registry Export ===")
    print(json.dumps(residue_registry.export(), indent=2))


if __name__ == "__main__":
    demo()
