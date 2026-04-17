
#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def safe_branch_name(branch: str) -> str:
    return branch.strip().replace(" ", "_").replace("/", "_")

def session_sort_key(name: str) -> Tuple[int, str]:
    digits = "".join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 0, name)

DEFAULT_BUDGET: Dict[str, Any] = {
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

MATH_MODULES_V18 = [
    "RuntimeStateManager","ContinuityPackManager","SessionStateAdapter","ResumeSelector",
    "BranchResolver","FabricOrchestratorV18","PromptClassifier","TokenDifficultyEstimator",
    "DepthGovernor","MemoryTileManager","RouteMemoryEngine","ResidueRegistry",
    "DeferredWorkRegistry","HorizonPlanner","MultiScaleScheduler","IntegrityGuard",
    "AuditTrailEngine","VerificationTrigger",
]

SIMPLE_MODULES_V18 = [
    "RuntimeStateManager","ContinuityPackManager","SessionStateAdapter","ResumeSelector",
    "BranchResolver","FabricOrchestratorV18","PromptClassifier","TokenDifficultyEstimator",
    "DepthGovernor","MemoryTileManager","RouteMemoryEngine","ResidueRegistry",
    "DeferredWorkRegistry","HorizonPlanner","MultiScaleScheduler","IntegrityGuard",
    "AuditTrailEngine",
]

DEFAULT_TASK_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "math": {
        "task_type": "math",
        "chosen_route": "math_deep_verify",
        "verification_armed": True,
        "avg_depth": 3.0,
        "health_score": 0.9,
        "route_confidence": 1.0,
        "hot_memory_ids": ["math_simulator", "beal_method", "morph_v05"],
        "warm_memory_ids": ["flux_programming", "morph_v07", "activation_pack"],
        "cold_memory_ids": ["long_context_notes"],
        "horizon_loads": {"immediate": 1, "short": 1, "medium": 1, "deep": 2},
        "schedule_loads": {"immediate": 1, "short": 1, "medium": 1, "deep": 2},
        "last_schedule": {
            "immediate_queue": ["route_commit"],
            "short_queue": ["core_claim_pass"],
            "medium_queue": ["structural_consistency_pass"],
            "deep_queue": ["proof_pressure_pass", "route_deepening"],
        },
        "active_modules": MATH_MODULES_V18,
    },
    "simple": {
        "task_type": "simple",
        "chosen_route": "default_contextual",
        "verification_armed": False,
        "avg_depth": 1.0,
        "health_score": 0.8,
        "route_confidence": 0.53,
        "hot_memory_ids": ["long_context_notes", "morph_v05", "math_simulator"],
        "warm_memory_ids": ["flux_programming", "morph_v07", "beal_method"],
        "cold_memory_ids": ["activation_pack"],
        "horizon_loads": {"immediate": 0, "short": 0, "medium": 0, "deep": 0},
        "schedule_loads": {"immediate": 0, "short": 0, "medium": 0, "deep": 0},
        "last_schedule": {
            "immediate_queue": [],
            "short_queue": [],
            "medium_queue": [],
            "deep_queue": [],
        },
        "active_modules": SIMPLE_MODULES_V18,
    },
}

