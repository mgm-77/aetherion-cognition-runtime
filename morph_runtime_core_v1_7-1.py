#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return deepcopy(default)
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding='utf-8')


def list_session_files(project_dir: Path) -> List[Path]:
    return sorted([p for p in project_dir.glob('*.json') if p.name not in {
        'project_manifest.json', 'integrity_report.json', 'archive_summary.json',
        'replay_snapshot.json', 'audit_tail.json'
    } and not p.name.startswith('merge_snapshot_') and not p.name.startswith('fork_snapshot_')])


def task_defaults(task_type: str) -> Dict[str, Any]:
    if task_type == 'math':
        return {
            'route_name': 'math_deep_verify',
            'verification_armed': True,
            'avg_depth': 3.0,
            'health_score': 0.9,
            'route_confidence': 0.95,
            'hot_memory_ids': ['math_simulator', 'beal_method', 'morph_v05'],
            'warm_memory_ids': ['flux_programming', 'morph_v07', 'activation_pack'],
            'cold_memory_ids': ['long_context_notes'],
            'horizon_loads': {'immediate': 1, 'short': 1, 'medium': 1, 'deep': 2},
            'schedule_loads': {'immediate': 1, 'short': 1, 'medium': 1, 'deep': 2},
            'deferred_item_count': 1,
        }
    return {
        'route_name': 'default_contextual',
        'verification_armed': False,
        'avg_depth': 1.0,
        'health_score': 0.8,
        'route_confidence': 0.53,
        'hot_memory_ids': ['long_context_notes', 'morph_v05', 'math_simulator'],
        'warm_memory_ids': ['flux_programming', 'morph_v07', 'beal_method'],
        'cold_memory_ids': ['activation_pack'],
        'horizon_loads': {'immediate': 0, 'short': 0, 'medium': 0, 'deep': 0},
        'schedule_loads': {'immediate': 0, 'short': 0, 'medium': 0, 'deep': 0},
        'deferred_item_count': 0,
    }


def active_modules(task_type: str) -> List[str]:
    base = [
        'RuntimeStateManager', 'ContinuityPackManager', 'SessionStateAdapter',
        'ComparativeResumeEngine', 'MergeResolver', 'PromptClassifier',
        'TokenDifficultyEstimator', 'DepthGovernor', 'MemoryTileManager',
        'RouteMemoryEngine', 'ResidueRegistry', 'DeferredWorkRegistry',
        'HorizonPlanner', 'MultiScaleScheduler', 'SchedulerPressureEngine',
        'ConflictResolver', 'QueueArbitrationLayer', 'CandidateRouteGenerator',
        'BranchScoringLayer', 'EarlyCollapseController', 'VerificationTrigger'
    ]
    v = ['FabricOrchestratorV17', 'AuditTrailEngine', 'ReplayEngine', 'IntegrityGuard']
    if task_type == 'math':
        return base[:1] + v + base[1:]
    return base[:1] + v + base[1:]


def default_budget() -> Dict[str, Any]:
    return {
        'max_depth': 3,
        'verification_threshold': 2,
        'max_hot_items': 3,
        'max_warm_items': 3,
        'force_cold_tail': True,
        'max_candidate_routes': 3,
        'max_residue_bundles_per_task': 5,
        'max_deferred_items_per_task': 12,
        'deferred_trigger_on_medium_normal': True,
        'deferred_trigger_on_deep_normal': True,
    }


def latest_session_for_branch(manifest: Dict[str, Any], branch_label: str) -> Optional[Dict[str, Any]]:
    sessions = manifest.get('sessions', [])
    candidates = [s for s in sessions if s.get('branch_label') == branch_label]
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x.get('created_at', ''))[-1]


