#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile, os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = 'v3.3'
PACK_ROOT_NAME = 'morph_runtime_core_v3_3'
DEFAULT_PROJECT_ID = 'project_math_lab'

MODULES_BY_TASK = {
    'math': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'RecoveryEngine','AutoRepairBasic','OrphanHandler','ComparativeResumeEngine','HandoffExporter',
        'QuickResumePack','SummaryPackBuilder','PackValidator','IntegrityGuard','FabricOrchestratorV33',
        'MergeIntelligenceEngine','CompareModesEngine','BranchVerdictEngine','StateInspector','RuntimeDashboardBuilder',
        'CheckpointManager','ReleaseReportBuilder','SnapshotExporter','SessionQueryEngine','HistoryTimelineBuilder',
        'PressureSignalBuilder'
    ],
    'simple': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'RecoveryEngine','AutoRepairBasic','OrphanHandler','ComparativeResumeEngine','HandoffExporter',
        'QuickResumePack','SummaryPackBuilder','PackValidator','IntegrityGuard','FabricOrchestratorV33',
        'MergeIntelligenceEngine','CompareModesEngine','BranchVerdictEngine','StateInspector','RuntimeDashboardBuilder',
        'CheckpointManager','ReleaseReportBuilder','SnapshotExporter','SessionQueryEngine','HistoryTimelineBuilder',
        'PressureSignalBuilder'
    ]
}

TASK_DEFAULTS = {
    'math': {
        'chosen_route': 'math_deep_verify','verification_armed': True,'route_confidence': 1.0,
        'deferred_item_count': 1,'health_score': 0.9,
        'hot_memory_ids': ['math_simulator','beal_method','morph_v05'],
        'warm_memory_ids': ['flux_programming','morph_v07','activation_pack'],
        'cold_memory_ids': ['long_context_notes'],
        'last_schedule': {
            'immediate_queue': ['route_commit'],'short_queue': ['core_claim_pass'],
            'medium_queue': ['structural_consistency_pass'],'deep_queue': ['proof_pressure_pass','route_deepening']
        }
    },
    'simple': {
        'chosen_route': 'default_contextual','verification_armed': False,'route_confidence': 0.53,
        'deferred_item_count': 0,'health_score': 0.8,
        'hot_memory_ids': ['long_context_notes','morph_v05','math_simulator'],
        'warm_memory_ids': ['flux_programming','morph_v07','beal_method'],
        'cold_memory_ids': ['activation_pack'],
        'last_schedule': {'immediate_queue': [],'short_queue': [],'medium_queue': [],'deep_queue': []}
    }
}

DEFAULT_BUDGET = {
    'max_depth': 3,'verification_threshold': 2,'max_hot_items': 3,'max_warm_items': 3,
    'force_cold_tail': True,'max_candidate_routes': 3,'max_residue_bundles_per_task': 5,
    'max_deferred_items_per_task': 12,'deferred_trigger_on_medium_normal': True,'deferred_trigger_on_deep_normal': True
}

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')

def read_json(path: Path, default=None) -> Any:
    if not path.exists():
        return deepcopy(default)
    return json.loads(path.read_text(encoding='utf-8'))

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def slugify(value: str) -> str:
    out = []
    for ch in value.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in (' ', '-', '_'):
            out.append('_')
    s = ''.join(out).strip('_')
    while '__' in s:
        s = s.replace('__', '_')
    return s or 'item'

