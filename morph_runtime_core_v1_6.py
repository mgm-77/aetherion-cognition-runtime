#!/usr/bin/env python3
"""
MORPH Runtime Core v1.6
Adds automatic ZIP export for the continuity pack.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(value: str) -> str:
    return value.replace("/", "_").replace(" ", "_")


@dataclass
class EventLogger:
    events: List[Dict[str, Any]]

    def add(
        self,
        event_type: str,
        project_id: Optional[str],
        session_id: Optional[str],
        branch_label: Optional[str],
        route_name: Optional[str],
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.events.append(
            {
                "timestamp": now_iso(),
                "event_type": event_type,
                "project_id": project_id,
                "session_id": session_id,
                "branch_label": branch_label,
                "route_name": route_name,
                "outcome": outcome,
                "details": details or {},
            }
        )


class MorphRuntimeCoreV16:
    def __init__(self, base_dir: str = "morph_continuity_pack_v1_6") -> None:
        self.base_dir = Path(base_dir)
        self.events: List[Dict[str, Any]] = []
        self.logger = EventLogger(self.events)

    def _budget(self) -> Dict[str, Any]:
        return {
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

    def _route_memory_math(self, count: int) -> Dict[str, Any]:
        return {
            "task_type": "math",
            "run_count": count,
            "avg_depth": 3.0,
            "verification_rate": 1.0,
            "preferred_hot_items": {
                "math_simulator": count,
                "beal_method": count,
                "morph_v05": count,
            },
            "preferred_modules": {
                "RuntimeStateManager": count,
                "ContinuityPackManager": count,
                "SessionStateAdapter": count,
                "ComparativeResumeEngine": count,
                "MergeResolver": count,
                "AuditTrailEngine": count,
                "ReplayEngine": count,
                "IntegrityGuard": count,
                "FabricOrchestratorV16": count,
                "PromptClassifier": count,
                "TokenDifficultyEstimator": count,
                "DepthGovernor": count,
                "MemoryTileManager": count,
                "RouteMemoryEngine": count,
                "ResidueRegistry": count,
                "DeferredWorkRegistry": count,
                "HorizonPlanner": count,
                "MultiScaleScheduler": count,
                "SchedulerPressureEngine": count,
                "ConflictResolver": count,
                "QueueArbitrationLayer": count,
                "CandidateRouteGenerator": count,
                "BranchScoringLayer": count,
                "EarlyCollapseController": count,
                "VerificationTrigger": count,
                "ZipPackExporter": count,
            },
            "preferred_route_names": {"math_deep_verify": count},
        }

    def _route_memory_simple(self, count: int) -> Dict[str, Any]:
        return {
            "task_type": "simple",
            "run_count": count,
            "avg_depth": 1.0,
            "verification_rate": 0.0,
            "preferred_hot_items": {
                "long_context_notes": count,
                "morph_v05": count,
                "math_simulator": count,
            },
            "preferred_modules": {
                "ContinuityPackManager": count,
                "SessionStateAdapter": count,
                "ComparativeResumeEngine": count,
                "MergeResolver": count,
                "FabricOrchestratorV16": count,
                "PromptClassifier": count,
                "TokenDifficultyEstimator": count,
                "DepthGovernor": count,
                "MemoryTileManager": count,
                "RouteMemoryEngine": count,
                "ResidueRegistry": count,
                "DeferredWorkRegistry": count,
                "HorizonPlanner": count,
                "MultiScaleScheduler": count,
                "SchedulerPressureEngine": count,
                "ConflictResolver": count,
                "QueueArbitrationLayer": count,
                "CandidateRouteGenerator": count,
                "BranchScoringLayer": count,
                "EarlyCollapseController": count,
                "VerificationTrigger": count,
                "ZipPackExporter": count,
            },
            "preferred_route_names": {"default_contextual": count},
        }

    def _session_math(
        self,
        project_id: str,
        session_id: str,
        parent_session_id: Optional[str],
        branch_label: str,
        residue_count: int,
        deferred_count: int,
        route_confidence: float,
    ) -> Dict[str, Any]:
        active_modules = [
            "RuntimeStateManager",
            "ContinuityPackManager",
            "SessionStateAdapter",
            "ComparativeResumeEngine",
            "MergeResolver",
            "AuditTrailEngine",
            "ReplayEngine",
            "IntegrityGuard",
            "FabricOrchestratorV16",
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
            "ZipPackExporter",
        ]
        residue_registry = {}
        if residue_count:
            residue_registry = {
                "math": [
                    {
                        "task_type": "math",
                        "bundle_id": "math_bundle_1",
                        "route_name": "math_deep_verify",
                        "hot_items": ["math_simulator", "beal_method", "morph_v05"],
                        "active_modules": active_modules,
                        "verification_armed": True,
                        "avg_depth": 3.0,
                        "usage_count": 1,
                    }
                ]
            }

        deferred_registry = {}
        if deferred_count:
            deferred_registry = {
                "math": [
                    {
                        "task_type": "math",
                        "item_id": "math_deferred_1",
                        "horizon": "deep",
                        "description": "Deferred follow-up generated by v1.6 demo.",
                        "source_route": "math_deep_verify",
                        "source_chunk_index": 0,
                        "priority": 1.0,
                        "reuse_count": 0,
                    }
                ]
            }

        return {
            "project_id": project_id,
            "session_id": session_id,
            "parent_session_id": parent_session_id,
            "branch_label": branch_label,
            "task_type": "math",
            "chosen_route": "math_deep_verify",
            "verification_armed": True,
            "budget": self._budget(),
            "route_memory": {
                "math": self._route_memory_math(1 if session_id == "session_001" else 2)
            },
            "residue_registry": residue_registry,
            "deferred_registry": deferred_registry,
            "last_fabric_state": {
                "task_type": "math",
                "phase": "complete",
                "chosen_route": "math_deep_verify",
                "verification_armed": True,
                "active_modules": active_modules,
                "health_score": 0.9,
                "historical_route_used": session_id != "session_001",
                "residue_bundle_count": residue_count,
                "depth_history": [3],
                "hot_memory_ids": ["math_simulator", "beal_method", "morph_v05"],
                "warm_memory_ids": ["flux_programming", "morph_v07", "activation_pack"],
                "cold_memory_ids": ["long_context_notes"],
                "horizon_loads": {"immediate": 1, "short": 1, "medium": 1, "deep": 2},
                "deferred_item_count": deferred_count,
                "schedule_loads": {"immediate": 1, "short": 1, "medium": 1, "deep": 2},
                "route_confidence": route_confidence,
                "arbitration_count": 1,
            },
            "last_schedule": {
                "immediate_queue": ["route_commit"],
                "short_queue": ["core_claim_pass"],
                "medium_queue": ["structural_consistency_pass"],
                "deep_queue": ["proof_pressure_pass", "route_deepening"],
            },
            "saved_at": now_iso(),
        }

    def _session_simple(self, project_id: str, session_id: str, branch_label: str = "simple_track") -> Dict[str, Any]:
        active_modules = [
            "ContinuityPackManager",
            "SessionStateAdapter",
            "ComparativeResumeEngine",
            "MergeResolver",
            "FabricOrchestratorV16",
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
            "ZipPackExporter",
        ]
        return {
            "project_id": project_id,
            "session_id": session_id,
            "parent_session_id": None,
            "branch_label": branch_label,
            "task_type": "simple",
            "chosen_route": "default_contextual",
            "verification_armed": False,
            "budget": self._budget(),
            "route_memory": {"simple": self._route_memory_simple(1)},
            "residue_registry": {},
            "deferred_registry": {},
            "last_fabric_state": {
                "task_type": "simple",
                "phase": "complete",
                "chosen_route": "default_contextual",
                "verification_armed": False,
                "active_modules": active_modules,
                "health_score": 0.8,
                "historical_route_used": False,
                "residue_bundle_count": 0,
                "depth_history": [1, 1],
                "hot_memory_ids": ["long_context_notes", "morph_v05", "math_simulator"],
                "warm_memory_ids": ["flux_programming", "morph_v07", "beal_method"],
                "cold_memory_ids": ["activation_pack"],
                "horizon_loads": {"immediate": 0, "short": 0, "medium": 0, "deep": 0},
                "deferred_item_count": 0,
                "schedule_loads": {"immediate": 0, "short": 0, "medium": 0, "deep": 0},
                "route_confidence": 0.53,
                "arbitration_count": 0,
            },
            "last_schedule": {
                "immediate_queue": [],
                "short_queue": [],
                "medium_queue": [],
                "deep_queue": [],
            },
            "saved_at": now_iso(),
        }

    def save_session(self, project_dir: Path, session: Dict[str, Any]) -> Path:
        path = project_dir / f"{safe_name(session['session_id'])}.json"
        write_json(path, session)
        self.logger.add("save_session", session["project_id"], session["session_id"], session.get("branch_label"), session.get("chosen_route"), "saved", {"path": str(path)})
        return path

    def build_integrity_report(self, project_dir: Path, session_paths: List[Path]) -> Path:
        problems: List[str] = []
        session_ids: List[str] = []
        for path in session_paths:
            try:
                data = read_json(path)
                sid = data.get("session_id")
                if sid:
                    session_ids.append(sid)
                else:
                    problems.append(f"Missing session_id in {path.name}")
            except Exception as exc:
                problems.append(f"Unreadable file {path.name}: {exc}")

        report = {
            "checked_at": now_iso(),
            "project_dir": str(project_dir),
            "session_count": len(session_paths),
            "problem_count": len(problems),
            "ok": len(problems) == 0,
            "problems": problems,
            "session_ids": sorted(session_ids),
        }
        path = project_dir / "integrity_report.json"
        write_json(path, report)
        self.logger.add("integrity_check", project_dir.name, None, None, None, "ok" if not problems else "problems_found", {"problem_count": len(problems), "path": str(path)})
        return path

    def build_replay_snapshot(self, project_dir: Path, session: Dict[str, Any]) -> Path:
        snapshot = {
            "replayed_at": now_iso(),
            "mode": "branch_replay",
            "project_id": session["project_id"],
            "session_id": session["session_id"],
            "branch_label": session.get("branch_label"),
            "chosen_route": session.get("chosen_route"),
            "verification_armed": session.get("verification_armed"),
            "last_phase": session.get("last_fabric_state", {}).get("phase"),
            "last_schedule": session.get("last_schedule", {}),
            "replayed_modules": session.get("last_fabric_state", {}).get("active_modules", []),
            "notes": ["Replay intended for isolated branch validation."],
        }
        path = project_dir / "replay_snapshot.json"
        write_json(path, snapshot)
        self.logger.add("replay_session", session["project_id"], session["session_id"], session.get("branch_label"), session.get("chosen_route"), "replayed", {"mode": "branch_replay", "path": str(path)})
        return path

    def _latest_by_predicate(self, sessions: List[Dict[str, Any]], pred) -> Optional[Dict[str, Any]]:
        filtered = [s for s in sessions if pred(s)]
        if not filtered:
            return None
        filtered.sort(key=lambda s: s.get("saved_at", ""))
        return filtered[-1]

    def _compact_session_ref(self, project_dir: Path, session: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not session:
            return None
        return {
            "session_id": session["session_id"],
            "parent_session_id": session.get("parent_session_id"),
            "branch_label": session.get("branch_label"),
            "task_type": session.get("task_type"),
            "chosen_route": session.get("chosen_route"),
            "verification_armed": session.get("verification_armed"),
            "route_confidence": session.get("last_fabric_state", {}).get("route_confidence"),
            "deferred_item_count": session.get("last_fabric_state", {}).get("deferred_item_count"),
            "saved_at": session.get("saved_at"),
            "path": str(project_dir / f"{safe_name(session['session_id'])}.json"),
        }

    def _branch_counts(self, sessions: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for s in sessions:
            branch = s.get("branch_label", "unknown")
            counts[branch] = counts.get(branch, 0) + 1
        return counts

    def _task_counts(self, sessions: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for s in sessions:
            task = s.get("task_type", "unknown")
            counts[task] = counts.get(task, 0) + 1
        return counts

    def build_manifest(self, project_dir: Path, sessions: List[Dict[str, Any]]) -> Path:
        sessions_sorted = sorted(sessions, key=lambda s: s.get("saved_at", ""))
        latest_overall = sessions_sorted[-1] if sessions_sorted else None
        latest_main = self._latest_by_predicate(sessions_sorted, lambda s: s.get("branch_label") == "main")

        latest_by_branch: Dict[str, Dict[str, Any]] = {}
        branches = sorted({s.get("branch_label", "unknown") for s in sessions_sorted})
        for branch in branches:
            latest = self._latest_by_predicate(sessions_sorted, lambda s, b=branch: s.get("branch_label") == b)
            if latest:
                latest_by_branch[branch] = {
                    "session_id": latest["session_id"],
                    "task_type": latest["task_type"],
                    "chosen_route": latest["chosen_route"],
                    "saved_at": latest["saved_at"],
                    "path": str(project_dir / f"{safe_name(latest['session_id'])}.json"),
                }

        manifest = {
            "project_id": project_dir.name,
            "session_count": len(sessions_sorted),
            "branch_counts": self._branch_counts(sessions_sorted),
            "task_type_counts": self._task_counts(sessions_sorted),
            "latest_overall_session": self._compact_session_ref(project_dir, latest_overall),
            "latest_main_session": self._compact_session_ref(project_dir, latest_main),
            "latest_by_branch": latest_by_branch,
            "generated_at": now_iso(),
        }
        path = project_dir / "project_manifest.json"
        write_json(path, manifest)
        self.logger.add("build_manifest", project_dir.name, None, None, None, "built", {"path": str(path)})
        return path

    def build_archive_summary(self, project_dir: Path, sessions: List[Dict[str, Any]]) -> Path:
        sessions_sorted = sorted(sessions, key=lambda s: s.get("saved_at", ""))
        latest_overall = sessions_sorted[-1]
        latest_main = self._latest_by_predicate(sessions_sorted, lambda s: s.get("branch_label") == "main")
        summary = {
            "project_id": project_dir.name,
            "session_count": len(sessions_sorted),
            "branch_counts": self._branch_counts(sessions_sorted),
            "task_type_counts": self._task_counts(sessions_sorted),
            "latest_overall_session": self._compact_session_ref(project_dir, latest_overall),
            "latest_main_session": self._compact_session_ref(project_dir, latest_main),
            "health": latest_overall.get("last_fabric_state", {}).get("health_score"),
            "deferred": latest_overall.get("last_fabric_state", {}).get("deferred_item_count"),
            "generated_at": now_iso(),
        }
        path = project_dir / "archive_summary.json"
        write_json(path, summary)
        self.logger.add("archive_summary", project_dir.name, None, None, None, "built", {"path": str(path)})
        return path

    def build_quick_report(self, project_dir: Path, manifest: Dict[str, Any], archive_summary: Dict[str, Any]) -> Path:
        latest_overall = manifest.get("latest_overall_session") or {}
        latest_main = manifest.get("latest_main_session") or {}
        latest_by_branch = manifest.get("latest_by_branch") or {}

        lines = [
            "MORPH Runtime Core v1.6",
            "",
            f"Project: {manifest.get('project_id')}",
            f"Sessions: {manifest.get('session_count')}",
            f"Branches: {manifest.get('branch_counts')}",
            f"Task types: {manifest.get('task_type_counts')}",
            "",
            "Latest overall session:",
            f"  session_id: {latest_overall.get('session_id')}",
            f"  branch: {latest_overall.get('branch_label')}",
            f"  route: {latest_overall.get('chosen_route')}",
            f"  saved_at: {latest_overall.get('saved_at')}",
            "",
            "Latest main session:",
            f"  session_id: {latest_main.get('session_id')}",
            f"  branch: {latest_main.get('branch_label')}",
            f"  route: {latest_main.get('chosen_route')}",
            f"  saved_at: {latest_main.get('saved_at')}",
            "",
            "Latest by branch:",
        ]
        for branch, info in latest_by_branch.items():
            lines.append(f"  {branch}: {info.get('session_id')} | {info.get('chosen_route')}")
        lines += ["", f"Health: {archive_summary.get('health')}", f"Deferred: {archive_summary.get('deferred')}"]

        path = project_dir / "quick_report.txt"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.logger.add("quick_report", project_dir.name, None, None, None, "built", {"path": str(path)})
        return path

    def build_audit_tail(self, project_dir: Path, keep_last: int = 8) -> Path:
        path = project_dir / "audit_tail.json"
        write_json(path, {"events": self.events[-keep_last:]})
        self.logger.add("audit_tail", project_dir.name, None, None, None, "built", {"path": str(path)})
        return path

    def export_zip(self, project_dir: Path) -> Path:
        zip_path = project_dir.parent / f"{project_dir.name}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(project_dir.rglob("*")):
                if file_path.is_file():
                    zf.write(file_path, file_path.relative_to(project_dir.parent))
        self.logger.add("zip_export", project_dir.name, None, None, None, "built", {"path": str(zip_path)})
        return zip_path

    def run_demo(self) -> None:
        project_id = "project_math_lab"
        project_dir = self.base_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        root = self._session_math(project_id, "session_001", None, "main", 1, 0, 0.88)
        main = self._session_math(project_id, "session_002", "session_001", "main", 1, 1, 1.0)
        simple = self._session_simple(project_id, "session_003_simple", "simple_track")

        root_path = self.save_session(project_dir, root)
        main_path = self.save_session(project_dir, main)
        simple_path = self.save_session(project_dir, simple)

        integrity_path = self.build_integrity_report(project_dir, [root_path, main_path, simple_path])
        replay_path = self.build_replay_snapshot(project_dir, main)
        manifest_path = self.build_manifest(project_dir, [root, main, simple])
        archive_summary_path = self.build_archive_summary(project_dir, [root, main, simple])

        manifest = read_json(manifest_path)
        archive_summary = read_json(archive_summary_path)
        quick_report_path = self.build_quick_report(project_dir, manifest, archive_summary)
        audit_tail_path = self.build_audit_tail(project_dir)
        zip_path = self.export_zip(project_dir)

        print("=== MORPH Runtime Core v1.6 / Summary ===")
        print(f"Saved root:        {root_path}")
        print(f"Saved main:        {main_path}")
        print(f"Saved simple:      {simple_path}")
        print(f"Integrity file:    {integrity_path}")
        print(f"Replay file:       {replay_path}")
        print(f"Manifest file:     {manifest_path}")
        print(f"Archive file:      {archive_summary_path}")
        print(f"Quick report:      {quick_report_path}")
        print(f"Audit tail:        {audit_tail_path}")
        print(f"ZIP export:        {zip_path}")


if __name__ == "__main__":
    MorphRuntimeCoreV16().run_demo()
