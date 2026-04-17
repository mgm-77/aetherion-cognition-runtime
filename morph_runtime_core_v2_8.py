
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import copy
import json
import os
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default=None):
    if not path.exists():
        return copy.deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data):
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_text(path: Path, text: str):
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    allowed = []
    for ch in value.strip().lower():
        if ch.isalnum():
            allowed.append(ch)
        elif ch in (" ", "-", "_"):
            allowed.append("_")
    out = "".join(allowed).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "item"


class MorphRuntimeCoreV28:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pack_root = self.base_dir / "morph_runtime_core_v2_8"
        self.project_id = "project_math_lab"
        self.project_dir = self.pack_root / self.project_id
        self.sessions_dir = self.project_dir / "sessions"
        self.reports_dir = self.project_dir / "reports"
        self.runtime_index_file = self.project_dir / "runtime_index.json"
        self.project_manifest_file = self.project_dir / "project_manifest.json"
        self.integrity_report_file = self.project_dir / "integrity_report.json"
        self.quick_report_file = self.project_dir / "quick_report.txt"
        self.compact_handoff_file = self.project_dir / "compact_handoff.json"
        self.quick_resume_pack_file = self.project_dir / "quick_resume_pack.json"
        self.summary_pack_file = self.project_dir / "summary_pack.json"
        self.branch_compare_file = self.project_dir / "branch_compare_v2_8.json"
        self.branch_verdict_md_file = self.project_dir / "branch_verdict_v2_8.md"
        self.branch_verdict_txt_file = self.project_dir / "branch_verdict_v2_8.txt"
        self.archive_summary_file = self.project_dir / "archive_summary.json"
        self.zip_export_file = self.pack_root / f"{self.project_id}.zip"

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

        self.modules = {
            "math": [
                "RuntimeKernel",
                "RuntimeStateManager",
                "RuntimeIndexManager",
                "ContinuityPackManager",
                "SessionStateAdapter",
                "ComparativeResumeEngine",
                "HandoffExporter",
                "PackValidator",
                "IntegrityGuard",
                "RecoveryEngine",
                "FabricOrchestratorV28",
                "BranchScoringLayer",
                "ConflictResolver",
                "QueueArbitrationLayer",
                "MultiScaleScheduler",
                "SchedulerPressureEngine",
                "DeferredWorkRegistry",
                "MemoryTileManager",
                "RouteMemoryEngine",
                "ResidueRegistry",
                "VerificationTrigger",
                "DepthGovernor",
                "TokenDifficultyEstimator",
                "PromptClassifier",
                "AuditTrailEngine",
                "ReplayEngine",
                "CandidateRouteGenerator",
                "HorizonPlanner",
                "EarlyCollapseController",
                "MergeResolver",
                "MergeIntelligenceEngine",
                "CompareModesEngine",
                "BranchVerdictEngine",
            ],
            "simple": [
                "RuntimeKernel",
                "RuntimeStateManager",
                "RuntimeIndexManager",
                "ContinuityPackManager",
                "SessionStateAdapter",
                "ComparativeResumeEngine",
                "HandoffExporter",
                "PackValidator",
                "IntegrityGuard",
                "RecoveryEngine",
                "FabricOrchestratorV28",
                "BranchScoringLayer",
                "ConflictResolver",
                "QueueArbitrationLayer",
                "MultiScaleScheduler",
                "SchedulerPressureEngine",
                "DeferredWorkRegistry",
                "MemoryTileManager",
                "RouteMemoryEngine",
                "ResidueRegistry",
                "VerificationTrigger",
                "DepthGovernor",
                "TokenDifficultyEstimator",
                "PromptClassifier",
                "AuditTrailEngine",
                "ReplayEngine",
                "CandidateRouteGenerator",
                "HorizonPlanner",
                "EarlyCollapseController",
                "MergeResolver",
                "MergeIntelligenceEngine",
                "CompareModesEngine",
                "BranchVerdictEngine",
            ],
        }

        self.route_defaults = {
            "math": {
                "chosen_route": "math_deep_verify",
                "verification_armed": True,
                "route_confidence": 1.0,
                "health_score": 0.9,
                "deferred_item_count": 1,
                "hot_memory_ids": ["math_simulator", "beal_method", "morph_v05"],
                "warm_memory_ids": ["flux_programming", "morph_v07", "activation_pack"],
                "cold_memory_ids": ["long_context_notes"],
                "last_schedule": {
                    "immediate_queue": ["route_commit"],
                    "short_queue": ["core_claim_pass"],
                    "medium_queue": ["structural_consistency_pass"],
                    "deep_queue": ["proof_pressure_pass", "route_deepening"],
                },
            },
            "simple": {
                "chosen_route": "default_contextual",
                "verification_armed": False,
                "route_confidence": 0.53,
                "health_score": 0.8,
                "deferred_item_count": 0,
                "hot_memory_ids": ["long_context_notes", "morph_v05", "math_simulator"],
                "warm_memory_ids": ["flux_programming", "morph_v07", "beal_method"],
                "cold_memory_ids": ["activation_pack"],
                "last_schedule": {
                    "immediate_queue": [],
                    "short_queue": [],
                    "medium_queue": [],
                    "deep_queue": [],
                },
            },
        }

    def init_pack(self):
        ensure_dir(self.sessions_dir)
        ensure_dir(self.reports_dir)
        if not self.runtime_index_file.exists():
            runtime_index = {
                "project_id": self.project_id,
                "created_at": now_iso(),
                "current_session_id": None,
                "sessions": {},
                "branches": {},
                "audit_tail": [],
            }
            write_json(self.runtime_index_file, runtime_index)

    def load_index(self):
        self.init_pack()
        return read_json(self.runtime_index_file, default={})

    def save_index(self, index):
        write_json(self.runtime_index_file, index)

    def next_session_id(self, index, branch_label, task_type):
        branch_sessions = [s for s in index["sessions"].values() if s["branch"] == branch_label]
        if branch_label == "main":
            n = len(branch_sessions) + 1
            return f"session_{n:03d}"
        n = len(branch_sessions) + 1
        return f"session_{n:03d}_{slugify(branch_label)}"

    def resolve_parent(self, index, branch_label, resume_session):
        if resume_session:
            return resume_session
        branch_info = index["branches"].get(branch_label)
        if branch_info:
            return branch_info.get("latest_session_id")
        return None

    def build_session(self, session_id, parent_id, branch_label, task_type):
        defaults = copy.deepcopy(self.route_defaults[task_type])
        session = {
            "project_id": self.project_id,
            "session_id": session_id,
            "parent": parent_id,
            "branch": branch_label,
            "task_type": task_type,
            "chosen_route": defaults["chosen_route"],
            "verification_armed": defaults["verification_armed"],
            "route_confidence": defaults["route_confidence"],
            "deferred_item_count": defaults["deferred_item_count"],
            "health_score": defaults["health_score"],
            "active_modules": copy.deepcopy(self.modules[task_type]),
            "hot_memory_ids": defaults["hot_memory_ids"],
            "warm_memory_ids": defaults["warm_memory_ids"],
            "cold_memory_ids": defaults["cold_memory_ids"],
            "last_schedule": defaults["last_schedule"],
            "budget": copy.deepcopy(self.default_budget),
            "saved_at": now_iso(),
        }
        return session

    def session_path(self, session_id):
        return self.sessions_dir / f"{session_id}.json"

    def append_task(self, task_type="math", branch_label="main", resume_session=None):
        index = self.load_index()

        root_created = False
        if not index["sessions"]:
            root_created = True
            root_session_id = "session_001"
            root_session = self.build_session(root_session_id, None, "main", "math")
            write_json(self.session_path(root_session_id), root_session)
            index["sessions"][root_session_id] = {
                "path": str(self.session_path(root_session_id)),
                "parent": None,
                "branch": "main",
                "task_type": "math",
                "chosen_route": root_session["chosen_route"],
                "health_score": root_session["health_score"],
                "saved_at": root_session["saved_at"],
            }
            index["branches"]["main"] = {
                "root_session_id": root_session_id,
                "latest_session_id": root_session_id,
                "session_ids": [root_session_id],
            }
            index["current_session_id"] = root_session_id
            self.audit(index, "save_session", root_session_id, "main", root_session["chosen_route"], "saved", {"path": str(self.session_path(root_session_id))})

        if resume_session is None and task_type == "math" and branch_label == "main" and root_created:
            self.save_index(index)
            self.build_all_reports()
            return root_session, True

        parent_id = self.resolve_parent(index, branch_label, resume_session)
        session_id = self.next_session_id(index, branch_label, task_type)
        session = self.build_session(session_id, parent_id, branch_label, task_type)

        if parent_id and parent_id in index["sessions"]:
            parent = read_json(Path(index["sessions"][parent_id]["path"]), default={})
            if parent:
                session["hot_memory_ids"] = parent.get("hot_memory_ids", session["hot_memory_ids"])
                session["warm_memory_ids"] = parent.get("warm_memory_ids", session["warm_memory_ids"])
                session["cold_memory_ids"] = parent.get("cold_memory_ids", session["cold_memory_ids"])
                session["budget"] = parent.get("budget", session["budget"])

        write_json(self.session_path(session_id), session)
        index["sessions"][session_id] = {
            "path": str(self.session_path(session_id)),
            "parent": parent_id,
            "branch": branch_label,
            "task_type": task_type,
            "chosen_route": session["chosen_route"],
            "health_score": session["health_score"],
            "saved_at": session["saved_at"],
        }

        branch_info = index["branches"].setdefault(branch_label, {
            "root_session_id": session_id,
            "latest_session_id": session_id,
            "session_ids": [],
        })
        if not branch_info["session_ids"]:
            branch_info["root_session_id"] = session_id
        branch_info["latest_session_id"] = session_id
        branch_info["session_ids"].append(session_id)
        index["current_session_id"] = session_id

        self.audit(index, "save_session", session_id, branch_label, session["chosen_route"], "saved", {"path": str(self.session_path(session_id))})
        self.save_index(index)
        self.build_all_reports()
        return session, root_created

    def audit(self, index, event_type, session_id, branch_label, route_name, outcome, details):
        index["audit_tail"].append({
            "timestamp": now_iso(),
            "event_type": event_type,
            "project_id": self.project_id,
            "session_id": session_id,
            "branch_label": branch_label,
            "route_name": route_name,
            "outcome": outcome,
            "details": details,
        })
        index["audit_tail"] = index["audit_tail"][-12:]

    def integrity_check(self):
        index = self.load_index()
        problems = []
        for session_id, meta in index["sessions"].items():
            p = Path(meta["path"])
            if not p.exists():
                problems.append({"type": "missing_session_file", "session_id": session_id, "path": str(p)})
        report = {
            "checked_at": now_iso(),
            "project_dir": str(self.project_dir),
            "session_count": len(index["sessions"]),
            "problem_count": len(problems),
            "ok": len(problems) == 0,
            "problems": problems,
            "session_ids": sorted(index["sessions"].keys()),
        }
        write_json(self.integrity_report_file, report)
        self.audit(index, "integrity_checked", None, None, None, "ok" if report["ok"] else "problems", {
            "problem_count": report["problem_count"],
            "path": str(self.integrity_report_file),
        })
        self.save_index(index)
        return report

    def build_manifest(self):
        index = self.load_index()
        manifest = {
            "project_id": self.project_id,
            "pack_root": str(self.pack_root),
            "project_dir": str(self.project_dir),
            "session_count": len(index["sessions"]),
            "branch_count": len(index["branches"]),
            "latest_session_id": index.get("current_session_id"),
            "generated_at": now_iso(),
            "files": {
                "runtime_index": self.runtime_index_file.name,
                "project_manifest": self.project_manifest_file.name,
                "integrity_report": self.integrity_report_file.name,
                "quick_report": self.quick_report_file.name,
                "compact_handoff": self.compact_handoff_file.name,
                "quick_resume_pack": self.quick_resume_pack_file.name,
                "summary_pack": self.summary_pack_file.name,
                "branch_compare": self.branch_compare_file.name,
                "branch_verdict_md": self.branch_verdict_md_file.name,
                "branch_verdict_txt": self.branch_verdict_txt_file.name,
            },
            "branches": index["branches"],
        }
        write_json(self.project_manifest_file, manifest)
        index = self.load_index()
        self.audit(index, "manifest_built", None, None, None, "built", {"path": self.project_manifest_file.name})
        self.save_index(index)
        return manifest

    def latest_session(self):
        index = self.load_index()
        sid = index.get("current_session_id")
        if not sid:
            return None
        meta = index["sessions"].get(sid)
        if not meta:
            return None
        return read_json(Path(meta["path"]), default=None)

    def build_quick_report(self):
        latest = self.latest_session()
        integrity = read_json(self.integrity_report_file, default={"ok": False, "problem_count": 999})
        if not latest:
            text = "No sessions yet.\n"
        else:
            text = textwrap.dedent(f"""\
            Project: {latest['project_id']}
            Latest session: {latest['session_id']}
            Branch: {latest['branch']}
            Task type: {latest['task_type']}
            Route: {latest['chosen_route']}
            Confidence: {latest['route_confidence']}
            Deferred: {latest['deferred_item_count']}
            Health: {latest['health_score']}
            Integrity ok: {integrity.get('ok')} ({integrity.get('problem_count')})
            Upload-ready reports: report_v2.8.txt / report_v2.8.md
            Extra packs: compact_handoff.json / quick_resume_pack.json / summary_pack.json
            V2.8 extras: branch_compare_v2_8.json / branch_verdict_v2_8.txt / branch_verdict_v2_8.md
            """)
        write_text(self.quick_report_file, text)
        index = self.load_index()
        self.audit(index, "quick_report_built", None, None, None, "built", {"path": self.quick_report_file.name})
        self.save_index(index)
        return text

    def build_compact_handoff(self):
        latest = self.latest_session()
        integrity = read_json(self.integrity_report_file, default={"ok": False, "problem_count": 999})
        index = self.load_index()
        branch_counts = {k: len(v["session_ids"]) for k, v in index["branches"].items()}
        task_counts = {}
        for meta in index["sessions"].values():
            task_counts[meta["task_type"]] = task_counts.get(meta["task_type"], 0) + 1

        data = {
            "project_id": self.project_id,
            "session_count": len(index["sessions"]),
            "branch_counts": branch_counts,
            "task_type_counts": task_counts,
            "latest_session": latest,
            "integrity_ok": integrity["ok"],
            "problem_count": integrity["problem_count"],
            "resume_main": f"python morph_runtime_core_v2_8.py --append-task math --resume-session {latest['session_id']}" if latest else None,
            "resume_simple": f"python morph_runtime_core_v2_8.py --append-task simple --branch simple_track" if latest else None,
        }
        write_json(self.compact_handoff_file, data)
        index = self.load_index()
        self.audit(index, "handoff_exported", None, None, None, "built", {"path": self.compact_handoff_file.name})
        self.save_index(index)
        return data

    def build_quick_resume_pack(self):
        index = self.load_index()
        latest = self.latest_session()
        if latest:
            pack = {
                "project_id": self.project_id,
                "latest_session_id": latest["session_id"],
                "main_resume": f"python morph_runtime_core_v2_8.py --append-task math --resume-session {latest['session_id']}",
                "simple_resume": "python morph_runtime_core_v2_8.py --append-task simple --branch simple_track",
                "known_branches": list(index["branches"].keys()),
                "saved_at": now_iso(),
            }
        else:
            pack = {"project_id": self.project_id, "latest_session_id": None, "saved_at": now_iso()}
        write_json(self.quick_resume_pack_file, pack)
        return pack

    def build_summary_pack(self):
        index = self.load_index()
        sessions = []
        for sid in index["sessions"]:
            session = read_json(Path(index["sessions"][sid]["path"]), default={})
            sessions.append({
                "session_id": sid,
                "parent": session.get("parent"),
                "branch": session.get("branch"),
                "task_type": session.get("task_type"),
                "chosen_route": session.get("chosen_route"),
                "verification_armed": session.get("verification_armed"),
                "route_confidence": session.get("route_confidence"),
                "health_score": session.get("health_score"),
                "saved_at": session.get("saved_at"),
            })
        summary = {
            "project_id": self.project_id,
            "generated_at": now_iso(),
            "sessions": sessions,
            "audit_tail": index["audit_tail"][-8:],
        }
        write_json(self.summary_pack_file, summary)
        return summary

    def build_archive_summary(self):
        index = self.load_index()
        archive = {
            "project_id": self.project_id,
            "session_ids": list(index["sessions"].keys()),
            "branch_ids": list(index["branches"].keys()),
            "latest_session_id": index.get("current_session_id"),
            "generated_at": now_iso(),
        }
        write_json(self.archive_summary_file, archive)
        index = self.load_index()
        self.audit(index, "archive_built", None, None, None, "built", {"path": self.archive_summary_file.name})
        self.save_index(index)
        return archive

    def collect_branch_latest(self):
        index = self.load_index()
        result = {}
        for branch, info in index["branches"].items():
            sid = info.get("latest_session_id")
            if sid and sid in index["sessions"]:
                result[branch] = read_json(Path(index["sessions"][sid]["path"]), default={})
        return result

    def compare_branches(self):
        latest_by_branch = self.collect_branch_latest()
        branches = sorted(latest_by_branch.keys())
        comparisons = []
        if len(branches) >= 2:
            for i in range(len(branches)):
                for j in range(i + 1, len(branches)):
                    left = latest_by_branch[branches[i]]
                    right = latest_by_branch[branches[j]]
                    same_route = left.get("chosen_route") == right.get("chosen_route")
                    same_task = left.get("task_type") == right.get("task_type")
                    confidence_gap = round(abs(left.get("route_confidence", 0) - right.get("route_confidence", 0)), 3)
                    health_gap = round(abs(left.get("health_score", 0) - right.get("health_score", 0)), 3)
                    deferred_gap = abs(left.get("deferred_item_count", 0) - right.get("deferred_item_count", 0))
                    module_overlap = len(set(left.get("active_modules", [])) & set(right.get("active_modules", [])))
                    comparisons.append({
                        "left_branch": branches[i],
                        "right_branch": branches[j],
                        "left_session_id": left.get("session_id"),
                        "right_session_id": right.get("session_id"),
                        "same_route": same_route,
                        "same_task": same_task,
                        "confidence_gap": confidence_gap,
                        "health_gap": health_gap,
                        "deferred_gap": deferred_gap,
                        "module_overlap": module_overlap,
                    })

        data = {
            "project_id": self.project_id,
            "generated_at": now_iso(),
            "branch_latest_sessions": {
                k: {
                    "session_id": v.get("session_id"),
                    "task_type": v.get("task_type"),
                    "chosen_route": v.get("chosen_route"),
                    "route_confidence": v.get("route_confidence"),
                    "health_score": v.get("health_score"),
                    "deferred_item_count": v.get("deferred_item_count"),
                } for k, v in latest_by_branch.items()
            },
            "comparisons": comparisons,
        }
        write_json(self.branch_compare_file, data)
        return data

    def branch_verdicts(self):
        compare = read_json(self.branch_compare_file, default={"comparisons": []})
        lines = ["# Branch Verdicts v2.8", ""]
        plain = ["Branch Verdicts v2.8", ""]
        if not compare["comparisons"]:
            msg = "Only one branch is present, so no branch-to-branch verdict is available yet."
            lines.append(msg)
            plain.append(msg)
        else:
            for item in compare["comparisons"]:
                if item["same_route"] and item["confidence_gap"] <= 0.1 and item["health_gap"] <= 0.1:
                    verdict = "merge-friendly"
                    reason = "same route, close confidence, close health"
                elif item["same_task"] and item["confidence_gap"] <= 0.25:
                    verdict = "keep-under-review"
                    reason = "same task but meaningful divergence remains"
                else:
                    verdict = "keep-separated"
                    reason = "different task/route profile"
                line = (
                    f"- {item['left_branch']} vs {item['right_branch']}: "
                    f"**{verdict}** — {reason}; "
                    f"confidence_gap={item['confidence_gap']}, health_gap={item['health_gap']}, "
                    f"deferred_gap={item['deferred_gap']}, module_overlap={item['module_overlap']}"
                )
                lines.append(line)
                plain.append(line.replace("**", ""))

        write_text(self.branch_verdict_md_file, "\n".join(lines) + "\n")
        write_text(self.branch_verdict_txt_file, "\n".join(plain) + "\n")
        return {"md": str(self.branch_verdict_md_file), "txt": str(self.branch_verdict_txt_file)}

    def build_zip(self):
        ensure_dir(self.pack_root)
        with zipfile.ZipFile(self.zip_export_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.project_dir):
                for name in files:
                    p = Path(root) / name
                    zf.write(p, p.relative_to(self.pack_root))
        return self.zip_export_file

    def build_upload_reports(self):
        compact = read_json(self.compact_handoff_file, default={})
        txt_lines = [
            f"Project: {compact.get('project_id')}",
            f"Session count: {compact.get('session_count')}",
            f"Integrity ok: {compact.get('integrity_ok')}",
            f"Problem count: {compact.get('problem_count')}",
        ]
        latest = compact.get("latest_session") or {}
        if latest:
            txt_lines.extend([
                f"Latest session: {latest.get('session_id')}",
                f"Branch: {latest.get('branch')}",
                f"Task type: {latest.get('task_type')}",
                f"Route: {latest.get('chosen_route')}",
                f"Confidence: {latest.get('route_confidence')}",
                f"Health: {latest.get('health_score')}",
                f"Deferred: {latest.get('deferred_item_count')}",
            ])
        txt_lines.extend([
            "",
            "V2.8 features:",
            "- merge intelligence",
            "- compare modes",
            "- branch verdicts",
        ])
        report_txt = self.project_dir / "report_v2.8.txt"
        report_md = self.project_dir / "report_v2.8.md"
        write_text(report_txt, "\n".join(txt_lines) + "\n")
        write_text(report_md, "# Report v2.8\n\n" + "\n".join(f"- {line}" for line in txt_lines if line.strip()) + "\n")
        return report_txt, report_md

    def build_all_reports(self):
        self.integrity_check()
        self.build_manifest()
        self.build_quick_report()
        self.build_compact_handoff()
        self.build_quick_resume_pack()
        self.build_summary_pack()
        self.build_archive_summary()
        self.compare_branches()
        self.branch_verdicts()
        self.build_upload_reports()
        self.build_zip()

    def print_summary(self, session, root_created):
        print("=== MORPH Runtime Core v2.8 / Summary ===")
        print(f"Project:        {self.project_id}")
        print(f"Root created:   {root_created}")
        print(f"Root session:   session_001")
        print(f"Saved session:  {session['session_id']}")
        print(f"Branch used:    {session['branch']}")
        print(f"Task type:      {session['task_type']}")
        print(f"Chosen route:   {session['chosen_route']}")
        print(f"Session file:   {self.session_path(session['session_id'])}")
        print(f"Manifest file:  {self.project_manifest_file}")
        print(f"Quick report:   {self.quick_report_file}")
        print(f"Compare file:   {self.branch_compare_file}")
        print(f"Verdict txt:    {self.branch_verdict_txt_file}")
        print(f"ZIP export:     {self.zip_export_file}")
        print()
        print("=== Status Snapshot ===")
        print(json.dumps({
            "session_id": session["session_id"],
            "parent": session["parent"],
            "branch": session["branch"],
            "task_type": session["task_type"],
            "chosen_route": session["chosen_route"],
            "verification_armed": session["verification_armed"],
            "route_confidence": session["route_confidence"],
            "deferred_item_count": session["deferred_item_count"],
            "health_score": session["health_score"],
            "saved_at": session["saved_at"],
        }, indent=2))

    def cli(self):
        parser = argparse.ArgumentParser(description="MORPH Runtime Core v2.8")
        parser.add_argument("--fresh-if-missing", action="store_true", help="Create root session if missing.")
        parser.add_argument("--append-task", choices=["math", "simple"], help="Append a task/session.")
        parser.add_argument("--resume-session", help="Resume from a specific session id.")
        parser.add_argument("--branch", default="main", help="Branch label to use.")
        parser.add_argument("--report-only", action="store_true", help="Only rebuild reports.")
        args = parser.parse_args()

        if args.report_only:
            self.init_pack()
            self.build_all_reports()
            print("Reports rebuilt.")
            print(self.quick_report_file)
            print(self.branch_compare_file)
            print(self.branch_verdict_txt_file)
            return

        if args.fresh_if_missing or args.append_task:
            task_type = args.append_task or "math"
            session, root_created = self.append_task(
                task_type=task_type,
                branch_label=args.branch,
                resume_session=args.resume_session
            )
            self.print_summary(session, root_created)
            return

        parser.print_help()


def main():
    base_dir = Path.cwd()
    MorphRuntimeCoreV28(base_dir).cli()


if __name__ == "__main__":
    main()
