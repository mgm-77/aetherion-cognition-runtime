from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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


class AuditTrailEngine:
    def __init__(self, audit_path: Path) -> None:
        self.audit_path = audit_path
        self.events: List[Dict[str, Any]] = read_json(audit_path, default=[])

    def log(
        self,
        event_type: str,
        project_id: str,
        session_id: Optional[str],
        branch_label: Optional[str],
        route_name: Optional[str],
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.events.append(
            {
                'timestamp': utc_now(),
                'event_type': event_type,
                'project_id': project_id,
                'session_id': session_id,
                'branch_label': branch_label,
                'route_name': route_name,
                'outcome': outcome,
                'details': details or {},
            }
        )
        self.save()

    def save(self) -> None:
        write_json(self.audit_path, self.events)

    def export(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.events)


class IntegrityGuard:
    REQUIRED_SESSION_KEYS = {
        'project_id',
        'session_id',
        'parent_session_id',
        'branch_label',
        'task_type',
        'chosen_route',
        'verification_armed',
        'active_modules',
        'budget',
        'route_memory',
        'residue_registry',
        'deferred_registry',
        'last_fabric_state',
        'last_schedule',
    }

    def check(self, project_dir: Path) -> Dict[str, Any]:
        problems: List[Dict[str, Any]] = []
        sessions: Dict[str, Dict[str, Any]] = {}
        ids_seen: set[str] = set()

        for path in sorted(project_dir.glob('*.json')):
            if path.name in {'audit_log.json', 'integrity_report.json', 'replay_snapshot.json', 'project_registry.json'}:
                continue
            data = read_json(path, default={})
            session_id = data.get('session_id')
            if not session_id:
                problems.append({'type': 'missing_session_id', 'file': path.name})
                continue
            if session_id in ids_seen:
                problems.append({'type': 'duplicate_session_id', 'session_id': session_id, 'file': path.name})
            ids_seen.add(session_id)
            sessions[session_id] = data

        for session_id, data in sessions.items():
            missing = sorted(list(self.REQUIRED_SESSION_KEYS - set(data.keys())))
            if missing:
                problems.append({'type': 'missing_required_fields', 'session_id': session_id, 'fields': missing})

            parent = data.get('parent_session_id')
            if parent is not None and parent not in sessions:
                problems.append({'type': 'invalid_parent', 'session_id': session_id, 'parent_session_id': parent})

            branch_label = data.get('branch_label')
            if not isinstance(branch_label, str) or not branch_label.strip():
                problems.append({'type': 'empty_branch_label', 'session_id': session_id})

            merge_parents = data.get('merge_parents', [])
            if merge_parents:
                for merge_parent in merge_parents:
                    if merge_parent not in sessions:
                        problems.append(
                            {
                                'type': 'invalid_merge_parent',
                                'session_id': session_id,
                                'merge_parent': merge_parent,
                            }
                        )

        return {
            'checked_at': utc_now(),
            'project_dir': str(project_dir),
            'session_count': len(sessions),
            'problem_count': len(problems),
            'ok': len(problems) == 0,
            'problems': problems,
            'session_ids': sorted(sessions.keys()),
        }


class ReplayEngine:
    def replay(self, session_data: Dict[str, Any], mode: str) -> Dict[str, Any]:
        mode = mode.strip().lower()
        if mode not in {'dry_replay', 'branch_replay', 'full_replay'}:
            raise ValueError(f'Unsupported replay mode: {mode}')

        snapshot = {
            'replayed_at': utc_now(),
            'mode': mode,
            'project_id': session_data.get('project_id'),
            'session_id': session_data.get('session_id'),
            'branch_label': session_data.get('branch_label'),
            'chosen_route': session_data.get('chosen_route'),
            'verification_armed': session_data.get('verification_armed'),
            'last_phase': session_data.get('last_fabric_state', {}).get('phase'),
            'last_schedule': copy.deepcopy(session_data.get('last_schedule', {})),
            'replayed_modules': copy.deepcopy(session_data.get('active_modules', [])),
            'notes': [],
        }

        if mode == 'dry_replay':
            snapshot['notes'].append('No state mutation requested.')
        elif mode == 'branch_replay':
            snapshot['notes'].append('Replay intended for isolated branch validation.')
        else:
            snapshot['notes'].append('Replay intended as full state restoration check.')

        return snapshot


class SessionStateAdapter:
    def build_session_state(
        self,
        project_id: str,
        session_id: str,
        branch_label: str,
        task_type: str,
        chosen_route: str,
        verification_armed: bool,
        active_modules: List[str],
        budget: Dict[str, Any],
        parent_session_id: Optional[str] = None,
        merge_parents: Optional[List[str]] = None,
        merge_note: Optional[str] = None,
        route_memory: Optional[Dict[str, Any]] = None,
        residue_registry: Optional[Dict[str, Any]] = None,
        deferred_registry: Optional[Dict[str, Any]] = None,
        last_fabric_state: Optional[Dict[str, Any]] = None,
        last_schedule: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            'project_id': project_id,
            'session_id': session_id,
            'parent_session_id': parent_session_id,
            'branch_label': branch_label,
            'merge_parents': merge_parents or [],
            'merge_note': merge_note,
            'task_type': task_type,
            'chosen_route': chosen_route,
            'verification_armed': verification_armed,
            'active_modules': active_modules,
            'budget': copy.deepcopy(budget),
            'route_memory': copy.deepcopy(route_memory or {}),
            'residue_registry': copy.deepcopy(residue_registry or {}),
            'deferred_registry': copy.deepcopy(deferred_registry or {}),
            'last_fabric_state': copy.deepcopy(last_fabric_state or {}),
            'last_schedule': copy.deepcopy(last_schedule or {}),
            'saved_at': utc_now(),
        }


class ComparativeResumeEngine:
    def compare(self, left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
        left_modules = set(left.get('active_modules', []))
        right_modules = set(right.get('active_modules', []))
        left_deferred = sum(len(v) for v in left.get('deferred_registry', {}).values())
        right_deferred = sum(len(v) for v in right.get('deferred_registry', {}).values())
        left_route = left.get('chosen_route')
        right_route = right.get('chosen_route')

        return {
            'left_session_id': left.get('session_id'),
            'right_session_id': right.get('session_id'),
            'left_branch_label': left.get('branch_label'),
            'right_branch_label': right.get('branch_label'),
            'same_route': left_route == right_route,
            'left_route': left_route,
            'right_route': right_route,
            'module_overlap_count': len(left_modules & right_modules),
            'left_only_modules': sorted(list(left_modules - right_modules)),
            'right_only_modules': sorted(list(right_modules - left_modules)),
            'left_deferred_count': left_deferred,
            'right_deferred_count': right_deferred,
            'merge_suggestion': (
                'preserve_common_route_and_union_deferred_items'
                if left_route == right_route
                else 'create_branch_review_before_merge'
            ),
        }


class MergeResolver:
    def merge(
        self,
        left: Dict[str, Any],
        right: Dict[str, Any],
        merge_session_id: str,
        merge_branch_label: str,
        merge_note: str,
    ) -> Dict[str, Any]:
        comparator = ComparativeResumeEngine()
        summary = comparator.compare(left, right)
        merged_route = left.get('chosen_route') if summary['same_route'] else 'branch_review_required'
        merged_modules = sorted(list(set(left.get('active_modules', [])) | set(right.get('active_modules', []))))

        merged_deferred = copy.deepcopy(left.get('deferred_registry', {}))
        for task_type, items in right.get('deferred_registry', {}).items():
            merged_deferred.setdefault(task_type, [])
            known_ids = {item.get('item_id') for item in merged_deferred[task_type]}
            for item in items:
                if item.get('item_id') not in known_ids:
                    merged_deferred[task_type].append(copy.deepcopy(item))

        merged_residue = copy.deepcopy(left.get('residue_registry', {}))
        for task_type, bundles in right.get('residue_registry', {}).items():
            merged_residue.setdefault(task_type, [])
            known_bundle_ids = {bundle.get('bundle_id') for bundle in merged_residue[task_type]}
            for bundle in bundles:
                if bundle.get('bundle_id') not in known_bundle_ids:
                    merged_residue[task_type].append(copy.deepcopy(bundle))

        route_memory = copy.deepcopy(left.get('route_memory', {}))
        for task_type, right_mem in right.get('route_memory', {}).items():
            left_mem = route_memory.get(task_type)
            if not left_mem:
                route_memory[task_type] = copy.deepcopy(right_mem)
                continue
            left_mem['run_count'] = max(left_mem.get('run_count', 0), right_mem.get('run_count', 0))
            left_mem['avg_depth'] = max(left_mem.get('avg_depth', 0), right_mem.get('avg_depth', 0))
            left_mem['verification_rate'] = max(
                left_mem.get('verification_rate', 0.0),
                right_mem.get('verification_rate', 0.0),
            )

        merged_schedule = copy.deepcopy(left.get('last_schedule', {}))
        right_schedule = right.get('last_schedule', {})
        for queue_name, queue_items in right_schedule.items():
            merged_schedule.setdefault(queue_name, [])
            for item in queue_items:
                if item not in merged_schedule[queue_name]:
                    merged_schedule[queue_name].append(item)

        return {
            'project_id': left.get('project_id'),
            'session_id': merge_session_id,
            'parent_session_id': left.get('session_id'),
            'branch_label': merge_branch_label,
            'merge_parents': [left.get('session_id'), right.get('session_id')],
            'merge_note': merge_note,
            'merge_summary': summary,
            'task_type': left.get('task_type', 'unknown'),
            'chosen_route': merged_route,
            'verification_armed': bool(left.get('verification_armed') or right.get('verification_armed')),
            'active_modules': merged_modules,
            'budget': copy.deepcopy(left.get('budget', default_budget())),
            'route_memory': route_memory,
            'residue_registry': merged_residue,
            'deferred_registry': merged_deferred,
            'last_fabric_state': copy.deepcopy(left.get('last_fabric_state', {})),
            'last_schedule': merged_schedule,
            'saved_at': utc_now(),
        }


class RuntimeStateManager:
    def __init__(self, budget: Dict[str, Any]) -> None:
        self.budget = budget


class FabricOrchestratorV14:
    def __init__(self, budget: Dict[str, Any]) -> None:
        self.budget = budget
        self.base_modules = [
            'RuntimeStateManager',
            'ContinuityPackManager',
            'SessionStateAdapter',
            'ComparativeResumeEngine',
            'MergeResolver',
            'AuditTrailEngine',
            'ReplayEngine',
            'IntegrityGuard',
            'FabricOrchestratorV14',
            'PromptClassifier',
            'TokenDifficultyEstimator',
            'DepthGovernor',
            'MemoryTileManager',
            'RouteMemoryEngine',
            'ResidueRegistry',
            'DeferredWorkRegistry',
            'HorizonPlanner',
            'MultiScaleScheduler',
            'SchedulerPressureEngine',
            'ConflictResolver',
            'QueueArbitrationLayer',
            'CandidateRouteGenerator',
            'BranchScoringLayer',
            'EarlyCollapseController',
            'VerificationTrigger',
        ]

    def run(self, task_type: str) -> Dict[str, Any]:
        task_type = task_type.strip().lower()
        if task_type == 'math':
            route = 'math_deep_verify'
            verification = True
            hot_memory = ['math_simulator', 'beal_method', 'morph_v05']
            warm_memory = ['flux_programming', 'morph_v07', 'activation_pack']
            cold_memory = ['long_context_notes']
            schedule = {
                'immediate_queue': ['route_commit'],
                'short_queue': ['core_claim_pass'],
                'medium_queue': ['structural_consistency_pass'],
                'deep_queue': ['proof_pressure_pass', 'route_deepening'],
            }
        else:
            route = 'default_contextual'
            verification = False
            hot_memory = ['long_context_notes', 'morph_v05', 'math_simulator']
            warm_memory = ['flux_programming', 'morph_v07', 'beal_method']
            cold_memory = ['activation_pack']
            schedule = {
                'immediate_queue': [],
                'short_queue': [],
                'medium_queue': [],
                'deep_queue': [],
            }

        return {
            'task_type': task_type,
            'chosen_route': route,
            'verification_armed': verification,
            'active_modules': copy.deepcopy(self.base_modules),
            'route_memory': {
                task_type: {
                    'task_type': task_type,
                    'run_count': 1,
                    'avg_depth': 3.0 if verification else 1.0,
                    'verification_rate': 1.0 if verification else 0.0,
                    'preferred_hot_items': {k: 1 for k in hot_memory[:3]},
                    'preferred_modules': {k: 1 for k in self.base_modules},
                    'preferred_route_names': {route: 1},
                }
            },
            'residue_registry': {
                task_type: [
                    {
                        'task_type': task_type,
                        'bundle_id': f'{task_type}_bundle_1',
                        'route_name': route,
                        'hot_items': hot_memory[:3],
                        'active_modules': copy.deepcopy(self.base_modules),
                        'verification_armed': verification,
                        'avg_depth': 3.0 if verification else 1.0,
                        'usage_count': 1,
                    }
                ]
            },
            'deferred_registry': (
                {
                    task_type: [
                        {
                            'task_type': task_type,
                            'item_id': f'{task_type}_deferred_1',
                            'horizon': 'deep',
                            'description': 'Deferred follow-up generated by v1.4 demo.',
                            'source_route': route,
                            'source_chunk_index': 0,
                            'priority': 1.0 if verification else 0.4,
                            'reuse_count': 0,
                        }
                    ]
                }
                if verification
                else {}
            ),
            'last_fabric_state': {
                'task_type': task_type,
                'phase': 'complete',
                'chosen_route': route,
                'verification_armed': verification,
                'active_modules': copy.deepcopy(self.base_modules),
                'health_score': 0.9 if verification else 0.75,
                'historical_route_used': False,
                'residue_bundle_count': 1,
                'depth_history': [3] if verification else [1],
                'hot_memory_ids': hot_memory,
                'warm_memory_ids': warm_memory,
                'cold_memory_ids': cold_memory,
                'horizon_loads': {
                    'immediate': len(schedule['immediate_queue']),
                    'short': len(schedule['short_queue']),
                    'medium': len(schedule['medium_queue']),
                    'deep': len(schedule['deep_queue']),
                },
                'deferred_item_count': 1 if verification else 0,
                'schedule_loads': {
                    'immediate': len(schedule['immediate_queue']),
                    'short': len(schedule['short_queue']),
                    'medium': len(schedule['medium_queue']),
                    'deep': len(schedule['deep_queue']),
                },
                'route_confidence': 0.95 if verification else 0.53,
                'arbitration_count': 1 if verification else 0,
            },
            'last_schedule': schedule,
        }


class ContinuityPackManager:
    def __init__(self, root_dir: str = 'morph_continuity_pack_v1_4') -> None:
        self.root_dir = Path(root_dir)
        ensure_dir(self.root_dir)
        self.adapter = SessionStateAdapter()
        self.integrity_guard = IntegrityGuard()
        self.replay_engine = ReplayEngine()
        self.merge_resolver = MergeResolver()
        self.comparative_engine = ComparativeResumeEngine()

    def project_dir(self, project_id: str) -> Path:
        path = self.root_dir / project_id
        ensure_dir(path)
        return path

    def audit_engine(self, project_id: str) -> AuditTrailEngine:
        return AuditTrailEngine(self.project_dir(project_id) / 'audit_log.json')

    def session_path(self, project_id: str, session_id: str) -> Path:
        return self.project_dir(project_id) / f'{session_id}.json'

    def save_session(self, state: Dict[str, Any]) -> Path:
        path = self.session_path(state['project_id'], state['session_id'])
        write_json(path, state)
        self.audit_engine(state['project_id']).log(
            event_type='save_session',
            project_id=state['project_id'],
            session_id=state['session_id'],
            branch_label=state.get('branch_label'),
            route_name=state.get('chosen_route'),
            outcome='saved',
            details={'path': str(path)},
        )
        return path

    def load_session(self, project_id: str, session_id: str) -> Dict[str, Any]:
        path = self.session_path(project_id, session_id)
        state = read_json(path, default={})
        self.audit_engine(project_id).log(
            event_type='resume_session',
            project_id=project_id,
            session_id=session_id,
            branch_label=state.get('branch_label'),
            route_name=state.get('chosen_route'),
            outcome='loaded' if state else 'missing',
            details={'path': str(path)},
        )
        return state

    def save_integrity_report(self, project_id: str) -> Dict[str, Any]:
        report = self.integrity_guard.check(self.project_dir(project_id))
        report_path = self.project_dir(project_id) / 'integrity_report.json'
        write_json(report_path, report)
        self.audit_engine(project_id).log(
            event_type='integrity_check',
            project_id=project_id,
            session_id=None,
            branch_label=None,
            route_name=None,
            outcome='ok' if report['ok'] else 'problems_found',
            details={'problem_count': report['problem_count'], 'path': str(report_path)},
        )
        return report

    def save_replay_snapshot(self, project_id: str, session_id: str, mode: str) -> Dict[str, Any]:
        state = self.load_session(project_id, session_id)
        snapshot = self.replay_engine.replay(state, mode)
        snapshot_path = self.project_dir(project_id) / 'replay_snapshot.json'
        write_json(snapshot_path, snapshot)
        self.audit_engine(project_id).log(
            event_type='replay_session',
            project_id=project_id,
            session_id=session_id,
            branch_label=state.get('branch_label'),
            route_name=state.get('chosen_route'),
            outcome='replayed',
            details={'mode': mode, 'path': str(snapshot_path)},
        )
        return snapshot

    def fork_session(
        self,
        project_id: str,
        parent_session_id: str,
        fork_session_id: str,
        fork_branch_label: str,
    ) -> Dict[str, Any]:
        parent = self.load_session(project_id, parent_session_id)
        forked = copy.deepcopy(parent)
        forked['session_id'] = fork_session_id
        forked['parent_session_id'] = parent_session_id
        forked['branch_label'] = fork_branch_label
        forked['saved_at'] = utc_now()
        self.save_session(forked)
        self.audit_engine(project_id).log(
            event_type='fork_session',
            project_id=project_id,
            session_id=fork_session_id,
            branch_label=fork_branch_label,
            route_name=forked.get('chosen_route'),
            outcome='forked',
            details={'parent_session_id': parent_session_id},
        )
        return forked

    def merge_sessions(
        self,
        project_id: str,
        left_session_id: str,
        right_session_id: str,
        merge_session_id: str,
        merge_branch_label: str,
        merge_note: str,
    ) -> Dict[str, Any]:
        left = self.load_session(project_id, left_session_id)
        right = self.load_session(project_id, right_session_id)
        merged = self.merge_resolver.merge(
            left=left,
            right=right,
            merge_session_id=merge_session_id,
            merge_branch_label=merge_branch_label,
            merge_note=merge_note,
        )
        self.save_session(merged)
        self.audit_engine(project_id).log(
            event_type='merge_sessions',
            project_id=project_id,
            session_id=merge_session_id,
            branch_label=merge_branch_label,
            route_name=merged.get('chosen_route'),
            outcome='merged',
            details={
                'left_session_id': left_session_id,
                'right_session_id': right_session_id,
            },
        )
        return merged


def print_block(title: str, data: Any) -> None:
    print(f'\n=== {title} ===')
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    budget = default_budget()
    project_id = 'project_math_lab'
    manager = ContinuityPackManager()
    orchestrator = FabricOrchestratorV14(budget)
    adapter = SessionStateAdapter()

    root_runtime = orchestrator.run('math')
    session_001 = adapter.build_session_state(
        project_id=project_id,
        session_id='session_001',
        parent_session_id=None,
        branch_label='main',
        task_type=root_runtime['task_type'],
        chosen_route=root_runtime['chosen_route'],
        verification_armed=root_runtime['verification_armed'],
        active_modules=root_runtime['active_modules'],
        budget=budget,
        route_memory=root_runtime['route_memory'],
        residue_registry=root_runtime['residue_registry'],
        deferred_registry=root_runtime['deferred_registry'],
        last_fabric_state=root_runtime['last_fabric_state'],
        last_schedule=root_runtime['last_schedule'],
    )
    session_001_path = manager.save_session(session_001)

    session_002 = copy.deepcopy(session_001)
    session_002['session_id'] = 'session_002'
    session_002['parent_session_id'] = 'session_001'
    session_002['saved_at'] = utc_now()
    session_002_path = manager.save_session(session_002)

    fork_state = manager.fork_session(
        project_id=project_id,
        parent_session_id='session_002',
        fork_session_id='session_002__fork_experimental_verify',
        fork_branch_label='experimental_verify',
    )

    merged = manager.merge_sessions(
        project_id=project_id,
        left_session_id='session_002',
        right_session_id='session_002__fork_experimental_verify',
        merge_session_id='merge__session_002__session_002__fork_experimental_verify',
        merge_branch_label='merge_main_experimental',
        merge_note='Merged main branch with experimental verification branch.',
    )

    integrity_report = manager.save_integrity_report(project_id)

    replay_snapshot = manager.save_replay_snapshot(
        project_id=project_id,
        session_id=merged['session_id'],
        mode='branch_replay',
    )

    audit_log = manager.audit_engine(project_id).export()

    print('=== MORPH Runtime Core v1.4 Demo ===')
    print(f'Root session saved: {session_001_path}')
    print(f'Continuation saved: {session_002_path}')
    print(f"Fork saved: {manager.session_path(project_id, fork_state['session_id'])}")
    print(f"Merge saved: {manager.session_path(project_id, merged['session_id'])}")
    print(f"Integrity report: {manager.project_dir(project_id) / 'integrity_report.json'}")
    print(f"Replay snapshot: {manager.project_dir(project_id) / 'replay_snapshot.json'}")
    print(f"Audit log: {manager.project_dir(project_id) / 'audit_log.json'}")

    print_block('Merged Session Snapshot', merged)
    print_block('Integrity Report', integrity_report)
    print_block('Replay Snapshot', replay_snapshot)
    print_block('Audit Tail (Last 8 Events)', audit_log[-8:])


if __name__ == '__main__':
    main()