class ContinuityPackManager:
    def __init__(self, base_dir: Path, project_id: str) -> None:
        self.base_dir = base_dir
        self.project_id = project_id
        self.project_dir = self.base_dir / self.project_id
        ensure_dir(self.project_dir)
        self.manifest_path = self.project_dir / "project_manifest.json"
        self.integrity_path = self.project_dir / "integrity_report.json"
        self.audit_path = self.project_dir / "audit_tail.json"
        self.archive_path = self.project_dir / "archive_summary.json"
        self.quick_report_path = self.project_dir / "quick_report.txt"
        self.zip_path = self.project_dir.with_suffix(".zip")

    def all_session_files(self) -> List[Path]:
        skip = {"project_manifest.json","integrity_report.json","audit_tail.json","archive_summary.json","replay_snapshot.json"}
        return sorted([p for p in self.project_dir.glob("*.json") if p.name not in skip], key=lambda p: session_sort_key(p.stem))

    def load_manifest(self) -> Dict[str, Any]:
        return read_json(self.manifest_path, default={
            "project_id": self.project_id,
            "created_at": now_iso(),
            "session_count": 0,
            "branches": {},
            "latest_session_id": None,
            "latest_by_branch": {},
            "task_type_counts": {},
        })

    def save_manifest(self, manifest: Dict[str, Any]) -> None:
        write_json(self.manifest_path, manifest)

    def append_audit(self, event_type: str, session_id: Optional[str], branch_label: Optional[str], route_name: Optional[str], outcome: str, details: Dict[str, Any]) -> None:
        audit = read_json(self.audit_path, default=[])
        audit.append({
            "timestamp": now_iso(),
            "event_type": event_type,
            "project_id": self.project_id,
            "session_id": session_id,
            "branch_label": branch_label,
            "route_name": route_name,
            "outcome": outcome,
            "details": details,
        })
        write_json(self.audit_path, audit[-12:])

    def save_quick_report(self, lines: List[str]) -> None:
        ensure_dir(self.quick_report_path.parent)
        with self.quick_report_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")

    def build_integrity_report(self) -> Dict[str, Any]:
        problems: List[str] = []
        manifest = self.load_manifest()
        session_ids: List[str] = []
        for path in self.all_session_files():
            try:
                data = read_json(path, default={})
                sid = data.get("session_id")
                if not sid:
                    problems.append(f"Missing session_id in {path.name}")
                else:
                    session_ids.append(sid)
            except Exception as exc:
                problems.append(f"Unreadable {path.name}: {exc}")
        report = {
            "checked_at": now_iso(),
            "project_dir": str(self.project_dir),
            "session_count": len(session_ids),
            "problem_count": len(problems),
            "ok": len(problems) == 0,
            "problems": problems,
            "session_ids": sorted(session_ids, key=session_sort_key),
            "manifest_latest_session_id": manifest.get("latest_session_id"),
        }
        write_json(self.integrity_path, report)
        self.append_audit("integrity_check", None, None, None, "ok" if not problems else "problem", {"problem_count": len(problems), "path": str(self.integrity_path)})
        return report

    def build_archive_summary(self) -> Dict[str, Any]:
        manifest = self.load_manifest()
        latest_session_id = manifest.get("latest_session_id")
        latest_path = self.project_dir / f"{latest_session_id}.json" if latest_session_id else None
        latest_data = read_json(latest_path, default={}) if latest_path and latest_path.exists() else {}
        summary = {
            "project_id": self.project_id,
            "session_count": manifest.get("session_count", 0),
            "branch_counts": {k: len(v) for k, v in manifest.get("branches", {}).items()},
            "task_type_counts": manifest.get("task_type_counts", {}),
            "latest_session": {
                "session_id": latest_data.get("session_id"),
                "parent_session_id": latest_data.get("parent_session_id"),
                "branch_label": latest_data.get("branch_label"),
                "task_type": latest_data.get("task_type"),
                "chosen_route": latest_data.get("chosen_route"),
                "verification_armed": latest_data.get("verification_armed"),
                "route_confidence": latest_data.get("route_confidence"),
                "deferred_item_count": latest_data.get("deferred_item_count", 0),
                "saved_at": latest_data.get("saved_at"),
                "path": str(latest_path) if latest_path else None,
            },
        }
        write_json(self.archive_path, summary)
        self.append_audit("archive_summary", None, None, None, "built", {"path": str(self.archive_path)})
        return summary

    def export_zip(self) -> Path:
        if self.zip_path.exists():
            self.zip_path.unlink()
        with zipfile.ZipFile(self.zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(self.project_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(self.project_dir.parent)))
        return self.zip_path

