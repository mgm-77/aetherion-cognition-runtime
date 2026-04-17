"""
MORPH Runtime Core v1.2
Session Branching + Fork Resume

Adds on top of v1.1:
- parent_session_id
- branch_label
- branch-aware registry
- forked session creation from existing session
- session tree per project
- selective resume from parent while keeping independent branch state

Prototype only.
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
    project_id: str = "default_project"
    session_id: str = "session_001"
    parent_session_id: Optional[str] = None
    branch_label: str = "main"
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
    arbitration_trace: List[Dict] = field(default_factory=list)


class PromptClassifier:
    @classmethod
    def classify(cls, prompt: str, context_items: List[ContextItem]) -> TaskType:
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
        for b in residue_bundles:
            residue_route_counts[b.route_name] = residue_route_counts.get(b.route_name, 0) + 1
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
            lid = item.item_id.lower()
            if lid in route_focus:
                score += 0.7
            if lid in preferred:
                score += min(0.6, preferred[lid] * 0.12)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        ordered = [item for _, item in scored]
        hot = ordered[: budget.max_hot_items]
        warm = ordered[budget.max_hot_items : budget.max_hot_items + budget.max_warm_items]
        cold = ordered[budget.max_hot_items + budget.max_warm_items :]
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
    TASK_BASE_DEPTH = {TaskType.SIMPLE:1, TaskType.RETRIEVAL:1, TaskType.CODING:2, TaskType.MATH:2, TaskType.LONG_CONTEXT:2, TaskType.VERIFICATION_HEAVY:2}
    DIFFICULTY_BOOST = {Difficulty.EASY:0, Difficulty.NORMAL:0, Difficulty.CRITICAL:1}

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
        if pressure.get("short", 0) > 0.45 and "deferred_reuse_scan" not in schedule.short_queue:
            schedule.short_queue.append("deferred_reuse_scan")
        return schedule


class ConflictResolver:
    @staticmethod
    def resolve(schedule: MultiScaleSchedule, pressure: Dict[str, float], route_confidence: float) -> List[ArbitrationDecision]:
        decisions: List[ArbitrationDecision] = []
        if pressure.get("deep", 0) > pressure.get("short", 0) and route_confidence >= 0.9 and "core_claim_pass" in schedule.short_queue:
            schedule.short_queue.remove("core_claim_pass")
            schedule.deep_queue.append("core_claim_pass")
            decisions.append(ArbitrationDecision("core_claim_pass", "short", "deep", "deep_pressure_dominates_with_high_confidence"))
        return decisions


class QueueArbitrationLayer:
    @staticmethod
    def apply(schedule: MultiScaleSchedule, decisions: List[ArbitrationDecision]) -> MultiScaleSchedule:
        return schedule


class ContinuityPackManager:
    def __init__(self, root_dir: str = "morph_continuity_pack_v1_2") -> None:
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

    def save_session(self, project_id: str, session_id: str, payload: Dict, parent_session_id: Optional[str], branch_label: str) -> Path:
        file_path = self.get_session_file(project_id, session_id)
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        registry = self._load_registry()
        project = registry["projects"].setdefault(project_id, {"sessions": {}, "roots": []})
        if session_id not in project["sessions"]:
            project["sessions"][session_id] = {
                "parent_session_id": parent_session_id,
                "branch_label": branch_label,
                "children": [],
            }
        else:
            project["sessions"][session_id]["parent_session_id"] = parent_session_id
            project["sessions"][session_id]["branch_label"] = branch_label
        if parent_session_id:
            parent_node = project["sessions"].setdefault(parent_session_id, {"parent_session_id": None, "branch_label": "main", "children": []})
            if session_id not in parent_node["children"]:
                parent_node["children"].append(session_id)
        else:
            if session_id not in project["roots"]:
                project["roots"].append(session_id)
        self._save_registry(registry)
        return file_path

    def load_session(self, project_id: str, session_id: str) -> Dict:
        file_path = self.get_session_file(project_id, session_id)
        return json.loads(file_path.read_text(encoding="utf-8"))

    def list_projects(self) -> List[str]:
        return sorted(self._load_registry()["projects"].keys())

    def list_sessions(self, project_id: str) -> List[str]:
        project = self._load_registry()["projects"].get(project_id, {})
        return sorted(project.get("sessions", {}).keys())

    def get_session_tree(self, project_id: str) -> Dict:
        return self._load_registry()["projects"].get(project_id, {})

    def create_fork_session_id(self, base_session_id: str, branch_label: str) -> str:
        sanitized = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in branch_label.lower())
        return f"{base_session_id}__fork__{sanitized}"


class SessionStateAdapter:
    @staticmethod
    def export_payload(project_id: str, session_id: str, parent_session_id: Optional[str], branch_label: str, budget: BudgetProfile, route_memory: RouteMemoryEngine, residue_registry: ResidueRegistry, deferred_registry: DeferredWorkRegistry, last_fabric_state: FabricStateModel, last_schedule: MultiScaleSchedule) -> Dict:
        return {
            "project_id": project_id,
            "session_id": session_id,
            "parent_session_id": parent_session_id,
            "branch_label": branch_label,
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


class FabricOrchestratorV12:
    def __init__(self, project_id: str, session_id: str, parent_session_id: Optional[str] = None, branch_label: str = "main", budget: Optional[BudgetProfile] = None, route_memory: Optional[RouteMemoryEngine] = None, residue_registry: Optional[ResidueRegistry] = None, deferred_registry: Optional[DeferredWorkRegistry] = None, last_fabric_state: Optional[FabricStateModel] = None, last_schedule: Optional[MultiScaleSchedule] = None):
        self.project_id = project_id
        self.session_id = session_id
        self.parent_session_id = parent_session_id
        self.branch_label = branch_label
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

        state = RuntimeState(
            prompt=prompt,
            task_type=task_type,
            budget=self.budget,
            project_id=self.project_id,
            session_id=self.session_id,
            parent_session_id=self.parent_session_id,
            branch_label=self.branch_label,
        )
        state.historical_route_used = historical_record is not None
        state.historical_record_snapshot = asdict(historical_record) if historical_record else None
        state.residue_bundles_used = [asdict(b) for b in residue_bundles]
        state.deferred_items_used = [asdict(x) for x in deferred_items]
        state.candidate_routes = candidate_routes
        state.route_scores = route_scores
        state.chosen_route = chosen_route.name

        state.active_modules = [
            "ContinuityPackManager", "SessionStateAdapter", "FabricOrchestratorV12",
            "PromptClassifier", "TokenDifficultyEstimator", "DepthGovernor",
            "MemoryTileManager", "RouteMemoryEngine", "ResidueRegistry", "DeferredWorkRegistry",
            "HorizonPlanner", "MultiScaleScheduler", "SchedulerPressureEngine",
            "ConflictResolver", "QueueArbitrationLayer", "CandidateRouteGenerator",
            "BranchScoringLayer", "EarlyCollapseController", "VerificationTrigger"
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
        state.arbitration_trace = [asdict(d) for d in decisions]
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
                        priority=0.9 if state.branch_label != "main" else 0.8,
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
        chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
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

    main_prompt = "Prove why a structural contradiction route may be stronger than brute-force checking in a mathematics simulator."
    branch_prompt = "Prove the same idea but emphasize branch-sensitive verification pressure and experimental route deepening."

    # Root session
    main_session_1 = "session_001"
    runtime_main_1 = FabricOrchestratorV12(project_id=project_id, session_id=main_session_1, parent_session_id=None, branch_label="main")
    state_main_1 = runtime_main_1.run(main_prompt, context)
    payload_main_1 = SessionStateAdapter.export_payload(project_id, main_session_1, None, "main", runtime_main_1.budget, runtime_main_1.route_memory, runtime_main_1.residue_registry, runtime_main_1.deferred_registry, runtime_main_1.last_fabric_state, runtime_main_1.last_schedule)
    path_main_1 = manager.save_session(project_id, main_session_1, payload_main_1, None, "main")

    # Main continuation
    main_session_2 = "session_002"
    loaded_main_1 = manager.load_session(project_id, main_session_1)
    budget, route_memory, residue_registry, deferred_registry, last_fabric_state, last_schedule = SessionStateAdapter.restore(loaded_main_1)
    runtime_main_2 = FabricOrchestratorV12(project_id=project_id, session_id=main_session_2, parent_session_id=main_session_1, branch_label="main", budget=budget, route_memory=route_memory, residue_registry=residue_registry, deferred_registry=deferred_registry, last_fabric_state=last_fabric_state, last_schedule=last_schedule)
    state_main_2 = runtime_main_2.run(main_prompt, context)
    payload_main_2 = SessionStateAdapter.export_payload(project_id, main_session_2, main_session_1, "main", runtime_main_2.budget, runtime_main_2.route_memory, runtime_main_2.residue_registry, runtime_main_2.deferred_registry, runtime_main_2.last_fabric_state, runtime_main_2.last_schedule)
    path_main_2 = manager.save_session(project_id, main_session_2, payload_main_2, main_session_1, "main")

    # Fork from session_002
    fork_session = manager.create_fork_session_id(main_session_2, "experimental_verify")
    loaded_main_2 = manager.load_session(project_id, main_session_2)
    budget_f, route_memory_f, residue_registry_f, deferred_registry_f, last_fabric_state_f, last_schedule_f = SessionStateAdapter.restore(loaded_main_2)
    runtime_fork = FabricOrchestratorV12(project_id=project_id, session_id=fork_session, parent_session_id=main_session_2, branch_label="experimental_verify", budget=budget_f, route_memory=route_memory_f, residue_registry=residue_registry_f, deferred_registry=deferred_registry_f, last_fabric_state=last_fabric_state_f, last_schedule=last_schedule_f)
    state_fork = runtime_fork.run(branch_prompt, context)
    payload_fork = SessionStateAdapter.export_payload(project_id, fork_session, main_session_2, "experimental_verify", runtime_fork.budget, runtime_fork.route_memory, runtime_fork.residue_registry, runtime_fork.deferred_registry, runtime_fork.last_fabric_state, runtime_fork.last_schedule)
    path_fork = manager.save_session(project_id, fork_session, payload_fork, main_session_2, "experimental_verify")

    print("=== v1.2 / Root Session Saved ===")
    print(f"Saved: {path_main_1}")
    print(f"Project: {state_main_1.project_id}")
    print(f"Session: {state_main_1.session_id}")
    print(f"Parent: {state_main_1.parent_session_id}")
    print(f"Branch: {state_main_1.branch_label}")
    print(f"Chosen route: {state_main_1.chosen_route}")

    print("\n=== v1.2 / Main Continuation Saved ===")
    print(f"Saved: {path_main_2}")
    print(f"Project: {state_main_2.project_id}")
    print(f"Session: {state_main_2.session_id}")
    print(f"Parent: {state_main_2.parent_session_id}")
    print(f"Branch: {state_main_2.branch_label}")
    print(f"Historical route used: {state_main_2.historical_route_used}")
    print(f"Chosen route: {state_main_2.chosen_route}")
    print(f"Arbitration count: {state_main_2.fabric_state.arbitration_count}")

    print("\n=== v1.2 / Fork Session Saved ===")
    print(f"Saved: {path_fork}")
    print(f"Project: {state_fork.project_id}")
    print(f"Session: {state_fork.session_id}")
    print(f"Parent: {state_fork.parent_session_id}")
    print(f"Branch: {state_fork.branch_label}")
    print(f"Historical route used: {state_fork.historical_route_used}")
    print(f"Chosen route: {state_fork.chosen_route}")
    print(f"Deferred items created: {len(state_fork.deferred_items_created)}")

    print("\n=== Session Tree ===")
    print(json.dumps(manager.get_session_tree(project_id), indent=2))

    print("\n=== Fork Snapshot ===")
    print(json.dumps(manager.load_session(project_id, fork_session), indent=2))


if __name__ == "__main__":
    demo()