def latest_session_for_task(manifest: Dict[str, Any], task_type: str, branch_label: Optional[str] = None) -> Optional[Dict[str, Any]]:
    sessions = manifest.get('sessions', [])
    candidates = [s for s in sessions if s.get('task_type') == task_type]
    if branch_label is not None:
        candidates = [s for s in candidates if s.get('branch_label') == branch_label]
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x.get('created_at', ''))[-1]


def next_session_id(manifest: Dict[str, Any], task_type: str, branch_label: str) -> str:
    nums = []
    for s in manifest.get('sessions', []):
        m = re.match(r'^session_(\d+)', s.get('session_id', ''))
        if m:
            nums.append(int(m.group(1)))
    n = (max(nums) if nums else 0) + 1
    suffix = ''
    if task_type == 'simple':
        suffix = '_simple'
    elif branch_label not in ('main', 'simple_track'):
        safe = re.sub(r'[^a-zA-Z0-9_]+', '_', branch_label).strip('_')
        suffix = f'__{safe}'
    return f'session_{n:03d}{suffix}'


def build_last_schedule(task_type: str) -> Dict[str, List[str]]:
    if task_type == 'math':
        return {
            'immediate_queue': ['route_commit'],
            'short_queue': ['core_claim_pass'],
            'medium_queue': ['structural_consistency_pass'],
            'deep_queue': ['proof_pressure_pass', 'route_deepening'],
        }
    return {
        'immediate_queue': [],
        'short_queue': [],
        'medium_queue': [],
        'deep_queue': [],
    }


def build_session_snapshot(project_id: str, session_id: str, parent_session_id: Optional[str],
                           branch_label: str, task_type: str, note: str = '') -> Dict[str, Any]:
    defaults = task_defaults(task_type)
    data = {
        'project_id': project_id,
        'session_id': session_id,
        'parent_session_id': parent_session_id,
        'branch_label': branch_label,
        'task_type': task_type,
        'chosen_route': defaults['route_name'],
        'route_name': defaults['route_name'],
        'verification_armed': defaults['verification_armed'],
        'avg_depth': defaults['avg_depth'],
        'active_modules': active_modules(task_type),
        'health_score': defaults['health_score'],
        'historical_route_used': parent_session_id is not None,
        'residue_bundle_count': 1 if task_type == 'math' else 0,
        'depth_history': [3] if task_type == 'math' else [1, 1],
        'hot_memory_ids': defaults['hot_memory_ids'],
        'warm_memory_ids': defaults['warm_memory_ids'],
        'cold_memory_ids': defaults['cold_memory_ids'],
        'horizon_loads': defaults['horizon_loads'],
        'deferred_item_count': defaults['deferred_item_count'],
        'schedule_loads': defaults['schedule_loads'],
        'horizon_pressure': {'immediate': 0.25, 'short': 0.48, 'medium': 0.29, 'deep': 0.54} if task_type == 'math' else {'immediate': 0.0, 'short': 0.0, 'medium': 0.0, 'deep': 0.0},
        'route_confidence': defaults['route_confidence'],
        'arbitration_count': 1 if task_type == 'math' else 0,
        'last_schedule': build_last_schedule(task_type),
        'saved_at': utc_now(),
        'notes': [note] if note else [],
        'budget': default_budget(),
    }
    return data


def append_audit(audit_path: Path, event_type: str, project_id: str, session_id: Optional[str],
                 branch_label: Optional[str], route_name: Optional[str], outcome: str,
                 details: Dict[str, Any]) -> None:
    audit = read_json(audit_path, default=[])
    audit.append({
        'timestamp': utc_now(),
        'event_type': event_type,
        'project_id': project_id,
        'session_id': session_id,
        'branch_label': branch_label,
        'route_name': route_name,
        'outcome': outcome,
        'details': details,
    })
    write_json(audit_path, audit)