class FabricOrchestratorV18:
    def __init__(self, task_type: str) -> None:
        self.task_type = task_type
        if task_type not in DEFAULT_TASK_TEMPLATES:
            raise ValueError(f"Unsupported task_type: {task_type}")

    def build_base_state(self) -> Dict[str, Any]:
        t = deepcopy(DEFAULT_TASK_TEMPLATES[self.task_type])
        return {
            "task_type": t["task_type"],
            "chosen_route": t["chosen_route"],
            "verification_armed": t["verification_armed"],
            "active_modules": t["active_modules"],
            "health_score": t["health_score"],
            "historical_route_used": False,
            "residue_bundle_count": 0,
            "depth_history": [int(t["avg_depth"])],
            "hot_memory_ids": t["hot_memory_ids"],
            "warm_memory_ids": t["warm_memory_ids"],
            "cold_memory_ids": t["cold_memory_ids"],
            "horizon_loads": t["horizon_loads"],
            "deferred_item_count": 0,
            "schedule_loads": t["schedule_loads"],
            "route_confidence": t["route_confidence"],
            "arbitration_count": 0,
            "last_schedule": t["last_schedule"],
        }

    def build_residue_entry(self, session_index: int, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "task_type": self.task_type,
            "bundle_id": f"{self.task_type}_bundle_{session_index}",
            "route_name": state["chosen_route"],
            "hot_items": state["hot_memory_ids"],
            "active_modules": state["active_modules"],
            "verification_armed": state["verification_armed"],
            "avg_depth": float(sum(state["depth_history"]) / max(len(state["depth_history"]), 1)),
            "usage_count": 0,
        }

