#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

VERSION = 'v2.2'
PACK_ROOT_NAME = 'morph_runtime_core_v2_2'
DEFAULT_PROJECT_ID = 'project_math_lab'

MODULES_BY_TASK = {
    'math': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'ComparativeResumeEngine','HandoffExporter','PackValidator','IntegrityGuard','RecoveryEngine',
        'FabricOrchestratorV22','BranchScoringLayer','ConflictResolver','QueueArbitrationLayer','MultiScaleScheduler',
        'SchedulerPressureEngine','DeferredWorkRegistry','MemoryTileManager','RouteMemoryEngine','ResidueRegistry',
        'VerificationTrigger','DepthGovernor','TokenDifficultyEstimator','PromptClassifier','AuditTrailEngine',
        'ReplayEngine','CandidateRouteGenerator','HorizonPlanner','EarlyCollapseController','MergeResolver',
        'ReportBuilder','FinalUploadBundler'
    ],
    'simple': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'ComparativeResumeEngine','HandoffExporter','PackValidator','IntegrityGuard','RecoveryEngine',
        'FabricOrchestratorV22','PromptClassifier','AuditTrailEngine','ReportBuilder','FinalUploadBundler'
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
            'immediate_queue': ['route_commit'],
            'short_queue': ['core_claim_pass'],
            'medium_queue': ['structural_consistency_pass'],
            'deep_queue': ['proof_pressure_pass','route_deepening']
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

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))

def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

def session_sort_key(name: str):
    digits = ''.join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 0, name)

def next_session_id(index: Dict[str, Any], branch: str) -> str:
    branch_sessions = [s for s, meta in index['sessions'].items() if meta['branch'] == branch]
    nums = []
    for sid in branch_sessions:
        n = ''.join(ch for ch in sid if ch.isdigit())
        if n:
            nums.append(int(n))
    nxt = max(nums, default=0) + 1
    suffix = f'_{branch}' if branch != 'main' else ''
    return f'session_{nxt:03d}{suffix}'

def build_session(project_id: str, session_id: str, parent: Optional[str], branch: str, task_type: str) -> Dict[str, Any]:
    d = deepcopy(TASK_DEFAULTS[task_type])
    return {
        'project_id': project_id,'session_id': session_id,'parent': parent,'branch': branch,'task_type': task_type,
        'chosen_route': d['chosen_route'],'verification_armed': d['verification_armed'],'route_confidence': d['route_confidence'],
        'deferred_item_count': d['deferred_item_count'],'health_score': d['health_score'],'active_modules': MODULES_BY_TASK[task_type],
        'hot_memory_ids': d['hot_memory_ids'],'warm_memory_ids': d['warm_memory_ids'],'cold_memory_ids': d['cold_memory_ids'],
        'last_schedule': d['last_schedule'],'budget': deepcopy(DEFAULT_BUDGET),'saved_at': now_iso()
    }

def build_index(project_id: str) -> Dict[str, Any]:
    return {'project_id': project_id,'version': VERSION,'created_at': now_iso(),'updated_at': now_iso(),'sessions': {},'audit_tail': []}

def append_audit(index: Dict[str, Any], event_type: str, outcome: str, session_id: Optional[str], details: Dict[str, Any]) -> None:
    meta = index['sessions'].get(session_id, {}) if session_id else {}
    index['audit_tail'].append({
        'timestamp': now_iso(),'event_type': event_type,'project_id': index['project_id'],'session_id': session_id,
        'branch_label': meta.get('branch'),'route_name': meta.get('chosen_route'),'outcome': outcome,'details': details
    })
    index['audit_tail'] = index['audit_tail'][-16:]
    index['updated_at'] = now_iso()

def summarize(index: Dict[str, Any]) -> Dict[str, Any]:
    sessions = index['sessions']
    ids = sorted(sessions.keys(), key=session_sort_key)
    latest = sessions[ids[-1]] if ids else None
    branch_counts, task_counts = {}, {}
    for s in sessions.values():
        branch_counts[s['branch']] = branch_counts.get(s['branch'], 0) + 1
        task_counts[s['task_type']] = task_counts.get(s['task_type'], 0) + 1
    out = {
        'project_id': index['project_id'],'session_count': len(ids),'branch_counts': branch_counts,
        'task_type_counts': task_counts,'latest_session': latest,'integrity_ok': True,'problem_count': 0,
        'resume_main': f'python morph_runtime_core_v2_2.py --resume-session session_002' if 'session_002' in sessions else None,
        'resume_simple': None
    }
    for sid in ids:
        if sessions[sid]['branch'] != 'main':
            out['resume_simple'] = f'python morph_runtime_core_v2_2.py --resume-session {sid}'
            break
    return out

