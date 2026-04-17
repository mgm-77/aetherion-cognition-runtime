#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding='utf-8'))

def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

@dataclass
class SessionState:
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
        return {
            'session_id': self.session_id,
            'parent': self.parent,
            'branch': self.branch,
            'task_type': self.task_type,
            'chosen_route': self.chosen_route,
            'verification_armed': self.verification_armed,
            'route_confidence': self.route_confidence,
            'deferred_item_count': self.deferred_item_count,
            'health_score': self.health_score,
            'saved_at': self.saved_at,
        }

class MorphCoreV18a:
    def __init__(self, base_dir: Path, project_id: str = 'project_math_lab') -> None:
        self.base_dir = base_dir
        self.project_id = project_id
        self.project_dir = self.base_dir / self.project_id
        self.manifest_path = self.project_dir / 'project_manifest.json'
        self.quick_report_path = self.project_dir / 'quick_report.txt'
        self.archive_summary_path = self.project_dir / 'archive_summary.json'
        self.integrity_report_path = self.project_dir / 'integrity_report.json'
        self.zip_export_path = self.base_dir / f'{self.project_id}.zip'
        ensure_dir(self.project_dir)
        if not self.manifest_path.exists():
            self._init_manifest()

    def _init_manifest(self) -> None:
        write_json(self.manifest_path, {
            'project_id': self.project_id,
            'created_at': now_iso(),
            'latest_session_id': None,
            'branch_heads': {},
            'sessions': {},
        })

    def _load_manifest(self) -> Dict[str, Any]:
        return read_json(self.manifest_path, default={})

    def _save_manifest(self, manifest: Dict[str, Any]) -> None:
        write_json(self.manifest_path, manifest)

    def _next_session_id(self, manifest: Dict[str, Any], branch: str) -> str:
        sessions = manifest.get('sessions', {})
        if branch == 'main':
            nums = []
            for sid, meta in sessions.items():
                if meta.get('branch') == 'main' and sid.startswith('session_'):
                    tail = sid.replace('session_', '', 1)
                    if tail.isdigit():
                        nums.append(int(tail))
            return f"session_{(max(nums)+1) if nums else 1:03d}"
        nums = []
        suffix = f'_{branch}'
        for sid, meta in sessions.items():
            if meta.get('branch') == branch and sid.startswith('session_') and sid.endswith(suffix):
                core = sid[len('session_'):-len(suffix)]
                if core.isdigit():
                    nums.append(int(core))
        return f"session_{(max(nums)+1) if nums else 1:03d}_{branch}"

    def _derive_task_profile(self, task_type: str) -> Dict[str, Any]:
        if task_type == 'math':
            return {
                'task_type': 'math',
                'chosen_route': 'math_deep_verify',
                'verification_armed': True,
                'route_confidence': 1.0,
                'deferred_item_count': 1,
                'health_score': 0.9,
            }
        return {
            'task_type': 'simple',
            'chosen_route': 'default_contextual',
            'verification_armed': False,
            'route_confidence': 0.53,
            'deferred_item_count': 0,
            'health_score': 0.8,
        }

    def _save_session(self, state: SessionState) -> Path:
        path = self.project_dir / f'{state.session_id}.json'
        write_json(path, state.to_dict())
        return path

    def _build_quick_report(self, state: SessionState) -> None:
        text = (
            f"Project: {self.project_id}\n"
            f"Session: {state.session_id}\n"
            f"Parent: {state.parent}\n"
            f"Branch: {state.branch}\n"
            f"Task type: {state.task_type}\n"
            f"Chosen route: {state.chosen_route}\n"
            f"Verification armed: {state.verification_armed}\n"
            f"Route confidence: {state.route_confidence}\n"
            f"Deferred items: {state.deferred_item_count}\n"
            f"Health: {state.health_score}\n"
        )
        self.quick_report_path.write_text(text, encoding='utf-8')

    def _build_archive_summary(self, manifest: Dict[str, Any]) -> None:
        sessions = manifest.get('sessions', {})
        task_type_counts: Dict[str, int] = {}
        branch_counts: Dict[str, int] = {}
        latest_id = manifest.get('latest_session_id')
        latest = sessions.get(latest_id) if latest_id else None
        for meta in sessions.values():
            branch = meta.get('branch', 'unknown')
            task = meta.get('task_type', 'unknown')
            branch_counts[branch] = branch_counts.get(branch, 0) + 1
            task_type_counts[task] = task_type_counts.get(task, 0) + 1
        write_json(self.archive_summary_path, {
            'project_id': self.project_id,
            'session_count': len(sessions),
            'branch_counts': branch_counts,
            'task_type_counts': task_type_counts,
            'latest_session': latest,
        })

    def _build_integrity_report(self, manifest: Dict[str, Any]) -> Dict[str, Any]:
        problems: List[str] = []
        sessions = manifest.get('sessions', {})
        for sid, meta in sessions.items():
            parent = meta.get('parent')
            if parent is not None and parent not in sessions:
                problems.append(f'{sid}: missing parent {parent}')
            if not (self.project_dir / f'{sid}.json').exists():
                problems.append(f'{sid}: missing session file')
        report = {
            'checked_at': now_iso(),
            'project_dir': str(self.project_dir),
            'session_count': len(sessions),
            'problem_count': len(problems),
            'ok': len(problems) == 0,
            'problems': problems,
            'session_ids': sorted(sessions.keys()),
        }
        write_json(self.integrity_report_path, report)
        return report

    def _zip_project(self) -> None:
        with zipfile.ZipFile(self.zip_export_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(self.project_dir.rglob('*')):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(self.base_dir)))

    def fresh_if_missing(self) -> Dict[str, Any]:
        manifest = self._load_manifest()
        sessions = manifest.get('sessions', {})
        created_root = False
        if not sessions:
            profile = self._derive_task_profile('math')
            state = SessionState(
                session_id='session_001',
                parent=None,
                branch='main',
                task_type=profile['task_type'],
                chosen_route=profile['chosen_route'],
                verification_armed=profile['verification_armed'],
                route_confidence=profile['route_confidence'],
                deferred_item_count=profile['deferred_item_count'],
                health_score=profile['health_score'],
                saved_at=now_iso(),
            )
            self._save_session(state)
            manifest['sessions']['session_001'] = state.to_dict()
            manifest['latest_session_id'] = 'session_001'
            manifest['branch_heads']['main'] = 'session_001'
            self._save_manifest(manifest)
            created_root = True
        manifest = self._load_manifest()
        latest_id = manifest.get('latest_session_id')
        latest = manifest['sessions'].get(latest_id, {}) if latest_id else {}
        self._build_quick_report(SessionState(**latest))
        integrity = self._build_integrity_report(manifest)
        self._build_archive_summary(manifest)
        self._zip_project()
        return {
            'project': self.project_id,
            'root_created': created_root,
            'root_session': manifest['sessions'].get('session_001', {}).get('session_id'),
            'saved_session': latest.get('session_id'),
            'branch_used': latest.get('branch'),
            'resume_source': latest.get('parent'),
            'task_type': latest.get('task_type'),
            'chosen_route': latest.get('chosen_route'),
            'session_file': str(self.project_dir / f"{latest.get('session_id')}.json"),
            'manifest_file': str(self.manifest_path),
            'quick_report': str(self.quick_report_path),
            'archive_file': str(self.archive_summary_path),
            'integrity': str(self.integrity_report_path),
            'zip_export': str(self.zip_export_path),
            'status_snapshot': latest,
            'integrity_ok': integrity['ok'],
            'integrity_problem_count': integrity['problem_count'],
        }

    def append_task(self, task_type: str, branch: str, resume_session: Optional[str]) -> Dict[str, Any]:
        manifest = self._load_manifest()
        if resume_session:
            parent = resume_session
            if parent not in manifest['sessions']:
                raise ValueError(f'Unknown resume session: {parent}')
        else:
            if branch != 'main' and branch not in manifest.get('branch_heads', {}):
                parent = None
            else:
                parent = manifest.get('branch_heads', {}).get(branch)
        sid = self._next_session_id(manifest, branch)
        profile = self._derive_task_profile(task_type)
        state = SessionState(
            session_id=sid,
            parent=parent,
            branch=branch,
            task_type=profile['task_type'],
            chosen_route=profile['chosen_route'],
            verification_armed=profile['verification_armed'],
            route_confidence=profile['route_confidence'],
            deferred_item_count=profile['deferred_item_count'],
            health_score=profile['health_score'],
            saved_at=now_iso(),
        )
        self._save_session(state)
        manifest['sessions'][sid] = state.to_dict()
        manifest['latest_session_id'] = sid
        manifest['branch_heads'][branch] = sid
        self._save_manifest(manifest)
        self._build_quick_report(state)
        integrity = self._build_integrity_report(manifest)
        self._build_archive_summary(manifest)
        self._zip_project()
        return {
            'project': self.project_id,
            'root_created': False,
            'root_session': manifest['sessions'].get('session_001', {}).get('session_id'),
            'saved_session': sid,
            'branch_used': branch,
            'resume_source': parent,
            'task_type': state.task_type,
            'chosen_route': state.chosen_route,
            'session_file': str(self.project_dir / f'{sid}.json'),
            'manifest_file': str(self.manifest_path),
            'quick_report': str(self.quick_report_path),
            'archive_file': str(self.archive_summary_path),
            'integrity': str(self.integrity_report_path),
            'zip_export': str(self.zip_export_path),
            'status_snapshot': state.to_dict(),
            'integrity_ok': integrity['ok'],
            'integrity_problem_count': integrity['problem_count'],
        }

