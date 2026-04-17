#!/usr/bin/env python3
"""
MORPH Runtime Core v2.0
Single-file runtime kernel for session continuity, branching, merge, replay,
integrity checking, light repair, and compact handoff export.
"""

from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    out = []
    for ch in value.strip().lower():
        if ch.isalnum() or ch in ("_", "-"):
            out.append(ch)
        elif ch in (" ", "/", "\\", ":"):
            out.append("_")
    text = "".join(out).strip("_")
    return text or "unnamed"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


DEFAULT_PROJECT_ID = "project_math_lab"
DEFAULT_TASK_TYPE = "math"
DEFAULT_MAIN_BRANCH = "main"
DEFAULT_SIMPLE_BRANCH = "simple_track"

ROUTE_BY_TASK = {
    "math": {
        "route": "math_deep_verify",
        "verification_armed": True,
        "route_confidence": 1.0,
        "health_score": 0.9,
        "deferred_item_count": 1,
    },
    "simple": {
        "route": "default_contextual",
        "verification_armed": False,
        "route_confidence": 0.53,
        "health_score": 0.8,
        "deferred_item_count": 0,
    },
}

DEFAULT_MODULES = [
    "RuntimeKernel", "RuntimeStateManager", "RuntimeIndexManager",
    "ContinuityPackManager", "SessionStateAdapter", "ComparativeResumeEngine",
    "HandoffExporter", "PackValidator", "IntegrityGuard", "RecoveryEngine",
    "FabricOrchestratorV20", "BranchScoringLayer", "ConflictResolver",
    "QueueArbitrationLayer", "MultiScaleScheduler", "SchedulerPressureEngine",
    "DeferredWorkRegistry", "MemoryTileManager", "RouteMemoryEngine",
    "ResidueRegistry", "VerificationTrigger", "DepthGovernor",
    "TokenDifficultyEstimator", "PromptClassifier", "AuditTrailEngine",
    "ReplayEngine", "CandidateRouteGenerator", "HorizonPlanner",
    "EarlyCollapseController", "MergeResolver",
]

