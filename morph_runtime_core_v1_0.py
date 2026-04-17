"""
MORPH Runtime Core v1.0
Runtime State Persistence + Resume

Adds on top of v0.9:
- state persistence to JSON
- resume from saved state
- restore route memory / residue / deferred registries
- last fabric state snapshot
- last schedule snapshot
- simple state manager

Prototype only.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional
import re
import json
from pathlib import Path


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
    HORIZON_PLANNING = "horizon_planning"
    MULTI_SCALE_SCHEDULING = "multi_scale_scheduling"
    ADAPTIVE_REBALANCING = "adaptive_rebalancing"
    CONFLICT_ARBITRATION = "conflict_arbitration"
    EXECUTION = "execution"
    STABILIZATION = "stabilization"
    COMPLETE = "complete"


class Horizon(str, Enum):
    IMMEDIATE = "immediate"
    SHORT = "short"
    MEDIUM = "medium"
    DEEP = "deep"


@dataclass
class BudgetProfile:
    max_depth: int = 3
    verification_threshold: int = 2
    max_hot_items: int = 3
    max_warm_items: int = 3
    force_cold_tail: bool = True
    max_candidate_routes: int = 3
    max_residue_bundles_per_task: int = 5
    max_deferred_items_per_task: int = 12
    deferred_trigger_on_medium_normal: bool = True
    deferred_trigger_on_deep_normal: bool = True


@dataclass
class ContextItem:
    item_id: str
    text: str
    priority: float = 0.0


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
class DeferredWorkItem:
    task_type: str
    item_id: str
    horizon: str
    description: str
    source_route: str
    source_chunk_index: Optional[int] = None
    priority: float = 0.0
    reuse_count: int = 0


@dataclass
class HorizonPlan:
    immediate: List[str] = field(default_factory=list)
    short: List[str] = field(default_factory=list)
    medium: List[str] = field(default_factory=list)
    deep: List[str] = field(default_factory=list)


@dataclass
class MultiScaleSchedule:
    immediate_queue: List[str] = field(default_factory=list)
    short_queue: List[str] = field(default_factory=list)
    medium_queue: List[str] = field(default_factory=list)
    deep_queue: List[str] = field(default_factory=list)


@dataclass
class ArbitrationDecision:
    item: str
    from_horizon: str
    to_horizon: str
    reason: str


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
    horizon_loads: Dict[str, int] = field(default_factory=dict)
    deferred_item_count: int = 0
    schedule_loads: Dict[str, int] = field(default_factory=dict)
    horizon_pressure: Dict[str, float] = field(default_factory=dict)
    route_confidence: float = 0.0
    arbitration_count: int = 0


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
    horizon_plan: HorizonPlan = field(default_factory=HorizonPlan)
    schedule: MultiScaleSchedule = field(default_factory=MultiScaleSchedule)
    deferred_items_used: List[Dict] = field(default_factory=list)
    deferred_items_created: List[Dict] = field(default_factory=list)
    arbitration_trace: List[Dict] = field(default_factory=list)

    def log(self, event: str, **payload: object) -> None:
        self.trace.append({"event": event, **payload})


class PromptClassifier:
    @classmethod
    def classify(cls, prompt: str, context_items: List[ContextItem]) -> TaskType:
        lower = prompt.lower()
        if len(prompt) > 1200 or len(context_items) > 12:
            return TaskType.LONG_CONTEXT
        scores = {
            TaskType.SIMPLE: sum(w for h, w in {"summary":1.4,"short":1,"friendly":1,"brief":1,"simple":1,"overview":1.1}.items() if h in lower),
            TaskType.RETRIEVAL: sum(w for h, w in {"find":1.7,"search":1.7,"look up":1.7,"extract":1.7,"retrieve":1.7,"from the document":1.8,"from the file":1.8,"compare these":1.6}.items() if h in lower),
            TaskType.CODING: sum(w for h, w in {"code":2,"python":2,"javascript":2,"bug":1.8,"function":1.7,"class":1.7,"compile":1.8,"script":1.6,"api":1.4,"refactor":2,"debug":2,"stack trace":2.2}.items() if h in lower),
            TaskType.MATH: sum(w for h, w in {"prove":2,"lemma":1.8,"theorem":1.8,"equation":1.6,"integral":1.6,"derivative":1.6,"conjecture":2,"prime":1.3,"matrix":1.3,"rk(":2,"arithmetic progression":2,"contradiction":1.7}.items() if h in lower),
            TaskType.VERIFICATION_HEAVY: sum(w for h, w in {"verify":2,"check carefully":2.2,"double-check":2.2,"validate":2,"audit":2,"be certain":1.8,"prove rigorously":2.2}.items() if h in lower),
            TaskType.LONG_CONTEXT: 2.2 if ("long context" in lower or "unified architecture summary" in lower) else 0.0,
        }
        if ("short" in lower or "friendly" in lower or "summary" in lower) and scores[TaskType.CODING] < 2.5:
            scores[TaskType.SIMPLE] += 1.2
        best = max(scores, key=scores.get)
        return best if scores[best] >= 1.5 else TaskType.SIMPLE


class TokenDifficultyEstimator:
    CRIT = [r"\btherefore\b", r"\bprove\b", r"\bcontradiction\b", r"=", r"->", r"\bif and only if\b", r"\bmust\b", r"\bcritical\b", r"\bunsafe\b", r"\bdelete\b", r"\bvalidate\b", r"\bverify\b"]
    NORM = [r"\bdefine\b", r"\bbecause\b", r"\bbranch\b", r"\bmodule\b", r"\bmemory\b", r"\bsummary\b", r"\barchitecture\b", r"\broute\b"]

    @classmethod
    def estimate(cls, chunk: str, task_type: TaskType) -> Difficulty:
        lower = chunk.lower()
        if task_type in {TaskType.MATH, TaskType.VERIFICATION_HEAVY}:
            for p in cls.CRIT:
                if re.search(p, lower):
                    return Difficulty.CRITICAL
        for p in cls.CRIT:
            if re.search(p, lower):
                return Difficulty.CRITICAL
        for p in cls.NORM:
            if re.search(p, lower):
                return Difficulty.NORMAL
        return Difficulty.EASY if len(chunk.strip()) < 20 else Difficulty.NORMAL


class RouteMemoryEngine:
    def __init__(self) -> None:
        self.records: Dict[str, RouteMemoryRecord] = {}

    def retrieve(self, task_type: TaskType) -> Optional[RouteMemoryRecord]:
        return self.records.get(task_type.value)

    def update(self, task_type: TaskType, chosen_depths: List[int], verification_armed: bool, hot_items: List[str], active_modules: List[str], chosen_route_name: Optional[str] = None) -> None:
        key = task_type.value
        r = self.records.get(key)
        if r is None:
            r = RouteMemoryRecord(task_type=key)
            self.records[key] = r
        r.run_count += 1
        avg = sum(chosen_depths) / max(1, len(chosen_depths))
        r.avg_depth = ((r.avg_depth * (r.run_count - 1)) + avg) / r.run_count
        vr = 1.0 if verification_armed else 0.0
        r.verification_rate = ((r.verification_rate * (r.run_count - 1)) + vr) / r.run_count
        for x in hot_items:
            r.preferred_hot_items[x] = r.preferred_hot_items.get(x, 0) + 1
        for x in active_modules:
            r.preferred_modules[x] = r.preferred_modules.get(x, 0) + 1
        if chosen_route_name:
            r.preferred_route_names[chosen_route_name] = r.preferred_route_names.get(chosen_route_name, 0) + 1

    def export(self) -> Dict[str, Dict]:
        return {k: asdict(v) for k, v in self.records.items()}

    def load(self, data: Dict[str, Dict]) -> None:
        self.records = {k: RouteMemoryRecord(**v) for k, v in data.items()}


class ResidueRegistry:
    def __init__(self, max_bundles_per_task: int = 5) -> None:
        self.max = max_bundles_per_task
        self.registry: Dict[str, List[ResidueBundle]] = {}

    def retrieve(self, task_type: TaskType) -> List[ResidueBundle]:
        bundles = self.registry.get(task_type.value, [])
        for b in bundles:
            b.usage_count += 1
        return bundles[:]

    def store(self, task_type: TaskType, chosen_route_name: str, hot_items: List[str], active_modules: List[str], verification_armed: bool, avg_depth: float) -> None:
        key = task_type.value
        bundles = self.registry.setdefault(key, [])
        bundles.append(
            ResidueBundle(
                task_type=key,
                bundle_id=f"{key}_bundle_{len(bundles)+1}",
                route_name=chosen_route_name,
                hot_items=hot_items[:],
                active_modules=active_modules[:],
                verification_armed=verification_armed,
                avg_depth=avg_depth,
                usage_count=0,
            )
        )
        if len(bundles) > self.max:
            bundles.pop(0)

    def export(self) -> Dict[str, List[Dict]]:
        return {k: [asdict(b) for b in v] for k, v in self.registry.items()}

    def load(self, data: Dict[str, List[Dict]]) -> None:
        self.registry = {k: [ResidueBundle(**x) for x in v] for k, v in data.items()}


class DeferredWorkRegistry:
    def __init__(self, max_items_per_task: int = 12) -> None:
        self.max = max_items_per_task
        self.registry: Dict[str, List[DeferredWorkItem]] = {}

    def retrieve(self, task_type: TaskType) -> List[DeferredWorkItem]:
        items = self.registry.get(task_type.value, [])
        for item in items:
            item.reuse_count += 1
            item.priority = round(min(1.0, item.priority + 0.05), 3)
        items.sort(key=lambda x: (x.priority, x.reuse_count), reverse=True)
        return items[:]

    def store(self, task_type: TaskType, items: List[DeferredWorkItem]) -> None:
        if not items:
            return
        key = task_type.value
        bucket = self.registry.setdefault(key, [])
        for new_item in items:
            merged = False
            for existing in bucket:
                if (
                    existing.task_type == new_item.task_type
                    and existing.source_route == new_item.source_route
                    and existing.horizon == new_item.horizon
                    and existing.description == new_item.description
                ):
                    existing.priority = round(min(1.0, max(existing.priority, new_item.priority) + 0.05), 3)
                    merged = True
                    break
            if not merged:
                bucket.append(new_item)
        bucket.sort(key=lambda x: (x.priority, x.reuse_count), reverse=True)
        if len(bucket) > self.max:
            self.registry[key] = bucket[: self.max]

    def export(self) -> Dict[str, List[Dict]]:
        return {k: [asdict(x) for x in v] for k, v in self.registry.items()}

    def load(self, data: Dict[str, List[Dict]]) -> None:
        self.registry = {k: [DeferredWorkItem(**x) for x in v] for k, v in data.items()}


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
    def score_all(routes: List[CandidateRoute], task_type: TaskType, historical_record: Optional[RouteMemoryRecord], residue_bundles: List[ResidueBundle]) -> List[CandidateRouteScore]:
        results: List[CandidateRouteScore] = []
        residue_route_counts: Dict[str, int] = {}
        residue_hot_items: Dict[str, int] = {}
        for b in residue_bundles:
            residue_route_counts[b.route_name] = residue_route_counts.get(b.route_name, 0) + 1
            for it in b.hot_items:
                residue_hot_items[it] = residue_hot_items.get(it, 0) + 1
        for route in routes:
            score = route.depth_bias * 0.8 + route.verification_bias * 1.0 + route.reactivation_bias * 0.7
            reasons: List[str] = []
            if task_type == TaskType.MATH and "math" in route.name:
                score += 0.8; reasons.append("math_route_match")
            if historical_record and route.name in historical_record.preferred_route_names:
                score += min(1.0, historical_record.preferred_route_names[route.name] * 0.2); reasons.append("historical_preference")
            if route.name in residue_route_counts:
                score += min(0.8, residue_route_counts[route.name] * 0.2); reasons.append("residue_route_support")
            overlap = sum(1 for item in route.memory_focus if item in residue_hot_items)
            if overlap > 0:
                score += min(0.6, overlap * 0.2); reasons.append("residue_memory_overlap")
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
    @staticmethod
    def build_tiles(prompt: str, context_items: List[ContextItem], task_type: TaskType, budget: BudgetProfile, historical_record: Optional[RouteMemoryRecord] = None, chosen_route: Optional[CandidateRoute] = None, residue_bundles: Optional[List[ResidueBundle]] = None) -> MemoryTiles:
        prompt_lower = prompt.lower()
        residue_hot_counts: Dict[str, int] = {}
        if residue_bundles:
            for b in residue_bundles:
                for item in b.hot_items:
                    residue_hot_counts[item] = residue_hot_counts.get(item, 0) + 1
        scored = []
        for item in context_items:
            score = item.priority
            text_lower = item.text.lower()
            item_id_lower = item.item_id.lower()
            overlap = sum(1 for w in prompt_lower.split() if len(w) > 3 and w in text_lower)
            score += overlap * 0.18
            if historical_record and item_id_lower in historical_record.preferred_hot_items:
                score += min(0.6, 0.12 * historical_record.preferred_hot_items[item_id_lower])
            if chosen_route and item_id_lower in [x.lower() for x in chosen_route.memory_focus]:
                score += 0.7
            if item_id_lower in residue_hot_counts:
                score += min(0.8, residue_hot_counts[item_id_lower] * 0.15)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        ordered = [item for _, item in scored]
        hot = ordered[: budget.max_hot_items]
        warm = ordered[budget.max_hot_items : budget.max_hot_items + budget.max_warm_items]
        cold = ordered[budget.max_hot_items + budget.max_warm_items :]
        latent_summary = [MemoryTileManager._make_summary(item.text) for item in cold[: min(5, len(cold))]]
        return MemoryTiles(hot=hot, warm=warm, cold=cold, latent_summary=latent_summary)

    @staticmethod
    def _make_summary(text: str, max_len: int = 100) -> str:
        text = " ".join(text.strip().split())
        return text if len(text) <= max_len else text[: max_len - 3] + "..."


class ReactivationGate:
    @staticmethod
    def maybe_reactivate(query: str, memory: MemoryTiles, chosen_route: Optional[CandidateRoute] = None, residue_bundles: Optional[List[ResidueBundle]] = None) -> Optional[ContextItem]:
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
        return None


class VerificationTrigger:
    @staticmethod
    def should_verify(task_type: TaskType, difficulty: Difficulty, chosen_depth: int, budget: BudgetProfile, chunk: str, historical_record: Optional[RouteMemoryRecord] = None, chosen_route: Optional[CandidateRoute] = None, residue_bundles: Optional[List[ResidueBundle]] = None) -> bool:
        if task_type == TaskType.VERIFICATION_HEAVY:
            return True
        if difficulty == Difficulty.CRITICAL and chosen_depth >= budget.verification_threshold:
            return True
        if task_type == TaskType.MATH and any(sym in chunk.lower() for sym in ["=", "therefore", "implies", "contradiction"]):
            return True
        if historical_record and historical_record.verification_rate > 0.7 and difficulty == Difficulty.NORMAL:
            return True
        if chosen_route and chosen_route.verification_bias > 0.5 and difficulty != Difficulty.EASY:
            return True
        return False


class DepthGovernor:
    TASK_BASE_DEPTH = {TaskType.SIMPLE:1,TaskType.RETRIEVAL:1,TaskType.CODING:2,TaskType.MATH:2,TaskType.LONG_CONTEXT:2,TaskType.VERIFICATION_HEAVY:2}
    DIFFICULTY_BOOST = {Difficulty.EASY:0,Difficulty.NORMAL:0,Difficulty.CRITICAL:1}

    @classmethod
    def choose_depth(cls, difficulty: Difficulty, task_type: TaskType, budget: BudgetProfile, historical_record: Optional[RouteMemoryRecord] = None, chosen_route: Optional[CandidateRoute] = None, residue_bundles: Optional[List[ResidueBundle]] = None, horizon: Optional[Horizon] = None) -> int:
        depth = cls.TASK_BASE_DEPTH[task_type] + cls.DIFFICULTY_BOOST[difficulty]
        if historical_record and historical_record.avg_depth > 1.5:
            depth += 0.2
        if chosen_route:
            depth += chosen_route.depth_bias
        if horizon == Horizon.DEEP:
            depth += 0.3
        return max(1, min(int(round(depth)), budget.max_depth))


class HorizonPlanner:
    @staticmethod
    def plan(prompt: str, task_type: TaskType, chosen_route: CandidateRoute, chunks: List[str], deferred_items: List[DeferredWorkItem]) -> HorizonPlan:
        plan = HorizonPlan()
        if task_type == TaskType.MATH:
            plan.immediate += ["route_commit"]
            plan.short += ["core_claim_pass"]
            plan.medium += ["structural_consistency_pass"]
            plan.deep += ["proof_pressure_pass", "route_deepening"]
        if deferred_items:
            plan.short += ["deferred_reuse_scan"]
        return plan


class MultiScaleScheduler:
    @staticmethod
    def build(plan: HorizonPlan, deferred_items: List[DeferredWorkItem]) -> MultiScaleSchedule:
        schedule = MultiScaleSchedule(
            immediate_queue=plan.immediate[:],
            short_queue=plan.short[:],
            medium_queue=plan.medium[:],
            deep_queue=plan.deep[:],
        )
        for item in sorted(deferred_items, key=lambda x: (x.priority, x.reuse_count), reverse=True):
            label = f"deferred::{item.item_id}"
            if item.horizon == Horizon.DEEP.value:
                schedule.deep_queue.append(label)
            elif item.horizon == Horizon.MEDIUM.value:
                schedule.medium_queue.append(label)
            elif item.horizon == Horizon.SHORT.value:
                schedule.short_queue.append(label)
        return schedule


class SchedulerPressureEngine:
    @staticmethod
    def compute(route_scores: List[CandidateRouteScore], verification_armed: bool, residue_bundles: List[ResidueBundle], deferred_items: List[DeferredWorkItem]) -> Dict[str, float]:
        top = route_scores[0].score if route_scores else 0.0
        second = route_scores[1].score if len(route_scores) > 1 else 0.0
        confidence = max(0.0, round(min(1.0, top - second + 0.5), 3))
        residue_pressure = min(1.0, len(residue_bundles) * 0.2)
        deferred_pressure = min(1.0, sum(x.priority for x in deferred_items) / max(1, len(deferred_items))) if deferred_items else 0.0
        verification_pressure = 1.0 if verification_armed else 0.0
        return {
            Horizon.IMMEDIATE.value: round(0.25 + verification_pressure * 0.2, 3),
            Horizon.SHORT.value: round(0.25 + deferred_pressure * 0.25, 3),
            Horizon.MEDIUM.value: round(0.25 + residue_pressure * 0.2, 3),
            Horizon.DEEP.value: round(0.35 + (1.0 - confidence) * 0.3 + deferred_pressure * 0.2, 3),
        }

    @staticmethod
    def rebalance(schedule: MultiScaleSchedule, pressure: Dict[str, float]) -> MultiScaleSchedule:
        if pressure.get(Horizon.SHORT.value, 0) > 0.45 and "deferred_reuse_scan" not in schedule.short_queue:
            schedule.short_queue.append("deferred_reuse_scan")
        if pressure.get(Horizon.DEEP.value, 0) > 0.55 and "deep_pressure_review" not in schedule.deep_queue:
            schedule.deep_queue.append("deep_pressure_review")
        return schedule


class ConflictResolver:
    @staticmethod
    def resolve(schedule: MultiScaleSchedule, pressure: Dict[str, float], route_confidence: float) -> List[ArbitrationDecision]:
        decisions: List[ArbitrationDecision] = []
        if pressure.get(Horizon.DEEP.value, 0) > pressure.get(Horizon.SHORT.value, 0) and route_confidence >= 0.9:
            if "core_claim_pass" in schedule.short_queue:
                schedule.short_queue.remove("core_claim_pass")
                schedule.deep_queue.append("core_claim_pass")
                decisions.append(ArbitrationDecision("core_claim_pass", "short", "deep", "deep_pressure_dominates_with_high_confidence"))
        return decisions


class QueueArbitrationLayer:
    @staticmethod
    def apply(schedule: MultiScaleSchedule, decisions: List[ArbitrationDecision]) -> MultiScaleSchedule:
        return schedule


class RuntimeStateManager:
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)

    def save(self, budget: BudgetProfile, route_memory: RouteMemoryEngine, residue_registry: ResidueRegistry, deferred_registry: DeferredWorkRegistry, last_fabric_state: FabricStateModel, last_schedule: MultiScaleSchedule) -> None:
        payload = {
            "budget": asdict(budget),
            "route_memory": route_memory.export(),
            "residue_registry": residue_registry.export(),
            "deferred_registry": deferred_registry.export(),
            "last_fabric_state": asdict(last_fabric_state),
            "last_schedule": asdict(last_schedule),
        }
        self.filepath.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def exists(self) -> bool:
        return self.filepath.exists()

    def load(self):
        data = json.loads(self.filepath.read_text(encoding="utf-8"))
        budget = BudgetProfile(**data["budget"])
        route_memory = RouteMemoryEngine()
        route_memory.load(data["route_memory"])
        residue_registry = ResidueRegistry(budget.max_residue_bundles_per_task)
        residue_registry.load(data["residue_registry"])
        deferred_registry = DeferredWorkRegistry(budget.max_deferred_items_per_task)
        deferred_registry.load(data["deferred_registry"])
        last_fabric_state = FabricStateModel(**data["last_fabric_state"])
        last_schedule = MultiScaleSchedule(**data["last_schedule"])
        return budget, route_memory, residue_registry, deferred_registry, last_fabric_state, last_schedule


class FabricOrchestratorV10:
    def __init__(self, budget: Optional[BudgetProfile] = None, route_memory: Optional[RouteMemoryEngine] = None, residue_registry: Optional[ResidueRegistry] = None, deferred_registry: Optional[DeferredWorkRegistry] = None, last_fabric_state: Optional[FabricStateModel] = None, last_schedule: Optional[MultiScaleSchedule] = None):
        self.budget = budget or BudgetProfile()
        self.route_memory = route_memory or RouteMemoryEngine()
        self.residue_registry = residue_registry or ResidueRegistry(self.budget.max_residue_bundles_per_task)
        self.deferred_registry = deferred_registry or DeferredWorkRegistry(self.budget.max_deferred_items_per_task)
        self.last_fabric_state = last_fabric_state or FabricStateModel()
        self.last_schedule = last_schedule or MultiScaleSchedule()

    def run(self, prompt: str, context_items: List[ContextItem]) -> RuntimeState:
        task_type = PromptClassifier.classify(prompt, context_items)
        historical_record = self.route_memory.retrieve(task_type)
        residue_bundles = self.residue_registry.retrieve(task_type)
        deferred_items = self.deferred_registry.retrieve(task_type)
        candidate_routes = CandidateRouteGenerator.generate(task_type, historical_record, self.budget)
        route_scores = BranchScoringLayer.score_all(candidate_routes, task_type, historical_record, residue_bundles)
        chosen_route = EarlyCollapseController.select(route_scores, candidate_routes)

        state = RuntimeState(prompt=prompt, task_type=task_type, budget=self.budget)
        state.historical_route_used = historical_record is not None
        state.historical_record_snapshot = asdict(historical_record) if historical_record else None
        state.residue_bundles_used = [asdict(b) for b in residue_bundles]
        state.deferred_items_used = [asdict(x) for x in deferred_items]
        state.candidate_routes = candidate_routes
        state.route_scores = route_scores
        state.chosen_route = chosen_route.name
        state.fabric_state.task_type = task_type.value
        state.fabric_state.historical_route_used = state.historical_route_used
        state.fabric_state.residue_bundle_count = len(residue_bundles)
        state.fabric_state.deferred_item_count = len(deferred_items)
        if route_scores:
            top = route_scores[0].score
            second = route_scores[1].score if len(route_scores) > 1 else 0.0
            state.fabric_state.route_confidence = max(0.0, round(min(1.0, top - second + 0.5), 3))

        state.active_modules = [
            "RuntimeStateManager","FabricOrchestratorV10","PromptClassifier","TokenDifficultyEstimator","DepthGovernor","MemoryTileManager",
            "RouteMemoryEngine","ResidueRegistry","DeferredWorkRegistry","HorizonPlanner","MultiScaleScheduler","SchedulerPressureEngine",
            "ConflictResolver","QueueArbitrationLayer","CandidateRouteGenerator","BranchScoringLayer","EarlyCollapseController","VerificationTrigger",
        ]
        state.fabric_state.active_modules = state.active_modules[:]
        state.fabric_state.chosen_route = chosen_route.name

        state.memory = MemoryTileManager.build_tiles(prompt, context_items, task_type, self.budget, historical_record, chosen_route, residue_bundles)
        state.fabric_state.hot_memory_ids = [x.item_id for x in state.memory.hot]
        state.fabric_state.warm_memory_ids = [x.item_id for x in state.memory.warm]
        state.fabric_state.cold_memory_ids = [x.item_id for x in state.memory.cold]

        chunks = self._make_chunks(prompt)
        state.horizon_plan = HorizonPlanner.plan(prompt, task_type, chosen_route, chunks, deferred_items)
        state.fabric_state.horizon_loads = {
            "immediate": len(state.horizon_plan.immediate),
            "short": len(state.horizon_plan.short),
            "medium": len(state.horizon_plan.medium),
            "deep": len(state.horizon_plan.deep),
        }

        state.schedule = MultiScaleScheduler.build(state.horizon_plan, deferred_items)
        pressure = SchedulerPressureEngine.compute(route_scores, state.verification_armed, residue_bundles, deferred_items)
        state.fabric_state.horizon_pressure = pressure
        state.schedule = SchedulerPressureEngine.rebalance(state.schedule, pressure)
        decisions = ConflictResolver.resolve(state.schedule, pressure, state.fabric_state.route_confidence)
        state.schedule = QueueArbitrationLayer.apply(state.schedule, decisions)
        state.arbitration_trace = [asdict(d) for d in decisions]
        state.fabric_state.arbitration_count = len(decisions)
        state.fabric_state.schedule_loads = {
            "immediate": len(state.schedule.immediate_queue),
            "short": len(state.schedule.short_queue),
            "medium": len(state.schedule.medium_queue),
            "deep": len(state.schedule.deep_queue),
        }

        chosen_depths: List[int] = []
        created_deferred: List[DeferredWorkItem] = []
        chunk_horizons = [Horizon.SHORT, Horizon.DEEP] if len(chunks) == 2 else [Horizon.DEEP]

        for idx, chunk in enumerate(chunks):
            horizon = chunk_horizons[min(idx, len(chunk_horizons)-1)]
            difficulty = TokenDifficultyEstimator.estimate(chunk, task_type)
            depth = DepthGovernor.choose_depth(difficulty, task_type, self.budget, historical_record, chosen_route, residue_bundles, horizon)
            chosen_depths.append(depth)
            state.fabric_state.depth_history.append(depth)
            verify = VerificationTrigger.should_verify(task_type, difficulty, depth, self.budget, chunk, historical_record, chosen_route, residue_bundles)
            if verify:
                state.verification_armed = True
                state.fabric_state.verification_armed = True
            reactivated = ReactivationGate.maybe_reactivate(chunk, state.memory, chosen_route, residue_bundles)
            if reactivated and reactivated not in state.memory.hot:
                state.memory.hot.append(reactivated)
            if horizon == Horizon.DEEP and difficulty in {Difficulty.NORMAL, Difficulty.CRITICAL}:
                base_priority = 0.8
                boost = min(0.15, pressure.get(horizon.value, 0.0) * 0.15)
                created_deferred.append(
                    DeferredWorkItem(
                        task_type=task_type.value,
                        item_id=f"{task_type.value}_deferred_{idx+1}",
                        horizon=horizon.value,
                        description=f"Deferred follow-up from chunk {idx} under {horizon.value} horizon.",
                        source_route=chosen_route.name,
                        source_chunk_index=idx,
                        priority=round(min(1.0, base_priority + boost), 3),
                        reuse_count=0,
                    )
                )

        state.deferred_items_created = [asdict(x) for x in created_deferred]
        avg_depth = sum(chosen_depths) / max(1, len(chosen_depths))
        state.fabric_state.health_score = 0.8
        self.route_memory.update(task_type, chosen_depths, state.verification_armed, [x.item_id for x in state.memory.hot], state.active_modules, chosen_route.name)
        self.residue_registry.store(task_type, chosen_route.name, [x.item_id for x in state.memory.hot], state.active_modules, state.verification_armed, avg_depth)
        self.deferred_registry.store(task_type, created_deferred)

        self.last_fabric_state = state.fabric_state
        self.last_schedule = state.schedule
        state.fabric_state.phase = FabricPhase.COMPLETE.value
        return state

    @staticmethod
    def _make_chunks(prompt: str, chunk_size: int = 120) -> List[str]:
        text = " ".join(prompt.strip().split())
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        return chunks if chunks else [""]


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

    state_file = "morph_runtime_core_v1_0_state.json"
    manager = RuntimeStateManager(state_file)

    print("=== MORPH Runtime Core v1.0 / Fresh Run ===")
    runtime = FabricOrchestratorV10()
    prompt = "Prove why a structural contradiction route may be stronger than brute-force checking in a mathematics simulator."
    r1 = runtime.run(prompt, context)
    manager.save(runtime.budget, runtime.route_memory, runtime.residue_registry, runtime.deferred_registry, runtime.last_fabric_state, runtime.last_schedule)
    print(f"Saved state to: {state_file}")
    print(f"Task type: {r1.task_type.value}")
    print(f"Chosen route: {r1.chosen_route}")
    print(f"Route confidence: {r1.fabric_state.route_confidence}")
    print(f"Schedule loads: {r1.fabric_state.schedule_loads}")
    print(f"Arbitration count: {r1.fabric_state.arbitration_count}")
    print(f"Deferred items created: {len(r1.deferred_items_created)}")

    print("\n=== MORPH Runtime Core v1.0 / Resume Run ===")
    budget, route_memory, residue_registry, deferred_registry, last_fabric_state, last_schedule = manager.load()
    resumed = FabricOrchestratorV10(
        budget=budget,
        route_memory=route_memory,
        residue_registry=residue_registry,
        deferred_registry=deferred_registry,
        last_fabric_state=last_fabric_state,
        last_schedule=last_schedule,
    )
    r2 = resumed.run(prompt, context)
    manager.save(resumed.budget, resumed.route_memory, resumed.residue_registry, resumed.deferred_registry, resumed.last_fabric_state, resumed.last_schedule)

    print(f"Resumed from: {state_file}")
    print(f"Historical route used: {r2.historical_route_used}")
    print(f"Last saved phase before resume: {last_fabric_state.phase}")
    print(f"Last saved chosen route before resume: {last_fabric_state.chosen_route}")
    print(f"Restored schedule snapshot: {asdict(last_schedule)}")
    print(f"Task type: {r2.task_type.value}")
    print(f"Chosen route: {r2.chosen_route}")
    print(f"Route confidence: {r2.fabric_state.route_confidence}")
    print(f"Schedule loads: {r2.fabric_state.schedule_loads}")
    print(f"Arbitration count: {r2.fabric_state.arbitration_count}")
    print(f"Deferred items used: {len(r2.deferred_items_used)}")

    print("\n=== Saved State Snapshot ===")
    print(manager.filepath.read_text(encoding="utf-8"))


if __name__ == "__main__":
    demo()
