#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MORPH Runtime Core v1.5
Focus:
- continuity pack save
- merge / replay / integrity
- compact export manifest
- archive-ready summary
"""

from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from copy import deepcopy


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class MorphRuntimeCoreV15:
    def __init__(self, base_dir: str = "morph_continuity_pack_v1_5") -> None:
        self.base_dir = Path(base_dir)
        ensure_dir(self.base_dir)

        self.default_budget = {
            "max_depth": 3,
            "verification_threshold": 2,
            "max_hot_items": 3,
            "max_warm_items": 3,
            "force_cold_tail": True,
            "max_candidate_routes": 3,
            "max_residue_bundles_per_task": 5,
            "max_deferred_items_per_task": 12,
            "deferred_trigger_on_medium_normal": True,
            "deferred_trigger_on_deep_normal": True,
        }

        self.math_modules = [
            "RuntimeStateManager",
            "ContinuityPackManager",
            "SessionStateAdapter",
            "ComparativeResumeEngine",
            "MergeResolver",
            "AuditTrailEngine",
            "ReplayEngine",
            "IntegrityGuard",
            "FabricOrchestratorV15",
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

        self.simple_modules = list(self.math_modules)

        self.audit_events: list[dict] = []

    def event(self, event_type: str, project_id: str, session_id: str | None, branch_label: str | None,
              route_name: str | None, outcome: str, details: dict) -> None:
        self.audit_events.append({
            "timestamp": now_iso(),
            "event_type": event_type,
            "project_id": project_id,
            "session_id": session_id,
            "branch_label": branch_label,
            "route_name": route_name,
            "outcome": outcome,
            "details": details,
        })

    def save_session(self, project_dir: Path, session_id: str, parent_session_id: str | None, branch_label: str,
                     task_type: str, chosen_route: str, verification_armed: bool, confidence: float,
                     deferred_count: int, residue_bundle_count: int, health: float, hot_items: list[str],
                     warm_items: list[str], cold_items: list[str], schedule_loads: dict, horizon_loads: dict,
                     route_memory: dict, residue_registry: dict, deferred_registry: dict,
                     last_schedule: dict, notes: list[str] | None = None) -> Path:

        active_modules = self.math_modules if task_type == "math" else self.simple_modules
        avg_depth = 3.0 if task_type == "math" else 1.0

        session = {
            "project_id": project_dir.name,
            "session_id": session_id,
            "parent_session_id": parent_session_id,
            "branch_label": branch_label,
            "task_type": task_type,
            "chosen_route": chosen_route,
            "verification_armed": verification_armed,
            "budget": deepcopy(self.default_budget),
            "route_memory": route_memory,
            "residue_registry": residue_registry,
            "deferred_registry": deferred_registry,
            "last_fabric_state": {
                "task_type": task_type,
                "phase": "complete",
                "chosen_route": chosen_route,
                "verification_armed": verification_armed,
                "active_modules": active_modules,
                "health_score": health,
                "historical_route_used": residue_bundle_count > 0,
                "residue_bundle_count": residue_bundle_count,
                "depth_history": [3] if task_type == "math" else [1],
                "hot_memory_ids": hot_items,
                "warm_memory_ids": warm_items,
                "cold_memory_ids": cold_items,
                "horizon_loads": horizon_loads,
                "deferred_item_count": deferred_count,
                "schedule_loads": schedule_loads,
                "route_confidence": confidence,
                "arbitration_count": 1 if confidence >= 0.95 else 0,
            },
            "last_schedule": last_schedule,
            "notes": notes or [],
            "saved_at": now_iso(),
        }

        path = project_dir / f"{session_id}.json"
        write_json(path, session)

        self.event(
            event_type="save_session",
            project_id=project_dir.name,
            session_id=session_id,
            branch_label=branch_label,
            route_name=chosen_route,
            outcome="saved",
            details={"path": str(path)}
        )
        return path

    def integrity_check(self, project_dir: Path) -> Path:
        problems = []
        session_files = sorted(project_dir.glob("*.json"))
        session_ids = [p.stem for p in session_files if p.stem not in {"integrity_report", "project_manifest", "archive_summary", "replay_snapshot"}]

        for p in session_files:
            if p.stem in {"integrity_report", "project_manifest", "archive_summary", "replay_snapshot"}:
                continue
            try:
                data = read_json(p)
                required = ["project_id", "session_id", "branch_label", "task_type", "chosen_route", "last_fabric_state"]
                for key in required:
                    if key not in data:
                        problems.append(f"{p.name}: missing {key}")
            except Exception as e:
                problems.append(f"{p.name}: unreadable ({e})")

        report = {
            "checked_at": now_iso(),
            "project_dir": str(project_dir),
            "session_count": len(session_ids),
            "problem_count": len(problems),
            "ok": len(problems) == 0,
            "problems": problems,
            "session_ids": sorted(session_ids),
        }
        path = project_dir / "integrity_report.json"
        write_json(path, report)
        self.event("integrity_check", project_dir.name, None, None, None, "ok" if not problems else "problems",
                   {"problem_count": len(problems), "path": str(path)})
        return path

    def replay_snapshot(self, project_dir: Path, session_path: Path, mode: str = "branch_replay") -> Path:
        data = read_json(session_path)
        snap = {
            "replayed_at": now_iso(),
            "mode": mode,
            "project_id": data["project_id"],
            "session_id": data["session_id"],
            "branch_label": data["branch_label"],
            "chosen_route": data["chosen_route"],
            "verification_armed": data["verification_armed"],
            "last_phase": data["last_fabric_state"]["phase"],
            "last_schedule": data["last_schedule"],
            "replayed_modules": sorted(data["last_fabric_state"]["active_modules"]),
            "notes": ["Replay intended for isolated branch validation."],
        }
        path = project_dir / "replay_snapshot.json"
        write_json(path, snap)
        self.event("replay_session", data["project_id"], data["session_id"], data["branch_label"], data["chosen_route"],
                   "replayed", {"mode": mode, "path": str(path)})
        return path

    def build_project_manifest(self, project_dir: Path) -> Path:
        session_files = sorted(project_dir.glob("*.json"))
        sessions = []
        branches = {}
        task_types = {}
        latest_session = None

        skip = {"integrity_report", "project_manifest", "archive_summary", "replay_snapshot"}
        for p in session_files:
            if p.stem in skip:
                continue
            data = read_json(p)
            item = {
                "session_id": data["session_id"],
                "parent_session_id": data.get("parent_session_id"),
                "branch_label": data["branch_label"],
                "task_type": data["task_type"],
                "chosen_route": data["chosen_route"],
                "verification_armed": data["verification_armed"],
                "route_confidence": data["last_fabric_state"]["route_confidence"],
                "deferred_item_count": data["last_fabric_state"]["deferred_item_count"],
                "saved_at": data["saved_at"],
                "path": str(p),
            }
            sessions.append(item)
            branches.setdefault(data["branch_label"], 0)
            branches[data["branch_label"]] += 1
            task_types.setdefault(data["task_type"], 0)
            task_types[data["task_type"]] += 1
            latest_session = item

        manifest = {
            "generated_at": now_iso(),
            "project_id": project_dir.name,
            "session_count": len(sessions),
            "branch_counts": branches,
            "task_type_counts": task_types,
            "latest_session": latest_session,
            "sessions": sessions,
        }
        path = project_dir / "project_manifest.json"
        write_json(path, manifest)
        self.event("build_manifest", project_dir.name, None, None, None, "built", {"path": str(path)})
        return path

    def build_archive_summary(self, project_dir: Path) -> Path:
        manifest = read_json(project_dir / "project_manifest.json")
        summary = {
            "generated_at": now_iso(),
            "project_id": manifest["project_id"],
            "archive_ready": True,
            "compact_export": {
                "session_count": manifest["session_count"],
                "branches": manifest["branch_counts"],
                "task_types": manifest["task_type_counts"],
                "latest_session_id": manifest["latest_session"]["session_id"] if manifest["latest_session"] else None,
                "latest_route": manifest["latest_session"]["chosen_route"] if manifest["latest_session"] else None,
            },
            "recommended_keep_files": [
                "project_manifest.json",
                "archive_summary.json",
                "integrity_report.json",
                "replay_snapshot.json",
            ],
            "notes": [
                "Use project_manifest.json for compact inspection.",
                "Use replay_snapshot.json for quick branch replay state.",
                "Use integrity_report.json before archiving or sharing."
            ]
        }
        path = project_dir / "archive_summary.json"
        write_json(path, summary)
        self.event("archive_summary", project_dir.name, None, None, None, "built", {"path": str(path)})
        return path

    def demo(self) -> None:
        project_dir = self.base_dir / "project_math_lab"
        ensure_dir(project_dir)

        math_route_memory = {
            "math": {
                "task_type": "math",
                "run_count": 1,
                "avg_depth": 3.0,
                "verification_rate": 1.0,
                "preferred_hot_items": {
                    "math_simulator": 1,
                    "beal_method": 1,
                    "morph_v05": 1
                },
                "preferred_modules": {m: 1 for m in self.math_modules},
                "preferred_route_names": {
                    "math_deep_verify": 1
                }
            },
            "simple": {
                "task_type": "simple",
                "run_count": 1,
                "avg_depth": 1.0,
                "verification_rate": 0.0,
                "preferred_hot_items": {
                    "long_context_notes": 1,
                    "morph_v05": 1,
                    "math_simulator": 1
                },
                "preferred_modules": {m: 1 for m in self.simple_modules},
                "preferred_route_names": {
                    "default_contextual": 1
                }
            }
        }

        residue_registry = {
            "math": [
                {
                    "task_type": "math",
                    "bundle_id": "math_bundle_1",
                    "route_name": "math_deep_verify",
                    "hot_items": ["math_simulator", "beal_method", "morph_v05"],
                    "active_modules": self.math_modules,
                    "verification_armed": True,
                    "avg_depth": 3.0,
                    "usage_count": 1
                }
            ]
        }

        deferred_registry = {
            "math": [
                {
                    "task_type": "math",
                    "item_id": "math_deferred_1",
                    "horizon": "deep",
                    "description": "Deferred follow-up generated by v1.5 demo.",
                    "source_route": "math_deep_verify",
                    "source_chunk_index": 0,
                    "priority": 1.0,
                    "reuse_count": 0
                }
            ]
        }

        last_schedule = {
            "immediate_queue": ["route_commit"],
            "short_queue": ["core_claim_pass"],
            "medium_queue": ["structural_consistency_pass"],
            "deep_queue": ["proof_pressure_pass", "route_deepening"]
        }

        # root
        root_path = self.save_session(
            project_dir=project_dir,
            session_id="session_001",
            parent_session_id=None,
            branch_label="main",
            task_type="math",
            chosen_route="math_deep_verify",
            verification_armed=True,
            confidence=0.95,
            deferred_count=1,
            residue_bundle_count=1,
            health=0.9,
            hot_items=["math_simulator", "beal_method", "morph_v05"],
            warm_items=["flux_programming", "morph_v07", "activation_pack"],
            cold_items=["long_context_notes"],
            schedule_loads={"immediate": 1, "short": 1, "medium": 1, "deep": 2},
            horizon_loads={"immediate": 1, "short": 1, "medium": 1, "deep": 2},
            route_memory=math_route_memory,
            residue_registry=residue_registry,
            deferred_registry=deferred_registry,
            last_schedule=last_schedule,
            notes=["v1.5 root session"]
        )

        # main continuation
        math_route_memory["math"]["run_count"] = 2
        math_route_memory["math"]["preferred_hot_items"]["math_simulator"] = 2
        math_route_memory["math"]["preferred_hot_items"]["beal_method"] = 2
        math_route_memory["math"]["preferred_hot_items"]["morph_v05"] = 2
        for m in self.math_modules:
            math_route_memory["math"]["preferred_modules"][m] = 2
        math_route_memory["math"]["preferred_route_names"]["math_deep_verify"] = 2

        residue_registry["math"].append({
            "task_type": "math",
            "bundle_id": "math_bundle_2",
            "route_name": "math_deep_verify",
            "hot_items": ["math_simulator", "beal_method", "morph_v05"],
            "active_modules": self.math_modules,
            "verification_armed": True,
            "avg_depth": 3.0,
            "usage_count": 0
        })

        main_path = self.save_session(
            project_dir=project_dir,
            session_id="session_002",
            parent_session_id="session_001",
            branch_label="main",
            task_type="math",
            chosen_route="math_deep_verify",
            verification_armed=True,
            confidence=1.0,
            deferred_count=1,
            residue_bundle_count=2,
            health=0.9,
            hot_items=["math_simulator", "beal_method", "morph_v05"],
            warm_items=["flux_programming", "morph_v07", "activation_pack"],
            cold_items=["long_context_notes"],
            schedule_loads={"immediate": 1, "short": 1, "medium": 1, "deep": 3},
            horizon_loads={"immediate": 1, "short": 2, "medium": 1, "deep": 2},
            route_memory=deepcopy(math_route_memory),
            residue_registry=deepcopy(residue_registry),
            deferred_registry=deepcopy(deferred_registry),
            last_schedule=deepcopy(last_schedule),
            notes=["v1.5 main continuation"]
        )

        # independent simple session
        simple_path = self.save_session(
            project_dir=project_dir,
            session_id="session_003_simple",
            parent_session_id=None,
            branch_label="simple_track",
            task_type="simple",
            chosen_route="default_contextual",
            verification_armed=False,
            confidence=0.53,
            deferred_count=0,
            residue_bundle_count=0,
            health=0.8,
            hot_items=["long_context_notes", "morph_v05", "math_simulator"],
            warm_items=["flux_programming", "morph_v07", "beal_method"],
            cold_items=["activation_pack"],
            schedule_loads={"immediate": 0, "short": 0, "medium": 0, "deep": 0},
            horizon_loads={"immediate": 0, "short": 0, "medium": 0, "deep": 0},
            route_memory=deepcopy(math_route_memory),
            residue_registry=deepcopy(residue_registry),
            deferred_registry={},
            last_schedule={"immediate_queue": [], "short_queue": [], "medium_queue": [], "deep_queue": []},
            notes=["independent simple branch"]
        )

        integrity_path = self.integrity_check(project_dir)
        replay_path = self.replay_snapshot(project_dir, main_path)
        manifest_path = self.build_project_manifest(project_dir)
        archive_path = self.build_archive_summary(project_dir)

        print("=== MORPH Runtime Core v1.5 / Summary ===")
        print(f"Saved root:      {root_path}")
        print(f"Saved main:      {main_path}")
        print(f"Saved simple:    {simple_path}")
        print(f"Integrity file:  {integrity_path}")
        print(f"Replay file:     {replay_path}")
        print(f"Manifest file:   {manifest_path}")
        print(f"Archive file:    {archive_path}")
        print()
        print("=== Quick Snapshot ===")
        print("Project:   project_math_lab")
        print("Main route: math_deep_verify")
        print("Simple route: default_contextual")
        print("Health:    0.9")
        print("Deferred:  1")
        print()
        print("=== Compact Export ===")
        manifest = read_json(manifest_path)
        print(json.dumps({
            "project_id": manifest["project_id"],
            "session_count": manifest["session_count"],
            "branch_counts": manifest["branch_counts"],
            "task_type_counts": manifest["task_type_counts"],
            "latest_session": manifest["latest_session"],
        }, indent=2))

        print()
        print("=== Audit Tail (Last 6 Events) ===")
        for e in self.audit_events[-6:]:
            print(f"- {e['event_type']} | {e['outcome']} | {e['session_id']}")

if __name__ == "__main__":
    MorphRuntimeCoreV15().demo()