def build_integrity_report(project_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    problems: List[str] = []
    sessions = manifest.get('sessions', [])
    session_ids = {s['session_id'] for s in sessions}
    for s in sessions:
        parent = s.get('parent_session_id')
        if parent and parent not in session_ids:
            problems.append(f"Missing parent for {s['session_id']}: {parent}")
        path = project_dir / f"{s['session_id']}.json"
        if not path.exists():
            problems.append(f"Missing session file: {path.name}")
    report = {
        'checked_at': utc_now(),
        'project_dir': str(project_dir),
        'session_count': len(sessions),
        'problem_count': len(problems),
        'ok': len(problems) == 0,
        'problems': problems,
        'session_ids': sorted(session_ids),
    }
    return report


def compact_export(manifest: Dict[str, Any]) -> Dict[str, Any]:
    sessions = manifest.get('sessions', [])
    branch_counts: Dict[str, int] = {}
    task_counts: Dict[str, int] = {}
    for s in sessions:
        branch_counts[s['branch_label']] = branch_counts.get(s['branch_label'], 0) + 1
        task_counts[s['task_type']] = task_counts.get(s['task_type'], 0) + 1
    latest = sorted(sessions, key=lambda x: x.get('created_at', ''))[-1] if sessions else None
    return {
        'project_id': manifest.get('project_id'),
        'session_count': len(sessions),
        'branch_counts': branch_counts,
        'task_type_counts': task_counts,
        'latest_session': latest,
    }


def build_archive_summary(manifest: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
    return {
        'built_at': utc_now(),
        'project_id': manifest.get('project_id'),
        'project_dir': str(project_dir),
        'compact_export': compact_export(manifest),
    }


def build_quick_report(manifest: Dict[str, Any]) -> str:
    compact = compact_export(manifest)
    latest = compact.get('latest_session') or {}
    lines = [
        '=== Quick Snapshot ===',
        f"Project: {compact.get('project_id')}",
        f"Sessions: {compact.get('session_count')}",
        f"Latest session: {latest.get('session_id')}",
        f"Latest route: {latest.get('chosen_route')}",
        f"Branch: {latest.get('branch_label')}",
        f"Task type: {latest.get('task_type')}",
    ]
    return '\n'.join(lines) + '\n'


def save_manifest(project_dir: Path, manifest: Dict[str, Any]) -> None:
    write_json(project_dir / 'project_manifest.json', manifest)


def load_manifest(project_dir: Path, project_id: str) -> Dict[str, Any]:
    path = project_dir / 'project_manifest.json'
    manifest = read_json(path, default=None)
    if manifest is None:
        manifest = {
            'project_id': project_id,
            'created_at': utc_now(),
            'updated_at': utc_now(),
            'sessions': [],
        }
    return manifest


def add_session(project_dir: Path, manifest: Dict[str, Any], project_id: str, task_type: str,
                branch_label: str, parent_session_id: Optional[str], note: str) -> Tuple[Dict[str, Any], Path]:
    session_id = next_session_id(manifest, task_type, branch_label)
    snapshot = build_session_snapshot(project_id, session_id, parent_session_id, branch_label, task_type, note)
    session_path = project_dir / f'{session_id}.json'
    write_json(session_path, snapshot)
    manifest['sessions'].append({
        'session_id': session_id,
        'parent_session_id': parent_session_id,
        'branch_label': branch_label,
        'task_type': task_type,
        'chosen_route': snapshot['chosen_route'],
        'verification_armed': snapshot['verification_armed'],
        'route_confidence': snapshot['route_confidence'],
        'deferred_item_count': snapshot['deferred_item_count'],
        'created_at': snapshot['saved_at'],
        'path': str(session_path.relative_to(project_dir.parent)),
    })
    manifest['updated_at'] = utc_now()
    return snapshot, session_path


def rebuild_outputs(project_dir: Path, manifest: Dict[str, Any]) -> Dict[str, Path]:
    save_manifest(project_dir, manifest)
    integrity = build_integrity_report(project_dir, manifest)
    integrity_path = project_dir / 'integrity_report.json'
    write_json(integrity_path, integrity)

    archive_summary = build_archive_summary(manifest, project_dir)
    archive_path = project_dir / 'archive_summary.json'
    write_json(archive_path, archive_summary)

    quick_path = project_dir / 'quick_report.txt'
    write_text(quick_path, build_quick_report(manifest))

    audit_tail_path = project_dir / 'audit_tail.json'
    audit_full = read_json(audit_tail_path, default=[])
    write_json(audit_tail_path, audit_full[-8:])

    zip_base = project_dir.parent / project_dir.name
    zip_file = shutil.make_archive(str(zip_base), 'zip', root_dir=project_dir.parent, base_dir=project_dir.name)

    return {
        'integrity': integrity_path,
        'archive': archive_path,
        'quick': quick_path,
        'audit_tail': audit_tail_path,
        'zip': Path(zip_file),
        'manifest': project_dir / 'project_manifest.json',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='MORPH Runtime Core v1.7')
    parser.add_argument('--pack-root', default='morph_continuity_pack_v1_7')
    parser.add_argument('--project-id', default='project_math_lab')
    parser.add_argument('--append-task', choices=['math', 'simple'], default='math')
    parser.add_argument('--append-branch', default=None)
    parser.add_argument('--note', default='')
    parser.add_argument('--fresh-if-missing', action='store_true', help='Create root session if project is missing.')
    args = parser.parse_args()

    base_dir = Path.cwd() / args.pack_root
    project_dir = base_dir / args.project_id
    ensure_dir(project_dir)

    manifest = load_manifest(project_dir, args.project_id)
    audit_path = project_dir / 'audit_tail.json'

    created_root = False
    if not manifest.get('sessions') and args.fresh_if_missing:
        root_snapshot, root_path = add_session(project_dir, manifest, args.project_id, 'math', 'main', None, 'Initial root session')
        append_audit(audit_path, 'save_session', args.project_id, root_snapshot['session_id'], 'main', root_snapshot['route_name'], 'saved', {'path': str(root_path.relative_to(base_dir))})
        created_root = True

    branch_label = args.append_branch
    if not branch_label:
        branch_label = 'main' if args.append_task == 'math' else 'simple_track'

    parent_session_id = None
    if manifest.get('sessions'):
        if branch_label == 'main':
            latest = latest_session_for_task(manifest, 'math', 'main')
            parent_session_id = latest['session_id'] if latest else None
        elif args.append_task == 'simple':
            parent_session_id = None
        else:
            latest = latest_session_for_branch(manifest, branch_label)
            parent_session_id = latest['session_id'] if latest else None

    snapshot, session_path = add_session(project_dir, manifest, args.project_id, args.append_task, branch_label, parent_session_id, args.note)
    append_audit(audit_path, 'save_session', args.project_id, snapshot['session_id'], branch_label, snapshot['route_name'], 'saved', {'path': str(session_path.relative_to(base_dir))})

    outputs = rebuild_outputs(project_dir, manifest)
    integrity = read_json(outputs['integrity'])

    print('=== MORPH Runtime Core v1.7 / Summary ===')
    if created_root:
        print('Created root session automatically because the project pack was missing.')
    print(f'Saved session:   {session_path.relative_to(base_dir)}')
    print(f'Project:         {args.project_id}')
    print(f'Branch:          {branch_label}')
    print(f'Task type:       {args.append_task}')
    print(f'Chosen route:    {snapshot["route_name"]}')
    print(f'Parent session:  {parent_session_id}')
    print(f'Integrity:       {'ok' if integrity.get("ok") else 'problem'} ({integrity.get("problem_count")})')
    print(f'Manifest file:   {outputs["manifest"].relative_to(base_dir)}')
    print(f'Quick report:    {outputs["quick"].relative_to(base_dir)}')
    print(f'Archive file:    {outputs["archive"].relative_to(base_dir)}')
    print(f'ZIP export:      {outputs["zip"].name}')


if __name__ == '__main__':
    main()
