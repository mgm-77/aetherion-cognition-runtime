"""
MORPH Runtime Core v1.3
Branch Merge + Comparative Resume

Prototype:
- project/session continuity
- branch fork support
- branch comparison
- merge session creation
- merge parents + merge note + merge summary
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional
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
    route_confidence: float = 0.0
    arbitration_count: int = 0


@dataclass
class RuntimeState:
    prompt: str
    task_type: TaskType
    budget: BudgetProfile
    project_id: str = "default_project"
    session_id: str = "session_001"
    parent_session_id: Optional[str] = None
    branch_label: str = "main"
    merge_parents: List[str] = field(default_factory=list)
    merge_note: Optional[str] = None
    merge_summary: Optional[Dict] = None
    active_modules: List[str] = field(default_factory=list)
    memory: MemoryTiles = field(default_factory=MemoryTiles)
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


class PromptClassifier:
    @classmethod
    def classify(cls, prompt: str) -> TaskType:
        lower = prompt.lower()
        if any(x in lower for x in ["prove", "lemma", "theorem", "contradiction", "equation"]):
            return TaskType.MATH
        if any(x in lower for x in ["verify", "validate", "audit"]):
            return TaskType.VERIFICATION_HEAVY
        if any(x in lower for x in ["code", "python", "debug", "script"]):
            return TaskType.CODING
        if any(x in lower for x in ["find", "search", "retrieve", "extract"]):
            return TaskType.RETRIEVAL
        return TaskType.SIMPLE


class TokenDifficultyEstimator:
    @classmethod
    def estimate(cls, chunk: str, task_type: TaskType) -> Difficulty:
        lower = chunk.lower()
        if any(x in lower for x in ["prove", "contradiction", "verify", "="]):
            return Difficulty.CRITICAL if task_type in {TaskType.MATH, TaskType.VERIFICATION_HEAVY} else Difficulty.NORMAL
        return Difficulty.NORMAL if len(chunk.strip()) > 20 else Difficulty.EASY


class RouteMemoryEngine:
    def __init__(self) -> None:
        self.records: Dict[str, RouteMemoryRecord] = {}

    def retrieve(self, task_type: TaskType) -> Optional[RouteMemoryRecord]:
        return self.records.get(task_type.value)

    def update(self, task_type: TaskType, chosen_depths: List[int], verification_armed: bool, hot_items: List[str], active_modules: List[str], chosen_route_name: Optional[str] = None) -> None:
        key = task_type.value
        record = self.records.get(key)
        if record is None:
            record = RouteMemoryRecord(task_type=key)
            self.records[key] = record
        record.run_count += 1
        avg = sum(chosen_depths) / max(1, len(chosen_depths))
        record.avg_depth = ((record.avg_depth * (record.run_count - 1)) + avg) / record.run_count
        vr = 1.0 if verification_armed else 0.0
        record.verification_rate = ((record.verification_rate * (record.run_count - 1)) + vr) / record.run_count
        for item_id in hot_items:
            record.preferred_hot_items[item_id] = record.preferred_hot_items.get(item_id, 0) + 1
        for module_name in active_modules:
            record.preferred_modules[module_name] = record.preferred_modules.get(module_name, 0) + 1
        if chosen_route_name:
            record.preferred_route_names[chosen_route_name] = record.preferred_route_names.get(chosen_route_name, 0) + 1

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
        for bundle in bundles:
            bundle.usage_count += 1
        return bundles[:]

    def store(self, task_type: TaskType, chosen_route_name: str, hot_items: List[str], active_modules: List[str], verification_armed: bool, avg_depth: float) -> None:
        key = task_type.value
        bucket = self.registry.setdefault(key, [])
        bucket.append(
            ResidueBundle(
                task_type=key,
                bundle_id=f"{key}_bundle_{len(bucket)+1}",
                route_name=chosen_route_name,
                hot_items=hot_items[:],
                active_modules=active_modules[:],
                verification_armed=verification_armed,
                avg_depth=avg_depth,
                usage_count=0,
            )
        )
        if len(bucket) > self.max:
            bucket.pop(0)

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
                if existing.description == new_item.description and existing.horizon == new_item.horizon and existing.source_route == new_item.source_route:
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
        else:
            routes = [
                CandidateRoute("default_balanced", 0.2, 0.2, 0.2, ["morph_v05"]),
                CandidateRoute("default_contextual", 0.1, 0.1, 0.5, ["long_context_notes"]),
            ]
        if historical_record and historical_record.preferred_route_names:
            routes.sort(key=lambda r: historical_record.preferred_route_names.get(r.name, 0), reverse=True)
        return routes[: budget.max_candidate_routes]


class BranchScoringLayer:
    @staticmethod
    def score_all(routes: List[CandidateRoute], task_type: TaskType, historical_record: Optional[RouteMemoryRecord], residue_bundles: List[ResidueBundle]) -> List[CandidateRouteScore]:
        results: List[CandidateRouteScore] = []
        residue_route_counts: Dict[str, int] = {}
        for bundle in residue_bundles:
            residue_route_counts[bundle.route_name] = residue_route_counts.get(bundle.route_name, 0) + 1
        for route in routes:
            score = route.depth_bias * 0.8 + route.verification_bias * 1.0 + route.reactivation_bias * 0.7
            reasons: List[str] = []
            if task_type == TaskType.MATH and "math" in route.name:
                score += 0.8
                reasons.append("math_route_match")
            if historical_record and route.name in historical_record.preferred_route_names:
                score += min(1.0, historical_record.preferred_route_names[route.name] * 0.2)
                reasons.append("historical_preference")
            if route.name in residue_route_counts:
                score += min(0.8, residue_route_counts[route.name] * 0.2)
                reasons.append("residue_route_support")
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
    def build_tiles(context_items: List[ContextItem], budget: BudgetProfile, historical_record: Optional[RouteMemoryRecord] = None, chosen_route: Optional[CandidateRoute] = None) -> MemoryTiles:
        scored = []
        route_focus = [x.lower() for x in chosen_route.memory_focus] if chosen_route else []
        preferred = historical_record.preferred_hot_items if historical_record else {}
        for item in context_items:
            score = item.priority
            lowered = item.item_id.lower()
            if lowered in route_focus:
                score += 0.7
            if lowered in preferred:
                score += min(0.6, preferred[lowered] * 0.12)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        ordered = [item for _, item in scored]
        hot = ordered[: budget.max_hot_items]
        warm = ordered[budget.max_hot_items: budget.max_hot_items + budget.max_warm_items]
        cold = ordered[budget.max_hot_items + budget.max_warm_items:]
        latent_summary = [(" ".join(item.text.split()))[:100] for item in cold[: min(5, len(cold))]]
        return MemoryTiles(hot=hot, warm=warm, cold=cold, latent_summary=latent_summary)


class VerificationTrigger:
    @staticmethod
    def should_verify(task_type: TaskType, difficulty: Difficulty, chosen_depth: int, budget: BudgetProfile, chunk: str, historical_record: Optional[RouteMemoryRecord], chosen_route: CandidateRoute) -> bool:
        if task_type == TaskType.VERIFICATION_HEAVY:
            return True
        if difficulty == Difficulty.CRITICAL and chosen_depth >= budget.verification_threshold:
            return True
        if task_type == TaskType.MATH and any(sym in chunk.lower() for sym in ["=", "therefore", "implies", "contradiction"]):
            return True
        if historical_record and historical_record.verification_rate > 0.7 and difficulty == Difficulty.NORMAL:
            return True
        return chosen_route.verification_bias > 0.5 and difficulty != Difficulty.EASY


class DepthGovernor:
    TASK_BASE_DEPTH = {
        TaskType.SIMPLE: 1,
        TaskType.RETRIEVAL: 1,
        TaskType.CODING: 2,
        TaskType.MATH: 2,
        TaskType.LONG_CONTEXT: 2,
        TaskType.VERIFICATION_HEAVY: 2,
    }
    DIFFICULTY_BOOST = {Difficulty.EASY: 0, Difficulty.NORMAL: 0, Difficulty.CRITICAL: 1}

    @classmethod
    def choose_depth(cls, difficulty: Difficulty, task_type: TaskType, budget: BudgetProfile, historical_record: Optional[RouteMemoryRecord], chosen_route: CandidateRoute, horizon: Horizon) -> int:
        depth = cls.TASK_BASE_DEPTH[task_type] + cls.DIFFICULTY_BOOST[difficulty]
        if historical_record and historical_record.avg_depth > 1.5:
            depth += 0.2
        depth += chosen_route.depth_bias
        if horizon == Horizon.DEEP:
            depth += 0.3
        return max(1, min(int(round(depth)), budget.max_depth))


class HorizonPlanner:
    @staticmethod
    def plan(task_type: TaskType, deferred_items: List[DeferredWorkItem]) -> HorizonPlan:
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
    def compute(route_scores: List[CandidateRouteScore], deferred_items: List[DeferredWorkItem]) -> Dict[str, float]:
        top = route_scores[0].score if route_scores else 0.0
        second = route_scores[1].score if len(route_scores) > 1 else 0.0
        confidence = max(0.0, round(min(1.0, top - second + 0.5), 3))
        deferred_pressure = min(1.0, sum(x.priority for x in deferred_items) / max(1, len(deferred_items))) if deferred_items else 0.0
        return {
            "immediate": 0.25,
            "short": round(0.25 + deferred_pressure * 0.25, 3),
            "medium": 0.29,
            "deep": round(0.35 + (1.0 - confidence) * 0.3 + deferred_pressure * 0.2, 3),
        }

    @staticmethod
    def rebalance(schedule: MultiScaleSchedule, pressure: Dict[str, float]) -> MultiScaleSchedule:
        if pressure.get("short", 0.0) > 0.45 and "deferred_reuse_scan" not in schedule.short_queue:
            schedule.short_queue.append("deferred_reuse_scan")
        return schedule


class ConflictResolver:
    @staticmethod
    def resolve(schedule: MultiScaleSchedule, pressure: Dict[str, float], route_confidence: float) -> List[Dict]:
        decisions: List[Dict] = []
        if pressure.get("deep", 0.0) > pressure.get("short", 0.0) and route_confidence >= 0.9 and "core_claim_pass" in schedule.short_queue:
            schedule.short_queue.remove("core_claim_pass")
            schedule.deep_queue.append("core_claim_pass")
            decisions.append({
                "item": "core_claim_pass",
                "from_horizon": "short",
                "to_horizon": "deep",
                "reason": "deep_pressure_dominates_with_high_confidence",
            })
        return decisions


class QueueArbitrationLayer:
    @staticmethod
    def apply(schedule: MultiScaleSchedule, decisions: List[Dict]) -> MultiScaleSchedule:
        return schedule


class ContinuityPackManager:
    def __init__(self, root_dir: str = "morph_continuity_pack_v1_3") -> None:
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / "continuity_registry.json"
        if not self.registry_path.exists():
            self.registry_path.write_text(json.dumps({"projects": {}}, indent=2), encoding="utf-8")

    def _load_registry(self) -> Dict:
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def _save_registry(self, data: Dict) -> None:
        self.registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_project_dir(self, project_id: str) -> Path:
        path = self.root / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_session_file(self, project_id: str, session_id: str) -> Path:
        return self.get_project_dir(project_id) / f"{session_id}.json"

    def save_session(self, project_id: str, session_id: str, payload: Dict, parent_session_id: Optional[str], branch_label: str, merge_parents: Optional[List[str]] = None, merge_note: Optional[str] = None) -> Path:
        file_path = self.get_session_file(project_id, session_id)
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        registry = self._load_registry()
        project = registry["projects"].setdefault(project_id, {"sessions": {}, "roots": []})
        node = project["sessions"].setdefault(session_id, {
            "parent_session_id": None,
            "branch_label": branch_label,
            "children": [],
            "merge_parents": [],
            "merge_note": None,
        })
        node["parent_session_id"] = parent_session_id
        node["branch_label"] = branch_label
        node["merge_parents"] = merge_parents or []
        node["merge_note"] = merge_note
        if parent_session_id:
            parent_node = project["sessions"].setdefault(parent_session_id, {
                "parent_session_id": None,
                "branch_label": "main",
                "children": [],
                "merge_parents": [],
                "merge_note": None,
            })
            if session_id not in parent_node["children"]:
                parent_node["children"].append(session_id)
        else:
            if session_id not in project["roots"]:
                project["roots"].append(session_id)
        for merge_parent in merge_parents or []:
            merge_parent_node = project["sessions"].setdefault(merge_parent, {
                "parent_session_id": None,
                "branch_label": "main",
                "children": [],
                "merge_parents": [],
                "merge_note": None,
            })
            if session_id not in merge_parent_node["children"]:
                merge_parent_node["children"].append(session_id)
        self._save_registry(registry)
        return file_path

    def load_session(self, project_id: str, session_id: str) -> Dict:
        file_path = self.get_session_file(project_id, session_id)
        return json.loads(file_path.read_text(encoding="utf-8"))

    def get_session_tree(self, project_id: str) -> Dict:
        return self._load_registry()["projects"].get(project_id, {})

    def create_fork_session_id(self, base_session_id: str, branch_label: str) -> str:
        sanitized = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in branch_label.lower())
        return f"{base_session_id}__fork__{sanitized}"

    def create_merge_session_id(self, left_session_id: str, right_session_id: str) -> str:
        return f"merge__{left_session_id}__{right_session_id}"


class SessionStateAdapter:
    @staticmethod
    def export_payload(project_id: str, session_id: str, parent_session_id: Optional[str], branch_label: str, budget: BudgetProfile, route_memory: RouteMemoryEngine, residue_registry: ResidueRegistry, deferred_registry: DeferredWorkRegistry, last_fabric_state: FabricStateModel, last_schedule: MultiScaleSchedule, merge_parents: Optional[List[str]] = None, merge_note: Optional[str] = None, merge_summary: Optional[Dict] = None) -> Dict:
        return {
            "project_id": project_id,
            "session_id": session_id,
            "parent_session_id": parent_session_id,
            "branch_label": branch_label,
            "merge_parents": merge_parents or [],
            "merge_note": merge_note,
            "merge_summary": merge_summary,
            "budget": asdict(budget),
            "route_memory": route_memory.export(),
            "residue_registry": residue_registry.export(),
            "deferred_registry": deferred_registry.export(),
            "last_fabric_state": asdict(last_fabric_state),
            "last_schedule": asdict(last_schedule),
        }

    @staticmethod
    def restore(payload: Dict):
        budget = BudgetProfile(**payload["budget"])
        route_memory = RouteMemoryEngine()
        route_memory.load(payload["route_memory"])
        residue_registry = ResidueRegistry(budget.max_residue_bundles_per_task)
        residue_registry.load(payload["residue_registry"])
        deferred_registry = DeferredWorkRegistry(budget.max_deferred_items_per_task)
        deferred_registry.load(payload["deferred_registry"])
        last_fabric_state = FabricStateModel(**payload["last_fabric_state"])
        last_schedule = MultiScaleSchedule(**payload["last_schedule"])
        return budget, route_memory, residue_registry, deferred_registry, last_fabric_state, last_schedule


class ComparativeResumeEngine:
    @staticmethod
    def compare_sessions(left_payload: Dict, right_payload: Dict) -> Dict:
        left_route = left_payload["last_fabric_state"].get("chosen_route")
        right_route = right_payload["last_fabric_state"].get("chosen_route")
        left_deferred = left_payload["deferred_registry"].get("math", [])
        right_deferred = right_payload["deferred_registry"].get("math", [])
        left_modules = set(left_payload["last_fabric_state"].get("active_modules", []))
        right_modules = set(right_payload["last_fabric_state"].get("active_modules", []))
        return {
            "left_session_id": left_payload["session_id"],
            "right_session_id": right_payload["session_id"],
            "left_branch_label": left_payload.get("branch_label"),
            "right_branch_label": right_payload.get("branch_label"),
            "same_route": left_route == right_route,
            "left_route": left_route,
            "right_route": right_route,
            "module_overlap_count": len(left_modules & right_modules),
            "left_only_modules": sorted(left_modules - right_modules),
            "right_only_modules": sorted(right_modules - left_modules),
            "left_deferred_count": len(left_deferred),
            "right_deferred_count": len(right_deferred),
            "merge_suggestion": "preserve_common_route_and_union_deferred_items",
        }


class MergeResolver:
    @staticmethod
    def merge_payloads(left_payload: Dict, right_payload: Dict, merge_note: str):
        budget_l, route_memory_l, residue_registry_l, deferred_registry_l, last_fabric_state_l, last_schedule_l = SessionStateAdapter.restore(left_payload)
        _, route_memory_r, residue_registry_r, deferred_registry_r, last_fabric_state_r, last_schedule_r = SessionStateAdapter.restore(right_payload)

        merged_budget = budget_l
        merged_route_memory = route_memory_l
        for task_key, record in route_memory_r.records.items():
            if task_key not in merged_route_memory.records:
                merged_route_memory.records[task_key] = record
            else:
                existing = merged_route_memory.records[task_key]
                existing.run_count = max(existing.run_count, record.run_count)
                existing.avg_depth = max(existing.avg_depth, record.avg_depth)
                existing.verification_rate = max(existing.verification_rate, record.verification_rate)
                for k, v in record.preferred_hot_items.items():
                    existing.preferred_hot_items[k] = max(existing.preferred_hot_items.get(k, 0), v)
                for k, v in record.preferred_modules.items():
                    existing.preferred_modules[k] = max(existing.preferred_modules.get(k, 0), v)
                for k, v in record.preferred_route_names.items():
                    existing.preferred_route_names[k] = max(existing.preferred_route_names.get(k, 0), v)

        merged_residue = residue_registry_l
        for task_key, bundles in residue_registry_r.registry.items():
            bucket = merged_residue.registry.setdefault(task_key, [])
            for bundle in bundles:
                if not any(x.bundle_id == bundle.bundle_id for x in bucket):
                    bucket.append(bundle)
            if len(bucket) > merged_residue.max:
                bucket[:] = bucket[: merged_residue.max]

        merged_deferred = deferred_registry_l
        for task_key, items in deferred_registry_r.registry.items():
            try:
                task_enum = TaskType(task_key)
            except ValueError:
                continue
            merged_deferred.store(task_enum, items)

        merged_fabric = last_fabric_state_l
        merged_fabric.historical_route_used = True
        merged_fabric.phase = FabricPhase.COMPLETE.value
        merged_fabric.chosen_route = last_fabric_state_l.chosen_route if last_fabric_state_l.chosen_route == last_fabric_state_r.chosen_route else (last_fabric_state_l.chosen_route or last_fabric_state_r.chosen_route)
        merged_fabric.active_modules = sorted(set(last_fabric_state_l.active_modules) | set(last_fabric_state_r.active_modules))
        merged_fabric.residue_bundle_count = max(last_fabric_state_l.residue_bundle_count, last_fabric_state_r.residue_bundle_count)
        merged_fabric.deferred_item_count = max(last_fabric_state_l.deferred_item_count, last_fabric_state_r.deferred_item_count)
        merged_fabric.route_confidence = max(last_fabric_state_l.route_confidence, last_fabric_state_r.route_confidence)
        merged_fabric.arbitration_count = last_fabric_state_l.arbitration_count + last_fabric_state_r.arbitration_count
        merged_fabric.depth_history = last_fabric_state_l.depth_history or last_fabric_state_r.depth_history
        merged_fabric.hot_memory_ids = list(dict.fromkeys(last_fabric_state_l.hot_memory_ids + last_fabric_state_r.hot_memory_ids))[:3]
        merged_fabric.warm_memory_ids = list(dict.fromkeys(last_fabric_state_l.warm_memory_ids + last_fabric_state_r.warm_memory_ids))[:3]
        merged_fabric.cold_memory_ids = list(dict.fromkeys(last_fabric_state_l.cold_memory_ids + last_fabric_state_r.cold_memory_ids))[:3]

        merged_schedule = MultiScaleSchedule(
            immediate_queue=list(dict.fromkeys(last_schedule_l.immediate_queue + last_schedule_r.immediate_queue)),
            short_queue=list(dict.fromkeys(last_schedule_l.short_queue + last_schedule_r.short_queue)),
            medium_queue=list(dict.fromkeys(last_schedule_l.medium_queue + last_schedule_r.medium_queue)),
            deep_queue=list(dict.fromkeys(last_schedule_l.deep_queue + last_schedule_r.deep_queue)),
        )

        merge_summary = ComparativeResumeEngine.compare_sessions(left_payload, right_payload)
        merge_summary["merge_note"] = merge_note
        merge_summary["merged_route"] = merged_fabric.chosen_route
        merge_summary["merged_deferred_count"] = sum(len(v) for v in merged_deferred.registry.values())

        return merged_budget, merged_route_memory, merged_residue, merged_deferred, merged_fabric, merged_schedule, merge_summary


class FabricOrchestratorV13:
    def __init__(self, project_id: str, session_id: str, parent_session_id: Optional[str] = None, branch_label: str = "main", budget: Optional[BudgetProfile] = None, route_memory: Optional[RouteMemoryEngine] = None, residue_registry: Optional[ResidueRegistry] = None, deferred_registry: Optional[DeferredWorkRegistry] = None, last_fabric_state: Optional[FabricStateModel] = None, last_schedule: Optional[MultiScaleSchedule] = None, merge_parents: Optional[List[str]] = None, merge_note: Optional[str] = None, merge_summary: Optional[Dict] = None):
        self.project_id = project_id
        self.session_id = session_id
        self.parent_session_id = parent_session_id
        self.branch_label = branch_label
        self.merge_parents = merge_parents or []
        self.merge_note = merge_note
        self.merge_summary = merge_summary
        self.budget = budget or BudgetProfile()
        self.route_memory = route_memory or RouteMemoryEngine()
        self.residue_registry = residue_registry or ResidueRegistry(self.budget.max_residue_bundles_per_task)
        self.deferred_registry = deferred_registry or DeferredWorkRegistry(self.budget.max_deferred_items_per_task)
        self.last_fabric_state = last_fabric_state or FabricStateModel()
        self.last_schedule = last_schedule or MultiScaleSchedule()

    def run(self, prompt: str, context_items: List[ContextItem]) -> RuntimeState:
        task_type = PromptClassifier.classify(prompt)
        historical_record = self.route_memory.retrieve(task_type)
        residue_bundles = self.residue_registry.retrieve(task_type)
        deferred_items = self.deferred_registry.retrieve(task_type)

        candidate_routes = CandidateRouteGenerator.generate(task_type, historical_record, self.budget)
        route_scores = BranchScoringLayer.score_all(candidate_routes, task_type, historical_record, residue_bundles)
        chosen_route = EarlyCollapseController.select(route_scores, candidate_routes)

        state = RuntimeState(
            prompt=prompt,
            task_type=task_type,
            budget=self.budget,
            project_id=self.project_id,
            session_id=self.session_id,
            parent_session_id=self.parent_session_id,
            branch_label=self.branch_label,
            merge_parents=self.merge_parents[:],
            merge_note=self.merge_note,
            merge_summary=self.merge_summary,
        )
        state.historical_route_used = historical_record is not None
        state.historical_record_snapshot = asdict(historical_record) if historical_record else None
        state.residue_bundles_used = [asdict(b) for b in residue_bundles]
        state.deferred_items_used = [asdict(x) for x in deferred_items]
        state.candidate_routes = candidate_routes
        state.route_scores = route_scores
        state.chosen_route = chosen_route.name

        state.active_modules = [
            "ContinuityPackManager",
            "SessionStateAdapter",
            "ComparativeResumeEngine",
            "MergeResolver",
            "FabricOrchestratorV13",
            "PromptClassifier",
            "TokenDifficultyEstimator",
            "DepthGovernor",
            "MemoryTileManager",
            "RouteMemoryEngine",
            "ResidueRegistry",
            "DeferredWorkRegistry",
            "HorizonPlanner",
            "MultiScaleScheduler",
            "SchedulerPressureEngine",
            "ConflictResolver",
            "QueueArbitrationLayer",
            "CandidateRouteGenerator",
            "BranchScoringLayer",
            "EarlyCollapseController",
            "VerificationTrigger",
        ]

        state.fabric_state.task_type = task_type.value
        state.fabric_state.chosen_route = chosen_route.name
        state.fabric_state.active_modules = state.active_modules[:]
        state.fabric_state.historical_route_used = state.historical_route_used
        state.fabric_state.residue_bundle_count = len(residue_bundles)
        state.fabric_state.deferred_item_count = len(deferred_items)

        top = route_scores[0].score if route_scores else 0.0
        second = route_scores[1].score if len(route_scores) > 1 else 0.0
        state.fabric_state.route_confidence = max(0.0, round(min(1.0, top - second + 0.5), 3))

        state.memory = MemoryTileManager.build_tiles(context_items, self.budget, historical_record, chosen_route)
        state.fabric_state.hot_memory_ids = [x.item_id for x in state.memory.hot]
        state.fabric_state.warm_memory_ids = [x.item_id for x in state.memory.warm]
        state.fabric_state.cold_memory_ids = [x.item_id for x in state.memory.cold]

        state.horizon_plan = HorizonPlanner.plan(task_type, deferred_items)
        state.fabric_state.horizon_loads = {
            "immediate": len(state.horizon_plan.immediate),
            "short": len(state.horizon_plan.short),
            "medium": len(state.horizon_plan.medium),
            "deep": len(state.horizon_plan.deep),
        }

        state.schedule = MultiScaleScheduler.build(state.horizon_plan, deferred_items)
        pressure = SchedulerPressureEngine.compute(route_scores, deferred_items)
        state.fabric_state.horizon_pressure = pressure
        state.schedule = SchedulerPressureEngine.rebalance(state.schedule, pressure)
        decisions = ConflictResolver.resolve(state.schedule, pressure, state.fabric_state.route_confidence)
        state.schedule = QueueArbitrationLayer.apply(state.schedule, decisions)
        state.fabric_state.arbitration_count = len(decisions)
        state.fabric_state.schedule_loads = {
            "immediate": len(state.schedule.immediate_queue),
            "short": len(state.schedule.short_queue),
            "medium": len(state.schedule.medium_queue),
            "deep": len(state.schedule.deep_queue),
        }

        chunks = self._make_chunks(prompt)
        chunk_horizons = [Horizon.SHORT, Horizon.DEEP] if len(chunks) >= 2 else [Horizon.DEEP]
        chosen_depths: List[int] = []
        created_deferred: List[DeferredWorkItem] = []

        for idx, chunk in enumerate(chunks):
            horizon = chunk_horizons[min(idx, len(chunk_horizons) - 1)]
            difficulty = TokenDifficultyEstimator.estimate(chunk, task_type)
            depth = DepthGovernor.choose_depth(difficulty, task_type, self.budget, historical_record, chosen_route, horizon)
            chosen_depths.append(depth)
            state.fabric_state.depth_history.append(depth)

            verify = VerificationTrigger.should_verify(task_type, difficulty, depth, self.budget, chunk, historical_record, chosen_route)
            if verify:
                state.verification_armed = True
                state.fabric_state.verification_armed = True

            if horizon == Horizon.DEEP and difficulty in {Difficulty.NORMAL, Difficulty.CRITICAL}:
                created_deferred.append(
                    DeferredWorkItem(
                        task_type=task_type.value,
                        item_id=f"{task_type.value}_deferred_{idx+1}",
                        horizon=horizon.value,
                        description=f"Deferred follow-up from chunk {idx} under {horizon.value} horizon.",
                        source_route=chosen_route.name,
                        source_chunk_index=idx,
                        priority=0.95 if state.branch_label.startswith("merge") else (0.9 if state.branch_label != "main" else 0.8),
                        reuse_count=0,
                    )
                )

        state.deferred_items_created = [asdict(x) for x in created_deferred]
        avg_depth = sum(chosen_depths) / max(1, len(chosen_depths))
        state.fabric_state.health_score = 0.8
        state.fabric_state.phase = FabricPhase.COMPLETE.value

        self.route_memory.update(task_type, chosen_depths, state.verification_armed, [x.item_id for x in state.memory.hot], state.active_modules, chosen_route.name)
        self.residue_registry.store(task_type, chosen_route.name, [x.item_id for x in state.memory.hot], state.active_modules, state.verification_armed, avg_depth)
        self.deferred_registry.store(task_type, created_deferred)

        self.last_fabric_state = state.fabric_state
        self.last_schedule = state.schedule
        return state

    @staticmethod
    def _make_chunks(prompt: str, chunk_size: int = 120) -> List[str]:
        text = " ".join(prompt.strip().split())
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        return chunks if chunks else [""]


def demo() -> None:
    context = [
        ContextItem("beal_method", "Reusable Beal method using structural reduction, local valuations, and compression.", 0.8),
        ContextItem("morph_v05", "MORPH v0.5 defines the Cognitive Fabric Runtime with route memory, residues, and orchestration.", 0.95),
        ContextItem("morph_v07", "MORPH v0.7 adds multi-scale scheduling with immediate, short, medium, and deep horizons.", 0.85),
        ContextItem("math_simulator", "The mathematics simulator includes branch atlas, verification stack, and discovery engine.", 0.9),
        ContextItem("activation_pack", "Activation pack for continuity and reactivation in a new chat.", 0.7),
        ContextItem("flux_programming", "Flux programming means loss minimization through living continuity.", 0.88),
        ContextItem("long_context_notes", "Long context needs memory tiles, reactivation gates, and summary compression.", 0.6),
    ]

    manager = ContinuityPackManager()
    project_id = "project_math_lab"

    prompt_main = "Prove a route-sensitive structural contradiction path for the mathematics simulator and stabilize the deep verification route."
    prompt_branch = "Prove the same but emphasize experimental verification pressure, branch-sensitive checks, and deeper reuse of deferred work."
    prompt_merge = "Merge the strongest parts of the main branch and the experimental verification branch into a single comparative resume state."

    runtime_root = FabricOrchestratorV13(project_id=project_id, session_id="session_001", branch_label="main")
    state_root = runtime_root.run(prompt_main, context)
    payload_root = SessionStateAdapter.export_payload(project_id, "session_001", None, "main", runtime_root.budget, runtime_root.route_memory, runtime_root.residue_registry, runtime_root.deferred_registry, runtime_root.last_fabric_state, runtime_root.last_schedule)
    path_root = manager.save_session(project_id, "session_001", payload_root, None, "main")

    payload_loaded_root = manager.load_session(project_id, "session_001")
    budget1, rm1, rr1, dr1, ff1, ss1 = SessionStateAdapter.restore(payload_loaded_root)
    runtime_main = FabricOrchestratorV13(project_id=project_id, session_id="session_002", parent_session_id="session_001", branch_label="main", budget=budget1, route_memory=rm1, residue_registry=rr1, deferred_registry=dr1, last_fabric_state=ff1, last_schedule=ss1)
    state_main = runtime_main.run(prompt_main, context)
    payload_main = SessionStateAdapter.export_payload(project_id, "session_002", "session_001", "main", runtime_main.budget, runtime_main.route_memory, runtime_main.residue_registry, runtime_main.deferred_registry, runtime_main.last_fabric_state, runtime_main.last_schedule)
    path_main = manager.save_session(project_id, "session_002", payload_main, "session_001", "main")

    fork_id = manager.create_fork_session_id("session_002", "experimental_verify")
    payload_loaded_main = manager.load_session(project_id, "session_002")
    budget2, rm2, rr2, dr2, ff2, ss2 = SessionStateAdapter.restore(payload_loaded_main)
    runtime_fork = FabricOrchestratorV13(project_id=project_id, session_id=fork_id, parent_session_id="session_002", branch_label="experimental_verify", budget=budget2, route_memory=rm2, residue_registry=rr2, deferred_registry=dr2, last_fabric_state=ff2, last_schedule=ss2)
    state_fork = runtime_fork.run(prompt_branch, context)
    payload_fork = SessionStateAdapter.export_payload(project_id, fork_id, "session_002", "experimental_verify", runtime_fork.budget, runtime_fork.route_memory, runtime_fork.residue_registry, runtime_fork.deferred_registry, runtime_fork.last_fabric_state, runtime_fork.last_schedule)
    path_fork = manager.save_session(project_id, fork_id, payload_fork, "session_002", "experimental_verify")

    compare = ComparativeResumeEngine.compare_sessions(payload_main, payload_fork)
    merge_budget, merge_rm, merge_rr, merge_dr, merge_ff, merge_ss, merge_summary = MergeResolver.merge_payloads(payload_main, payload_fork, "Merged main branch with experimental verification branch.")
    merge_session_id = manager.create_merge_session_id("session_002", fork_id)
    runtime_merge = FabricOrchestratorV13(
        project_id=project_id,
        session_id=merge_session_id,
        parent_session_id="session_002",
        branch_label="merge_main_experimental",
        budget=merge_budget,
        route_memory=merge_rm,
        residue_registry=merge_rr,
        deferred_registry=merge_dr,
        last_fabric_state=merge_ff,
        last_schedule=merge_ss,
        merge_parents=["session_002", fork_id],
        merge_note="Merged main branch with experimental verification branch.",
        merge_summary=merge_summary,
    )
    state_merge = runtime_merge.run(prompt_merge, context)
    payload_merge = SessionStateAdapter.export_payload(
        project_id,
        merge_session_id,
        "session_002",
        "merge_main_experimental",
        runtime_merge.budget,
        runtime_merge.route_memory,
        runtime_merge.residue_registry,
        runtime_merge.deferred_registry,
        runtime_merge.last_fabric_state,
        runtime_merge.last_schedule,
        merge_parents=["session_002", fork_id],
        merge_note="Merged main branch with experimental verification branch.",
        merge_summary=merge_summary,
    )
    path_merge = manager.save_session(
        project_id,
        merge_session_id,
        payload_merge,
        "session_002",
        "merge_main_experimental",
        merge_parents=["session_002", fork_id],
        merge_note="Merged main branch with experimental verification branch.",
    )

    print("=== v1.3 / Root Saved ===")
    print(f"Saved: {path_root}")
    print(f"Session: {state_root.session_id}")
    print(f"Branch: {state_root.branch_label}")

    print("\n=== v1.3 / Main Saved ===")
    print(f"Saved: {path_main}")
    print(f"Session: {state_main.session_id}")
    print(f"Branch: {state_main.branch_label}")

    print("\n=== v1.3 / Fork Saved ===")
    print(f"Saved: {path_fork}")
    print(f"Session: {state_fork.session_id}")
    print(f"Branch: {state_fork.branch_label}")

    print("\n=== Comparative Summary ===")
    print(json.dumps(compare, indent=2))

    print("\n=== v1.3 / Merge Saved ===")
    print(f"Saved: {path_merge}")
    print(f"Session: {state_merge.session_id}")
    print(f"Branch: {state_merge.branch_label}")
    print(f"Merge parents: {state_merge.merge_parents}")
    print(f"Merge note: {state_merge.merge_note}")

    print("\n=== Session Tree ===")
    print(json.dumps(manager.get_session_tree(project_id), indent=2))

    print("\n=== Merge Snapshot ===")
    print(json.dumps(manager.load_session(project_id, merge_session_id), indent=2))


if __name__ == "__main__":
    demo()
