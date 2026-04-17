#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile, os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

VERSION = "v4.2"
PACK_ROOT_NAME = "morph_runtime_core_v4_2"
DEFAULT_PROJECT_ID = "project_math_lab"
ALLOWED_STATUS = ["active", "stable", "experimental", "paused", "broken"]

MODULES_BY_TASK = {
    "math": ["RuntimeKernel","RuntimeStateManager","RuntimeIndexManager","ContinuityPackManager","SessionStateAdapter",
             "RecoveryEngine","AutoRepairBasic","OrphanHandler","ComparativeResumeEngine","HandoffExporter",
             "QuickResumePack","SummaryPackBuilder","PackValidator","IntegrityGuard","FabricOrchestratorV42",
             "RegressionDetector","AnomalyDetector","TrendDetector","SmartResumeEngine","NextBestActionEngine",
             "StatusRegistry","MilestoneManager","StablePromotionEngine","ReleasePackBuilder","HandoffPackBuilder",
             "ExportPackBuilder","ProjectDigestBuilder"],
    "simple": ["RuntimeKernel","RuntimeStateManager","RuntimeIndexManager","ContinuityPackManager","SessionStateAdapter",
               "RecoveryEngine","AutoRepairBasic","OrphanHandler","ComparativeResumeEngine","HandoffExporter",
               "QuickResumePack","SummaryPackBuilder","PackValidator","IntegrityGuard","FabricOrchestratorV42",
               "RegressionDetector","AnomalyDetector","TrendDetector","SmartResumeEngine","NextBestActionEngine",
               "StatusRegistry","MilestoneManager","StablePromotionEngine","ReleasePackBuilder","HandoffPackBuilder",
               "ExportPackBuilder","ProjectDigestBuilder"],
}

TASK_DEFAULTS = {
    "math": {"chosen_route": "math_deep_verify","verification_armed": True,"route_confidence": 1.0,
             "deferred_item_count": 1,"health_score": 0.9,
             "hot_memory_ids": ["math_simulator","beal_method","morph_v05"],
             "warm_memory_ids": ["flux_programming","morph_v07","activation_pack"],
             "cold_memory_ids": ["long_context_notes"],
             "last_schedule": {"immediate_queue": ["route_commit"],"short_queue": ["core_claim_pass"],
                               "medium_queue": ["structural_consistency_pass"],"deep_queue": ["proof_pressure_pass","route_deepening"]}},
    "simple": {"chosen_route": "default_contextual","verification_armed": False,"route_confidence": 0.53,
               "deferred_item_count": 0,"health_score": 0.8,
               "hot_memory_ids": ["long_context_notes","morph_v05","math_simulator"],
               "warm_memory_ids": ["flux_programming","morph_v07","beal_method"],
               "cold_memory_ids": ["activation_pack"],
               "last_schedule": {"immediate_queue": [],"short_queue": [],"medium_queue": [],"deep_queue": []}},
}

DEFAULT_BUDGET = {
    "max_depth": 3,"verification_threshold": 2,"max_hot_items": 3,"max_warm_items": 3,
    "force_cold_tail": True,"max_candidate_routes": 3,"max_residue_bundles_per_task": 5,
    "max_deferred_items_per_task": 12,"deferred_trigger_on_medium_normal": True,"deferred_trigger_on_deep_normal": True,
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

def read_json(path: Path, default=None):
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding="utf-8"))

def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def slugify(value: str):
    out = []
    for ch in value.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s or "item"

