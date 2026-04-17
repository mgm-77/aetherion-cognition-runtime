#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile, os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

VERSION = "v4.3"
PACK_ROOT_NAME = "morph_runtime_core_v4_3"
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

class MorphRuntimeCoreV43:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pack_root = self.base_dir / PACK_ROOT_NAME
        self.project_id = DEFAULT_PROJECT_ID
        self.project_dir = self.pack_root / self.project_id
        self.sessions_dir = self.project_dir / "sessions"
        self.runtime_index_file = self.project_dir / "runtime_index.json"

        self.report_txt = self.project_dir / "report_v4.3.txt"
        self.report_md = self.project_dir / "report_v4.3.md"
        self.branch_compare_txt = self.project_dir / "branch_compare_pack_v4_3.txt"
        self.branch_compare_json = self.project_dir / "branch_compare_pack_v4_3.json"
        self.branch_compare_md = self.project_dir / "branch_compare_pack_v4_3.md"
        self.merge_txt = self.project_dir / "merge_recommendation_v4_3.txt"
        self.merge_json = self.project_dir / "merge_recommendation_v4_3.json"
        self.merge_md = self.project_dir / "merge_recommendation_v4_3.md"
        self.branch_ranking_txt = self.project_dir / "branch_ranking_v4_3.txt"
        self.branch_ranking_json = self.project_dir / "branch_ranking_v4_3.json"
        self.branch_ranking_md = self.project_dir / "branch_ranking_v4_3.md"
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
            })

    def load_index(self):
        self.init_pack()
        idx = read_json(self.runtime_index_file, default={})
        idx.setdefault("sessions", {})
        idx.setdefault("branches", {})
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

    def build_branch_compare(self):
        index = self.load_index()
        latest = {}
        for branch, info in index["branches"].items():
            sid = info.get("latest_session_id")
            if sid and sid in index["sessions"]:
                latest[branch] = read_json(Path(index["sessions"][sid]["path"]), default={})

        branches = sorted(latest.keys())
        comparisons = []
        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                a = latest[branches[i]]
                b = latest[branches[j]]
                comparisons.append({
                    "left_branch": branches[i],
                    "right_branch": branches[j],
                    "left_session": a.get("session_id"),
                    "right_session": b.get("session_id"),
                    "same_task": a.get("task_type") == b.get("task_type"),
                    "same_route": a.get("chosen_route") == b.get("chosen_route"),
                    "confidence_gap": round(abs(float(a.get("route_confidence", 0) or 0) - float(b.get("route_confidence", 0) or 0)), 3),
                    "health_gap": round(abs(float(a.get("health_score", 0) or 0) - float(b.get("health_score", 0) or 0)), 3),
                    "deferred_gap": abs(int(a.get("deferred_item_count", 0) or 0) - int(b.get("deferred_item_count", 0) or 0)),
                })
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "comparisons": comparisons}
        write_json(self.branch_compare_json, payload)
        lines = [f"Branch Compare Pack {VERSION}", f"Project: {self.project_id}", f"Comparison count: {len(comparisons)}", ""]
        for c in comparisons:
            lines.append(
                f"- {c['left_branch']} vs {c['right_branch']} | "
                f"left={c['left_session']} | right={c['right_session']} | "
                f"same_task={c['same_task']} | same_route={c['same_route']} | "
                f"confidence_gap={c['confidence_gap']} | health_gap={c['health_gap']} | deferred_gap={c['deferred_gap']}"
            )
        write_text(self.branch_compare_txt, "\n".join(lines) + "\n")
        write_text(self.branch_compare_md, "# Branch Compare Pack v4.3\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
        return payload

    def build_branch_ranking(self):
        index = self.load_index()
        rows = []
        for branch, info in index["branches"].items():
            sid = info.get("latest_session_id")
            if sid and sid in index["sessions"]:
                s = read_json(Path(index["sessions"][sid]["path"]), default={})
                score = round(float(s.get("health_score", 0) or 0) * 100 + float(s.get("route_confidence", 0) or 0) * 50 - int(s.get("deferred_item_count", 0) or 0) * 10, 3)
                rows.append({
                    "branch": branch,
                    "latest_session": sid,
                    "task_type": s.get("task_type"),
                    "route": s.get("chosen_route"),
                    "score": score,
                })
        rows.sort(key=lambda x: x["score"], reverse=True)
        payload = {"version": VERSION, "project_id": self.project_id, "generated_at": now_iso(), "ranking": rows}
        write_json(self.branch_ranking_json, payload)
        lines = [f"Branch Ranking {VERSION}", f"Project: {self.project_id}", ""]
        for i, r in enumerate(rows, start=1):
            lines.append(f"{i}. {r['branch']} | session={r['latest_session']} | task={r['task_type']} | route={r['route']} | score={r['score']}")
        write_text(self.branch_ranking_txt, "\n".join(lines) + "\n")
        write_text(self.branch_ranking_md, "# Branch Ranking v4.3\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
        return payload

    def build_merge_recommendation(self):
        compare = read_json(self.branch_compare_json, default={"comparisons": []}).get("comparisons", [])
        ranking = read_json(self.branch_ranking_json, default={"ranking": []}).get("ranking", [])
        recommendation = None
        if compare:
            best_pair = None
            best_score = None
            for c in compare:
                pair_score = c["confidence_gap"] + c["health_gap"] + c["deferred_gap"]
                if best_score is None or pair_score < best_score:
                    best_score = pair_score
                    best_pair = c
            if best_pair:
                if best_pair["same_route"] and best_pair["confidence_gap"] <= 0.2 and best_pair["health_gap"] <= 0.2:
                    verdict = "merge-friendly"
                elif best_pair["same_task"]:
                    verdict = "review-before-merge"
                else:
                    verdict = "keep-separated"
                recommendation = {
                    "left_branch": best_pair["left_branch"],
                    "right_branch": best_pair["right_branch"],
                    "verdict": verdict,
                    "pair_score": round(best_score, 3),
                }
        payload = {
            "version": VERSION,
            "project_id": self.project_id,
            "generated_at": now_iso(),
            "top_branch": ranking[0]["branch"] if ranking else None,
            "recommendation": recommendation,
        }
        write_json(self.merge_json, payload)
        lines = [f"Merge Recommendation {VERSION}", f"Project: {self.project_id}"]
        if recommendation:
            lines.extend([
                f"Top branch: {payload['top_branch']}",
                f"Left branch: {recommendation['left_branch']}",
                f"Right branch: {recommendation['right_branch']}",
                f"Verdict: {recommendation['verdict']}",
                f"Pair score: {recommendation['pair_score']}",
            ])
        else:
            lines.append("No merge recommendation available yet.")
        write_text(self.merge_txt, "\n".join(lines) + "\n")
        write_text(self.merge_md, "# Merge Recommendation v4.3\n\n" + "\n".join(f"- {x}" for x in lines) + "\n")
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
            "V4.3 features:",
            "- branch comparison pack",
            "- merge recommendation pack",
            "- branch ranking",
            "- priority order for work",
        ]
        write_text(self.report_txt, "\n".join(txt_lines) + "\n")
        write_text(self.report_md, "# Report v4.3\n\n" + "\n".join(f"- {x}" for x in txt_lines if x.strip()) + "\n")

    def build_zip(self):
        self.pack_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_export_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.project_dir):
                for name in files:
                    p = Path(root) / name
                    zf.write(p, p.relative_to(self.pack_root))

    def build_all_reports(self):
        self.build_branch_compare()
        self.build_branch_ranking()
        self.build_merge_recommendation()
        self.build_upload_reports()
        self.build_zip()

    def print_summary(self, session, root_created):
        print("=== MORPH Runtime Core v4.3 / Summary ===")
        print(f"Project:        {self.project_id}")
        print(f"Root created:   {root_created}")
        print(f"Saved session:  {session['session_id']}")
        print(f"Branch used:    {session['branch']}")
        print(f"Task type:      {session['task_type']}")
        print(f"Chosen route:   {session['chosen_route']}")
        print(f"Report txt:     {self.report_txt}")
        print(f"Branch compare: {self.branch_compare_txt}")
        print(f"Merge rec:      {self.merge_txt}")
        print(f"Branch ranking: {self.branch_ranking_txt}")
        print(f"ZIP export:     {self.zip_export_file}")

    def cli(self):
        parser = argparse.ArgumentParser(description="MORPH Runtime Core v4.3")
        parser.add_argument("--fresh-if-missing", action="store_true")
        parser.add_argument("--append-task", choices=["math", "simple"])
        parser.add_argument("--resume-session")
        parser.add_argument("--branch", default="main")
        parser.add_argument("--report-only", action="store_true")
        parser.add_argument("--branch-compare-only", action="store_true")
        parser.add_argument("--merge-recommendation-only", action="store_true")
        parser.add_argument("--branch-ranking-only", action="store_true")
        args = parser.parse_args()

        if args.report_only:
            self.init_pack()
            self.build_all_reports()
            print("Reports rebuilt.")
            print(self.report_txt)
            print(self.branch_compare_txt)
            print(self.merge_txt)
            print(self.branch_ranking_txt)
            return

        if args.branch_compare_only:
            self.init_pack()
            self.build_branch_compare()
            print(self.branch_compare_txt)
            print(self.branch_compare_json)
            return

        if args.merge_recommendation_only:
            self.init_pack()
            self.build_branch_compare()
            self.build_branch_ranking()
            self.build_merge_recommendation()
            print(self.merge_txt)
            print(self.merge_json)
            return

        if args.branch_ranking_only:
            self.init_pack()
            self.build_branch_ranking()
            print(self.branch_ranking_txt)
            print(self.branch_ranking_json)
            return

        if args.fresh_if_missing or args.append_task:
            task_type = args.append_task or "math"
            session, root_created = self.append_task(task_type=task_type, branch_label=args.branch, resume_session=args.resume_session)
            self.print_summary(session, root_created)
            return

        parser.print_help()

def main():
    MorphRuntimeCoreV43(Path.cwd()).cli()

if __name__ == "__main__":
    main()
