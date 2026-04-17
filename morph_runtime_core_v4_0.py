#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, zipfile, os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = 'v4.0'
PACK_ROOT_NAME = 'morph_runtime_core_v4_0'
DEFAULT_PROJECT_ID = 'project_math_lab'

MODULES_BY_TASK = {
    'math': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'RecoveryEngine','AutoRepairBasic','OrphanHandler','ComparativeResumeEngine','HandoffExporter',
        'QuickResumePack','SummaryPackBuilder','PackValidator','IntegrityGuard','FabricOrchestratorV40',
        'MergeIntelligenceEngine','CompareModesEngine','BranchVerdictEngine','StateInspector','RuntimeDashboardBuilder',
        'CheckpointManager','ReleaseReportBuilder','SnapshotExporter','SessionQueryEngine','HistoryTimelineBuilder',
        'PressureSignalBuilder','DriftNotesBuilder','CheckpointDiffBuilder','CheckpointRegistryBuilder',
        'CheckpointLineageBuilder','CheckpointChainComparer','BestCheckpointSelector','CheckpointLeaderboardBuilder',
        'RegressionDetector','AnomalyDetector','TrendDetector','SmartResumeEngine','NextBestActionEngine'
    ],
    'simple': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'RecoveryEngine','AutoRepairBasic','OrphanHandler','ComparativeResumeEngine','HandoffExporter',
        'QuickResumePack','SummaryPackBuilder','PackValidator','IntegrityGuard','FabricOrchestratorV40',
        'MergeIntelligenceEngine','CompareModesEngine','BranchVerdictEngine','StateInspector','RuntimeDashboardBuilder',
        'CheckpointManager','ReleaseReportBuilder','SnapshotExporter','SessionQueryEngine','HistoryTimelineBuilder',
        'PressureSignalBuilder','DriftNotesBuilder','CheckpointDiffBuilder','CheckpointRegistryBuilder',
        'CheckpointLineageBuilder','CheckpointChainComparer','BestCheckpointSelector','CheckpointLeaderboardBuilder',
        'RegressionDetector','AnomalyDetector','TrendDetector','SmartResumeEngine','NextBestActionEngine'
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