class MorphRuntimeCoreV42:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pack_root = self.base_dir / PACK_ROOT_NAME
        self.project_id = DEFAULT_PROJECT_ID
        self.project_dir = self.pack_root / self.project_id
        self.sessions_dir = self.project_dir / "sessions"
        self.checkpoints_dir = self.project_dir / "checkpoints"
        self.runtime_index_file = self.project_dir / "runtime_index.json"
        self.integrity_report_file = self.project_dir / "integrity_report.json"
        self.report_txt = self.project_dir / "report_v4.2.txt"
        self.report_md = self.project_dir / "report_v4.2.md"
        self.resume_txt = self.project_dir / "smart_resume_v4_2.txt"
        self.resume_json = self.project_dir / "smart_resume_v4_2.json"
        self.resume_md = self.project_dir / "smart_resume_v4_2.md"
        self.next_action_txt = self.project_dir / "next_best_action_v4_2.txt"
        self.next_action_json = self.project_dir / "next_best_action_v4_2.json"
        self.next_action_md = self.project_dir / "next_best_action_v4_2.md"
        self.status_txt = self.project_dir / "status_registry_v4_2.txt"
        self.status_json = self.project_dir / "status_registry_v4_2.json"
        self.milestone_txt = self.project_dir / "milestones_v4_2.txt"
        self.milestone_json = self.project_dir / "milestones_v4_2.json"
        self.stable_txt = self.project_dir / "stable_registry_v4_2.txt"
        self.stable_json = self.project_dir / "stable_registry_v4_2.json"
        self.release_txt = self.project_dir / "release_summary_v4_2.txt"
        self.release_json = self.project_dir / "release_summary_v4_2.json"
        self.checkpoint_registry_txt = self.project_dir / "checkpoint_registry_v4_2.txt"
        self.checkpoint_registry_json = self.project_dir / "checkpoint_registry_v4_2.json"
        self.best_checkpoint_txt = self.project_dir / "best_checkpoint_v4_2.txt"
        self.best_checkpoint_json = self.project_dir / "best_checkpoint_v4_2.json"
        self.leaderboard_txt = self.project_dir / "checkpoint_leaderboard_v4_2.txt"
        self.leaderboard_json = self.project_dir / "checkpoint_leaderboard_v4_2.json"
        self.regression_txt = self.project_dir / "regression_report_v4_2.txt"
        self.regression_json = self.project_dir / "regression_report_v4_2.json"
        self.anomaly_txt = self.project_dir / "anomaly_report_v4_2.txt"
        self.anomaly_json = self.project_dir / "anomaly_report_v4_2.json"
        self.trend_txt = self.project_dir / "trend_report_v4_2.txt"
        self.trend_json = self.project_dir / "trend_report_v4_2.json"
        self.release_pack_txt = self.project_dir / "release_pack_v4_2.txt"
        self.release_pack_json = self.project_dir / "release_pack_v4_2.json"
        self.release_pack_md = self.project_dir / "release_pack_v4_2.md"
        self.handoff_pack_txt = self.project_dir / "handoff_pack_v4_2.txt"
        self.handoff_pack_json = self.project_dir / "handoff_pack_v4_2.json"
        self.handoff_pack_md = self.project_dir / "handoff_pack_v4_2.md"
        self.export_pack_txt = self.project_dir / "export_pack_v4_2.txt"
        self.export_pack_json = self.project_dir / "export_pack_v4_2.json"
        self.export_pack_md = self.project_dir / "export_pack_v4_2.md"
        self.project_digest_txt = self.project_dir / "project_digest_v4_2.txt"
        self.project_digest_json = self.project_dir / "project_digest_v4_2.json"
        self.project_digest_md = self.project_dir / "project_digest_v4_2.md"
        self.zip_export_file = self.pack_root / f"{self.project_id}.zip"

    def ensure_dirs(self):
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def init_pack(self):
        self.ensure_dirs()
        if not self.runtime_index_file.exists():
            write_json(self.runtime_index_file, {
                "project_id": self.project_id,"created_at": now_iso(),"current_session_id": None,
                "sessions": {},"branches": {},"checkpoints": {},"branch_status": {},"session_status": {},
                "milestones": [],"stable_registry": [],"audit_tail": [],
            })

    def load_index(self):
        self.init_pack()
        idx = read_json(self.runtime_index_file, default={})
        for k, v in [("branch_status", {}), ("session_status", {}), ("milestones", []), ("stable_registry", []),
                     ("checkpoints", {}), ("branches", {}), ("sessions", {}), ("audit_tail", [])]:
            idx.setdefault(k, deepcopy(v))
        return idx

    def save_index(self, index):
        write_json(self.runtime_index_file, index)

    def session_path(self, session_id: str):
        return self.sessions_dir / f"{session_id}.json"

    def checkpoint_path(self, label: str):
        return self.checkpoints_dir / f"{slugify(label)}.json"

    def audit(self, index, event_type, session_id, branch_label, route_name, outcome, details):
        index["audit_tail"].append({
            "timestamp": now_iso(),"event_type": event_type,"project_id": self.project_id,
            "session_id": session_id,"branch_label": branch_label,"route_name": route_name,
            "outcome": outcome,"details": details
        })
        index["audit_tail"] = index["audit_tail"][-40:]

    def next_session_id(self, index, branch_label):
        branch_sessions = [sid for sid, meta in index["sessions"].items() if meta["branch"] == branch_label]
        n = len(branch_sessions) + 1
        return f"session_{n:03d}" if branch_label == "main" else f"session_{n:03d}_{slugify(branch_label)}"

    def build_session(self, session_id, parent_id, branch_label, task_type):
        d = deepcopy(TASK_DEFAULTS[task_type])
        return {
            "project_id": self.project_id,"session_id": session_id,"parent": parent_id,"branch": branch_label,
            "task_type": task_type,"chosen_route": d["chosen_route"],"verification_armed": d["verification_armed"],
            "route_confidence": d["route_confidence"],"deferred_item_count": d["deferred_item_count"],
            "health_score": d["health_score"],"active_modules": MODULES_BY_TASK[task_type],
            "hot_memory_ids": d["hot_memory_ids"],"warm_memory_ids": d["warm_memory_ids"],
            "cold_memory_ids": d["cold_memory_ids"],"last_schedule": d["last_schedule"],
            "budget": deepcopy(DEFAULT_BUDGET),"saved_at": now_iso()
        }

    def latest_session(self):
        index = self.load_index()
        sid = index.get("current_session_id")
        if not sid or sid not in index["sessions"]:
            return None
        return read_json(Path(index["sessions"][sid]["path"]), default=None)

    def append_task(self, task_type="math", branch_label="main", resume_session=None):
        index = self.load_index()
        root_created = False
        if not index["sessions"]:
            root_created = True
            root = self.build_session("session_001", None, "main", "math")
            write_json(self.session_path("session_001"), root)
            index["sessions"]["session_001"] = {"path": str(self.session_path("session_001")),"parent": None,"branch": "main","task_type": "math","chosen_route": root["chosen_route"],"health_score": root["health_score"],"saved_at": root["saved_at"]}
            index["branches"]["main"] = {"root_session_id": "session_001","latest_session_id": "session_001","session_ids": ["session_001"]}
            index["current_session_id"] = "session_001"
            index["branch_status"]["main"] = "active"
            index["session_status"]["session_001"] = "active"
            self.audit(index, "save_session", "session_001", "main", root["chosen_route"], "saved", {"path": str(self.session_path("session_001"))})
        if resume_session is None and task_type == "math" and branch_label == "main" and root_created:
            self.save_index(index)
            self.build_all_reports()
            return root, True
        parent_id = resume_session or index["branches"].get(branch_label, {}).get("latest_session_id")
        session_id = self.next_session_id(index, branch_label)
        session = self.build_session(session_id, parent_id, branch_label, task_type)
        write_json(self.session_path(session_id), session)
        index["sessions"][session_id] = {"path": str(self.session_path(session_id)),"parent": parent_id,"branch": branch_label,"task_type": task_type,"chosen_route": session["chosen_route"],"health_score": session["health_score"],"saved_at": session["saved_at"]}
        branch = index["branches"].setdefault(branch_label, {"root_session_id": session_id,"latest_session_id": session_id,"session_ids": []})
        if not branch["session_ids"]:
            branch["root_session_id"] = session_id
        branch["latest_session_id"] = session_id
        branch["session_ids"].append(session_id)
        index["current_session_id"] = session_id
        index["branch_status"].setdefault(branch_label, "active")
        index["session_status"][session_id] = "active"
        self.audit(index, "save_session", session_id, branch_label, session["chosen_route"], "saved", {"path": str(self.session_path(session_id))})
        self.save_index(index)
        self.build_all_reports()
        return session, root_created

    def create_checkpoint(self, label: str):
        index = self.load_index()
        latest = self.latest_session()
        payload = {"label": label,"created_at": now_iso(),"project_id": self.project_id,"latest_session": latest}
        cp_path = self.checkpoint_path(label)
        write_json(cp_path, payload)
        index["checkpoints"][slugify(label)] = {"label": label, "path": str(cp_path), "created_at": payload["created_at"]}
        self.audit(index, "checkpoint_saved", latest.get("session_id") if latest else None, latest.get("branch") if latest else None, latest.get("chosen_route") if latest else None, "saved", {"label": label, "path": str(cp_path)})
        self.save_index(index)
        self.build_all_reports()
        return cp_path

    def set_branch_status(self, branch: str, status: str):
        if status not in ALLOWED_STATUS:
            raise ValueError(f"invalid status: {status}")
        index = self.load_index()
        index["branch_status"][branch] = status
        self.audit(index, "branch_status_set", None, branch, None, status, {})
        self.save_index(index)
        self.build_all_reports()

    def set_session_status(self, session_id: str, status: str):
        if status not in ALLOWED_STATUS:
            raise ValueError(f"invalid status: {status}")
        index = self.load_index()
        index["session_status"][session_id] = status
        meta = index["sessions"].get(session_id, {})
        self.audit(index, "session_status_set", session_id, meta.get("branch"), meta.get("chosen_route"), status, {})
        self.save_index(index)
        self.build_all_reports()

    def add_milestone(self, label: str, note=None):
        index = self.load_index()
        latest = self.latest_session()
        item = {"label": label,"note": note,"created_at": now_iso(),"session_id": latest.get("session_id") if latest else None,"branch": latest.get("branch") if latest else None,"route": latest.get("chosen_route") if latest else None}
        index["milestones"].append(item)
        self.audit(index, "milestone_added", item["session_id"], item["branch"], item["route"], "added", {"label": label, "note": note})
        self.save_index(index)
        self.build_all_reports()

    def promote_stable(self, target_type: str, target_value: str, note=None):
        index = self.load_index()
        item = {"target_type": target_type, "target_value": target_value, "note": note, "promoted_at": now_iso()}
        index["stable_registry"].append(item)
        if target_type == "branch":
            index["branch_status"][target_value] = "stable"
        elif target_type == "session":
            index["session_status"][target_value] = "stable"
        self.audit(index, "promote_stable", target_value if target_type == "session" else None, target_value if target_type == "branch" else None, None, "stable", {"target_type": target_type, "note": note})
        self.save_index(index)
        self.build_all_reports()

    def build_integrity(self):
        index = self.load_index()
        problems = []
        for sid, meta in index["sessions"].items():
            if not Path(meta["path"]).exists():
                problems.append({"session_id": sid, "problem": "missing_file"})
        report = {"checked_at": now_iso(), "ok": len(problems) == 0, "problem_count": len(problems), "problems": problems}
        write_json(self.integrity_report_file, report)
        return report

    def build_checkpoint_registry(self):
        index = self.load_index()
        items = sorted(index["checkpoints"].items(), key=lambda x: x[1]["created_at"])
        rows = []
        for _, meta in items:
            cp = read_json(Path(meta["path"]), default={})
            s = cp.get("latest_session") or {}
            rows.append({"label": meta["label"],"created_at": meta["created_at"],"session_id": s.get("session_id"),"branch": s.get("branch"),"task_type": s.get("task_type"),"route": s.get("chosen_route"),"confidence": s.get("route_confidence"),"health": s.get("health_score"),"deferred": s.get("deferred_item_count")})
        payload = {"version": VERSION, "project_id": self.project_id, "checkpoint_count": len(rows), "checkpoints": rows}
        write_json(self.checkpoint_registry_json, payload)
        lines = [f"Checkpoint Registry {VERSION}", f"Project: {self.project_id}", f"Checkpoint count: {len(rows)}", ""]
        for r in rows:
            lines.append(f"- {r['label']} | session={r['session_id']} | branch={r['branch']} | task={r['task_type']} | route={r['route']} | conf={r['confidence']} | health={r['health']} | deferred={r['deferred']}")
        write_text(self.checkpoint_registry_txt, "\n".join(lines) + "\n")
        return payload

    def _checkpoint_score(self, entry):
        return round((float(entry.get("health") or 0) * 100) + (float(entry.get("confidence") or 0) * 50) - (int(entry.get("deferred") or 0) * 10), 3)

    def build_best_checkpoint(self):
        registry = read_json(self.checkpoint_registry_json, default={"checkpoints": []})
        rows = []
        for e in registry.get("checkpoints", []):
            x = dict(e); x["score"] = self._checkpoint_score(x); rows.append(x)
        best = max(rows, key=lambda x: x["score"]) if rows else None
        payload = {"version": VERSION, "project_id": self.project_id, "best_checkpoint": best}
        write_json(self.best_checkpoint_json, payload)
        if not best:
            txt = f"Best Checkpoint {VERSION}\nProject: {self.project_id}\nNo checkpoints available.\n"
        else:
            txt = "\n".join([f"Best Checkpoint {VERSION}",f"Project: {self.project_id}",f"Label: {best['label']}",f"Session: {best['session_id']}",f"Branch: {best['branch']}",f"Task: {best['task_type']}",f"Route: {best['route']}",f"Confidence: {best['confidence']}",f"Health: {best['health']}",f"Deferred: {best['deferred']}",f"Score: {best['score']}"]) + "\n"
        write_text(self.best_checkpoint_txt, txt)
        return payload

    def build_leaderboard(self):
        registry = read_json(self.checkpoint_registry_json, default={"checkpoints": []})
        rows = []
        for e in registry.get("checkpoints", []):
            x = dict(e); x["score"] = self._checkpoint_score(x); rows.append(x)
        rows.sort(key=lambda x: x["score"], reverse=True)
        payload = {"version": VERSION, "project_id": self.project_id, "leaderboard": rows}
        write_json(self.leaderboard_json, payload)
        lines = [f"Checkpoint Leaderboard {VERSION}", f"Project: {self.project_id}", ""]
        for i, r in enumerate(rows, start=1):
            lines.append(f"{i}. {r['label']} | score={r['score']} | branch={r['branch']} | task={r['task_type']} | route={r['route']}")
        write_text(self.leaderboard_txt, "\n".join(lines) + "\n")
        return payload

    def build_regression(self):
        index = self.load_index()
        findings = []
        for branch, info in index["branches"].items():
            sids = info.get("session_ids", [])
            if len(sids) < 2:
                findings.append({"branch": branch, "verdict": "insufficient_history"})
                continue
            first = read_json(Path(index["sessions"][sids[0]]["path"]), default={})
            last = read_json(Path(index["sessions"][sids[-1]]["path"]), default={})
            health_delta = round(float(last.get("health_score", 0) or 0) - float(first.get("health_score", 0) or 0), 3)
            conf_delta = round(float(last.get("route_confidence", 0) or 0) - float(first.get("route_confidence", 0) or 0), 3)
            deferred_delta = int(last.get("deferred_item_count", 0) or 0) - int(first.get("deferred_item_count", 0) or 0)
            verdict = "regression-risk" if health_delta < 0 or conf_delta < 0 or deferred_delta > 0 else "no-regression"
            findings.append({"branch": branch,"health_delta": health_delta,"confidence_delta": conf_delta,"deferred_delta": deferred_delta,"verdict": verdict})
        payload = {"version": VERSION, "project_id": self.project_id, "findings": findings}
        write_json(self.regression_json, payload)
        lines = [f"Regression Report {VERSION}", f"Project: {self.project_id}", ""]
        for f in findings:
            if f["verdict"] == "insufficient_history":
                lines.append(f"- {f['branch']} | verdict=insufficient_history")
            else:
                lines.append(f"- {f['branch']} | health_delta={f['health_delta']} | confidence_delta={f['confidence_delta']} | deferred_delta={f['deferred_delta']} | verdict={f['verdict']}")
        write_text(self.regression_txt, "\n".join(lines) + "\n")
        return payload

    def build_anomaly(self):
        index = self.load_index()
        anomalies = []
        for sid, meta in index["sessions"].items():
            s = read_json(Path(meta["path"]), default={})
            reasons = []
            if float(s.get("health_score", 0) or 0) < 0.5:
                reasons.append("low_health")
            if float(s.get("route_confidence", 0) or 0) < 0.4:
                reasons.append("low_confidence")
            if int(s.get("deferred_item_count", 0) or 0) >= 3:
                reasons.append("high_deferred")
            if reasons:
                anomalies.append({"session_id": sid, "branch": s.get("branch"), "reasons": reasons})
        payload = {"version": VERSION, "project_id": self.project_id, "anomaly_count": len(anomalies), "anomalies": anomalies}
        write_json(self.anomaly_json, payload)
        lines = [f"Anomaly Report {VERSION}", f"Project: {self.project_id}", f"Anomaly count: {len(anomalies)}", ""]
        for a in anomalies:
            lines.append(f"- {a['session_id']} | branch={a['branch']} | reasons={','.join(a['reasons'])}")
        write_text(self.anomaly_txt, "\n".join(lines) + "\n")
        return payload

    def build_trend(self):
        index = self.load_index()
        trends = []
        for branch, info in index["branches"].items():
            sids = info.get("session_ids", [])
            if len(sids) < 2:
                trends.append({"branch": branch, "trend": "flat", "reason": "insufficient_history"})
                continue
            first = read_json(Path(index["sessions"][sids[0]]["path"]), default={})
            last = read_json(Path(index["sessions"][sids[-1]]["path"]), default={})
            health_delta = round(float(last.get("health_score", 0) or 0) - float(first.get("health_score", 0) or 0), 3)
            conf_delta = round(float(last.get("route_confidence", 0) or 0) - float(first.get("route_confidence", 0) or 0), 3)
            deferred_delta = int(last.get("deferred_item_count", 0) or 0) - int(first.get("deferred_item_count", 0) or 0)
            if health_delta > 0 and conf_delta >= 0 and deferred_delta <= 0:
                trend = "improving"
            elif health_delta < 0 or conf_delta < 0 or deferred_delta > 0:
                trend = "declining"
            else:
                trend = "stable"
            trends.append({"branch": branch, "trend": trend})
        payload = {"version": VERSION, "project_id": self.project_id, "trends": trends}
        write_json(self.trend_json, payload)
        lines = [f"Trend Report {VERSION}", f"Project: {self.project_id}", ""]
        for t in trends:
            lines.append(f"- {t['branch']} | trend={t['trend']}")
        write_text(self.trend_txt, "\n".join(lines) + "\n")
        return payload

    def build_smart_resume(self):
        index = self.load_index()
        best_checkpoint = read_json(self.best_checkpoint_json, default={"best_checkpoint": None}).get("best_checkpoint")
        trends = {t["branch"]: t.get("trend") for t in read_json(self.trend_json, default={"trends": []}).get("trends", [])}
        regressions = {r["branch"]: r.get("verdict") for r in read_json(self.regression_json, default={"findings": []}).get("findings", [])}
        anomaly_counts = {}
        for a in read_json(self.anomaly_json, default={"anomalies": []}).get("anomalies", []):
            anomaly_counts[a["branch"]] = anomaly_counts.get(a["branch"], 0) + 1
        priorities = []
        for branch, info in index["branches"].items():
            sid = info.get("latest_session_id")
            s = read_json(Path(index["sessions"][sid]["path"]), default={}) if sid in index["sessions"] else {}
            score = round(float(s.get("health_score", 0) or 0) * 100 + float(s.get("route_confidence", 0) or 0) * 50 - int(s.get("deferred_item_count", 0) or 0) * 10 - anomaly_counts.get(branch, 0) * 15 - (25 if regressions.get(branch) == "regression-risk" else 0) + (10 if trends.get(branch) == "improving" else 0), 3)
            priorities.append({"branch": branch, "session_id": sid, "task_type": s.get("task_type"), "route": s.get("chosen_route"), "resume_score": score})
        priorities.sort(key=lambda x: x["resume_score"], reverse=True)
        rec = priorities[0] if priorities else None
        recommendation_type = "best_checkpoint" if best_checkpoint else "latest_session"
        recommendation_value = best_checkpoint.get("label") if best_checkpoint else (rec.get("session_id") if rec else None)
        cmd = None
        if rec:
            if rec["branch"] == "main":
                cmd = f"python morph_runtime_core_v4_2.py --append-task {rec['task_type']} --resume-session {rec['session_id']}"
            else:
                cmd = f"python morph_runtime_core_v4_2.py --append-task {rec['task_type']} --resume-session {rec['session_id']} --branch {rec['branch']}"
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"recommendation_type": recommendation_type,"recommendation_value": recommendation_value,"recommended_branch": rec.get("branch") if rec else None,"recommended_session_id": rec.get("session_id") if rec else None,"recommended_score": rec.get("resume_score") if rec else None,"best_checkpoint_label": best_checkpoint.get("label") if best_checkpoint else None,"resume_command": cmd,"branch_priority": priorities}
        write_json(self.resume_json, payload)
        lines = [f"Smart Resume {VERSION}",f"Project: {self.project_id}",f"Recommendation type: {payload['recommendation_type']}",f"Recommendation value: {payload['recommendation_value']}",f"Recommended branch: {payload['recommended_branch']}",f"Recommended session: {payload['recommended_session_id']}",f"Recommended score: {payload['recommended_score']}",f"Best checkpoint label: {payload['best_checkpoint_label']}",f"Resume command: {payload['resume_command']}","","Branch priority:"]
        for p in priorities:
            lines.append(f"- {p['branch']} | session={p['session_id']} | task={p['task_type']} | route={p['route']} | score={p['resume_score']}")
        write_text(self.resume_txt, "\n".join(lines) + "\n")
        write_text(self.resume_md, "# Smart Resume v4.2\n\n" + "\n".join(f"- {ln}" for ln in lines if ln.strip()) + "\n")
        return payload

    def build_next_best_action(self):
        resume = read_json(self.resume_json, default={})
        anomalies = read_json(self.anomaly_json, default={"anomaly_count": 0}).get("anomaly_count", 0)
        regressions = read_json(self.regression_json, default={"findings": []}).get("findings", [])
        actions = []
        if anomalies:
            actions.append({"priority": 1,"action": "investigate_anomalies","reason": f"{anomalies} anomaly items detected","suggested_command": "python morph_runtime_core_v4_2.py --report-only"})
        if any(r.get("verdict") == "regression-risk" for r in regressions):
            actions.append({"priority": 2,"action": "review_regression_risk","reason": "one or more branches show regression risk","suggested_command": "python morph_runtime_core_v4_2.py --report-only"})
        if resume.get("resume_command"):
            actions.append({"priority": 3 if actions else 1,"action": "resume_recommended_branch","reason": "best available continuation path","suggested_command": resume.get("resume_command")})
        if not actions:
            actions.append({"priority": 1,"action": "create_stable_checkpoint","reason": "system is stable and no issues were detected","suggested_command": "python morph_runtime_core_v4_2.py --checkpoint-label stable_v4_2"})
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"recommended_action": actions[0],"actions": actions}
        write_json(self.next_action_json, payload)
        lines = [f"Next Best Action {VERSION}",f"Project: {self.project_id}",f"Recommended action: {actions[0]['action']}",f"Reason: {actions[0]['reason']}",f"Suggested command: {actions[0]['suggested_command']}","","Action queue:"]
        for a in actions:
            lines.append(f"- p{a['priority']} | {a['action']} | reason={a['reason']} | cmd={a['suggested_command']}")
        write_text(self.next_action_txt, "\n".join(lines) + "\n")
        return payload

    def build_status_registry(self):
        index = self.load_index()
        branch_rows = [{"branch": branch, "status": index["branch_status"].get(branch, "active"), "latest_session_id": info.get("latest_session_id")} for branch, info in index["branches"].items()]
        session_rows = [{"session_id": sid, "branch": meta.get("branch"), "status": index["session_status"].get(sid, "active")} for sid, meta in index["sessions"].items()]
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"branch_status": branch_rows,"session_status": session_rows}
        write_json(self.status_json, payload)
        lines = [f"Status Registry {VERSION}", f"Project: {self.project_id}", "", "Branch status:"]
        for r in branch_rows:
            lines.append(f"- {r['branch']} | status={r['status']} | latest={r['latest_session_id']}")
        lines.extend(["", "Session status:"])
        for r in session_rows:
            lines.append(f"- {r['session_id']} | branch={r['branch']} | status={r['status']}")
        write_text(self.status_txt, "\n".join(lines) + "\n")
        return payload

    def build_milestones(self):
        index = self.load_index()
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"milestone_count": len(index["milestones"]),"milestones": index["milestones"]}
        write_json(self.milestone_json, payload)
        lines = [f"Milestones {VERSION}", f"Project: {self.project_id}", f"Milestone count: {len(index['milestones'])}", ""]
        for m in index["milestones"]:
            lines.append(f"- {m['label']} | session={m['session_id']} | branch={m['branch']} | route={m['route']} | note={m['note']} | created_at={m['created_at']}")
        write_text(self.milestone_txt, "\n".join(lines) + "\n")
        return payload

    def build_stable_registry(self):
        index = self.load_index()
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"stable_count": len(index["stable_registry"]),"stable_registry": index["stable_registry"]}
        write_json(self.stable_json, payload)
        lines = [f"Stable Registry {VERSION}", f"Project: {self.project_id}", f"Stable count: {len(index['stable_registry'])}", ""]
        for s in index["stable_registry"]:
            lines.append(f"- {s['target_type']} | target={s['target_value']} | note={s['note']} | promoted_at={s['promoted_at']}")
        write_text(self.stable_txt, "\n".join(lines) + "\n")
        return payload

    def build_release(self):
        integrity = read_json(self.integrity_report_file, default={"ok": False, "problem_count": 999})
        resume = read_json(self.resume_json, default={})
        action = read_json(self.next_action_json, default={})
        status = read_json(self.status_json, default={})
        milestones = read_json(self.milestone_json, default={})
        stable = read_json(self.stable_json, default={})
        latest = self.latest_session()
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"latest_session_id": latest.get("session_id") if latest else None,"integrity_ok": integrity.get("ok"),"problem_count": integrity.get("problem_count"),"resume_recommendation": resume.get("recommendation_value"),"next_action": (action.get("recommended_action") or {}).get("action"),"branch_status_count": len(status.get("branch_status", [])),"session_status_count": len(status.get("session_status", [])),"milestone_count": milestones.get("milestone_count", 0),"stable_count": stable.get("stable_count", 0)}
        write_json(self.release_json, payload)
        lines = [f"Release Summary {VERSION}",f"Project: {self.project_id}",f"Latest session: {payload['latest_session_id']}",f"Integrity ok: {payload['integrity_ok']} ({payload['problem_count']})",f"Resume recommendation: {payload['resume_recommendation']}",f"Next action: {payload['next_action']}",f"Branch status count: {payload['branch_status_count']}",f"Session status count: {payload['session_status_count']}",f"Milestone count: {payload['milestone_count']}",f"Stable count: {payload['stable_count']}","","Report TXT: report_v4.2.txt","Smart Resume TXT: smart_resume_v4_2.txt","Next Best Action TXT: next_best_action_v4_2.txt","Status Registry TXT: status_registry_v4_2.txt","Milestones TXT: milestones_v4_2.txt","Stable Registry TXT: stable_registry_v4_2.txt"]
        write_text(self.release_txt, "\n".join(lines) + "\n")
        return payload

    def build_release_pack(self):
        release = read_json(self.release_json, default={})
        resume = read_json(self.resume_json, default={})
        action = read_json(self.next_action_json, default={})
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"release_summary": release,"resume_recommendation": resume.get("recommendation_value"),"resume_command": resume.get("resume_command"),"next_action": action.get("recommended_action")}
        write_json(self.release_pack_json, payload)
        lines = [f"Release Pack {VERSION}",f"Project: {self.project_id}",f"Latest session: {release.get('latest_session_id')}",f"Integrity ok: {release.get('integrity_ok')} ({release.get('problem_count')})",f"Resume recommendation: {resume.get('recommendation_value')}",f"Resume command: {resume.get('resume_command')}",f"Next action: {(action.get('recommended_action') or {}).get('action')}"]
        write_text(self.release_pack_txt, "\n".join(lines) + "\n")
        write_text(self.release_pack_md, "# Release Pack v4.2\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
        return payload

    def build_handoff_pack(self):
        latest = self.latest_session() or {}
        resume = read_json(self.resume_json, default={})
        milestones = read_json(self.milestone_json, default={})
        stable = read_json(self.stable_json, default={})
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"latest_session_id": latest.get("session_id"),"latest_branch": latest.get("branch"),"latest_route": latest.get("chosen_route"),"resume_command": resume.get("resume_command"),"milestone_count": milestones.get("milestone_count", 0),"stable_count": stable.get("stable_count", 0)}
        write_json(self.handoff_pack_json, payload)
        lines = [f"Handoff Pack {VERSION}",f"Project: {self.project_id}",f"Latest session: {payload['latest_session_id']}",f"Latest branch: {payload['latest_branch']}",f"Latest route: {payload['latest_route']}",f"Resume command: {payload['resume_command']}",f"Milestone count: {payload['milestone_count']}",f"Stable count: {payload['stable_count']}"]
        write_text(self.handoff_pack_txt, "\n".join(lines) + "\n")
        write_text(self.handoff_pack_md, "# Handoff Pack v4.2\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
        return payload

    def build_export_pack(self):
        files = [self.report_txt.name, self.resume_txt.name, self.next_action_txt.name, self.status_txt.name, self.milestone_txt.name, self.stable_txt.name, self.release_pack_txt.name, self.handoff_pack_txt.name, self.project_digest_txt.name]
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "export_files": files, "zip_file": self.zip_export_file.name}
        write_json(self.export_pack_json, payload)
        lines = [f"Export Pack {VERSION}", f"Project: {self.project_id}", f"ZIP: {self.zip_export_file.name}", "", "Files:"]
        for f in files:
            lines.append(f"- {f}")
        write_text(self.export_pack_txt, "\n".join(lines) + "\n")
        write_text(self.export_pack_md, "# Export Pack v4.2\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
        return payload

    def build_project_digest(self):
        release = read_json(self.release_json, default={})
        resume = read_json(self.resume_json, default={})
        action = read_json(self.next_action_json, default={})
        best = read_json(self.best_checkpoint_json, default={}).get("best_checkpoint") or {}
        payload = {"version": VERSION,"project_id": self.project_id,"generated_at": now_iso(),"latest_session_id": release.get("latest_session_id"),"resume_recommendation": resume.get("recommendation_value"),"resume_command": resume.get("resume_command"),"next_action": (action.get("recommended_action") or {}).get("action"),"best_checkpoint": best.get("label"),"checkpoint_count": read_json(self.checkpoint_registry_json, default={"checkpoint_count": 0}).get("checkpoint_count", 0),"milestone_count": read_json(self.milestone_json, default={"milestone_count": 0}).get("milestone_count", 0),"stable_count": read_json(self.stable_json, default={"stable_count": 0}).get("stable_count", 0)}
        write_json(self.project_digest_json, payload)
        lines = [f"Project Digest {VERSION}",f"Project: {self.project_id}",f"Latest session: {payload['latest_session_id']}",f"Best checkpoint: {payload['best_checkpoint']}",f"Resume recommendation: {payload['resume_recommendation']}",f"Resume command: {payload['resume_command']}",f"Next action: {payload['next_action']}",f"Checkpoint count: {payload['checkpoint_count']}",f"Milestone count: {payload['milestone_count']}",f"Stable count: {payload['stable_count']}"]
        write_text(self.project_digest_txt, "\n".join(lines) + "\n")
        write_text(self.project_digest_md, "# Project Digest v4.2\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
        return payload

    def build_upload_reports(self):
        latest = self.latest_session() or {}
        txt_lines = [f"Project: {self.project_id}",f"Latest session: {latest.get('session_id')}",f"Branch: {latest.get('branch')}",f"Task type: {latest.get('task_type')}",f"Route: {latest.get('chosen_route')}",f"Confidence: {latest.get('route_confidence')}",f"Health: {latest.get('health_score')}",f"Deferred: {latest.get('deferred_item_count')}","","V4.2 features:","- release pack","- handoff pack","- export pack","- project digest"]
        write_text(self.report_txt, "\n".join(txt_lines) + "\n")
        write_text(self.report_md, "# Report v4.2\n\n" + "\n".join(f"- {line}" for line in txt_lines if line.strip()) + "\n")

    def build_zip(self):
        self.pack_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_export_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.project_dir):
                for name in files:
                    p = Path(root) / name
                    zf.write(p, p.relative_to(self.pack_root))

    def build_all_reports(self):
        self.build_integrity()
        self.build_checkpoint_registry()
        self.build_best_checkpoint()
        self.build_leaderboard()
        self.build_regression()
        self.build_anomaly()
        self.build_trend()
        self.build_smart_resume()
        self.build_next_best_action()
        self.build_status_registry()
        self.build_milestones()
        self.build_stable_registry()
        self.build_release()
        self.build_release_pack()
        self.build_handoff_pack()
        self.build_project_digest()
        self.build_upload_reports()
        self.build_zip()
        self.build_export_pack()

    def print_summary(self, session, root_created):
        print("=== MORPH Runtime Core v4.2 / Summary ===")
        print(f"Project:        {self.project_id}")
        print(f"Root created:   {root_created}")
        print("Root session:   session_001")
        print(f"Saved session:  {session['session_id']}")
        print(f"Branch used:    {session['branch']}")
        print(f"Task type:      {session['task_type']}")
        print(f"Chosen route:   {session['chosen_route']}")
        print(f"Session file:   {self.session_path(session['session_id'])}")
        print(f"Report txt:     {self.report_txt}")
        print(f"Release pack:   {self.release_pack_txt}")
        print(f"Handoff pack:   {self.handoff_pack_txt}")
        print(f"Digest txt:     {self.project_digest_txt}")
        print(f"ZIP export:     {self.zip_export_file}")

    def cli(self):
        parser = argparse.ArgumentParser(description="MORPH Runtime Core v4.2")
        parser.add_argument("--fresh-if-missing", action="store_true")
        parser.add_argument("--append-task", choices=["math", "simple"])
        parser.add_argument("--resume-session")
        parser.add_argument("--branch", default="main")
        parser.add_argument("--report-only", action="store_true")
        parser.add_argument("--checkpoint-label")
        parser.add_argument("--smart-resume-only", action="store_true")
        parser.add_argument("--next-action-only", action="store_true")
        parser.add_argument("--set-branch-status")
        parser.add_argument("--set-session-status")
        parser.add_argument("--status")
        parser.add_argument("--add-milestone")
        parser.add_argument("--note")
        parser.add_argument("--promote-stable-branch")
        parser.add_argument("--promote-stable-session")
        parser.add_argument("--release-pack-only", action="store_true")
        parser.add_argument("--handoff-pack-only", action="store_true")
        parser.add_argument("--export-pack-only", action="store_true")
        parser.add_argument("--project-digest-only", action="store_true")
        args = parser.parse_args()

        if args.report_only:
            self.init_pack(); self.build_all_reports()
            print("Reports rebuilt.")
            print(self.report_txt); print(self.release_pack_txt); print(self.handoff_pack_txt); print(self.export_pack_txt); print(self.project_digest_txt)
            return
        if args.smart_resume_only:
            self.init_pack(); self.build_all_reports(); print(self.resume_txt); print(self.resume_json); return
        if args.next_action_only:
            self.init_pack(); self.build_all_reports(); print(self.next_action_txt); print(self.next_action_json); return
        if args.release_pack_only:
            self.init_pack(); self.build_all_reports(); print(self.release_pack_txt); print(self.release_pack_json); return
        if args.handoff_pack_only:
            self.init_pack(); self.build_all_reports(); print(self.handoff_pack_txt); print(self.handoff_pack_json); return
        if args.export_pack_only:
            self.init_pack(); self.build_all_reports(); print(self.export_pack_txt); print(self.export_pack_json); return
        if args.project_digest_only:
            self.init_pack(); self.build_all_reports(); print(self.project_digest_txt); print(self.project_digest_json); return
        if args.set_branch_status and args.status:
            self.init_pack(); self.set_branch_status(args.set_branch_status, args.status); print(self.status_txt); return
        if args.set_session_status and args.status:
            self.init_pack(); self.set_session_status(args.set_session_status, args.status); print(self.status_txt); return
        if args.add_milestone:
            self.init_pack(); self.add_milestone(args.add_milestone, args.note); print(self.milestone_txt); return
        if args.promote_stable_branch:
            self.init_pack(); self.promote_stable("branch", args.promote_stable_branch, args.note); print(self.stable_txt); print(self.status_txt); return
        if args.promote_stable_session:
            self.init_pack(); self.promote_stable("session", args.promote_stable_session, args.note); print(self.stable_txt); print(self.status_txt); return
        if args.checkpoint_label:
            self.init_pack(); cp = self.create_checkpoint(args.checkpoint_label); print(f"Checkpoint saved: {cp}"); print(self.report_txt); return
        if args.fresh_if_missing or args.append_task:
            task_type = args.append_task or "math"
            session, root_created = self.append_task(task_type=task_type, branch_label=args.branch, resume_session=args.resume_session)
            self.print_summary(session, root_created); return
        parser.print_help()

def main():
    MorphRuntimeCoreV42(Path.cwd()).cli()

if __name__ == "__main__":
    main()
