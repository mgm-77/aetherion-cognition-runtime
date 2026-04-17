#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile, os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

VERSION = "v4.7"
PACK_ROOT_NAME = "morph_runtime_core_v4_7"
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
    return round(
        float(s.get("health_score", 0) or 0) * 100
        + float(s.get("route_confidence", 0) or 0) * 50
        - int(s.get("deferred_item_count", 0) or 0) * 10,
        3,
    )

class MorphRuntimeCoreV47:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pack_root = self.base_dir / PACK_ROOT_NAME
        self.project_id = DEFAULT_PROJECT_ID
        self.project_dir = self.pack_root / self.project_id
        self.sessions_dir = self.project_dir / "sessions"
        self.runtime_index_file = self.project_dir / "runtime_index.json"
        self.report_txt = self.project_dir / "report_v4.7.txt"
        self.report_md = self.project_dir / "report_v4.7.md"
        self.historical_txt = self.project_dir / "historical_target_v4_7.txt"
        self.historical_json = self.project_dir / "historical_target_v4_7.json"
        self.current_txt = self.project_dir / "current_target_v4_7.txt"
        self.current_json = self.project_dir / "current_target_v4_7.json"
        self.recent_txt = self.project_dir / "recent_target_v4_7.txt"
        self.recent_json = self.project_dir / "recent_target_v4_7.json"
        self.conflict_txt = self.project_dir / "target_conflict_v4_7.txt"
        self.conflict_json = self.project_dir / "target_conflict_v4_7.json"
        self.switch_txt = self.project_dir / "target_switch_v4_7.txt"
        self.switch_json = self.project_dir / "target_switch_v4_7.json"
        self.switch_md = self.project_dir / "target_switch_v4_7.md"
        self.lock_txt = self.project_dir / "target_lock_v4_7.txt"
        self.lock_json = self.project_dir / "target_lock_v4_7.json"
        self.protection_txt = self.project_dir / "target_protection_v4_7.txt"
        self.protection_json = self.project_dir / "target_protection_v4_7.json"
        self.drift_alert_txt = self.project_dir / "target_drift_alert_v4_7.txt"
        self.drift_alert_json = self.project_dir / "target_drift_alert_v4_7.json"
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
                "target_lock": None,
                "target_protection": {"enabled": False, "protected_target": None, "protected_since": None},
            })

    def load_index(self):
        self.init_pack()
        idx = read_json(self.runtime_index_file, default={})
        idx.setdefault("sessions", {})
        idx.setdefault("branches", {})
        idx.setdefault("target_lock", None)
        idx.setdefault("target_protection", {"enabled": False, "protected_target": None, "protected_since": None})
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
        return {
            "project_id": self.project_id,
            "session_id": session_id,
            "parent": parent_id,
            "branch": branch_label,
            "task_type": task_type,
            "chosen_route": d["chosen_route"],
            "route_confidence": d["route_confidence"],
            "deferred_item_count": d["deferred_item_count"],
            "health_score": d["health_score"],
            "saved_at": now_iso(),
        }

    def append_task(self, task_type="math", branch_label="main", resume_session=None):
        index = self.load_index()
        root_created = False
        if not index["sessions"]:
            root_created = True
            root = self.build_session("session_001", None, "main", "math")
            write_json(self.session_path("session_001"), root)
            index["sessions"]["session_001"] = {
                "path": str(self.session_path("session_001")),
                "parent": None,
                "branch": "main",
                "task_type": "math",
                "chosen_route": root["chosen_route"],
                "saved_at": root["saved_at"],
            }
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
        index["sessions"][session_id] = {
            "path": str(self.session_path(session_id)),
            "parent": parent_id,
            "branch": branch_label,
            "task_type": task_type,
            "chosen_route": session["chosen_route"],
            "saved_at": session["saved_at"],
        }
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

    def build_historical_target(self):
        sessions = self.all_sessions()
        best = max(sessions, key=lambda x: x["score"]) if sessions else None
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "historical_target": best}
        write_json(self.historical_json, payload)
        lines = [f"Historical Target {VERSION}", f"Project: {self.project_id}"]
        if best:
            lines += [f"Session: {best['session_id']}", f"Branch: {best['branch']}", f"Task: {best['task_type']}", f"Route: {best['chosen_route']}", f"Score: {best['score']}"]
        else:
            lines.append("No historical target available yet.")
        write_text(self.historical_txt, "\n".join(lines) + "\n")
        return payload

    def build_current_target(self):
        index = self.load_index()
        current_id = index.get("current_session_id")
        current = None
        if current_id and current_id in index["sessions"]:
            current = read_json(Path(index["sessions"][current_id]["path"]), default={})
            if current:
                current["score"] = score_session(current)
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "current_target": current}
        write_json(self.current_json, payload)
        lines = [f"Current Target {VERSION}", f"Project: {self.project_id}"]
        if current:
            lines += [f"Session: {current['session_id']}", f"Branch: {current['branch']}", f"Task: {current['task_type']}", f"Route: {current['chosen_route']}", f"Score: {current['score']}"]
        else:
            lines.append("No current target available yet.")
        write_text(self.current_txt, "\n".join(lines) + "\n")
        return payload

    def build_recent_target(self):
        sessions = self.all_sessions()
        recent = sessions[-3:] if len(sessions) >= 3 else sessions
        best = max(recent, key=lambda x: x["score"]) if recent else None
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "recent_pool_size": len(recent), "recent_target": best}
        write_json(self.recent_json, payload)
        lines = [f"Recent Target {VERSION}", f"Project: {self.project_id}", f"Recent pool size: {len(recent)}"]
        if best:
            lines += [f"Session: {best['session_id']}", f"Branch: {best['branch']}", f"Task: {best['task_type']}", f"Route: {best['chosen_route']}", f"Score: {best['score']}"]
        else:
            lines.append("No recent target available yet.")
        write_text(self.recent_txt, "\n".join(lines) + "\n")
        return payload

    def build_conflict_detector(self):
        historical = read_json(self.historical_json, default={}).get("historical_target")
        current = read_json(self.current_json, default={}).get("current_target")
        recent = read_json(self.recent_json, default={}).get("recent_target")
        same_hist_current = historical and current and historical.get("session_id") == current.get("session_id")
        same_recent_current = recent and current and recent.get("session_id") == current.get("session_id")
        score_gap_hist_current = None
        if historical and current:
            score_gap_hist_current = round(float(historical.get("score", 0)) - float(current.get("score", 0)), 3)
        score_gap_recent_current = None
        if recent and current:
            score_gap_recent_current = round(float(recent.get("score", 0)) - float(current.get("score", 0)), 3)
        conflict = False
        reasons = []
        if historical and current and not same_hist_current:
            conflict = True
            reasons.append("historical_differs_from_current")
        if recent and current and not same_recent_current:
            conflict = True
            reasons.append("recent_differs_from_current")
        payload = {
            "version": VERSION,
            "project_id": self.project_id,
            "generated_at": now_iso(),
            "conflict_detected": conflict,
            "same_historical_current": same_hist_current,
            "same_recent_current": same_recent_current,
            "score_gap_historical_current": score_gap_hist_current,
            "score_gap_recent_current": score_gap_recent_current,
            "reasons": reasons,
        }
        write_json(self.conflict_json, payload)
        lines = [
            f"Target Conflict {VERSION}",
            f"Project: {self.project_id}",
            f"Conflict detected: {payload['conflict_detected']}",
            f"Same historical/current: {payload['same_historical_current']}",
            f"Same recent/current: {payload['same_recent_current']}",
            f"Score gap historical/current: {payload['score_gap_historical_current']}",
            f"Score gap recent/current: {payload['score_gap_recent_current']}",
            f"Reasons: {','.join(payload['reasons']) if payload['reasons'] else 'none'}",
        ]
        write_text(self.conflict_txt, "\n".join(lines) + "\n")
        return payload

    def build_switch_recommendation(self):
        historical = read_json(self.historical_json, default={}).get("historical_target")
        current = read_json(self.current_json, default={}).get("current_target")
        recent = read_json(self.recent_json, default={}).get("recent_target")
        conflict = read_json(self.conflict_json, default={})
        recommendation = "stay_current"
        reason = "current target is the best available active option"
        target_type = "current"
        target_value = current.get("session_id") if current else None

        hist_gap = conflict.get("score_gap_historical_current")
        recent_gap = conflict.get("score_gap_recent_current")

        if historical and current and hist_gap is not None and hist_gap >= 15:
            recommendation = "switch_to_historical"
            reason = "historical target is materially stronger than current target"
            target_type = "historical"
            target_value = historical.get("session_id")
        elif recent and current and recent_gap is not None and recent_gap >= 10:
            recommendation = "switch_to_recent"
            reason = "recent target is stronger than current target"
            target_type = "recent"
            target_value = recent.get("session_id")
        elif current and historical and current.get("session_id") == historical.get("session_id"):
            recommendation = "stay_current"
            reason = "current target already matches historical best"
            target_type = "current"
            target_value = current.get("session_id")

        payload = {
            "version": VERSION,
            "project_id": self.project_id,
            "generated_at": now_iso(),
            "recommendation": recommendation,
            "reason": reason,
            "target_type": target_type,
            "target_value": target_value,
        }
        write_json(self.switch_json, payload)
        lines = [
            f"Target Switch {VERSION}",
            f"Project: {self.project_id}",
            f"Recommendation: {recommendation}",
            f"Reason: {reason}",
            f"Target type: {target_type}",
            f"Target value: {target_value}",
        ]
        write_text(self.switch_txt, "\n".join(lines) + "\n")
        write_text(self.switch_md, "# Target Switch v4.6\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
        return payload

    def set_target_lock(self, target_type: str, target_value: str):
        index = self.load_index()
        index["target_lock"] = {
            "locked": True,
            "target_type": target_type,
            "target_value": target_value,
            "locked_at": now_iso(),
        }
        self.save_index(index)
        self.build_all_reports()

    def set_target_protection(self, target_type: str, target_value: str):
        index = self.load_index()
        index["target_protection"] = {
            "enabled": True,
            "protected_target": {"target_type": target_type, "target_value": target_value},
            "protected_since": now_iso(),
        }
        self.save_index(index)
        self.build_all_reports()

    def build_target_lock(self):
        index = self.load_index()
        lock = index.get("target_lock")
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "target_lock": lock}
        write_json(self.lock_json, payload)
        lines = [f"Target Lock {VERSION}", f"Project: {self.project_id}"]
        if lock and lock.get("locked"):
            lines += [
                f"Locked: True",
                f"Target type: {lock.get('target_type')}",
                f"Target value: {lock.get('target_value')}",
                f"Locked at: {lock.get('locked_at')}",
            ]
        else:
            lines.append("Locked: False")
        write_text(self.lock_txt, "\n".join(lines) + "\n")
        return payload

    def build_target_protection(self):
        index = self.load_index()
        protection = index.get("target_protection", {})
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "target_protection": protection}
        write_json(self.protection_json, payload)
        lines = [f"Target Protection {VERSION}", f"Project: {self.project_id}"]
        if protection.get("enabled"):
            tgt = protection.get("protected_target") or {}
            lines += [
                "Protection enabled: True",
                f"Target type: {tgt.get('target_type')}",
                f"Target value: {tgt.get('target_value')}",
                f"Protected since: {protection.get('protected_since')}",
            ]
        else:
            lines.append("Protection enabled: False")
        write_text(self.protection_txt, "\n".join(lines) + "\n")
        return payload

    def build_drift_alert(self):
        lock = read_json(self.lock_json, default={}).get("target_lock")
        current = read_json(self.current_json, default={}).get("current_target")
        switch = read_json(self.switch_json, default={})
        alert = False
        reasons = []
        if lock and lock.get("locked") and current and lock.get("target_value") != current.get("session_id"):
            alert = True
            reasons.append("current_differs_from_locked_target")
        if switch.get("recommendation") in ("switch_to_historical", "switch_to_recent"):
            alert = True
            reasons.append("switch_recommended")
        payload = {
            "version": VERSION,
            "project_id": self.project_id,
            "generated_at": now_iso(),
            "drift_alert": alert,
            "reasons": reasons,
            "current_session": current.get("session_id") if current else None,
            "locked_target": lock.get("target_value") if lock else None,
            "switch_recommendation": switch.get("recommendation"),
        }
        write_json(self.drift_alert_json, payload)
        lines = [
            f"Target Drift Alert {VERSION}",
            f"Project: {self.project_id}",
            f"Drift alert: {payload['drift_alert']}",
            f"Current session: {payload['current_session']}",
            f"Locked target: {payload['locked_target']}",
            f"Switch recommendation: {payload['switch_recommendation']}",
            f"Reasons: {','.join(reasons) if reasons else 'none'}",
        ]
        write_text(self.drift_alert_txt, "\n".join(lines) + "\n")
        return payload

    def build_upload_reports(self):
        index = self.load_index()
        latest_id = index.get("current_session_id")
        latest = None
        if latest_id and latest_id in index["sessions"]:
            latest = read_json(Path(index["sessions"][latest_id]["path"]), default={})
        txt_lines = [
            f"Project: {self.project_id}",
            f"Latest session: {latest.get('session_id') if latest else None}",
            f"Branch: {latest.get('branch') if latest else None}",
            f"Task type: {latest.get('task_type') if latest else None}",
            f"Route: {latest.get('chosen_route') if latest else None}",
            f"Confidence: {latest.get('route_confidence') if latest else None}",
            f"Health: {latest.get('health_score') if latest else None}",
            f"Deferred: {latest.get('deferred_item_count') if latest else None}",
            "",
            "V4.7 features:",
            "- target lock",
            "- target protection",
            "- target drift alerts",
            "- stability guard around best target",
        ]
        write_text(self.report_txt, "\n".join(txt_lines) + "\n")
        write_text(self.report_md, "# Report v4.7\n\n" + "\n".join(f"- {x}" for x in txt_lines if x.strip()) + "\n")

    def build_zip(self):
        self.pack_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_export_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.project_dir):
                for name in files:
                    p = Path(root) / name
                    zf.write(p, p.relative_to(self.pack_root))

    def build_all_reports(self):
        self.build_historical_target()
        self.build_current_target()
        self.build_recent_target()
        self.build_conflict_detector()
        self.build_switch_recommendation()
        self.build_target_lock()
        self.build_target_protection()
        self.build_drift_alert()
        self.build_upload_reports()
        self.build_zip()

    def print_summary(self, session, root_created):
        print("=== MORPH Runtime Core v4.7 / Summary ===")
        print(f"Project:          {self.project_id}")
        print(f"Root created:     {root_created}")
        print(f"Saved session:    {session['session_id']}")
        print(f"Branch used:      {session['branch']}")
        print(f"Task type:        {session['task_type']}")
        print(f"Chosen route:     {session['chosen_route']}")
        print(f"Report txt:       {self.report_txt}")
        print(f"Lock txt:         {self.lock_txt}")
        print(f"Protection txt:   {self.protection_txt}")
        print(f"Drift alert txt:  {self.drift_alert_txt}")
        print(f"ZIP export:       {self.zip_export_file}")

    def cli(self):
        parser = argparse.ArgumentParser(description="MORPH Runtime Core v4.7")
        parser.add_argument("--fresh-if-missing", action="store_true")
        parser.add_argument("--append-task", choices=["math", "simple"])
        parser.add_argument("--resume-session")
        parser.add_argument("--branch", default="main")
        parser.add_argument("--report-only", action="store_true")
        parser.add_argument("--target-lock-only", action="store_true")
        parser.add_argument("--target-protection-only", action="store_true")
        parser.add_argument("--target-drift-alert-only", action="store_true")
        parser.add_argument("--lock-target-type")
        parser.add_argument("--lock-target-value")
        parser.add_argument("--protect-target-type")
        parser.add_argument("--protect-target-value")
        args = parser.parse_args()

        if args.report_only:
            self.init_pack()
            self.build_all_reports()
            print("Reports rebuilt.")
            print(self.report_txt)
            print(self.lock_txt)
            print(self.protection_txt)
            print(self.drift_alert_txt)
            return

        if args.target_lock_only:
            self.init_pack()
            self.build_all_reports()
            print(self.lock_txt)
            print(self.lock_json)
            return

        if args.target_protection_only:
            self.init_pack()
            self.build_all_reports()
            print(self.protection_txt)
            print(self.protection_json)
            return

        if args.target_drift_alert_only:
            self.init_pack()
            self.build_all_reports()
            print(self.drift_alert_txt)
            print(self.drift_alert_json)
            return

        if args.lock_target_type and args.lock_target_value:
            self.init_pack()
            self.set_target_lock(args.lock_target_type, args.lock_target_value)
            print(self.lock_txt)
            return

        if args.protect_target_type and args.protect_target_value:
            self.init_pack()
            self.set_target_protection(args.protect_target_type, args.protect_target_value)
            print(self.protection_txt)
            return

        if args.fresh_if_missing or args.append_task:
            task_type = args.append_task or "math"
            session, root_created = self.append_task(task_type=task_type, branch_label=args.branch, resume_session=args.resume_session)
            self.print_summary(session, root_created)
            return

        parser.print_help()

def main():
    MorphRuntimeCoreV47(Path.cwd()).cli()

if __name__ == "__main__":
    main()
