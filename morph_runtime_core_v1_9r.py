#!/usr/bin/env python3
import argparse
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

VERSION = "v1.9r"
PACK_DIR = f"morph_runtime_core_{VERSION}"
DEFAULT_PROJECT = "project_math_lab"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@dataclass
class RuntimeSession:
    session_id: str
    parent: Optional[str]
    branch: str
    task_type: str
    chosen_route: str
    verification_armed: bool
    route_confidence: float
    deferred_item_count: int
    health_score: float
    saved_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RuntimeCore:
    def __init__(self, base_dir: Path, project_id: str):
        self.base_dir = base_dir
        self.project_id = project_id
        self.project_dir = base_dir / PACK_DIR / project_id
        self.sessions_dir = self.project_dir / "sessions"
        self.index_file = self.project_dir / "runtime_index.json"
        ensure_dir(self.sessions_dir)
        self.index = read_json(
            self.index_file,
            {
                "project_id": project_id,
                "version": VERSION,
                "root_session": None,
                "latest_by_branch": {},
                "session_counter": 0,
                "sessions": {},
            },
        )

    def save_index(self) -> None:
        write_json(self.index_file, self.index)

    def _next_session_id(self, branch: str) -> str:
        self.index["session_counter"] += 1
        counter = self.index["session_counter"]
        if branch == "main":
            return f"session_{counter:03d}"
        return f"session_{counter:03d}_{branch}"

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def load_session(self, session_id: str) -> RuntimeSession:
        data = read_json(self._session_path(session_id), None)
        if data is None:
            raise FileNotFoundError(f"Session not found: {session_id}")
        return RuntimeSession(**data)

    def _build_session(self, parent: Optional[RuntimeSession], branch: str, task_type: str) -> RuntimeSession:
        chosen_route = "math_deep_verify" if task_type == "math" else "default_contextual"
        verification_armed = task_type == "math"
        route_confidence = 1.0 if task_type == "math" else 0.53
        deferred_item_count = 1 if task_type == "math" else 0
        health_score = 0.9 if task_type == "math" else 0.8
        if parent and parent.task_type == task_type:
            route_confidence = parent.route_confidence
            health_score = parent.health_score
        return RuntimeSession(
            session_id=self._next_session_id(branch),
            parent=parent.session_id if parent else None,
            branch=branch,
            task_type=task_type,
            chosen_route=chosen_route,
            verification_armed=verification_armed,
            route_confidence=route_confidence,
            deferred_item_count=deferred_item_count,
            health_score=health_score,
            saved_at=now_iso(),
        )

    def create_root_if_missing(self) -> Optional[RuntimeSession]:
        if self.index.get("root_session"):
            return None
        root = self._build_session(parent=None, branch="main", task_type="math")
        self._save_session(root)
        self.index["root_session"] = root.session_id
        self.index["latest_by_branch"]["main"] = root.session_id
        self.save_index()
        return root

    def _save_session(self, session: RuntimeSession) -> None:
        write_json(self._session_path(session.session_id), session.to_dict())
        self.index["sessions"][session.session_id] = {
            "parent": session.parent,
            "branch": session.branch,
            "task_type": session.task_type,
            "saved_at": session.saved_at,
        }
        self.index["latest_by_branch"][session.branch] = session.session_id

    def append_task(self, task_type: str, resume_session: Optional[str], branch: Optional[str]) -> RuntimeSession:
        parent = None
        target_branch = branch or "main"
        if resume_session:
            parent = self.load_session(resume_session)
            if branch is None:
                target_branch = parent.branch
        else:
            latest = self.index["latest_by_branch"].get(target_branch)
            if latest:
                parent = self.load_session(latest)
        session = self._build_session(parent=parent, branch=target_branch, task_type=task_type)
        self._save_session(session)
        if not self.index.get("root_session"):
            self.index["root_session"] = session.session_id
        self.save_index()
        return session

    def summary_lines(self, session: RuntimeSession, root_created: bool, resume_source: Optional[str]) -> List[str]:
        return [
            f"=== MORPH Runtime Core {VERSION} / Summary ===",
            f"Project:        {self.project_id}",
            f"Root created:   {str(root_created)}",
            f"Root session:   {self.index.get('root_session')}",
            f"Saved session:  {session.session_id}",
            f"Branch used:    {session.branch}",
            f"Resume source:  {resume_source or 'None'}",
            f"Task type:      {session.task_type}",
            f"Chosen route:   {session.chosen_route}",
            f"Session file:   {self._session_path(session.session_id)}",
            f"Index file:     {self.index_file}",
            "",
            "=== Status Snapshot ===",
            json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
        ]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MORPH Runtime Core v1.9r")
    p.add_argument("--base-dir", default=".", help="Base directory for runtime files")
    p.add_argument("--project", default=DEFAULT_PROJECT, help="Project id")
    p.add_argument("--fresh-if-missing", action="store_true", help="Create root session if project pack is missing")
    p.add_argument("--append-task", choices=["math", "simple"], help="Append a runtime task")
    p.add_argument("--resume-session", help="Resume from a specific session id")
    p.add_argument("--branch", help="Target branch label")
    return p


def main() -> None:
    args = build_parser().parse_args()
    core = RuntimeCore(Path(args.base_dir), args.project)

    root = None
    if args.fresh_if_missing:
        root = core.create_root_if_missing()

    if not args.append_task:
        if root is None:
            print(f"=== MORPH Runtime Core {VERSION} ===")
            print("Nothing to do. Use --fresh-if-missing and/or --append-task.")
            return
        session = root
        resume_source = None
        root_created = True
    else:
        session = core.append_task(
            task_type=args.append_task,
            resume_session=args.resume_session,
            branch=args.branch,
        )
        resume_source = args.resume_session
        root_created = root is not None

    print("\n".join(core.summary_lines(session, root_created, resume_source)))


if __name__ == "__main__":
    main()