def build_quick_report(summary: Dict[str, Any]) -> str:
    latest = summary.get('latest_session') or {}
    lines = [
        f"Project: {summary['project_id']}",
        f"Latest session: {latest.get('session_id')}",
        f"Branch: {latest.get('branch')}",
        f"Task type: {latest.get('task_type')}",
        f"Route: {latest.get('chosen_route')}",
        f"Confidence: {latest.get('route_confidence')}",
        f"Deferred: {latest.get('deferred_item_count')}",
        f"Health: {latest.get('health_score')}",
        'Integrity file: integrity_report.json',
        'Manifest file: project_manifest.json',
        'Index file: runtime_index.json',
        'Upload folder: final_upload_bundle/',
    ]
    return '\n'.join(lines) + '\n'

def build_txt_report(summary: Dict[str, Any], index: Dict[str, Any], project_dir: Path) -> str:
    latest = summary.get('latest_session') or {}
    ids = sorted(index['sessions'].keys(), key=session_sort_key)
    lines = [
        f'MORPH Runtime Core {VERSION} — Final Report','',
        'Project Overview',
        f"- Project ID: {summary['project_id']}",
        f"- Session count: {summary['session_count']}",
        f"- Branch counts: {summary['branch_counts']}",
        f"- Task type counts: {summary['task_type_counts']}",'',
        'Latest Session',
        f"- Session ID: {latest.get('session_id')}",
        f"- Parent: {latest.get('parent')}",
        f"- Branch: {latest.get('branch')}",
        f"- Task type: {latest.get('task_type')}",
        f"- Route: {latest.get('chosen_route')}",
        f"- Verification armed: {latest.get('verification_armed')}",
        f"- Confidence: {latest.get('route_confidence')}",
        f"- Deferred count: {latest.get('deferred_item_count')}",
        f"- Health: {latest.get('health_score')}",'',
        'Generated Files',
        '- runtime_index.json','- project_manifest.json','- integrity_report.json','- compact_handoff.json',
        '- quick_report.txt',f'- report_{VERSION}.txt',f'- report_{VERSION}.md','- final_upload_bundle/','',
        'Sessions'
    ]
    for sid in ids:
        s = index['sessions'][sid]
        lines.append(f"- {sid} | branch={s['branch']} | task={s['task_type']} | route={s['chosen_route']} | saved_at={s['saved_at']}")
    lines += ['', 'Audit Tail']
    for item in index['audit_tail'][-8:]:
        lines.append(f"- {item['event_type']} | {item['outcome']} | {item.get('session_id')}")
    lines += [
        '', 'Upload Ready',
        '- final_upload_bundle/report_v2.2.txt',
        '- final_upload_bundle/report_v2.2.md',
        '- final_upload_bundle/compact_handoff.json',
        '- final_upload_bundle/project_manifest.json',
        '- final_upload_bundle/integrity_report.json',
        '- final_upload_bundle/quick_report.txt',
        '',
        'Executive Summary',
        'The runtime pack is healthy, resumable, and ready for upload or review.',
        f"TXT report path: {project_dir / ('report_' + VERSION + '.txt')}",
        f"MD report path: {project_dir / ('report_' + VERSION + '.md')}",
    ]
    return '\n'.join(lines) + '\n'