DEFAULT_BUDGET = {
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

TASK_MEMORY = {
    "math": {
        "hot_memory_ids": ["math_simulator", "beal_method", "morph_v05"],
        "warm_memory_ids": ["flux_programming", "morph_v07", "activation_pack"],
        "cold_memory_ids": ["long_context_notes"],
    },
    "simple": {
        "hot_memory_ids": ["long_context_notes", "morph_v05", "math_simulator"],
        "warm_memory_ids": ["flux_programming", "morph_v07", "beal_method"],
        "cold_memory_ids": ["activation_pack"],
    },
}

TASK_SCHEDULE = {
    "math": {
        "immediate_queue": ["route_commit"],
        "short_queue": ["core_claim_pass"],
        "medium_queue": ["structural_consistency_pass"],
        "deep_queue": ["proof_pressure_pass", "route_deepening"],
    },
    "simple": {
        "immediate_queue": [], "short_queue": [], "medium_queue": [], "deep_queue": [],
    },
}

TASK_MODULES = {"math": DEFAULT_MODULES, "simple": DEFAULT_MODULES}


@dataclass
class RuntimePaths:
    root: Path
    project_id: str

    @property
    def project_dir(self) -> Path: return self.root / self.project_id
    @property
    def sessions_dir(self) -> Path: return self.project_dir / "sessions"
    @property
    def branches_dir(self) -> Path: return self.project_dir / "branches"
    @property
    def merges_dir(self) -> Path: return self.project_dir / "merges"
    @property
    def recovery_dir(self) -> Path: return self.project_dir / "recovery"
    @property
    def handoff_dir(self) -> Path: return self.project_dir / "handoff"
    @property
    def runtime_index(self) -> Path: return self.project_dir / "runtime_index.json"
    @property
    def manifest(self) -> Path: return self.project_dir / "project_manifest.json"
    @property
    def integrity_report(self) -> Path: return self.project_dir / "integrity_report.json"
    @property
    def recovery_report(self) -> Path: return self.project_dir / "recovery_report.json"
    @property
    def archive_summary(self) -> Path: return self.project_dir / "archive_summary.json"
    @property
    def compact_handoff(self) -> Path: return self.project_dir / "compact_handoff.json"
    @property
    def latest_resume_block(self) -> Path: return self.handoff_dir / "latest_resume_block.txt"
    @property
    def audit_tail(self) -> Path: return self.project_dir / "audit_tail.json"
    @property
    def replay_snapshot(self) -> Path: return self.project_dir / "replay_snapshot.json"
    @property
    def quick_report(self) -> Path: return self.project_dir / "quick_report.txt"
    @property
    def audit_log(self) -> Path: return self.project_dir / "audit_log.json"


class RuntimeKernel:
    def __init__(self, root: Path, project_id: str = DEFAULT_PROJECT_ID) -> None:
        self.paths = RuntimePaths(root=root, project_id=project_id)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for p in [self.paths.project_dir, self.paths.sessions_dir, self.paths.branches_dir,
                  self.paths.merges_dir, self.paths.recovery_dir, self.paths.handoff_dir]:
            p.mkdir(parents=True, exist_ok=True)

    def _blank_index(self) -> Dict[str, Any]:
        return {
            "project_id": self.paths.project_id,
            "created_at": now_iso(),
            "latest_session_global": None,
            "latest_sessions_by_branch": {},
            "sessions": {},
            "branches": {},
            "merges": {},
            "replays": {},
            "archives": {},
            "recovery": {},
        }

    def load_index(self) -> Dict[str, Any]:
        return read_json(self.paths.runtime_index, self._blank_index())

    def save_index(self, index: Dict[str, Any]) -> None:
        write_json(self.paths.runtime_index, index)

    def load_audit(self) -> List[Dict[str, Any]]:
        return read_json(self.paths.audit_log, [])

    def save_audit(self, audit: List[Dict[str, Any]]) -> None:
        write_json(self.paths.audit_log, audit)

    def audit_event(self, event_type: str, outcome: str,
                    session_id: Optional[str] = None,
                    branch_label: Optional[str] = None,
                    route_name: Optional[str] = None,
                    details: Optional[Dict[str, Any]] = None) -> None:
        audit = self.load_audit()
        audit.append({
            "timestamp": now_iso(),
            "event_type": event_type,
            "project_id": self.paths.project_id,
            "session_id": session_id,
            "branch_label": branch_label,
            "route_name": route_name,
            "outcome": outcome,
            "details": details or {},
        })
        self.save_audit(audit)

    def session_path(self, session_id: str) -> Path:
        return self.paths.sessions_dir / f"{session_id}.json"

    def branch_path(self, branch_label: str) -> Path:
        return self.paths.branches_dir / f"{branch_label}.json"

    def merge_path(self, merge_session_id: str) -> Path:
        return self.paths.merges_dir / f"{merge_session_id}.json"

    def read_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        path = self.session_path(session_id)
        if not path.exists():
            return None
        return read_json(path, None)

    def _next_session_id(self, index: Dict[str, Any], branch_label: str, task_type: str) -> str:
        base_n = len(index["sessions"]) + 1
        if branch_label == DEFAULT_MAIN_BRANCH:
            return f"session_{base_n:03d}"
        return f"session_{base_n:03d}_{slugify(branch_label)}"

    def _route_payload(self, task_type: str) -> Dict[str, Any]:
        base = deepcopy(ROUTE_BY_TASK.get(task_type, ROUTE_BY_TASK["simple"]))
        base.update(deepcopy(TASK_MEMORY.get(task_type, TASK_MEMORY["simple"])))
        base["last_schedule"] = deepcopy(TASK_SCHEDULE.get(task_type, TASK_SCHEDULE["simple"]))
        base["active_modules"] = deepcopy(TASK_MODULES.get(task_type, TASK_MODULES["simple"]))
        return base

    def _make_session_payload(self, session_id: str, parent: Optional[str], branch: str,
                              task_type: str, budget: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        route = self._route_payload(task_type)
        return {
            "project_id": self.paths.project_id,
            "session_id": session_id,
            "parent": parent,
            "branch": branch,
            "task_type": task_type,
            "chosen_route": route["route"],
            "verification_armed": route["verification_armed"],
            "route_confidence": route["route_confidence"],
            "deferred_item_count": route["deferred_item_count"],
            "health_score": route["health_score"],
            "active_modules": route["active_modules"],
            "hot_memory_ids": route["hot_memory_ids"],
            "warm_memory_ids": route["warm_memory_ids"],
            "cold_memory_ids": route["cold_memory_ids"],
            "last_schedule": route["last_schedule"],
            "budget": deepcopy(budget or DEFAULT_BUDGET),
            "saved_at": now_iso(),
        }

    def _write_branch_file(self, branch_label: str, payload: Dict[str, Any]) -> None:
        write_json(self.branch_path(branch_label), payload)

    def ensure_root(self, task_type: str = DEFAULT_TASK_TYPE) -> Tuple[Dict[str, Any], bool]:
        index = self.load_index()
        if index["latest_session_global"]:
            return index, False
        session_id = "session_001"
        payload = self._make_session_payload(session_id, None, DEFAULT_MAIN_BRANCH, task_type)
        write_json(self.session_path(session_id), payload)
        index["latest_session_global"] = session_id
        index["latest_sessions_by_branch"][DEFAULT_MAIN_BRANCH] = session_id
        index["sessions"][session_id] = {
            "path": str(self.session_path(session_id).relative_to(self.paths.project_dir)),
            "parent": None, "branch": DEFAULT_MAIN_BRANCH,
            "task_type": task_type, "saved_at": payload["saved_at"],
        }
        index["branches"][DEFAULT_MAIN_BRANCH] = {"latest_session_id": session_id, "session_ids": [session_id]}
        self.save_index(index)
        self._write_branch_file(DEFAULT_MAIN_BRANCH, index["branches"][DEFAULT_MAIN_BRANCH])
        self.audit_event("root_created", "created", session_id=session_id,
                         branch_label=DEFAULT_MAIN_BRANCH, route_name=payload["chosen_route"],
                         details={"path": str(self.session_path(session_id).relative_to(self.paths.project_dir))})
        self.rebuild_exports()
        return index, True

    def append_task(self, task_type: str, resume_session: Optional[str] = None,
                    branch: Optional[str] = None) -> Dict[str, Any]:
        index = self.load_index()
        if not index["latest_session_global"]:
            index, _ = self.ensure_root(task_type=DEFAULT_TASK_TYPE)

        chosen_branch = branch or DEFAULT_MAIN_BRANCH
        parent = resume_session or index["latest_sessions_by_branch"].get(chosen_branch)
        if parent is not None and parent not in index["sessions"]:
            raise ValueError(f"Unknown session for resume: {parent}")

        session_id = self._next_session_id(index, chosen_branch, task_type)
        parent_payload = self.read_session(parent) if parent else None
        budget = parent_payload.get("budget") if parent_payload else deepcopy(DEFAULT_BUDGET)
        payload = self._make_session_payload(session_id, parent, chosen_branch, task_type, budget)
        write_json(self.session_path(session_id), payload)

        index["latest_session_global"] = session_id
        index["latest_sessions_by_branch"][chosen_branch] = session_id
        index["sessions"][session_id] = {
            "path": str(self.session_path(session_id).relative_to(self.paths.project_dir)),
            "parent": parent, "branch": chosen_branch,
            "task_type": task_type, "saved_at": payload["saved_at"],
        }
        branch_state = index["branches"].setdefault(chosen_branch, {"latest_session_id": None, "session_ids": []})
        branch_state["latest_session_id"] = session_id
        branch_state["session_ids"].append(session_id)
        self.save_index(index)
        self._write_branch_file(chosen_branch, branch_state)
        self.audit_event("task_appended", "saved", session_id=session_id,
                         branch_label=chosen_branch, route_name=payload["chosen_route"],
                         details={"parent_session_id": parent, "task_type": task_type})
        self.rebuild_exports()
        return payload

    def resume_session(self, session_id: str) -> Dict[str, Any]:
        payload = self.read_session(session_id)
        if not payload:
            raise ValueError(f"Session not found: {session_id}")
        self.audit_event("session_resumed", "loaded", session_id=session_id,
                         branch_label=payload["branch"], route_name=payload["chosen_route"],
                         details={"path": str(self.session_path(session_id).relative_to(self.paths.project_dir))})
        return payload

    def fork_branch(self, from_session: str, branch_label: str) -> Dict[str, Any]:
        parent_payload = self.read_session(from_session)
        if not parent_payload:
            raise ValueError(f"Cannot fork. Session not found: {from_session}")
        index = self.load_index()
        task_type = parent_payload["task_type"]
        session_id = self._next_session_id(index, branch_label, task_type)
        payload = self._make_session_payload(session_id, from_session, branch_label, task_type,
                                             parent_payload.get("budget", deepcopy(DEFAULT_BUDGET)))
        write_json(self.session_path(session_id), payload)
        index["latest_session_global"] = session_id
        index["latest_sessions_by_branch"][branch_label] = session_id
        index["sessions"][session_id] = {
            "path": str(self.session_path(session_id).relative_to(self.paths.project_dir)),
            "parent": from_session, "branch": branch_label,
            "task_type": task_type, "saved_at": payload["saved_at"],
        }
        index["branches"][branch_label] = {
            "latest_session_id": session_id, "session_ids": [session_id], "forked_from": from_session
        }
        self.save_index(index)
        self._write_branch_file(branch_label, index["branches"][branch_label])
        self.audit_event("branch_forked", "forked", session_id=session_id, branch_label=branch_label,
                         route_name=payload["chosen_route"], details={"parent_session_id": from_session})
        self.rebuild_exports()
        return payload

    def merge_sessions(self, left_session: str, right_session: str) -> Dict[str, Any]:
        left = self.read_session(left_session)
        right = self.read_session(right_session)
        if not left or not right:
            raise ValueError("Merge requires two valid sessions.")
        merge_session_id = f"merge_{left_session}__{right_session}"
        merged = self._make_session_payload(
            merge_session_id, left_session,
            f"merge_{slugify(left['branch'])}_{slugify(right['branch'])}",
            left["task_type"], left.get("budget", deepcopy(DEFAULT_BUDGET))
        )
        merged["merge_parents"] = [left_session, right_session]
        merged["merge_note"] = f"Merged {left['branch']} branch with {right['branch']} branch."
        merged["chosen_route"] = left["chosen_route"]
        merged["route_confidence"] = max(left.get("route_confidence", 0), right.get("route_confidence", 0))
        merged["deferred_item_count"] = max(left.get("deferred_item_count", 0), right.get("deferred_item_count", 0))
        write_json(self.merge_path(merge_session_id), merged)

        index = self.load_index()
        index["merges"][merge_session_id] = {
            "path": str(self.merge_path(merge_session_id).relative_to(self.paths.project_dir)),
            "parents": [left_session, right_session], "saved_at": merged["saved_at"],
        }
        self.save_index(index)
        self.audit_event("branch_merged", "merged", session_id=merge_session_id,
                         branch_label=merged["branch"], route_name=merged["chosen_route"],
                         details={"left_session_id": left_session, "right_session_id": right_session})
        self.rebuild_exports()
        return merged

    def replay_session(self, session_id: str) -> Dict[str, Any]:
        payload = self.read_session(session_id)
        if not payload:
            merge_path = self.merge_path(session_id)
            if merge_path.exists():
                payload = read_json(merge_path, None)
        if not payload:
            raise ValueError(f"Replay target not found: {session_id}")
        snapshot = {
            "replayed_at": now_iso(),
            "mode": "session_replay",
            "project_id": self.paths.project_id,
            "session_id": payload["session_id"],
            "branch_label": payload["branch"],
            "chosen_route": payload["chosen_route"],
            "verification_armed": payload["verification_armed"],
            "last_phase": "complete",
            "last_schedule": payload.get("last_schedule", {}),
            "replayed_modules": payload.get("active_modules", []),
            "notes": ["Replay intended for isolated branch validation."],
        }
        write_json(self.paths.replay_snapshot, snapshot)
        index = self.load_index()
        index["replays"][payload["session_id"]] = {
            "path": str(self.paths.replay_snapshot.relative_to(self.paths.project_dir)),
            "replayed_at": snapshot["replayed_at"],
        }
        self.save_index(index)
        self.audit_event("replay_completed", "replayed", session_id=payload["session_id"],
                         branch_label=payload["branch"], route_name=payload["chosen_route"],
                         details={"mode": "session_replay"})
        self.rebuild_exports()
        return snapshot

    def integrity_check(self) -> Dict[str, Any]:
        index = self.load_index()
        problems: List[Dict[str, Any]] = []
        for session_id, meta in index["sessions"].items():
            session_file = self.paths.project_dir / meta["path"]
            if not session_file.exists():
                problems.append({"type": "missing_session_file", "session_id": session_id, "path": meta["path"]})
            parent = meta.get("parent")
            if parent and parent not in index["sessions"]:
                problems.append({"type": "missing_parent", "session_id": session_id, "parent": parent})
        for branch_label, branch_info in index["branches"].items():
            latest = branch_info.get("latest_session_id")
            if latest and latest not in index["sessions"]:
                problems.append({"type": "bad_branch_latest", "branch": branch_label, "latest_session_id": latest})
        for merge_id, merge_meta in index["merges"].items():
            merge_file = self.paths.project_dir / merge_meta["path"]
            if not merge_file.exists():
                problems.append({"type": "missing_merge_file", "merge_id": merge_id, "path": merge_meta["path"]})
            for parent in merge_meta.get("parents", []):
                if parent not in index["sessions"]:
                    problems.append({"type": "missing_merge_parent", "merge_id": merge_id, "parent": parent})
        report = {
            "checked_at": now_iso(),
            "project_dir": str(self.paths.project_dir),
            "session_count": len(index["sessions"]),
            "merge_count": len(index["merges"]),
            "problem_count": len(problems),
            "ok": len(problems) == 0,
            "problems": problems,
            "session_ids": sorted(index["sessions"].keys()),
        }
        write_json(self.paths.integrity_report, report)
        self.audit_event("integrity_checked", "ok" if report["ok"] else "warning",
                         details={"problem_count": report["problem_count"],
                                  "path": str(self.paths.integrity_report.relative_to(self.paths.project_dir))})
        return report

    def repair(self) -> Dict[str, Any]:
        index = self.load_index()
        actions: List[Dict[str, Any]] = []
        rebuilt_branches: Dict[str, List[str]] = {}
        for session_id, meta in index["sessions"].items():
            rebuilt_branches.setdefault(meta["branch"], []).append(session_id)
        for branch_label, session_ids in rebuilt_branches.items():
            session_ids_sorted = sorted(session_ids, key=lambda sid: index["sessions"][sid]["saved_at"])
            index["branches"][branch_label] = {"latest_session_id": session_ids_sorted[-1], "session_ids": session_ids_sorted}
            actions.append({"action": "rebuilt_branch", "branch": branch_label})
        if index["latest_session_global"] not in index["sessions"] and index["sessions"]:
            latest_sid = max(index["sessions"], key=lambda sid: index["sessions"][sid]["saved_at"])
            index["latest_session_global"] = latest_sid
            actions.append({"action": "repaired_latest_session_global", "value": latest_sid})
        self.save_index(index)
        for branch_label, payload in index["branches"].items():
            self._write_branch_file(branch_label, payload)
        report = {"repaired_at": now_iso(), "project_dir": str(self.paths.project_dir),
                  "action_count": len(actions), "actions": actions}
        write_json(self.paths.recovery_report, report)
        self.audit_event("repair_completed", "completed",
                         details={"action_count": len(actions), "path": str(self.paths.recovery_report.relative_to(self.paths.project_dir))})
        self.rebuild_exports()
        return report

    def build_manifest(self) -> Dict[str, Any]:
        index = self.load_index()
        sessions = {sid: self.read_session(sid) for sid in index["sessions"].keys()}
        sessions = {k: v for k, v in sessions.items() if v}
        branch_counts: Dict[str, int] = {}
        task_counts: Dict[str, int] = {}
        for payload in sessions.values():
            branch_counts[payload["branch"]] = branch_counts.get(payload["branch"], 0) + 1
            task_counts[payload["task_type"]] = task_counts.get(payload["task_type"], 0) + 1
        latest_id = index["latest_session_global"]
        latest_payload = sessions.get(latest_id) if latest_id else None
        manifest = {
            "project_id": self.paths.project_id,
            "session_count": len(sessions),
            "branch_counts": branch_counts,
            "task_type_counts": task_counts,
            "latest_session": latest_payload,
            "latest_sessions_by_branch": index["latest_sessions_by_branch"],
            "merge_count": len(index["merges"]),
            "saved_at": now_iso(),
        }
        write_json(self.paths.manifest, manifest)
        self.audit_event("manifest_built", "built", details={"path": str(self.paths.manifest.relative_to(self.paths.project_dir))})
        return manifest

    def build_archive_summary(self) -> Dict[str, Any]:
        index = self.load_index()
        summary = {
            "project_id": self.paths.project_id,
            "session_count": len(index["sessions"]),
            "branch_count": len(index["branches"]),
            "merge_count": len(index["merges"]),
            "replay_count": len(index["replays"]),
            "saved_at": now_iso(),
            "files": {
                "runtime_index": str(self.paths.runtime_index.relative_to(self.paths.project_dir)),
                "manifest": str(self.paths.manifest.relative_to(self.paths.project_dir)),
                "integrity_report": str(self.paths.integrity_report.relative_to(self.paths.project_dir)),
                "quick_report": str(self.paths.quick_report.relative_to(self.paths.project_dir)),
                "compact_handoff": str(self.paths.compact_handoff.relative_to(self.paths.project_dir)),
                "replay_snapshot": str(self.paths.replay_snapshot.relative_to(self.paths.project_dir)),
            },
        }
        write_json(self.paths.archive_summary, summary)
        self.audit_event("archive_built", "built", details={"path": str(self.paths.archive_summary.relative_to(self.paths.project_dir))})
        return summary

    def build_quick_report(self) -> str:
        index = self.load_index()
        latest_id = index["latest_session_global"]
        latest = self.read_session(latest_id) if latest_id else None
        if not latest and index["merges"]:
            newest_merge = max(index["merges"], key=lambda k: index["merges"][k]["saved_at"])
            latest = read_json(self.paths.project_dir / index["merges"][newest_merge]["path"], {})
        lines = [
            f"Project: {self.paths.project_id}",
            f"Latest session: {latest.get('session_id') if latest else 'None'}",
            f"Branch: {latest.get('branch') if latest else 'None'}",
            f"Task type: {latest.get('task_type') if latest else 'None'}",
            f"Route: {latest.get('chosen_route') if latest else 'None'}",
            f"Confidence: {latest.get('route_confidence') if latest else 'None'}",
            f"Deferred: {latest.get('deferred_item_count') if latest else 'None'}",
            f"Health: {latest.get('health_score') if latest else 'None'}",
            f"Integrity file: {self.paths.integrity_report.name}",
            f"Manifest file: {self.paths.manifest.name}",
            f"Index file: {self.paths.runtime_index.name}",
        ]
        text = "\n".join(lines) + "\n"
        write_text(self.paths.quick_report, text)
        self.audit_event("quick_report_built", "built", details={"path": str(self.paths.quick_report.relative_to(self.paths.project_dir))})
        return text

    def build_audit_tail(self, n: int = 8) -> List[Dict[str, Any]]:
        audit = self.load_audit()
        tail = audit[-n:]
        write_json(self.paths.audit_tail, tail)
        return tail

    def export_handoff(self) -> Dict[str, Any]:
        index = self.load_index()
        latest_main_id = index["latest_sessions_by_branch"].get(DEFAULT_MAIN_BRANCH)
        latest_simple_id = index["latest_sessions_by_branch"].get(DEFAULT_SIMPLE_BRANCH)
        latest_main = self.read_session(latest_main_id) if latest_main_id else None
        latest_simple = self.read_session(latest_simple_id) if latest_simple_id else None
        integrity = read_json(self.paths.integrity_report, {"ok": False, "problem_count": -1})
        handoff = {
            "project_id": self.paths.project_id,
            "latest_main_session": latest_main_id,
            "latest_simple_session": latest_simple_id,
            "active_branches": sorted(index["branches"].keys()),
            "main_route": latest_main.get("chosen_route") if latest_main else None,
            "simple_route": latest_simple.get("chosen_route") if latest_simple else None,
            "health": latest_main.get("health_score") if latest_main else None,
            "deferred": latest_main.get("deferred_item_count") if latest_main else None,
            "integrity_ok": integrity.get("ok"),
            "integrity_problem_count": integrity.get("problem_count"),
            "resume_cmd_main": f"python morph_runtime_core_v2_0.py --resume-session {latest_main_id}" if latest_main_id else None,
            "resume_cmd_simple": f"python morph_runtime_core_v2_0.py --resume-session {latest_simple_id}" if latest_simple_id else None,
            "saved_at": now_iso(),
        }
        write_json(self.paths.compact_handoff, handoff)
        block = [
            f"PROJECT: {self.paths.project_id}",
            f"LATEST_MAIN: {latest_main_id}",
            f"LATEST_SIMPLE: {latest_simple_id}",
            f"MAIN_ROUTE: {handoff['main_route']}",
            f"SIMPLE_ROUTE: {handoff['simple_route']}",
            f"HEALTH: {handoff['health']}",
            f"DEFERRED: {handoff['deferred']}",
            f"INTEGRITY_OK: {handoff['integrity_ok']}",
            f"INTEGRITY_PROBLEMS: {handoff['integrity_problem_count']}",
            f"RESUME_MAIN: {handoff['resume_cmd_main']}",
            f"RESUME_SIMPLE: {handoff['resume_cmd_simple']}",
        ]
        write_text(self.paths.latest_resume_block, "\n".join(block) + "\n")
        self.audit_event("handoff_exported", "built", details={"path": str(self.paths.compact_handoff.relative_to(self.paths.project_dir))})
        return handoff

    def build_zip(self) -> Path:
        zip_base = self.paths.root / self.paths.project_id
        zip_path_str = shutil.make_archive(str(zip_base), "zip", root_dir=str(self.paths.root), base_dir=self.paths.project_id)
        return Path(zip_path_str)

    def rebuild_exports(self) -> None:
        self.integrity_check()
        self.build_manifest()
        self.build_archive_summary()
        self.build_quick_report()
        self.build_audit_tail()
        self.export_handoff()

    def compact_summary(self) -> Dict[str, Any]:
        manifest = read_json(self.paths.manifest, {})
        integrity = read_json(self.paths.integrity_report, {})
        handoff = read_json(self.paths.compact_handoff, {})
        return {
            "project_id": self.paths.project_id,
            "session_count": manifest.get("session_count", 0),
            "branch_counts": manifest.get("branch_counts", {}),
            "task_type_counts": manifest.get("task_type_counts", {}),
            "latest_session": manifest.get("latest_session"),
            "integrity_ok": integrity.get("ok"),
            "problem_count": integrity.get("problem_count"),
            "resume_main": handoff.get("resume_cmd_main"),
            "resume_simple": handoff.get("resume_cmd_simple"),
        }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="MORPH Runtime Core v2.0")
    p.add_argument("--project-dir", default="morph_runtime_core_v2_0", help="root pack directory")
    p.add_argument("--project-id", default=DEFAULT_PROJECT_ID, help="project id")
    p.add_argument("--fresh-if-missing", action="store_true", help="create root session if project is empty")
    p.add_argument("--append-task", choices=["math", "simple"], help="append a new task session")
    p.add_argument("--resume-session", help="resume / use as parent session id")
    p.add_argument("--branch", help="branch label for append")
    p.add_argument("--fork-from", help="fork new branch from a session")
    p.add_argument("--merge", nargs=2, metavar=("LEFT_SESSION", "RIGHT_SESSION"), help="merge two sessions")
    p.add_argument("--replay-session", help="replay a session or merge node")
    p.add_argument("--integrity-check", action="store_true", help="run integrity check")
    p.add_argument("--repair", action="store_true", help="attempt light repair")
    p.add_argument("--export-handoff", action="store_true", help="export compact handoff")
    p.add_argument("--quick", action="store_true", help="print compact summary")
    return p.parse_args()


def print_json(title: str, payload: Any) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    root = Path(args.project_dir)
    kernel = RuntimeKernel(root=root, project_id=args.project_id)

    created_root = False
    if args.fresh_if_missing:
        _, created_root = kernel.ensure_root()

    if args.append_task:
        payload = kernel.append_task(task_type=args.append_task, resume_session=args.resume_session, branch=args.branch)
        print_json("Saved Session", payload)

    if args.resume_session and not args.append_task:
        payload = kernel.resume_session(args.resume_session)
        print_json("Resumed Session", payload)

    if args.fork_from:
        if not args.branch:
            raise SystemExit("--fork-from requires --branch")
        payload = kernel.fork_branch(args.fork_from, args.branch)
        print_json("Forked Session", payload)

    if args.merge:
        payload = kernel.merge_sessions(args.merge[0], args.merge[1])
        print_json("Merge Snapshot", payload)

    if args.replay_session:
        payload = kernel.replay_session(args.replay_session)
        print_json("Replay Snapshot", payload)

    if args.integrity_check:
        report = kernel.integrity_check()
        print_json("Integrity Report", report)

    if args.repair:
        report = kernel.repair()
        print_json("Recovery Report", report)

    if args.export_handoff:
        handoff = kernel.export_handoff()
        print_json("Compact Handoff", handoff)

    kernel.rebuild_exports()
    zip_path = kernel.build_zip()
    summary = kernel.compact_summary()
    latest_quick = kernel.build_quick_report()

    print("\n=== MORPH Runtime Core v2.0 / Summary ===")
    print(f"Project:        {kernel.paths.project_id}")
    print(f"Pack root:      {kernel.paths.root}")
    print(f"Project dir:    {kernel.paths.project_dir}")
    print(f"Root created:   {created_root}")
    print(f"Index file:     {kernel.paths.runtime_index}")
    print(f"Manifest file:  {kernel.paths.manifest}")
    print(f"Integrity file: {kernel.paths.integrity_report}")
    print(f"Handoff file:   {kernel.paths.compact_handoff}")
    print(f"Quick report:   {kernel.paths.quick_report}")
    print(f"ZIP export:     {zip_path}")

    print_json("Compact Summary", summary)
    print("\n=== Quick Report ===")
    print(latest_quick.rstrip())
    print_json("Audit Tail (Last 8 Events)", read_json(kernel.paths.audit_tail, []))


if __name__ == "__main__":
    main()