class MorphRuntimeCoreV18:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.base_dir = Path(args.base_dir).expanduser().resolve()
        ensure_dir(self.base_dir)
        self.project_id = args.project or "project_math_lab"
        self.branch = safe_branch_name(args.branch or ("simple_track" if args.append_task == "simple" else "main"))
        self.task_type = args.append_task or "math"
        self.manager = ContinuityPackManager(self.base_dir, self.project_id)

    def _manifest_add_session(self, manifest: Dict[str, Any], session: Dict[str, Any]) -> None:
        branch = session["branch_label"]
        manifest["branches"].setdefault(branch, [])
        if session["session_id"] not in manifest["branches"][branch]:
            manifest["branches"][branch].append(session["session_id"])
        manifest["session_count"] = sum(len(v) for v in manifest["branches"].values())
        manifest["latest_session_id"] = session["session_id"]
        manifest["latest_by_branch"][branch] = session["session_id"]
        tt = session["task_type"]
        manifest["task_type_counts"][tt] = manifest["task_type_counts"].get(tt, 0) + 1

    def _next_session_id(self, manifest: Dict[str, Any], branch: str, task_type: str) -> str:
        existing = manifest.get("branches", {}).get(branch, [])
        base = f"session_{len(existing)+1:03d}"
        return base if branch == "main" else f"{base}_{branch}"

    def _resolve_resume_source(self, manifest: Dict[str, Any]) -> Optional[str]:
        if self.args.resume_session:
            return self.args.resume_session
        if self.branch in manifest.get("latest_by_branch", {}):
            return manifest["latest_by_branch"][self.branch]
        return manifest.get("latest_session_id")

    def _create_root_if_missing(self, manifest: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], bool]:
        if manifest.get("session_count", 0) > 0:
            return None, False
        orchestrator = FabricOrchestratorV18("math")
        state = orchestrator.build_base_state()
        session = {
            "project_id": self.project_id,
            "session_id": "session_001",
            "parent_session_id": None,
            "branch_label": "main",
            "task_type": "math",
            "chosen_route": state["chosen_route"],
            "verification_armed": state["verification_armed"],
            "active_modules": state["active_modules"],
            "health_score": state["health_score"],
            "historical_route_used": False,
            "residue_bundle_count": 0,
            "depth_history": state["depth_history"],
            "hot_memory_ids": state["hot_memory_ids"],
            "warm_memory_ids": state["warm_memory_ids"],
            "cold_memory_ids": state["cold_memory_ids"],
            "horizon_loads": state["horizon_loads"],
            "deferred_item_count": 0,
            "schedule_loads": state["schedule_loads"],
            "route_confidence": state["route_confidence"],
            "arbitration_count": 0,
            "last_schedule": state["last_schedule"],
            "residue_registry": {"math": [orchestrator.build_residue_entry(1, state)]},
            "deferred_registry": {},
            "budget": deepcopy(DEFAULT_BUDGET),
            "saved_at": now_iso(),
        }
        path = self.manager.project_dir / "session_001.json"
        write_json(path, session)
        self._manifest_add_session(manifest, session)
        self.manager.save_manifest(manifest)
        self.manager.append_audit("root_created", session["session_id"], "main", session["chosen_route"], "created", {"path": str(path)})
        return session, True

    def _build_from_template(self, task_type: str, session_id: str, parent_session_id: Optional[str], branch: str) -> Dict[str, Any]:
        orch = FabricOrchestratorV18(task_type)
        state = orch.build_base_state()
        residue_map = {task_type: [orch.build_residue_entry(1, state)]} if task_type == "math" else {}
        deferred_map = {"math": [{
            "task_type": "math",
            "item_id": "math_deferred_1",
            "horizon": "deep",
            "description": "Deferred follow-up generated by v1.8.",
            "source_route": state["chosen_route"],
            "source_chunk_index": 0,
            "priority": 1.0,
            "reuse_count": 0,
        }]} if task_type == "math" else {}
        return {
            "project_id": self.project_id,
            "session_id": session_id,
            "parent_session_id": parent_session_id,
            "branch_label": branch,
            "task_type": task_type,
            "chosen_route": state["chosen_route"],
            "verification_armed": state["verification_armed"],
            "active_modules": state["active_modules"],
            "health_score": state["health_score"],
            "historical_route_used": bool(parent_session_id),
            "residue_bundle_count": 1 if task_type == "math" else 0,
            "depth_history": state["depth_history"],
            "hot_memory_ids": state["hot_memory_ids"],
            "warm_memory_ids": state["warm_memory_ids"],
            "cold_memory_ids": state["cold_memory_ids"],
            "horizon_loads": state["horizon_loads"],
            "deferred_item_count": 1 if task_type == "math" else 0,
            "schedule_loads": state["schedule_loads"],
            "route_confidence": state["route_confidence"],
            "arbitration_count": 1 if parent_session_id else 0,
            "last_schedule": state["last_schedule"],
            "residue_registry": residue_map,
            "deferred_registry": deferred_map,
            "budget": deepcopy(DEFAULT_BUDGET),
            "saved_at": now_iso(),
        }

    def _clone_from_resume(self, src: Dict[str, Any], session_id: str, branch: str, task_type: str) -> Dict[str, Any]:
        if task_type != src.get("task_type"):
            return self._build_from_template(task_type, session_id, src["session_id"], branch)
        sess = deepcopy(src)
        sess["session_id"] = session_id
        sess["parent_session_id"] = src["session_id"]
        sess["branch_label"] = branch
        sess["task_type"] = task_type
        sess["historical_route_used"] = True
        sess["saved_at"] = now_iso()
        if task_type == "math":
            bundles = sess.setdefault("residue_registry", {}).setdefault("math", [])
            residue_index = len(bundles) + 1
            bundles.append({
                "task_type": "math",
                "bundle_id": f"math_bundle_{residue_index}",
                "route_name": sess["chosen_route"],
                "hot_items": sess["hot_memory_ids"],
                "active_modules": sess["active_modules"],
                "verification_armed": sess["verification_armed"],
                "avg_depth": float(sum(sess["depth_history"]) / max(len(sess["depth_history"]), 1)),
                "usage_count": 0,
            })
            sess["residue_bundle_count"] = len(bundles)
            deferred = sess.setdefault("deferred_registry", {}).setdefault("math", [])
            if deferred:
                deferred[0]["reuse_count"] = int(deferred[0].get("reuse_count", 0)) + 1
            else:
                deferred.append({
                    "task_type": "math",
                    "item_id": "math_deferred_1",
                    "horizon": "deep",
                    "description": "Deferred follow-up generated by v1.8.",
                    "source_route": sess["chosen_route"],
                    "source_chunk_index": 0,
                    "priority": 1.0,
                    "reuse_count": 0,
                })
            sess["deferred_item_count"] = len(deferred)
            sess["arbitration_count"] = int(sess.get("arbitration_count", 0)) + 1
        return sess

    def _save_session(self, session: Dict[str, Any]) -> Path:
        path = self.manager.project_dir / f"{session['session_id']}.json"
        write_json(path, session)
        manifest = self.manager.load_manifest()
        self._manifest_add_session(manifest, session)
        self.manager.save_manifest(manifest)
        self.manager.append_audit("session_saved", session["session_id"], session["branch_label"], session["chosen_route"], "saved", {"path": str(path)})
        return path

    def run(self) -> Dict[str, Any]:
        manifest = self.manager.load_manifest()
        root_session, root_created = self._create_root_if_missing(manifest)
        manifest = self.manager.load_manifest()
        resume_source = self._resolve_resume_source(manifest)
        resumed = False
        resume_data: Optional[Dict[str, Any]] = None
        if resume_source:
            rp = self.manager.project_dir / f"{resume_source}.json"
            if rp.exists():
                resume_data = read_json(rp, default={})
                resumed = True
                self.manager.append_audit("resume_session", resume_source, resume_data.get("branch_label"), resume_data.get("chosen_route"), "loaded", {"path": str(rp)})
        session_id = self._next_session_id(manifest, self.branch, self.task_type)
        session = self._clone_from_resume(resume_data, session_id, self.branch, self.task_type) if resume_data else self._build_from_template(self.task_type, session_id, None, self.branch)
        session_path = self._save_session(session)
        integrity = self.manager.build_integrity_report()
        archive = self.manager.build_archive_summary()
        zip_path = self.manager.export_zip()
        self.manager.save_quick_report([
            f"Project:      {self.project_id}",
            f"Session:      {session['session_id']}",
            f"Parent:       {session.get('parent_session_id')}",
            f"Branch:       {session['branch_label']}",
            f"Task type:    {session['task_type']}",
            f"Chosen route: {session['chosen_route']}",
            f"Confidence:   {session['route_confidence']}",
            f"Deferred:     {session['deferred_item_count']}",
            f"Health:       {session['health_score']}",
            f"Integrity:    {'ok' if integrity['ok'] else 'problem'} ({integrity['problem_count']})",
            f"Manifest:     {self.manager.manifest_path}",
            f"Archive:      {self.manager.archive_path}",
            f"ZIP:          {zip_path}",
        ])
        return {
            "root_created": root_created,
            "root_session_id": root_session["session_id"] if root_session else None,
            "session_saved": session["session_id"],
            "branch_used": session["branch_label"],
            "resume_source": resume_source if resumed else None,
            "project": self.project_id,
            "task_type": session["task_type"],
            "chosen_route": session["chosen_route"],
            "session_path": str(session_path),
            "manifest_path": str(self.manager.manifest_path),
            "quick_report_path": str(self.manager.quick_report_path),
            "archive_path": str(self.manager.archive_path),
            "integrity_path": str(self.manager.integrity_path),
            "zip_path": str(zip_path),
            "status_snapshot": {
                "current_session": session["session_id"],
                "parent": session.get("parent_session_id"),
                "branch": session["branch_label"],
                "task_type": session["task_type"],
                "chosen_route": session["chosen_route"],
                "verification_armed": session["verification_armed"],
                "route_confidence": session["route_confidence"],
                "deferred_item_count": session["deferred_item_count"],
                "health_score": session["health_score"],
            },
        }

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MORPH Runtime Core v1.8")
    p.add_argument("--project", default="project_math_lab", help="Project id")
    p.add_argument("--branch", default=None, help="Target branch label")
    p.add_argument("--resume-session", default=None, help="Explicit session id to resume from")
    p.add_argument("--append-task", choices=["math", "simple"], default=None, help="Task type for new session")
    p.add_argument("--fresh-if-missing", action="store_true", help="Create root automatically if project pack is missing")
    p.add_argument("--base-dir", default="morph_continuity_pack_v1_8", help="Base continuity directory")
    return p

def main() -> None:
    args = build_parser().parse_args()
    result = MorphRuntimeCoreV18(args).run()
    print("=== MORPH Runtime Core v1.8 / Summary ===")
    print(f"Project:       {result['project']}")
    print(f"Root created:  {result['root_created']}")
    print(f"Root session:  {result['root_session_id']}")
    print(f"Saved session: {result['session_saved']}")
    print(f"Branch used:   {result['branch_used']}")
    print(f"Resume source: {result['resume_source']}")
    print(f"Task type:     {result['task_type']}")
    print(f"Chosen route:  {result['chosen_route']}")
    print(f"Session file:  {result['session_path']}")
    print(f"Manifest file: {result['manifest_path']}")
    print(f"Quick report:  {result['quick_report_path']}")
    print(f"Archive file:  {result['archive_path']}")
    print(f"Integrity:     {result['integrity_path']}")
    print(f"ZIP export:    {result['zip_path']}")
    print()
    print("=== Status Snapshot ===")
    print(json.dumps(result["status_snapshot"], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