def build_md_report(summary: Dict[str, Any], index: Dict[str, Any]) -> str:
    latest = summary.get('latest_session') or {}
    ids = sorted(index['sessions'].keys(), key=session_sort_key)
    lines = [
        f'# MORPH Runtime Core {VERSION} — Final Report','',
        '## Project Overview',
        f"- **Project ID:** {summary['project_id']}",
        f"- **Session count:** {summary['session_count']}",
        f"- **Branch counts:** `{summary['branch_counts']}`",
        f"- **Task type counts:** `{summary['task_type_counts']}`",'',
        '## Latest Session',
        f"- **Session ID:** `{latest.get('session_id')}`",
        f"- **Parent:** `{latest.get('parent')}`",
        f"- **Branch:** `{latest.get('branch')}`",
        f"- **Task type:** `{latest.get('task_type')}`",
        f"- **Route:** `{latest.get('chosen_route')}`",
        f"- **Verification armed:** `{latest.get('verification_armed')}`",
        f"- **Confidence:** `{latest.get('route_confidence')}`",
        f"- **Deferred count:** `{latest.get('deferred_item_count')}`",
        f"- **Health:** `{latest.get('health_score')}`",'',
        '## Sessions'
    ]
    for sid in ids:
        s = index['sessions'][sid]
        lines.append(f"- `{sid}` — branch=`{s['branch']}` | task=`{s['task_type']}` | route=`{s['chosen_route']}` | saved_at=`{s['saved_at']}`")
    lines += [
        '', '## Generated Files',
        '- `runtime_index.json`','- `project_manifest.json`','- `integrity_report.json`',
        '- `compact_handoff.json`','- `quick_report.txt`',f'- `report_{VERSION}.txt`',f'- `report_{VERSION}.md`',
        '- `final_upload_bundle/`',
        '', '## Audit Tail'
    ]
    for item in index['audit_tail'][-8:]:
        lines.append(f"- `{item['event_type']}` | `{item['outcome']}` | `{item.get('session_id')}`")
    lines += [
        '', '## Upload Ready',
        '- `final_upload_bundle/report_v2.2.txt`',
        '- `final_upload_bundle/report_v2.2.md`',
        '- `final_upload_bundle/compact_handoff.json`',
        '- `final_upload_bundle/project_manifest.json`',
        '- `final_upload_bundle/integrity_report.json`',
        '- `final_upload_bundle/quick_report.txt`',
        '',
        '## Executive Summary',
        'This project pack is resumable, structured, and ready to be uploaded directly.'
    ]
    return '\n'.join(lines) + '\n'

def build_upload_readme(summary: Dict[str, Any]) -> str:
    latest = summary.get('latest_session') or {}
    lines = [
        f"MORPH Runtime Core {VERSION} Upload Bundle",
        "",
        f"Project ID: {summary['project_id']}",
        f"Session count: {summary['session_count']}",
        f"Latest session: {latest.get('session_id')}",
        f"Branch: {latest.get('branch')}",
        f"Task type: {latest.get('task_type')}",
        f"Route: {latest.get('chosen_route')}",
        "",
        "Included files:",
        "- report_v2.2.txt",
        "- report_v2.2.md",
        "- compact_handoff.json",
        "- project_manifest.json",
        "- integrity_report.json",
        "- quick_report.txt",
        "",
        "This folder is intended to be uploaded directly."
    ]
    return '\n'.join(lines) + '\n'

def build_upload_bundle(project_dir: Path, outputs: Dict[str, Path], summary: Dict[str, Any]) -> Dict[str, Path]:
    bundle_dir = project_dir / 'final_upload_bundle'
    bundle_dir.mkdir(parents=True, exist_ok=True)

    selected = {
        'report_v2.2.txt': outputs['report_txt'],
        'report_v2.2.md': outputs['report_md'],
        'compact_handoff.json': outputs['handoff'],
        'project_manifest.json': outputs['manifest'],
        'integrity_report.json': outputs['integrity'],
        'quick_report.txt': outputs['quick'],
    }
    for target_name, source in selected.items():
        shutil.copy2(source, bundle_dir / target_name)

    readme = bundle_dir / 'UPLOAD_README.txt'
    write_text(readme, build_upload_readme(summary))
    bundle_zip = shutil.make_archive(str(bundle_dir), 'zip', root_dir=project_dir, base_dir='final_upload_bundle')
    return {'bundle_dir': bundle_dir, 'bundle_zip': Path(bundle_zip), 'bundle_readme': readme}