class MorphRuntimeCoreV33:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.pack_root = self.base_dir / PACK_ROOT_NAME
        self.project_id = DEFAULT_PROJECT_ID
        self.project_dir = self.pack_root / self.project_id
        self.sessions_dir = self.project_dir / 'sessions'
        self.checkpoints_dir = self.project_dir / 'checkpoints'
        self.runtime_index_file = self.project_dir / 'runtime_index.json'
        self.project_manifest_file = self.project_dir / 'project_manifest.json'
        self.integrity_report_file = self.project_dir / 'integrity_report.json'
        self.quick_report_file = self.project_dir / 'quick_report.txt'
        self.compact_handoff_file = self.project_dir / 'compact_handoff.json'
        self.quick_resume_pack_file = self.project_dir / 'quick_resume_pack.json'
        self.summary_pack_file = self.project_dir / 'summary_pack.json'
        self.branch_compare_file = self.project_dir / 'branch_compare_v3_3.json'
        self.branch_verdict_md_file = self.project_dir / 'branch_verdict_v3_3.md'
        self.branch_verdict_txt_file = self.project_dir / 'branch_verdict_v3_3.txt'
        self.runtime_dashboard_json = self.project_dir / 'runtime_dashboard_v3_3.json'
        self.runtime_dashboard_txt = self.project_dir / 'runtime_dashboard_v3_3.txt'
        self.runtime_dashboard_md = self.project_dir / 'runtime_dashboard_v3_3.md'
        self.archive_summary_file = self.project_dir / 'archive_summary.json'
        self.release_summary_json = self.project_dir / 'release_summary_v3_3.json'
        self.release_summary_txt = self.project_dir / 'release_summary_v3_3.txt'
        self.report_txt = self.project_dir / 'report_v3.3.txt'
        self.report_md = self.project_dir / 'report_v3.3.md'
        self.session_query_json = self.project_dir / 'session_query_v3_3.json'
        self.session_query_txt = self.project_dir / 'session_query_v3_3.txt'
        self.timeline_json = self.project_dir / 'history_timeline_v3_3.json'
        self.timeline_txt = self.project_dir / 'history_timeline_v3_3.txt'
        self.timeline_md = self.project_dir / 'history_timeline_v3_3.md'
        self.pressure_json = self.project_dir / 'pressure_signals_v3_3.json'
        self.pressure_txt = self.project_dir / 'pressure_signals_v3_3.txt'
        self.pressure_md = self.project_dir / 'pressure_signals_v3_3.md'
        self.zip_export_file = self.pack_root / f'{self.project_id}.zip'

    def ensure_dirs(self):
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def init_pack(self):
        self.ensure_dirs()
        if not self.runtime_index_file.exists():
            write_json(self.runtime_index_file, {
                'project_id': self.project_id,
                'created_at': now_iso(),
                'current_session_id': None,
                'sessions': {},
                'branches': {},
                'checkpoints': {},
                'audit_tail': [],
            })

    def load_index(self):
        self.init_pack()
        return read_json(self.runtime_index_file, default={})

    def save_index(self, index):
        write_json(self.runtime_index_file, index)

    def session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f'{session_id}.json'

    def checkpoint_path(self, label: str) -> Path:
        return self.checkpoints_dir / f'{slugify(label)}.json'

    def audit(self, index, event_type, session_id, branch_label, route_name, outcome, details):
        index['audit_tail'].append({
            'timestamp': now_iso(),'event_type': event_type,'project_id': self.project_id,
            'session_id': session_id,'branch_label': branch_label,'route_name': route_name,
            'outcome': outcome,'details': details
        })
        index['audit_tail'] = index['audit_tail'][-24:]

    def next_session_id(self, index, branch_label):
        branch_sessions = [sid for sid, meta in index['sessions'].items() if meta['branch'] == branch_label]
        n = len(branch_sessions) + 1
        return f'session_{n:03d}' if branch_label == 'main' else f'session_{n:03d}_{slugify(branch_label)}'

    def build_session(self, session_id, parent_id, branch_label, task_type):
        d = deepcopy(TASK_DEFAULTS[task_type])
        return {
            'project_id': self.project_id,'session_id': session_id,'parent': parent_id,'branch': branch_label,
            'task_type': task_type,'chosen_route': d['chosen_route'],'verification_armed': d['verification_armed'],
            'route_confidence': d['route_confidence'],'deferred_item_count': d['deferred_item_count'],
            'health_score': d['health_score'],'active_modules': MODULES_BY_TASK[task_type],
            'hot_memory_ids': d['hot_memory_ids'],'warm_memory_ids': d['warm_memory_ids'],
            'cold_memory_ids': d['cold_memory_ids'],'last_schedule': d['last_schedule'],
            'budget': deepcopy(DEFAULT_BUDGET),'saved_at': now_iso()
        }

    def latest_session(self):
        index = self.load_index()
        sid = index.get('current_session_id')
        if not sid or sid not in index['sessions']:
            return None
        return read_json(Path(index['sessions'][sid]['path']), default=None)

    def append_task(self, task_type='math', branch_label='main', resume_session=None):
        index = self.load_index()
        root_created = False
        if not index['sessions']:
            root_created = True
            root = self.build_session('session_001', None, 'main', 'math')
            write_json(self.session_path('session_001'), root)
            index['sessions']['session_001'] = {
                'path': str(self.session_path('session_001')),'parent': None,'branch': 'main','task_type': 'math',
                'chosen_route': root['chosen_route'],'health_score': root['health_score'],'saved_at': root['saved_at']
            }
            index['branches']['main'] = {'root_session_id': 'session_001','latest_session_id': 'session_001','session_ids': ['session_001']}
            index['current_session_id'] = 'session_001'
            self.audit(index, 'save_session', 'session_001', 'main', root['chosen_route'], 'saved', {'path': str(self.session_path('session_001'))})
        if resume_session is None and task_type == 'math' and branch_label == 'main' and root_created:
            self.save_index(index)
            self.build_all_reports()
            return root, True
        parent_id = resume_session or index['branches'].get(branch_label, {}).get('latest_session_id')
        session_id = self.next_session_id(index, branch_label)
        session = self.build_session(session_id, parent_id, branch_label, task_type)
        if parent_id and parent_id in index['sessions']:
            parent = read_json(Path(index['sessions'][parent_id]['path']), default={})
            if parent:
                session['budget'] = parent.get('budget', session['budget'])
                session['hot_memory_ids'] = parent.get('hot_memory_ids', session['hot_memory_ids'])
                session['warm_memory_ids'] = parent.get('warm_memory_ids', session['warm_memory_ids'])
                session['cold_memory_ids'] = parent.get('cold_memory_ids', session['cold_memory_ids'])
        write_json(self.session_path(session_id), session)
        index['sessions'][session_id] = {
            'path': str(self.session_path(session_id)),'parent': parent_id,'branch': branch_label,
            'task_type': task_type,'chosen_route': session['chosen_route'],
            'health_score': session['health_score'],'saved_at': session['saved_at']
        }
        branch = index['branches'].setdefault(branch_label, {'root_session_id': session_id,'latest_session_id': session_id,'session_ids': []})
        if not branch['session_ids']:
            branch['root_session_id'] = session_id
        branch['latest_session_id'] = session_id
        branch['session_ids'].append(session_id)
        index['current_session_id'] = session_id
        self.audit(index, 'save_session', session_id, branch_label, session['chosen_route'], 'saved', {'path': str(self.session_path(session_id))})
        self.save_index(index)
        self.build_all_reports()
        return session, root_created

    def integrity_check(self):
        index = self.load_index()
        problems = []
        for sid, meta in index['sessions'].items():
            p = Path(meta['path'])
            if not p.exists():
                problems.append({'type': 'missing_session_file','session_id': sid,'path': str(p)})
        report = {
            'checked_at': now_iso(),'project_dir': str(self.project_dir),'session_count': len(index['sessions']),
            'problem_count': len(problems),'ok': len(problems) == 0,'problems': problems,
            'session_ids': sorted(index['sessions'].keys())
        }
        write_json(self.integrity_report_file, report)
        index = self.load_index()
        self.audit(index, 'integrity_checked', None, None, None, 'ok' if report['ok'] else 'problems', {'problem_count': report['problem_count']})
        self.save_index(index)
        return report

    def build_manifest(self):
        index = self.load_index()
        manifest = {
            'project_id': self.project_id,'pack_root': str(self.pack_root),'project_dir': str(self.project_dir),
            'session_count': len(index['sessions']),'branch_count': len(index['branches']),
            'checkpoint_count': len(index.get('checkpoints', {})),
            'latest_session_id': index.get('current_session_id'),'generated_at': now_iso(),'branches': index['branches']
        }
        write_json(self.project_manifest_file, manifest)
        return manifest

    def build_compact_handoff(self):
        index = self.load_index()
        latest = self.latest_session()
        integrity = read_json(self.integrity_report_file, default={'ok': False,'problem_count': 999})
        branch_counts = {k: len(v['session_ids']) for k, v in index['branches'].items()}
        task_counts = {}
        for meta in index['sessions'].values():
            task_counts[meta['task_type']] = task_counts.get(meta['task_type'], 0) + 1
        data = {
            'project_id': self.project_id,'session_count': len(index['sessions']),'branch_counts': branch_counts,
            'task_type_counts': task_counts,'latest_session': latest,'integrity_ok': integrity['ok'],
            'problem_count': integrity['problem_count'],
            'resume_main': f"python morph_runtime_core_v3_3.py --append-task math --resume-session {latest['session_id']}" if latest else None,
            'resume_simple': "python morph_runtime_core_v3_3.py --append-task simple --branch simple_track" if latest else None,
        }
        write_json(self.compact_handoff_file, data)
        return data

    def build_quick_resume_pack(self):
        index = self.load_index()
        latest = self.latest_session()
        data = {
            'project_id': self.project_id,'latest_session_id': latest.get('session_id') if latest else None,
            'main_resume': f"python morph_runtime_core_v3_3.py --append-task math --resume-session {latest['session_id']}" if latest and latest['task_type'] == 'math' else None,
            'simple_resume': "python morph_runtime_core_v3_3.py --append-task simple --branch simple_track",
            'checkpoint_create': "python morph_runtime_core_v3_3.py --checkpoint-label stable_v3_3",
            'known_branches': list(index['branches'].keys()),'saved_at': now_iso(),
        }
        write_json(self.quick_resume_pack_file, data)
        return data

    def build_summary_pack(self):
        index = self.load_index()
        sessions = []
        for sid in index['sessions']:
            s = read_json(Path(index['sessions'][sid]['path']), default={})
            sessions.append({
                'session_id': sid,'parent': s.get('parent'),'branch': s.get('branch'),'task_type': s.get('task_type'),
                'chosen_route': s.get('chosen_route'),'verification_armed': s.get('verification_armed'),
                'route_confidence': s.get('route_confidence'),'health_score': s.get('health_score'),
                'deferred_item_count': s.get('deferred_item_count'),'saved_at': s.get('saved_at')
            })
        data = {'project_id': self.project_id,'generated_at': now_iso(),'sessions': sessions,'audit_tail': index['audit_tail'][-8:]}
        write_json(self.summary_pack_file, data)
        return data

    def build_archive_summary(self):
        index = self.load_index()
        data = {'project_id': self.project_id,'session_ids': list(index['sessions'].keys()),
                'branch_ids': list(index['branches'].keys()),'latest_session_id': index.get('current_session_id'),
                'generated_at': now_iso()}
        write_json(self.archive_summary_file, data)
        return data

    def compare_branches(self):
        index = self.load_index()
        latest_by_branch = {}
        for branch, info in index['branches'].items():
            sid = info.get('latest_session_id')
            if sid and sid in index['sessions']:
                latest_by_branch[branch] = read_json(Path(index['sessions'][sid]['path']), default={})
        branches = sorted(latest_by_branch.keys())
        comparisons = []
        for i in range(len(branches)):
            for j in range(i + 1, len(branches)):
                left = latest_by_branch[branches[i]]
                right = latest_by_branch[branches[j]]
                comparisons.append({
                    'left_branch': branches[i],'right_branch': branches[j],
                    'left_session_id': left.get('session_id'),'right_session_id': right.get('session_id'),
                    'same_route': left.get('chosen_route') == right.get('chosen_route'),
                    'same_task': left.get('task_type') == right.get('task_type'),
                    'confidence_gap': round(abs(left.get('route_confidence', 0) - right.get('route_confidence', 0)), 3),
                    'health_gap': round(abs(left.get('health_score', 0) - right.get('health_score', 0)), 3),
                    'deferred_gap': abs(left.get('deferred_item_count', 0) - right.get('deferred_item_count', 0)),
                    'module_overlap': len(set(left.get('active_modules', [])) & set(right.get('active_modules', []))),
                })
        data = {'project_id': self.project_id,'generated_at': now_iso(),'branch_latest_sessions': {k: {
                'session_id': v.get('session_id'),'task_type': v.get('task_type'),'chosen_route': v.get('chosen_route'),
                'route_confidence': v.get('route_confidence'),'health_score': v.get('health_score'),
                'deferred_item_count': v.get('deferred_item_count'),
            } for k, v in latest_by_branch.items()},'comparisons': comparisons}
        write_json(self.branch_compare_file, data)
        return data

    def branch_verdicts(self):
        compare = read_json(self.branch_compare_file, default={'comparisons': []})
        md_lines = ['# Branch Verdicts v3.3', '']
        txt_lines = ['Branch Verdicts v3.3', '']
        if not compare['comparisons']:
            msg = 'Only one branch is present, so no branch-to-branch verdict is available yet.'
            md_lines.append(msg); txt_lines.append(msg)
        else:
            for item in compare['comparisons']:
                if item['same_route'] and item['confidence_gap'] <= 0.1 and item['health_gap'] <= 0.1:
                    verdict = 'merge-friendly'; reason = 'same route, close confidence, close health'
                elif item['same_task'] and item['confidence_gap'] <= 0.25:
                    verdict = 'keep-under-review'; reason = 'same task but meaningful divergence remains'
                else:
                    verdict = 'keep-separated'; reason = 'different task/route profile'
                line = f"- {item['left_branch']} vs {item['right_branch']}: **{verdict}** — {reason}; confidence_gap={item['confidence_gap']}, health_gap={item['health_gap']}, deferred_gap={item['deferred_gap']}, module_overlap={item['module_overlap']}"
                md_lines.append(line); txt_lines.append(line.replace('**', ''))
        write_text(self.branch_verdict_md_file, '\n'.join(md_lines) + '\n')
        write_text(self.branch_verdict_txt_file, '\n'.join(txt_lines) + '\n')

    def build_dashboard(self):
        index = self.load_index()
        latest = self.latest_session()
        integrity = read_json(self.integrity_report_file, default={'ok': False,'problem_count': 999})
        compare = read_json(self.branch_compare_file, default={'comparisons': []})
        branch_status = []
        for branch, info in index['branches'].items():
            latest_sid = info.get('latest_session_id')
            latest_s = read_json(Path(index['sessions'][latest_sid]['path']), default={}) if latest_sid in index['sessions'] else {}
            branch_status.append({
                'branch': branch,'latest_session_id': latest_sid,'task_type': latest_s.get('task_type'),
                'chosen_route': latest_s.get('chosen_route'),'route_confidence': latest_s.get('route_confidence'),
                'health_score': latest_s.get('health_score'),'deferred_item_count': latest_s.get('deferred_item_count'),
                'session_count': len(info.get('session_ids', [])),
            })
        dashboard = {'project_id': self.project_id,'generated_at': now_iso(),'latest_session': latest,
                     'integrity': integrity,'branch_status': branch_status,'comparison_count': len(compare.get('comparisons', [])),
                     'audit_tail': index['audit_tail'][-8:]}
        write_json(self.runtime_dashboard_json, dashboard)
        txt = [
            f'Runtime Dashboard {VERSION}','',f'Project: {self.project_id}',
            f"Latest session: {latest.get('session_id') if latest else None}",
            f"Latest branch: {latest.get('branch') if latest else None}",
            f"Latest task: {latest.get('task_type') if latest else None}",
            f"Latest route: {latest.get('chosen_route') if latest else None}",
            f"Confidence: {latest.get('route_confidence') if latest else None}",
            f"Health: {latest.get('health_score') if latest else None}",
            f"Deferred: {latest.get('deferred_item_count') if latest else None}",
            f"Integrity ok: {integrity.get('ok')} ({integrity.get('problem_count')})",
            f"Branch count: {len(branch_status)}",
            f"Comparison count: {len(compare.get('comparisons', []))}",
            '', 'Branch Status:'
        ]
        for item in branch_status:
            txt.append(f"- {item['branch']} | latest={item['latest_session_id']} | task={item['task_type']} | route={item['chosen_route']} | conf={item['route_confidence']} | health={item['health_score']} | deferred={item['deferred_item_count']} | count={item['session_count']}")
        write_text(self.runtime_dashboard_txt, '\n'.join(txt) + '\n')
        md = ['# Runtime Dashboard v3.3', '']
        md.extend([
            f"- **Project:** {self.project_id}",
            f"- **Latest session:** `{latest.get('session_id') if latest else None}`",
            f"- **Latest branch:** `{latest.get('branch') if latest else None}`",
            f"- **Latest task:** `{latest.get('task_type') if latest else None}`",
            f"- **Latest route:** `{latest.get('chosen_route') if latest else None}`",
            f"- **Confidence:** `{latest.get('route_confidence') if latest else None}`",
            f"- **Health:** `{latest.get('health_score') if latest else None}`",
            f"- **Deferred:** `{latest.get('deferred_item_count') if latest else None}`",
            f"- **Integrity ok:** `{integrity.get('ok')}` (`{integrity.get('problem_count')}`)",
            '', '## Branch Status'
        ])
        for item in branch_status:
            md.append(f"- `{item['branch']}` — latest=`{item['latest_session_id']}` | task=`{item['task_type']}` | route=`{item['chosen_route']}` | conf=`{item['route_confidence']}` | health=`{item['health_score']}` | deferred=`{item['deferred_item_count']}` | count=`{item['session_count']}`")
        write_text(self.runtime_dashboard_md, '\n'.join(md) + '\n')

    def build_release_summary(self):
        latest = self.latest_session()
        integrity = read_json(self.integrity_report_file, default={'ok': False,'problem_count': 999})
        branch_compare = read_json(self.branch_compare_file, default={'comparisons': []})
        pressure = read_json(self.pressure_json, default={'pressure_signals': []})
        data = {
            'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'latest_session': latest,
            'integrity_ok': integrity.get('ok'),'problem_count': integrity.get('problem_count'),
            'comparison_count': len(branch_compare.get('comparisons', [])),
            'pressure_signal_count': len(pressure.get('pressure_signals', [])),
            'files': {
                'quick_report': str(self.quick_report_file),
                'dashboard_txt': str(self.runtime_dashboard_txt),
                'dashboard_md': str(self.runtime_dashboard_md),
                'dashboard_json': str(self.runtime_dashboard_json),
                'report_txt': str(self.report_txt),
                'report_md': str(self.report_md),
                'session_query_txt': str(self.session_query_txt),
                'session_query_json': str(self.session_query_json),
                'timeline_txt': str(self.timeline_txt),
                'timeline_json': str(self.timeline_json),
                'pressure_txt': str(self.pressure_txt),
                'pressure_json': str(self.pressure_json),
            }
        }
        write_json(self.release_summary_json, data)
        lines = [
            f'Release Summary {VERSION}',
            f'Project: {self.project_id}',
            f"Latest session: {latest.get('session_id') if latest else None}",
            f"Latest branch: {latest.get('branch') if latest else None}",
            f"Latest route: {latest.get('chosen_route') if latest else None}",
            f"Integrity ok: {integrity.get('ok')} ({integrity.get('problem_count')})",
            f"Comparisons: {len(branch_compare.get('comparisons', []))}",
            f"Pressure signals: {len(pressure.get('pressure_signals', []))}",
            '',
            f'Report TXT: {self.report_txt.name}',
            f'Report MD: {self.report_md.name}',
            f'Dashboard TXT: {self.runtime_dashboard_txt.name}',
            f'Query TXT: {self.session_query_txt.name}',
            f'Timeline TXT: {self.timeline_txt.name}',
            f'Pressure TXT: {self.pressure_txt.name}',
        ]
        write_text(self.release_summary_txt, '\n'.join(lines) + '\n')

    def create_checkpoint(self, label: str):
        index = self.load_index()
        latest = self.latest_session()
        payload = {
            'label': label,'created_at': now_iso(),'project_id': self.project_id,'latest_session': latest,
            'manifest': read_json(self.project_manifest_file, default={}),
            'integrity': read_json(self.integrity_report_file, default={}),
        }
        cp_path = self.checkpoint_path(label)
        write_json(cp_path, payload)
        index.setdefault('checkpoints', {})[slugify(label)] = {'label': label, 'path': str(cp_path), 'created_at': payload['created_at']}
        self.audit(index, 'checkpoint_saved', latest.get('session_id') if latest else None, latest.get('branch') if latest else None, latest.get('chosen_route') if latest else None, 'saved', {'label': label, 'path': str(cp_path)})
        self.save_index(index)
        return cp_path

    def build_query_results(self, task_type=None, route=None, branch=None, min_health=None, max_deferred=None):
        index = self.load_index()
        results = []
        for sid in sorted(index['sessions'].keys()):
            s = read_json(Path(index['sessions'][sid]['path']), default={})
            if task_type and s.get('task_type') != task_type:
                continue
            if route and s.get('chosen_route') != route:
                continue
            if branch and s.get('branch') != branch:
                continue
            if min_health is not None and (s.get('health_score') is None or float(s.get('health_score')) < float(min_health)):
                continue
            if max_deferred is not None and (s.get('deferred_item_count') is None or int(s.get('deferred_item_count')) > int(max_deferred)):
                continue
            results.append({
                'session_id': s.get('session_id'),
                'parent': s.get('parent'),
                'branch': s.get('branch'),
                'task_type': s.get('task_type'),
                'chosen_route': s.get('chosen_route'),
                'verification_armed': s.get('verification_armed'),
                'route_confidence': s.get('route_confidence'),
                'deferred_item_count': s.get('deferred_item_count'),
                'health_score': s.get('health_score'),
                'saved_at': s.get('saved_at'),
            })
        payload = {
            'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),
            'filters': {'task_type': task_type,'route': route,'branch': branch,'min_health': min_health,'max_deferred': max_deferred},
            'result_count': len(results),'results': results,
        }
        write_json(self.session_query_json, payload)
        lines = [
            f"Session Query {VERSION}",
            f"Project: {self.project_id}",
            f"Filters: task_type={task_type}, route={route}, branch={branch}, min_health={min_health}, max_deferred={max_deferred}",
            f"Result count: {len(results)}",
            ""
        ]
        for r in results:
            lines.append(f"- {r['session_id']} | branch={r['branch']} | task={r['task_type']} | route={r['chosen_route']} | health={r['health_score']} | deferred={r['deferred_item_count']} | conf={r['route_confidence']} | saved_at={r['saved_at']}")
        write_text(self.session_query_txt, '\n'.join(lines) + '\n')
        return payload

    def build_timeline(self):
        index = self.load_index()
        entries = []
        for sid in sorted(index['sessions'].keys()):
            s = read_json(Path(index['sessions'][sid]['path']), default={})
            entries.append({
                'type': 'session','timestamp': s.get('saved_at'),'session_id': s.get('session_id'),
                'parent': s.get('parent'),'branch': s.get('branch'),'task_type': s.get('task_type'),
                'chosen_route': s.get('chosen_route'),'health_score': s.get('health_score'),
                'deferred_item_count': s.get('deferred_item_count'),
            })
        for a in index.get('audit_tail', []):
            entries.append({
                'type': 'audit','timestamp': a.get('timestamp'),'event_type': a.get('event_type'),
                'session_id': a.get('session_id'),'branch_label': a.get('branch_label'),
                'route_name': a.get('route_name'),'outcome': a.get('outcome'),
            })
        entries = sorted(entries, key=lambda x: (x.get('timestamp') or '', x.get('type') or ''))
        payload = {'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'entry_count': len(entries),'entries': entries}
        write_json(self.timeline_json, payload)
        lines = [f"History Timeline {VERSION}", f"Project: {self.project_id}", f"Entry count: {len(entries)}", ""]
        for e in entries:
            if e['type'] == 'session':
                lines.append(f"- SESSION | {e.get('timestamp')} | {e.get('session_id')} | parent={e.get('parent')} | branch={e.get('branch')} | task={e.get('task_type')} | route={e.get('chosen_route')} | health={e.get('health_score')} | deferred={e.get('deferred_item_count')}")
            else:
                lines.append(f"- AUDIT | {e.get('timestamp')} | event={e.get('event_type')} | session={e.get('session_id')} | branch={e.get('branch_label')} | route={e.get('route_name')} | outcome={e.get('outcome')}")
        write_text(self.timeline_txt, '\n'.join(lines) + '\n')
        md = ['# History Timeline v3.3', '', f'- **Project:** {self.project_id}', f'- **Entry count:** `{len(entries)}`', '', '## Entries']
        for e in entries:
            if e['type'] == 'session':
                md.append(f"- `SESSION` | `{e.get('timestamp')}` | `{e.get('session_id')}` | parent=`{e.get('parent')}` | branch=`{e.get('branch')}` | task=`{e.get('task_type')}` | route=`{e.get('chosen_route')}` | health=`{e.get('health_score')}` | deferred=`{e.get('deferred_item_count')}`")
            else:
                md.append(f"- `AUDIT` | `{e.get('timestamp')}` | event=`{e.get('event_type')}` | session=`{e.get('session_id')}` | branch=`{e.get('branch_label')}` | route=`{e.get('route_name')}` | outcome=`{e.get('outcome')}`")
        write_text(self.timeline_md, '\n'.join(md) + '\n')
        return payload

    def build_pressure_signals(self):
        index = self.load_index()
        signals = []
        for sid in sorted(index['sessions'].keys()):
            s = read_json(Path(index['sessions'][sid]['path']), default={})
            pressure_score = round(float(s.get('route_confidence', 0)) + float(s.get('health_score', 0)) + (0.2 * int(s.get('deferred_item_count', 0))), 3)
            level = 'low'
            if pressure_score >= 1.7:
                level = 'high'
            elif pressure_score >= 1.1:
                level = 'medium'
            signals.append({
                'session_id': s.get('session_id'),
                'branch': s.get('branch'),
                'task_type': s.get('task_type'),
                'chosen_route': s.get('chosen_route'),
                'route_confidence': s.get('route_confidence'),
                'health_score': s.get('health_score'),
                'deferred_item_count': s.get('deferred_item_count'),
                'pressure_score': pressure_score,
                'pressure_level': level,
                'saved_at': s.get('saved_at'),
            })
        payload = {
            'version': VERSION,
            'project_id': self.project_id,
            'generated_at': now_iso(),
            'pressure_signals': signals,
        }
        write_json(self.pressure_json, payload)
        lines = [f"Pressure Signals {VERSION}", f"Project: {self.project_id}", f"Signal count: {len(signals)}", ""]
        for s in signals:
            lines.append(
                f"- {s['session_id']} | branch={s['branch']} | task={s['task_type']} | route={s['chosen_route']} | "
                f"conf={s['route_confidence']} | health={s['health_score']} | deferred={s['deferred_item_count']} | "
                f"pressure={s['pressure_score']} | level={s['pressure_level']}"
            )
        write_text(self.pressure_txt, '\n'.join(lines) + '\n')
        md = ['# Pressure Signals v3.3', '', f'- **Project:** {self.project_id}', f'- **Signal count:** `{len(signals)}`', '', '## Signals']
        for s in signals:
            md.append(
                f"- `{s['session_id']}` — branch=`{s['branch']}` | task=`{s['task_type']}` | route=`{s['chosen_route']}` | "
                f"conf=`{s['route_confidence']}` | health=`{s['health_score']}` | deferred=`{s['deferred_item_count']}` | "
                f"pressure=`{s['pressure_score']}` | level=`{s['pressure_level']}`"
            )
        write_text(self.pressure_md, '\n'.join(md) + '\n')
        return payload

    def build_upload_reports(self):
        compact = read_json(self.compact_handoff_file, default={})
        latest = compact.get('latest_session') or {}
        txt_lines = [
            f"Project: {compact.get('project_id')}",
            f"Session count: {compact.get('session_count')}",
            f"Integrity ok: {compact.get('integrity_ok')}",
            f"Problem count: {compact.get('problem_count')}",
            f"Latest session: {latest.get('session_id')}",
            f"Branch: {latest.get('branch')}",
            f"Task type: {latest.get('task_type')}",
            f"Route: {latest.get('chosen_route')}",
            f"Confidence: {latest.get('route_confidence')}",
            f"Health: {latest.get('health_score')}",
            f"Deferred: {latest.get('deferred_item_count')}",
            '',
            'V3.3 features:',
            '- pressure signals',
            '- session pressure scoring',
            '- pressure export txt / json / md',
        ]
        write_text(self.report_txt, '\n'.join(txt_lines) + '\n')
        write_text(self.report_md, '# Report v3.3\n\n' + '\n'.join(f'- {line}' for line in txt_lines if line.strip()) + '\n')

    def build_zip(self):
        self.pack_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_export_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(self.project_dir):
                for name in files:
                    p = Path(root) / name
                    zf.write(p, p.relative_to(self.pack_root))

    def build_all_reports(self):
        self.integrity_check()
        self.build_manifest()
        self.build_compact_handoff()
        self.build_quick_resume_pack()
        self.build_summary_pack()
        self.build_archive_summary()
        self.compare_branches()
        self.branch_verdicts()
        self.build_dashboard()
        self.build_query_results()
        self.build_timeline()
        self.build_pressure_signals()
        self.build_release_summary()
        self.build_upload_reports()
        self.build_zip()

    def print_summary(self, session, root_created):
        print('=== MORPH Runtime Core v3.3 / Summary ===')
        print(f'Project:        {self.project_id}')
        print(f'Root created:   {root_created}')
        print('Root session:   session_001')
        print(f'Saved session:  {session["session_id"]}')
        print(f'Branch used:    {session["branch"]}')
        print(f'Task type:      {session["task_type"]}')
        print(f'Chosen route:   {session["chosen_route"]}')
        print(f'Session file:   {self.session_path(session["session_id"])}')
        print(f'Report txt:     {self.report_txt}')
        print(f'Report md:      {self.report_md}')
        print(f'Pressure txt:   {self.pressure_txt}')
        print(f'Pressure md:    {self.pressure_md}')
        print(f'Pressure json:  {self.pressure_json}')
        print(f'ZIP export:     {self.zip_export_file}')
        print()
        print('=== Status Snapshot ===')
        print(json.dumps({
            'session_id': session['session_id'],'parent': session['parent'],'branch': session['branch'],
            'task_type': session['task_type'],'chosen_route': session['chosen_route'],
            'verification_armed': session['verification_armed'],'route_confidence': session['route_confidence'],
            'deferred_item_count': session['deferred_item_count'],'health_score': session['health_score'],
            'saved_at': session['saved_at'],
        }, indent=2))

    def cli(self):
        parser = argparse.ArgumentParser(description='MORPH Runtime Core v3.3')
        parser.add_argument('--fresh-if-missing', action='store_true')
        parser.add_argument('--append-task', choices=['math', 'simple'])
        parser.add_argument('--resume-session')
        parser.add_argument('--branch', default='main')
        parser.add_argument('--report-only', action='store_true')
        parser.add_argument('--checkpoint-label')
        parser.add_argument('--query-sessions', action='store_true')
        parser.add_argument('--filter-task', choices=['math', 'simple'])
        parser.add_argument('--filter-route')
        parser.add_argument('--filter-branch')
        parser.add_argument('--min-health', type=float)
        parser.add_argument('--max-deferred', type=int)
        parser.add_argument('--timeline-only', action='store_true')
        parser.add_argument('--pressure-only', action='store_true')
        args = parser.parse_args()

        if args.report_only:
            self.init_pack()
            self.build_all_reports()
            print('Reports rebuilt.')
            print(self.report_txt)
            print(self.report_md)
            print(self.pressure_txt)
            print(self.pressure_md)
            print(self.release_summary_txt)
            return

        if args.timeline_only:
            self.init_pack()
            payload = self.build_timeline()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.timeline_txt)
            print(self.timeline_json)
            return

        if args.pressure_only:
            self.init_pack()
            payload = self.build_pressure_signals()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.pressure_txt)
            print(self.pressure_json)
            return

        if args.checkpoint_label:
            self.init_pack()
            self.build_all_reports()
            cp = self.create_checkpoint(args.checkpoint_label)
            print(f'Checkpoint saved: {cp}')
            return

        if args.query_sessions:
            self.init_pack()
            payload = self.build_query_results(
                task_type=args.filter_task,
                route=args.filter_route,
                branch=args.filter_branch,
                min_health=args.min_health,
                max_deferred=args.max_deferred,
            )
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.session_query_txt)
            print(self.session_query_json)
            return

        if args.fresh_if_missing or args.append_task:
            task_type = args.append_task or 'math'
            session, root_created = self.append_task(task_type=task_type, branch_label=args.branch, resume_session=args.resume_session)
            self.print_summary(session, root_created)
            return

        parser.print_help()

def main():
    MorphRuntimeCoreV33(Path.cwd()).cli()

if __name__ == '__main__':
    main()