class MorphRuntimeCoreV40:
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
        self.report_txt = self.project_dir / 'report_v4.0.txt'
        self.report_md = self.project_dir / 'report_v4.0.md'
        self.release_summary_txt = self.project_dir / 'release_summary_v4_0.txt'
        self.release_summary_json = self.project_dir / 'release_summary_v4_0.json'
        self.regression_txt = self.project_dir / 'regression_report_v4_0.txt'
        self.regression_json = self.project_dir / 'regression_report_v4_0.json'
        self.anomaly_txt = self.project_dir / 'anomaly_report_v4_0.txt'
        self.anomaly_json = self.project_dir / 'anomaly_report_v4_0.json'
        self.trend_txt = self.project_dir / 'trend_report_v4_0.txt'
        self.trend_json = self.project_dir / 'trend_report_v4_0.json'
        self.checkpoint_registry_txt = self.project_dir / 'checkpoint_registry_v4_0.txt'
        self.checkpoint_registry_json = self.project_dir / 'checkpoint_registry_v4_0.json'
        self.best_checkpoint_txt = self.project_dir / 'best_checkpoint_v4_0.txt'
        self.best_checkpoint_json = self.project_dir / 'best_checkpoint_v4_0.json'
        self.leaderboard_txt = self.project_dir / 'checkpoint_leaderboard_v4_0.txt'
        self.leaderboard_json = self.project_dir / 'checkpoint_leaderboard_v4_0.json'
        self.resume_txt = self.project_dir / 'smart_resume_v4_0.txt'
        self.resume_json = self.project_dir / 'smart_resume_v4_0.json'
        self.resume_md = self.project_dir / 'smart_resume_v4_0.md'
        self.next_action_txt = self.project_dir / 'next_best_action_v4_0.txt'
        self.next_action_json = self.project_dir / 'next_best_action_v4_0.json'
        self.next_action_md = self.project_dir / 'next_best_action_v4_0.md'
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
        index['audit_tail'] = index['audit_tail'][-40:]

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
            'resume_main': f"python morph_runtime_core_v4_0.py --append-task math --resume-session {latest['session_id']}" if latest else None,
            'resume_simple': "python morph_runtime_core_v4_0.py --append-task simple --branch simple_track" if latest else None,
        }
        write_json(self.compact_handoff_file, data)
        return data

    def build_quick_resume_pack(self):
        index = self.load_index()
        latest = self.latest_session()
        data = {
            'project_id': self.project_id,'latest_session_id': latest.get('session_id') if latest else None,
            'main_resume': f"python morph_runtime_core_v4_0.py --append-task math --resume-session {latest['session_id']}" if latest and latest['task_type'] == 'math' else None,
            'simple_resume': "python morph_runtime_core_v4_0.py --append-task simple --branch simple_track",
            'checkpoint_create': "python morph_runtime_core_v4_0.py --checkpoint-label stable_v4_0",
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

    def build_checkpoint_registry(self):
        index = self.load_index()
        items = sorted(index.get('checkpoints', {}).items(), key=lambda x: x[1]['created_at'])
        entries = []
        for key, meta in items:
            cp = read_json(Path(meta['path']), default={})
            latest = cp.get('latest_session') or {}
            entries.append({
                'key': key,'label': meta['label'],'created_at': meta['created_at'],'path': meta['path'],
                'session_id': latest.get('session_id'),'branch': latest.get('branch'),'task_type': latest.get('task_type'),
                'route': latest.get('chosen_route'),'confidence': latest.get('route_confidence'),
                'health': latest.get('health_score'),'deferred': latest.get('deferred_item_count'),
            })
        payload = {'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'checkpoint_count': len(entries),'checkpoints': entries}
        write_json(self.checkpoint_registry_json, payload)
        lines = [f"Checkpoint Registry {VERSION}", f"Project: {self.project_id}", f"Checkpoint count: {len(entries)}", ""]
        for e in entries:
            lines.append(f"- {e['label']} | created_at={e['created_at']} | session={e['session_id']} | branch={e['branch']} | task={e['task_type']} | route={e['route']} | conf={e['confidence']} | health={e['health']} | deferred={e['deferred']}")
        write_text(self.checkpoint_registry_txt, '\n'.join(lines) + '\n')
        return payload

    def _checkpoint_score(self, entry):
        health = float(entry.get('health') or 0)
        conf = float(entry.get('confidence') or 0)
        deferred = int(entry.get('deferred') or 0)
        return round((health * 100) + (conf * 50) - (deferred * 10), 3)

    def build_best_checkpoint(self):
        registry = read_json(self.checkpoint_registry_json, default={'checkpoints': []})
        entries = registry.get('checkpoints', [])
        best = None
        if entries:
            enriched = []
            for e in entries:
                x = dict(e); x['score'] = self._checkpoint_score(x); enriched.append(x)
            best = max(enriched, key=lambda e: (e['score'], float(e.get('health') or 0), float(e.get('confidence') or 0), -(int(e.get('deferred') or 0)), e.get('created_at') or ''))
        payload = {'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'best_checkpoint': best,'checkpoint_count': len(entries)}
        write_json(self.best_checkpoint_json, payload)
        if best is None:
            txt = f"Best Checkpoint {VERSION}\nProject: {self.project_id}\nNo checkpoints available.\n"
        else:
            txt = "\n".join([
                f"Best Checkpoint {VERSION}",f"Project: {self.project_id}",f"Label: {best['label']}",f"Session: {best['session_id']}",
                f"Branch: {best['branch']}",f"Task: {best['task_type']}",f"Route: {best['route']}",
                f"Confidence: {best['confidence']}",f"Health: {best['health']}",f"Deferred: {best['deferred']}",f"Score: {best['score']}",
                f"Created at: {best['created_at']}",
            ]) + "\n"
        write_text(self.best_checkpoint_txt, txt)
        return payload

    def build_leaderboard(self):
        registry = read_json(self.checkpoint_registry_json, default={'checkpoints': []})
        entries = registry.get('checkpoints', [])
        leaderboard = []
        for e in entries:
            x = dict(e); x['score'] = self._checkpoint_score(x); leaderboard.append(x)
        leaderboard.sort(key=lambda e: (e['score'], float(e.get('health') or 0), float(e.get('confidence') or 0), -(int(e.get('deferred') or 0))), reverse=True)
        best_per_branch = {}
        best_per_task = {}
        for e in leaderboard:
            best_per_branch.setdefault(e['branch'], e['label'])
            best_per_task.setdefault(e['task_type'], e['label'])
        payload = {'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'checkpoint_count': len(leaderboard),'leaderboard': leaderboard,'best_per_branch': best_per_branch,'best_per_task': best_per_task}
        write_json(self.leaderboard_json, payload)
        lines = [f"Checkpoint Leaderboard {VERSION}", f"Project: {self.project_id}", f"Checkpoint count: {len(leaderboard)}", ""]
        for i, e in enumerate(leaderboard, start=1):
            lines.append(f"{i}. {e['label']} | score={e['score']} | branch={e['branch']} | task={e['task_type']} | route={e['route']} | conf={e['confidence']} | health={e['health']} | deferred={e['deferred']}")
        lines.extend(["", "Best per branch:"])
        for k, v in best_per_branch.items():
            lines.append(f"- {k}: {v}")
        lines.extend(["", "Best per task:"])
        for k, v in best_per_task.items():
            lines.append(f"- {k}: {v}")
        write_text(self.leaderboard_txt, '\n'.join(lines) + '\n')
        return payload

    def build_regression_report(self):
        index = self.load_index()
        findings = []
        for branch, info in index['branches'].items():
            sids = info.get('session_ids', [])
            if len(sids) < 2:
                findings.append({'branch': branch, 'verdict': 'insufficient_history'})
                continue
            first = read_json(Path(index['sessions'][sids[0]]['path']), default={})
            last = read_json(Path(index['sessions'][sids[-1]]['path']), default={})
            confidence_delta = round(float(last.get('route_confidence', 0) or 0) - float(first.get('route_confidence', 0) or 0), 3)
            health_delta = round(float(last.get('health_score', 0) or 0) - float(first.get('health_score', 0) or 0), 3)
            deferred_delta = int(last.get('deferred_item_count', 0) or 0) - int(first.get('deferred_item_count', 0) or 0)
            if health_delta < 0 or confidence_delta < 0 or deferred_delta > 0:
                verdict = 'regression-risk'
            else:
                verdict = 'no-regression'
            findings.append({
                'branch': branch,'start_session_id': first.get('session_id'),'end_session_id': last.get('session_id'),
                'confidence_delta': confidence_delta,'health_delta': health_delta,'deferred_delta': deferred_delta,'verdict': verdict
            })
        payload = {'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'findings': findings}
        write_json(self.regression_json, payload)
        lines = [f"Regression Report {VERSION}", f"Project: {self.project_id}", f"Branch count: {len(findings)}", ""]
        for f in findings:
            if f.get('verdict') == 'insufficient_history':
                lines.append(f"- {f['branch']} | verdict=insufficient_history")
            else:
                lines.append(f"- {f['branch']} | start={f['start_session_id']} | end={f['end_session_id']} | confidence_delta={f['confidence_delta']} | health_delta={f['health_delta']} | deferred_delta={f['deferred_delta']} | verdict={f['verdict']}")
        write_text(self.regression_txt, '\n'.join(lines) + '\n')
        return payload

    def build_anomaly_report(self):
        index = self.load_index()
        anomalies = []
        for sid in sorted(index['sessions'].keys()):
            s = read_json(Path(index['sessions'][sid]['path']), default={})
            reasons = []
            health = float(s.get('health_score', 0) or 0)
            conf = float(s.get('route_confidence', 0) or 0)
            deferred = int(s.get('deferred_item_count', 0) or 0)
            if health < 0.5:
                reasons.append('low_health')
            if conf < 0.4:
                reasons.append('low_confidence')
            if deferred >= 3:
                reasons.append('high_deferred')
            if reasons:
                anomalies.append({
                    'session_id': s.get('session_id'),'branch': s.get('branch'),'task_type': s.get('task_type'),
                    'route': s.get('chosen_route'),'health': health,'confidence': conf,'deferred': deferred,'reasons': reasons
                })
        payload = {'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'anomaly_count': len(anomalies),'anomalies': anomalies}
        write_json(self.anomaly_json, payload)
        lines = [f"Anomaly Report {VERSION}", f"Project: {self.project_id}", f"Anomaly count: {len(anomalies)}", ""]
        for a in anomalies:
            lines.append(f"- {a['session_id']} | branch={a['branch']} | task={a['task_type']} | route={a['route']} | health={a['health']} | confidence={a['confidence']} | deferred={a['deferred']} | reasons={','.join(a['reasons'])}")
        write_text(self.anomaly_txt, '\n'.join(lines) + '\n')
        return payload

    def build_trend_report(self):
        index = self.load_index()
        trends = []
        for branch, info in index['branches'].items():
            sids = info.get('session_ids', [])
            if len(sids) < 2:
                trends.append({'branch': branch, 'trend': 'flat', 'reason': 'insufficient_history'})
                continue
            first = read_json(Path(index['sessions'][sids[0]]['path']), default={})
            last = read_json(Path(index['sessions'][sids[-1]]['path']), default={})
            confidence_delta = round(float(last.get('route_confidence', 0) or 0) - float(first.get('route_confidence', 0) or 0), 3)
            health_delta = round(float(last.get('health_score', 0) or 0) - float(first.get('health_score', 0) or 0), 3)
            deferred_delta = int(last.get('deferred_item_count', 0) or 0) - int(first.get('deferred_item_count', 0) or 0)
            if health_delta > 0 and confidence_delta >= 0 and deferred_delta <= 0:
                trend = 'improving'
            elif health_delta < 0 or confidence_delta < 0 or deferred_delta > 0:
                trend = 'declining'
            else:
                trend = 'stable'
            trends.append({
                'branch': branch,'start_session_id': first.get('session_id'),'end_session_id': last.get('session_id'),
                'confidence_delta': confidence_delta,'health_delta': health_delta,'deferred_delta': deferred_delta,'trend': trend
            })
        payload = {'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'trends': trends}
        write_json(self.trend_json, payload)
        lines = [f"Trend Report {VERSION}", f"Project: {self.project_id}", f"Branch count: {len(trends)}", ""]
        for t in trends:
            if t.get('reason') == 'insufficient_history':
                lines.append(f"- {t['branch']} | trend=flat | reason=insufficient_history")
            else:
                lines.append(f"- {t['branch']} | start={t['start_session_id']} | end={t['end_session_id']} | confidence_delta={t['confidence_delta']} | health_delta={t['health_delta']} | deferred_delta={t['deferred_delta']} | trend={t['trend']}")
        write_text(self.trend_txt, '\n'.join(lines) + '\n')
        return payload

    def build_smart_resume(self):
        index = self.load_index()
        best_checkpoint = read_json(self.best_checkpoint_json, default={'best_checkpoint': None}).get('best_checkpoint')
        regressions = read_json(self.regression_json, default={'findings': []}).get('findings', [])
        anomalies = read_json(self.anomaly_json, default={'anomalies': []}).get('anomalies', [])
        trends = read_json(self.trend_json, default={'trends': []}).get('trends', [])
        latest = self.latest_session()

        branch_priority = []
        for branch, info in index.get('branches', {}).items():
            latest_sid = info.get('latest_session_id')
            latest_s = read_json(Path(index['sessions'][latest_sid]['path']), default={}) if latest_sid in index['sessions'] else {}
            trend = next((t for t in trends if t.get('branch') == branch), {})
            regression = next((r for r in regressions if r.get('branch') == branch), {})
            anomaly_count = sum(1 for a in anomalies if a.get('branch') == branch)
            score = round(
                (float(latest_s.get('health_score', 0) or 0) * 100) +
                (float(latest_s.get('route_confidence', 0) or 0) * 50) -
                (int(latest_s.get('deferred_item_count', 0) or 0) * 10) -
                (anomaly_count * 15) -
                (25 if regression.get('verdict') == 'regression-risk' else 0) +
                (10 if trend.get('trend') == 'improving' else 0),
                3
            )
            branch_priority.append({
                'branch': branch,
                'latest_session_id': latest_sid,
                'task_type': latest_s.get('task_type'),
                'route': latest_s.get('chosen_route'),
                'health': latest_s.get('health_score'),
                'confidence': latest_s.get('route_confidence'),
                'deferred': latest_s.get('deferred_item_count'),
                'trend': trend.get('trend'),
                'regression_verdict': regression.get('verdict'),
                'anomaly_count': anomaly_count,
                'resume_score': score,
            })
        branch_priority.sort(key=lambda x: x['resume_score'], reverse=True)

        recommended = branch_priority[0] if branch_priority else None
        recommendation_type = 'latest_session'
        recommendation_value = latest.get('session_id') if latest else None
        if recommended and recommended.get('latest_session_id'):
            recommendation_value = recommended['latest_session_id']
        if best_checkpoint:
            recommendation_type = 'best_checkpoint'
            recommendation_value = best_checkpoint.get('label')

        summary = {
            'version': VERSION,
            'project_id': self.project_id,
            'generated_at': now_iso(),
            'recommendation_type': recommendation_type,
            'recommendation_value': recommendation_value,
            'recommended_branch': recommended.get('branch') if recommended else None,
            'recommended_session_id': recommended.get('latest_session_id') if recommended else None,
            'recommended_score': recommended.get('resume_score') if recommended else None,
            'best_checkpoint_label': best_checkpoint.get('label') if best_checkpoint else None,
            'branch_priority': branch_priority,
            'resume_command': None,
        }
        if recommendation_type == 'best_checkpoint' and recommended:
            task = recommended.get('task_type') or 'math'
            sess = recommended.get('latest_session_id')
            if task in ('math', 'simple') and sess:
                if recommended.get('branch') == 'main':
                    summary['resume_command'] = f'python morph_runtime_core_v4_0.py --append-task {task} --resume-session {sess}'
                else:
                    summary['resume_command'] = f'python morph_runtime_core_v4_0.py --append-task {task} --resume-session {sess} --branch {recommended.get("branch")}'
        elif recommended:
            task = recommended.get('task_type') or 'math'
            sess = recommended.get('latest_session_id')
            if task in ('math', 'simple') and sess:
                if recommended.get('branch') == 'main':
                    summary['resume_command'] = f'python morph_runtime_core_v4_0.py --append-task {task} --resume-session {sess}'
                else:
                    summary['resume_command'] = f'python morph_runtime_core_v4_0.py --append-task {task} --resume-session {sess} --branch {recommended.get("branch")}'

        write_json(self.resume_json, summary)
        lines = [
            f"Smart Resume {VERSION}",
            f"Project: {self.project_id}",
            f"Recommendation type: {summary['recommendation_type']}",
            f"Recommendation value: {summary['recommendation_value']}",
            f"Recommended branch: {summary['recommended_branch']}",
            f"Recommended session: {summary['recommended_session_id']}",
            f"Recommended score: {summary['recommended_score']}",
            f"Best checkpoint label: {summary['best_checkpoint_label']}",
            f"Resume command: {summary['resume_command']}",
            "",
            "Branch priority:"
        ]
        for b in branch_priority:
            lines.append(f"- {b['branch']} | session={b['latest_session_id']} | task={b['task_type']} | route={b['route']} | trend={b['trend']} | regression={b['regression_verdict']} | anomalies={b['anomaly_count']} | score={b['resume_score']}")
        write_text(self.resume_txt, '\n'.join(lines) + '\n')
        md = ['# Smart Resume v4.0', '',
              f"- **Project:** {self.project_id}",
              f"- **Recommendation type:** `{summary['recommendation_type']}`",
              f"- **Recommendation value:** `{summary['recommendation_value']}`",
              f"- **Recommended branch:** `{summary['recommended_branch']}`",
              f"- **Recommended session:** `{summary['recommended_session_id']}`",
              f"- **Recommended score:** `{summary['recommended_score']}`",
              f"- **Best checkpoint label:** `{summary['best_checkpoint_label']}`",
              f"- **Resume command:** `{summary['resume_command']}`",
              '', '## Branch priority']
        for b in branch_priority:
            md.append(f"- `{b['branch']}` — session=`{b['latest_session_id']}` | task=`{b['task_type']}` | route=`{b['route']}` | trend=`{b['trend']}` | regression=`{b['regression_verdict']}` | anomalies=`{b['anomaly_count']}` | score=`{b['resume_score']}`")
        write_text(self.resume_md, '\n'.join(md) + '\n')
        return summary

    def build_next_best_action(self):
        resume = read_json(self.resume_json, default={})
        regression = read_json(self.regression_json, default={'findings': []}).get('findings', [])
        anomalies = read_json(self.anomaly_json, default={'anomalies': []}).get('anomalies', [])
        trends = read_json(self.trend_json, default={'trends': []}).get('trends', [])

        actions = []
        if anomalies:
            actions.append({
                'priority': 1,
                'action': 'investigate_anomalies',
                'reason': f'{len(anomalies)} anomaly items detected',
                'suggested_command': 'python morph_runtime_core_v4_0.py --anomaly-only'
            })
        if any(r.get('verdict') == 'regression-risk' for r in regression):
            actions.append({
                'priority': 2,
                'action': 'review_regression_risk',
                'reason': 'one or more branches show regression risk',
                'suggested_command': 'python morph_runtime_core_v4_0.py --regression-only'
            })
        if any(t.get('trend') == 'declining' for t in trends):
            actions.append({
                'priority': 3,
                'action': 'stabilize_declining_branch',
                'reason': 'one or more branches are declining',
                'suggested_command': 'python morph_runtime_core_v4_0.py --trend-only'
            })
        if resume.get('resume_command'):
            actions.append({
                'priority': 4 if actions else 1,
                'action': 'resume_recommended_branch',
                'reason': 'best available continuation path',
                'suggested_command': resume.get('resume_command')
            })
        if not actions:
            actions.append({
                'priority': 1,
                'action': 'create_checkpoint',
                'reason': 'system is stable and no issues were detected',
                'suggested_command': 'python morph_runtime_core_v4_0.py --checkpoint-label stable_v4_0'
            })

        payload = {
            'version': VERSION,
            'project_id': self.project_id,
            'generated_at': now_iso(),
            'recommended_action': actions[0],
            'actions': actions,
        }
        write_json(self.next_action_json, payload)
        lines = [
            f"Next Best Action {VERSION}",
            f"Project: {self.project_id}",
            f"Recommended action: {actions[0]['action']}",
            f"Reason: {actions[0]['reason']}",
            f"Suggested command: {actions[0]['suggested_command']}",
            "",
            "Action queue:"
        ]
        for a in actions:
            lines.append(f"- p{a['priority']} | {a['action']} | reason={a['reason']} | cmd={a['suggested_command']}")
        write_text(self.next_action_txt, '\n'.join(lines) + '\n')
        md = ['# Next Best Action v4.0', '',
              f"- **Project:** {self.project_id}",
              f"- **Recommended action:** `{actions[0]['action']}`",
              f"- **Reason:** `{actions[0]['reason']}`",
              f"- **Suggested command:** `{actions[0]['suggested_command']}`",
              '', '## Action queue']
        for a in actions:
            md.append(f"- `p{a['priority']}` | `{a['action']}` | reason=`{a['reason']}` | cmd=`{a['suggested_command']}`")
        write_text(self.next_action_md, '\n'.join(md) + '\n')
        return payload

    def build_release_summary(self):
        latest = self.latest_session()
        integrity = read_json(self.integrity_report_file, default={'ok': False,'problem_count': 999})
        checkpoint_registry = read_json(self.checkpoint_registry_json, default={'checkpoint_count': 0})
        best_checkpoint = read_json(self.best_checkpoint_json, default={'best_checkpoint': None})
        leaderboard = read_json(self.leaderboard_json, default={'checkpoint_count': 0})
        regression = read_json(self.regression_json, default={'findings': []})
        anomalies = read_json(self.anomaly_json, default={'anomaly_count': 0})
        trends = read_json(self.trend_json, default={'trends': []})
        resume = read_json(self.resume_json, default={})
        action = read_json(self.next_action_json, default={})
        data = {
            'version': VERSION,'project_id': self.project_id,'generated_at': now_iso(),'latest_session': latest,
            'integrity_ok': integrity.get('ok'),'problem_count': integrity.get('problem_count'),
            'checkpoint_count': checkpoint_registry.get('checkpoint_count', 0),
            'best_checkpoint_label': (best_checkpoint.get('best_checkpoint') or {}).get('label'),
            'leaderboard_count': leaderboard.get('checkpoint_count', 0),
            'anomaly_count': anomalies.get('anomaly_count', 0),
            'regression_branch_count': len(regression.get('findings', [])),
            'trend_branch_count': len(trends.get('trends', [])),
            'resume_recommendation': resume.get('recommendation_value'),
            'next_action': (action.get('recommended_action') or {}).get('action'),
        }
        write_json(self.release_summary_json, data)
        lines = [
            f'Release Summary {VERSION}',
            f'Project: {self.project_id}',
            f"Latest session: {latest.get('session_id') if latest else None}",
            f"Latest branch: {latest.get('branch') if latest else None}",
            f"Latest route: {latest.get('chosen_route') if latest else None}",
            f"Integrity ok: {integrity.get('ok')} ({integrity.get('problem_count')})",
            f"Checkpoint count: {checkpoint_registry.get('checkpoint_count', 0)}",
            f"Best checkpoint: {(best_checkpoint.get('best_checkpoint') or {}).get('label')}",
            f"Leaderboard count: {leaderboard.get('checkpoint_count', 0)}",
            f"Anomaly count: {anomalies.get('anomaly_count', 0)}",
            f"Regression branch count: {len(regression.get('findings', []))}",
            f"Trend branch count: {len(trends.get('trends', []))}",
            f"Resume recommendation: {resume.get('recommendation_value')}",
            f"Next action: {(action.get('recommended_action') or {}).get('action')}",
            '',
            f'Report TXT: {self.report_txt.name}',
            f'Smart Resume TXT: {self.resume_txt.name}',
            f'Next Best Action TXT: {self.next_action_txt.name}',
        ]
        write_text(self.release_summary_txt, '\n'.join(lines) + '\n')

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
            'V4.0 features:',
            '- smart resume engine',
            '- next best action engine',
            '- resume recommendation export',
            '- action queue export',
        ]
        write_text(self.report_txt, '\n'.join(txt_lines) + '\n')
        write_text(self.report_md, '# Report v4.0\n\n' + '\n'.join(f'- {line}' for line in txt_lines if line.strip()) + '\n')

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
        self.build_checkpoint_registry()
        self.build_best_checkpoint()
        self.build_leaderboard()
        self.build_regression_report()
        self.build_anomaly_report()
        self.build_trend_report()
        self.build_smart_resume()
        self.build_next_best_action()
        self.build_release_summary()
        self.build_upload_reports()
        self.build_zip()

    def print_summary(self, session, root_created):
        print('=== MORPH Runtime Core v4.0 / Summary ===')
        print(f'Project:        {self.project_id}')
        print(f'Root created:   {root_created}')
        print('Root session:   session_001')
        print(f'Saved session:  {session["session_id"]}')
        print(f'Branch used:    {session["branch"]}')
        print(f'Task type:      {session["task_type"]}')
        print(f'Chosen route:   {session["chosen_route"]}')
        print(f'Session file:   {self.session_path(session["session_id"])}')
        print(f'Report txt:     {self.report_txt}')
        print(f'Resume txt:     {self.resume_txt}')
        print(f'Action txt:     {self.next_action_txt}')
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
        parser = argparse.ArgumentParser(description='MORPH Runtime Core v4.0')
        parser.add_argument('--fresh-if-missing', action='store_true')
        parser.add_argument('--append-task', choices=['math', 'simple'])
        parser.add_argument('--resume-session')
        parser.add_argument('--branch', default='main')
        parser.add_argument('--report-only', action='store_true')
        parser.add_argument('--checkpoint-label')
        parser.add_argument('--smart-resume-only', action='store_true')
        parser.add_argument('--next-action-only', action='store_true')
        parser.add_argument('--regression-only', action='store_true')
        parser.add_argument('--anomaly-only', action='store_true')
        parser.add_argument('--trend-only', action='store_true')
        args = parser.parse_args()

        if args.report_only:
            self.init_pack()
            self.build_all_reports()
            print('Reports rebuilt.')
            print(self.report_txt)
            print(self.resume_txt)
            print(self.next_action_txt)
            print(self.release_summary_txt)
            return

        if args.smart_resume_only:
            self.init_pack()
            self.build_checkpoint_registry()
            self.build_best_checkpoint()
            self.build_leaderboard()
            self.build_regression_report()
            self.build_anomaly_report()
            self.build_trend_report()
            payload = self.build_smart_resume()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.resume_txt)
            print(self.resume_json)
            return

        if args.next_action_only:
            self.init_pack()
            self.build_checkpoint_registry()
            self.build_best_checkpoint()
            self.build_leaderboard()
            self.build_regression_report()
            self.build_anomaly_report()
            self.build_trend_report()
            self.build_smart_resume()
            payload = self.build_next_best_action()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.next_action_txt)
            print(self.next_action_json)
            return

        if args.regression_only:
            self.init_pack()
            payload = self.build_regression_report()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.regression_txt)
            return

        if args.anomaly_only:
            self.init_pack()
            payload = self.build_anomaly_report()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.anomaly_txt)
            return

        if args.trend_only:
            self.init_pack()
            payload = self.build_trend_report()
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            print(self.trend_txt)
            return

        if args.checkpoint_label:
            self.init_pack()
            cp = self.create_checkpoint(args.checkpoint_label)
            print(f'Checkpoint saved: {cp}')
            print(self.resume_txt)
            print(self.next_action_txt)
            return

        if args.fresh_if_missing or args.append_task:
            task_type = args.append_task or 'math'
            session, root_created = self.append_task(task_type=task_type, branch_label=args.branch, resume_session=args.resume_session)
            self.print_summary(session, root_created)
            return

        parser.print_help()

def main():
    MorphRuntimeCoreV40(Path.cwd()).cli()

if __name__ == '__main__':
    main()