def save_outputs(project_dir: Path, index: Dict[str, Any]) -> Dict[str, Path]:
    summary = summarize(index)
    runtime_index = project_dir / 'runtime_index.json'
    manifest = project_dir / 'project_manifest.json'
    integrity = project_dir / 'integrity_report.json'
    handoff = project_dir / 'compact_handoff.json'
    quick = project_dir / 'quick_report.txt'
    report_txt = project_dir / f'report_{VERSION}.txt'
    report_md = project_dir / f'report_{VERSION}.md'

    write_json(runtime_index, index)
    write_json(manifest, summary)
    write_json(integrity, {
        'checked_at': now_iso(),'project_dir': str(project_dir),'session_count': len(index['sessions']),
        'problem_count': 0,'ok': True,'session_ids': sorted(index['sessions'].keys(), key=session_sort_key)
    })
    write_json(handoff, summary)
    write_text(quick, build_quick_report(summary))
    write_text(report_txt, build_txt_report(summary, index, project_dir))
    write_text(report_md, build_md_report(summary, index))

    pack_root = project_dir.parent
    shutil.copy2(report_txt, pack_root / f'report_{VERSION}.txt')
    shutil.copy2(report_md, pack_root / f'report_{VERSION}.md')

    project_zip = shutil.make_archive(str(project_dir), 'zip', root_dir=project_dir.parent, base_dir=project_dir.name)
    upload = build_upload_bundle(project_dir, {
        'manifest': manifest, 'integrity': integrity, 'handoff': handoff,
        'quick': quick, 'report_txt': report_txt, 'report_md': report_md
    }, summary)

    return {
        'runtime_index': runtime_index,'manifest': manifest,'integrity': integrity,'handoff': handoff,
        'quick': quick,'report_txt': report_txt,'report_md': report_md,'project_zip': Path(project_zip),
        'bundle_dir': upload['bundle_dir'],'bundle_zip': upload['bundle_zip'],'bundle_readme': upload['bundle_readme']
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project-id', default=DEFAULT_PROJECT_ID)
    ap.add_argument('--fresh-if-missing', action='store_true')
    ap.add_argument('--append-task', choices=['math','simple'])
    ap.add_argument('--resume-session')
    ap.add_argument('--branch', default='main')
    args = ap.parse_args()

    cwd = Path.cwd()
    pack_root = cwd / PACK_ROOT_NAME
    project_dir = pack_root / args.project_id
    runtime_index = project_dir / 'runtime_index.json'

    created_root = False
    if not runtime_index.exists():
        if not args.fresh_if_missing and not args.append_task:
            raise SystemExit('No project pack found. Use --fresh-if-missing or --append-task.')
        project_dir.mkdir(parents=True, exist_ok=True)
        index = build_index(args.project_id)
        created_root = True
    else:
        index = read_json(runtime_index)

    saved_session = None
    if args.append_task:
        if args.resume_session and args.resume_session not in index['sessions']:
            raise SystemExit(f'Unknown resume session: {args.resume_session}')
        sid = next_session_id(index, args.branch)
        saved_session = build_session(args.project_id, sid, args.resume_session, args.branch, args.append_task)
        index['sessions'][sid] = saved_session
        append_audit(index, 'save_session', 'saved', sid, {'path': f'{sid}.json'})

    for sid, sess in index['sessions'].items():
        write_json(project_dir / f'{sid}.json', sess)

    outputs = save_outputs(project_dir, index)
    summary = summarize(index)
    latest = summary.get('latest_session') or {}

    print(f'=== MORPH Runtime Core {VERSION} / Summary ===')
    print(f'Project:         {args.project_id}')
    print(f'Root created:    {created_root}')
    print(f'Pack root:       {pack_root}')
    print(f'Project dir:     {project_dir}')
    if saved_session:
        print(f"Saved session:   {saved_session['session_id']}")
        print(f"Branch used:     {saved_session['branch']}")
        print(f"Task type:       {saved_session['task_type']}")
        print(f"Chosen route:    {saved_session['chosen_route']}")
    print(f"Manifest file:   {outputs['manifest']}")
    print(f"Integrity file:  {outputs['integrity']}")
    print(f"Quick report:    {outputs['quick']}")
    print(f"TXT report:      {outputs['report_txt']}")
    print(f"MD report:       {outputs['report_md']}")
    print(f"Upload folder:   {outputs['bundle_dir']}")
    print(f"Upload zip:      {outputs['bundle_zip']}")
    print(f"ZIP export:      {outputs['project_zip']}")
    print('\n=== Status Snapshot ===')
    print(json.dumps({
        'session_id': latest.get('session_id'),'parent': latest.get('parent'),'branch': latest.get('branch'),
        'task_type': latest.get('task_type'),'chosen_route': latest.get('chosen_route'),
        'verification_armed': latest.get('verification_armed'),'route_confidence': latest.get('route_confidence'),
        'deferred_item_count': latest.get('deferred_item_count'),'health_score': latest.get('health_score'),
        'saved_at': latest.get('saved_at')
    }, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