def print_summary(label: str, result: Dict[str, Any]) -> None:
    print(f'=== MORPH Runtime Core {label} / Summary ===')
    print(f"Project:       {result['project']}")
    print(f"Root created:  {result['root_created']}")
    print(f"Root session:  {result['root_session']}")
    print(f"Saved session: {result['saved_session']}")
    print(f"Branch used:   {result['branch_used']}")
    print(f"Resume source: {result['resume_source']}")
    print(f"Task type:     {result['task_type']}")
    print(f"Chosen route:  {result['chosen_route']}")
    print(f"Session file:  {result['session_file']}")
    print(f"Manifest file: {result['manifest_file']}")
    print(f"Quick report:  {result['quick_report']}")
    print(f"Archive file:  {result['archive_file']}")
    print(f"Integrity:     {result['integrity']} (ok={int(result['integrity_ok'])})")
    print(f"ZIP export:    {result['zip_export']}")
    print()
    print('=== Status Snapshot ===')
    print(json.dumps(result['status_snapshot'], indent=2, ensure_ascii=False))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-dir', default='morph_continuity_pack_v1_8a')
    parser.add_argument('--project-id', default='project_math_lab')
    parser.add_argument('--fresh-if-missing', action='store_true')
    parser.add_argument('--resume-session')
    parser.add_argument('--append-task', choices=['math', 'simple'])
    parser.add_argument('--branch', default='main')
    args = parser.parse_args()

    core = MorphCoreV18a(Path(args.base_dir), project_id=args.project_id)

    if args.fresh_if_missing:
        print_summary('v1.8a', core.fresh_if_missing())
        return
    if args.append_task:
        print_summary('v1.8a', core.append_task(args.append_task, args.branch, args.resume_session))
        return
    parser.error('Use --fresh-if-missing or --append-task {math,simple}')

if __name__ == '__main__':
    main()
