#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile, os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

VERSION = "v5.0"
PACK_ROOT_NAME = "morph_runtime_core_v5_0"
DEFAULT_PROJECT_ID = "project_math_lab"

TASK_DEFAULTS = {
    "math": {"chosen_route": "math_deep_verify", "route_confidence": 1.0, "deferred_item_count": 1, "health_score": 0.9},
    "simple": {"chosen_route": "default_contextual", "route_confidence": 0.53, "deferred_item_count": 0, "health_score": 0.8},
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

def score_session(s: dict) -> float:
    return round(float(s.get("health_score", 0) or 0) * 100 + float(s.get("route_confidence", 0) or 0) * 50 - int(s.get("deferred_item_count", 0) or 0) * 10, 3)

class MorphRuntimeCoreV50:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pack_root = self.base_dir / PACK_ROOT_NAME
        self.project_id = DEFAULT_PROJECT_ID
        self.project_dir = self.pack_root / self.project_id
        self.sessions_dir = self.project_dir / "sessions"
        self.runtime_index_file = self.project_dir / "runtime_index.json"
        self.report_txt = self.project_dir / "report_v5.0.txt"
        self.confirm_gate_txt = self.project_dir / "confirm_gate_v5_0.txt"
        self.confirm_gate_json = self.project_dir / "confirm_gate_v5_0.json"
        self.guarded_switch_txt = self.project_dir / "guarded_switch_pipeline_v5_0.txt"
        self.guarded_switch_json = self.project_dir / "guarded_switch_pipeline_v5_0.json"
        self.accept_reject_txt = self.project_dir / "accept_reject_path_v5_0.txt"
        self.accept_reject_json = self.project_dir / "accept_reject_path_v5_0.json"
        self.zip_export_file = self.pack_root / f"{self.project_id}.zip"

    def ensure_dirs(self):
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def init_pack(self):
        self.ensure_dirs()
        if not self.runtime_index_file.exists():
            write_json(self.runtime_index_file, {
                "project_id": self.project_id,
                "created_at": now_iso(),
                "current_session_id": None,
                "sessions": {},
                "branches": {},
                "switch_confirmation": {
                    "required": False,
                    "status": "pending",
                    "recommended_target": None,
                    "recommended_type": None,
                    "last_updated": None,
                },
            })

    def load_index(self):
        self.init_pack()
        idx = read_json(self.runtime_index_file, default={})
        idx.setdefault("sessions", {})
        idx.setdefault("branches", {})
        idx.setdefault("switch_confirmation", {
            "required": False,
            "status": "pending",
            "recommended_target": None,
            "recommended_type": None,
            "last_updated": None,
        })
        return idx

    def save_index(self, index):
        write_json(self.runtime_index_file, index)

    def session_path(self, session_id: str):
        return self.sessions_dir / f"{session_id}.json"

    def next_session_id(self, index, branch_label):
        branch_sessions = [sid for sid, meta in index["sessions"].items() if meta["branch"] == branch_label]
        n = len(branch_sessions) + 1
        return f"session_{n:03d}" if branch_label == "main" else f"session_{n:03d}_{slugify(branch_label)}"

    def build_session(self, session_id, parent_id, branch_label, task_type):
        d = deepcopy(TASK_DEFAULTS[task_type])
        return {"project_id": self.project_id, "session_id": session_id, "parent": parent_id, "branch": branch_label, "task_type": task_type, "chosen_route": d["chosen_route"], "route_confidence": d["route_confidence"], "deferred_item_count": d["deferred_item_count"], "health_score": d["health_score"], "saved_at": now_iso()}

    def append_task(self, task_type="math", branch_label="main", resume_session=None):
        index = self.load_index()
        root_created = False
        if not index["sessions"]:
            root_created = True
            root = self.build_session("session_001", None, "main", "math")
            write_json(self.session_path("session_001"), root)
            index["sessions"]["session_001"] = {"path": str(self.session_path("session_001")), "parent": None, "branch": "main", "task_type": "math", "chosen_route": root["chosen_route"], "saved_at": root["saved_at"]}
            index["branches"]["main"] = {"root_session_id": "session_001", "latest_session_id": "session_001", "session_ids": ["session_001"]}
            index["current_session_id"] = "session_001"
        if resume_session is None and task_type == "math" and branch_label == "main" and root_created:
            self.save_index(index)
            self.build_all_reports()
            return root, True
        parent_id = resume_session or index["branches"].get(branch_label, {}).get("latest_session_id")
        session_id = self.next_session_id(index, branch_label)
        session = self.build_session(session_id, parent_id, branch_label, task_type)
        write_json(self.session_path(session_id), session)
        index["sessions"][session_id] = {"path": str(self.session_path(session_id)), "parent": parent_id, "branch": branch_label, "task_type": task_type, "chosen_route": session["chosen_route"], "saved_at": session["saved_at"]}
        branch = index["branches"].setdefault(branch_label, {"root_session_id": session_id, "latest_session_id": session_id, "session_ids": []})
        if not branch["session_ids"]:
            branch["root_session_id"] = session_id
        branch["latest_session_id"] = session_id
        branch["session_ids"].append(session_id)
        index["current_session_id"] = session_id
        self.save_index(index)
        self.build_all_reports()
        return session, root_created

    def all_sessions(self):
        index = self.load_index()
        rows = []
        for sid, meta in index["sessions"].items():
            s = read_json(Path(meta["path"]), default={})
            if s:
                s["score"] = score_session(s)
                rows.append(s)
        rows.sort(key=lambda x: (x.get("saved_at") or "", x.get("session_id") or ""))
        return rows

    def best_targets(self):
        sessions = self.all_sessions()
        historical = max(sessions, key=lambda x: x["score"]) if sessions else None
        current = None
        index = self.load_index()
        cid = index.get("current_session_id")
        if cid and cid in index["sessions"]:
            current = read_json(Path(index["sessions"][cid]["path"]), default={})
            if current:
                current["score"] = score_session(current)
        recent_pool = sessions[-3:] if len(sessions) >= 3 else sessions
        recent = max(recent_pool, key=lambda x: x["score"]) if recent_pool else None
        return historical, current, recent

    def switch_recommendation(self):
        historical, current, recent = self.best_targets()
        recommendation = "stay_current"
        target_type = "current"
        target_value = current.get("session_id") if current else None
        reason = "current target is the best available active option"
        hist_gap = round(float(historical.get("score", 0)) - float(current.get("score", 0)), 3) if historical and current else None
        recent_gap = round(float(recent.get("score", 0)) - float(current.get("score", 0)), 3) if recent and current else None
        if historical and current and hist_gap is not None and hist_gap >= 15:
            recommendation = "switch_to_historical"
            target_type = "historical"
            target_value = historical.get("session_id")
            reason = "historical target is materially stronger than current target"
        elif recent and current and recent_gap is not None and recent_gap >= 10:
            recommendation = "switch_to_recent"
            target_type = "recent"
            target_value = recent.get("session_id")
            reason = "recent target is stronger than current target"
        return {"recommendation": recommendation, "target_type": target_type, "target_value": target_value, "reason": reason, "historical": historical, "current": current, "recent": recent}

    def recovery_command_for(self, session_id):
        index = self.load_index()
        meta = index.get("sessions", {}).get(session_id)
        if not meta:
            return None
        s = read_json(Path(meta["path"]), default={})
        branch = s.get("branch")
        task = s.get("task_type")
        if branch == "main":
            return f"python morph_runtime_core_v5_0.py --append-task {task} --resume-session {session_id}"
        return f"python morph_runtime_core_v5_0.py --append-task {task} --resume-session {session_id} --branch {branch}"

    def build_confirm_gate(self):
        index = self.load_index()
        sw = self.switch_recommendation()
        required = sw["recommendation"] in ("switch_to_historical", "switch_to_recent")
        gate = {"required": required, "status": "pending", "recommended_target": sw["target_value"], "recommended_type": sw["target_type"], "last_updated": now_iso()}
        gate.update({k: gate.get(k) for k in []})
        prev = index.get("switch_confirmation", {})
        if prev.get("recommended_target") == gate["recommended_target"] and prev.get("recommended_type") == gate["recommended_type"]:
            gate["status"] = prev.get("status", "pending")
        index["switch_confirmation"] = gate
        self.save_index(index)
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "confirm_gate": gate}
        write_json(self.confirm_gate_json, payload)
        lines = [f"Confirm Gate {VERSION}", f"Project: {self.project_id}", f"Required: {gate['required']}", f"Status: {gate['status']}", f"Recommended target: {gate['recommended_target']}", f"Recommended type: {gate['recommended_type']}"]
        write_text(self.confirm_gate_txt, "\n".join(lines) + "\n")
        return payload

    def build_guarded_switch_pipeline(self):
        gate = read_json(self.confirm_gate_json, default={}).get("confirm_gate", {})
        cmd = self.recovery_command_for(gate.get("recommended_target")) if gate.get("recommended_target") else None
        pipeline_mode = "direct_resume"
        next_step = "resume_now"
        if gate.get("required"):
            pipeline_mode = "guarded_switch_pipeline"
            if gate.get("status") == "accepted":
                next_step = "resume_recommended_target"
            elif gate.get("status") == "rejected":
                next_step = "stay_on_current_target"
            else:
                next_step = "await_user_confirmation"
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "pipeline_mode": pipeline_mode, "next_step": next_step, "resume_command": cmd}
        write_json(self.guarded_switch_json, payload)
        lines = [f"Guarded Switch Pipeline {VERSION}", f"Project: {self.project_id}", f"Pipeline mode: {pipeline_mode}", f"Next step: {next_step}", f"Resume command: {cmd}"]
        write_text(self.guarded_switch_txt, "\n".join(lines) + "\n")
        return payload

    def build_accept_reject_path(self):
        gate = read_json(self.confirm_gate_json, default={}).get("confirm_gate", {})
        sw = self.switch_recommendation()
        accept_command = self.recovery_command_for(gate.get("recommended_target")) if gate.get("recommended_target") else None
        current = sw["current"]
        reject_command = self.recovery_command_for(current.get("session_id")) if current else None
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "confirmation_required": gate.get("required"), "accept_path": {"action": "switch", "resume_command": accept_command}, "reject_path": {"action": "stay_current", "resume_command": reject_command}}
        write_json(self.accept_reject_json, payload)
        lines = [f"Accept Reject Path {VERSION}", f"Project: {self.project_id}", f"Confirmation required: {payload['confirmation_required']}", f"Accept action: switch", f"Accept command: {accept_command}", f"Reject action: stay_current", f"Reject command: {reject_command}"]
        write_text(self.accept_reject_txt, "\n".join(lines) + "\n")
        return payload

    def build_upload_reports(self):
        index = self.load_index()
        latest_id = index.get("current_session_id")
        latest = None
        if latest_id and latest_id in index["sessions"]:
            latest = read_json(Path(index["sessions"][latest_id]["path"]), default={})
        txt_lines = [f"Project: {self.project_id}", f"Latest session: {latest.get('session_id') if latest else None}", f"Branch: {latest.get('branch') if latest else None}", f"Task type: {latest.get('task_type') if latest else None}", f"Route: {latest.get('chosen_route') if latest else None}", "", "V5.0 features:", "- confirm gate", "- guarded switch pipeline", "- explicit accept/reject path", "- unified recovery control layer"]
        write_text(self.report_txt, "\n".join(txt_lines) + "\n")

    def build_zip(self):
        self.pack_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_export_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.project_dir):
                for name in files:
                    p = Path(root) / name
                    zf.write(p, p.relative_to(self.pack_root))

    def build_all_reports(self):
        self.build_confirm_gate()
        self.build_guarded_switch_pipeline()
        self.build_accept_reject_path()
        self.build_upload_reports()
        self.build_zip()

    def print_summary(self, session, root_created):
        print("=== MORPH Runtime Core v5.0 / Summary ===")
        print(f"Project:                {self.project_id}")
        print(f"Root created:           {root_created}")
        print(f"Saved session:          {session['session_id']}")
        print(f"Branch used:            {session['branch']}")
        print(f"Task type:              {session['task_type']}")
        print(f"Chosen route:           {session['chosen_route']}")
        print(f"Report txt:             {self.report_txt}")
        print(f"Confirm gate txt:       {self.confirm_gate_txt}")
        print(f"Guarded pipeline txt:   {self.guarded_switch_txt}")
        print(f"Accept reject txt:      {self.accept_reject_txt}")
        print(f"ZIP export:             {self.zip_export_file}")

    def cli(self):
        parser = argparse.ArgumentParser(description="MORPH Runtime Core v5.0")
        parser.add_argument("--fresh-if-missing", action="store_true")
        parser.add_argument("--append-task", choices=["math", "simple"])
        parser.add_argument("--resume-session")
        parser.add_argument("--branch", default="main")
        parser.add_argument("--report-only", action="store_true")
        parser.add_argument("--confirm-gate-only", action="store_true")
        parser.add_argument("--guarded-switch-only", action="store_true")
        parser.add_argument("--accept-reject-only", action="store_true")
        args = parser.parse_args()

        if args.report_only:
            self.init_pack()
            self.build_all_reports()
            print("Reports rebuilt.")
            print(self.report_txt)
            print(self.confirm_gate_txt)
            print(self.guarded_switch_txt)
            print(self.accept_reject_txt)
            return
        if args.confirm_gate_only:
            self.init_pack()
            self.build_all_reports()
            print(self.confirm_gate_txt)
            print(self.confirm_gate_json)
            return
        if args.guarded_switch_only:
            self.init_pack()
            self.build_all_reports()
            print(self.guarded_switch_txt)
            print(self.guarded_switch_json)
            return
        if args.accept_reject_only:
            self.init_pack()
            self.build_all_reports()
            print(self.accept_reject_txt)
            print(self.accept_reject_json)
            return
        if args.fresh_if_missing or args.append_task:
            task_type = args.append_task or "math"
            session, root_created = self.append_task(task_type=task_type, branch_label=args.branch, resume_session=args.resume_session)
            self.print_summary(session, root_created)
            return
        parser.print_help()

def main():
    MorphRuntimeCoreV50(Path.cwd()).cli()

if __name__ == "__main__":
    main()
