#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List

VERSION = 'v2.7'
PACK_ROOT_NAME = 'morph_runtime_core_v2_7'
DEFAULT_PROJECT_ID = 'project_math_lab'

MODULES_BY_TASK = {
    'math': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'RecoveryEngine','AutoRepairBasic','OrphanHandler','ComparativeResumeEngine','HandoffExporter',
        'QuickResumePack','SummaryPackBuilder','PackValidator','IntegrityGuard','FabricOrchestratorV27','ReportBuilder'
    ],
    'simple': [
        'RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
        'RecoveryEngine','AutoRepairBasic','OrphanHandler','ComparativeResumeEngine','HandoffExporter',
        'QuickResumePack','SummaryPackBuilder','PackValidator','IntegrityGuard','FabricOrchestratorV27','ReportBuilder'
    ]
}

TASK_DEFAULTS = {
    'math': {
        'chosen_route': 'math_deep_verify',
        'verification_armed': True,
        'route_confidence': 1.0,
        'deferred_item_count': 1,
        'health_score': 0.9,
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
        'chosen_route': 'default_contextual',
        'verification_armed': False,
        'route_confidence': 0.53,
        'deferred_item_count': 0,
        'health_score': 0.8,
        'hot_memory_ids': ['long_context_notes','morph_v05','math_simulator'],
        'warm_memory_ids': ['flux_programming','morph_v07','beal_method'],
        'cold_memory_ids': ['activation_pack'],
        'last_schedule': {
            'immediate_queue': [],
            'short_queue': [],
            'medium_queue': [],
            'deep_queue': []
        }
    }
}

DEFAULT_BUDGET = {
    'max_depth': 3,
    'verification_threshold': 2,
    'max_hot_items': 3,
    'max_warm_items': 3,
    'force_cold_tail': True,
    'max_candidate_routes': 3,
    'max_residue_bundles_per_task': 5,
    'max_deferred_items_per_task': 12,
    'deferred_trigger_on_medium_normal': True,
    'deferred_trigger_on_deep_normal': True
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
    nums: List[int] = []
    for sid in branch_sessions:
        digits = ''.join(ch for ch in sid if ch.isdigit())
        if digits:
            nums.append(int(digits))
    nxt = max(nums, default=0) + 1
    suffix = f'_{branch}' if branch != 'main' else ''
    return f'session_{nxt:03d}{suffix}'


def build_session(project_id: str, session_id: str, parent: Optional[str], branch: str, task_type: str) -> Dict[str, Any]:
    d = deepcopy(TASK_DEFAULTS[task_type])
    return {
        'project_id': project_id,
        'session_id': session_id,
        'parent': parent,
        'branch': branch,
        'task_type': task_type,
        'chosen_route': d['chosen_route'],
        'verification_armed': d['verification_armed'],
        'route_confidence': d['route_confidence'],
        'deferred_item_count': d['deferred_item_count'],
        'health_score': d['health_score'],
        'active_modules': MODULES_BY_TASK[task_type],
        'hot_memory_ids': d['hot_memory_ids'],
        'warm_memory_ids': d['warm_memory_ids'],
        'cold_memory_ids': d['cold_memory_ids'],
        'last_schedule': d['last_schedule'],
        'budget': deepcopy(DEFAULT_BUDGET),
        'saved_at': now_iso()
    }


def build_index(project_id: str) -> Dict[str, Any]:
    return {
        'project_id': project_id,
        'version': VERSION,
        'created_at': now_iso(),
        'updated_at': now_iso(),
        'sessions': {},
        'audit_tail': []
    }


def append_audit(index: Dict[str, Any], event_type: str, outcome: str, session_id: Optional[str], details: Dict[str, Any]) -> None:
    meta = index['sessions'].get(session_id, {}) if session_id else {}
    index['audit_tail'].append({
        'timestamp': now_iso(),
        'event_type': event_type,
        'project_id': index['project_id'],
        'session_id': session_id,
        'branch_label': meta.get('branch'),
        'route_name': meta.get('chosen_route'),
        'outcome': outcome,
        'details': details
    })
    index['audit_tail'] = index['audit_tail'][-24:]
    index['updated_at'] = now_iso()


def summarize(index: Dict[str, Any]) -> Dict[str, Any]:
    sessions = index['sessions']
    ids = sorted(sessions.keys(), key=session_sort_key)
    latest = sessions[ids[-1]] if ids else None
    branch_counts: Dict[str, int] = {}
    task_counts: Dict[str, int] = {}
    for s in sessions.values():
        branch_counts[s['branch']] = branch_counts.get(s['branch'], 0) + 1
        task_counts[s['task_type']] = task_counts.get(s['task_type'], 0) + 1
    return {
        'project_id': index['project_id'],
        'session_count': len(ids),
        'branch_counts': branch_counts,
        'task_type_counts': task_counts,
        'latest_session': latest
    }


def auto_repair_project(project_dir: Path, index: Dict[str, Any]) -> Dict[str, Any]:
    repaired_missing_files = []
    repaired_orphans = []
    repaired_modules = []

    known_sessions = set(index['sessions'].keys())

    for sid, sess in sorted(index['sessions'].items(), key=lambda item: session_sort_key(item[0])):
        expected_file = project_dir / f'{sid}.json'
        if not expected_file.exists():
            write_json(expected_file, sess)
            repaired_missing_files.append(sid)

        if sess.get('parent') and sess['parent'] not in known_sessions:
            sess['parent'] = None
            repaired_orphans.append(sid)

        expected_modules = MODULES_BY_TASK.get(sess['task_type'], [])
        if sess.get('active_modules') != expected_modules:
            sess['active_modules'] = expected_modules
            repaired_modules.append(sid)

        if 'budget' not in sess:
            sess['budget'] = deepcopy(DEFAULT_BUDGET)

    if repaired_missing_files:
        append_audit(index, 'auto_repair_basic', 'rebuilt_missing_session_files', None, {'sessions': repaired_missing_files})
    if repaired_orphans:
        append_audit(index, 'orphan_handling', 'detached_invalid_parents', None, {'sessions': repaired_orphans})
    if repaired_modules:
        append_audit(index, 'auto_repair_basic', 'normalized_active_modules', None, {'sessions': repaired_modules})

    return {
        'rebuilt_missing_session_files': repaired_missing_files,
        'detached_orphans': repaired_orphans,
        'normalized_modules': repaired_modules
    }


def build_integrity_report(project_dir: Path, index: Dict[str, Any], repair_summary: Dict[str, Any]) -> Dict[str, Any]:
    session_ids = sorted(index['sessions'].keys(), key=session_sort_key)
    problems = []
    orphan_sessions = []
    missing_files = []

    for sid, sess in index['sessions'].items():
        if sess.get('parent') and sess['parent'] not in index['sessions']:
            orphan_sessions.append(sid)
        if not (project_dir / f'{sid}.json').exists():
            missing_files.append(sid)

    if orphan_sessions:
        problems.append({'type': 'orphan_sessions', 'sessions': orphan_sessions})
    if missing_files:
        problems.append({'type': 'missing_session_files', 'sessions': missing_files})

    return {
        'checked_at': now_iso(),
        'project_dir': str(project_dir),
        'session_count': len(index['sessions']),
        'problem_count': len(problems),
        'ok': len(problems) == 0,
        'problems': problems,
        'session_ids': session_ids,
        'repair_summary': repair_summary
    }


def build_quick_resume_pack(summary: Dict[str, Any], integrity: Dict[str, Any]) -> Dict[str, Any]:
    latest = summary.get('latest_session') or {}
    return {
        'version': VERSION,
        'project_id': summary['project_id'],
        'latest_session_id': latest.get('session_id'),
        'latest_branch': latest.get('branch'),
        'latest_task_type': latest.get('task_type'),
        'latest_route': latest.get('chosen_route'),
        'verification_armed': latest.get('verification_armed'),
        'route_confidence': latest.get('route_confidence'),
        'deferred_item_count': latest.get('deferred_item_count'),
        'health_score': latest.get('health_score'),
        'resume_main': f'python morph_runtime_core_v2_7.py --append-task math --resume-session {latest.get("session_id")}' if latest.get('task_type') == 'math' else None,
        'resume_simple': f'python morph_runtime_core_v2_7.py --append-task simple --branch simple_track',
        'integrity_ok': integrity['ok'],
        'problem_count': integrity['problem_count']
    }


def build_summary_pack(summary: Dict[str, Any], index: Dict[str, Any], integrity: Dict[str, Any]) -> Dict[str, Any]:
    ids = sorted(index['sessions'].keys(), key=session_sort_key)
    compact_sessions = []
    for sid in ids:
        s = index['sessions'][sid]
        compact_sessions.append({
            'session_id': sid,
            'parent': s.get('parent'),
            'branch': s.get('branch'),
            'task_type': s.get('task_type'),
            'route': s.get('chosen_route'),
            'verification_armed': s.get('verification_armed'),
            'deferred_item_count': s.get('deferred_item_count'),
            'health_score': s.get('health_score'),
            'saved_at': s.get('saved_at')
        })
    return {
        'version': VERSION,
        'project_id': summary['project_id'],
        'session_count': summary['session_count'],
        'branch_counts': summary['branch_counts'],
        'task_type_counts': summary['task_type_counts'],
        'integrity_ok': integrity['ok'],
        'sessions': compact_sessions,
        'audit_tail': index['audit_tail'][-8:]
    }


def build_compact_handoff(summary: Dict[str, Any], integrity: Dict[str, Any], quick_resume_pack: Dict[str, Any]) -> Dict[str, Any]:
    latest = summary.get('latest_session') or {}
    return {
        'version': VERSION,
        'project_id': summary['project_id'],
        'latest_session_id': latest.get('session_id'),
        'branch': latest.get('branch'),
        'task_type': latest.get('task_type'),
        'route': latest.get('chosen_route'),
        'verification_armed': latest.get('verification_armed'),
        'confidence': latest.get('route_confidence'),
        'deferred': latest.get('deferred_item_count'),
        'health': latest.get('health_score'),
        'integrity_ok': integrity['ok'],
        'resume_commands': {
            'main': quick_resume_pack.get('resume_main'),
            'simple': quick_resume_pack.get('resume_simple')
        }
    }


def build_quick_report(summary: Dict[str, Any], integrity: Dict[str, Any], repair_summary: Dict[str, Any]) -> str:
    latest = summary.get('latest_session') or {}
    return '\n'.join([
        f"Project: {summary['project_id']}",
        f"Latest session: {latest.get('session_id')}",
        f"Branch: {latest.get('branch')}",
        f"Task type: {latest.get('task_type')}",
        f"Route: {latest.get('chosen_route')}",
        f"Confidence: {latest.get('route_confidence')}",
        f"Deferred: {latest.get('deferred_item_count')}",
        f"Health: {latest.get('health_score')}",
        f"Integrity ok: {integrity['ok']} ({integrity['problem_count']})",
        f"Rebuilt missing files: {len(repair_summary['rebuilt_missing_session_files'])}",
        f"Detached orphans: {len(repair_summary['detached_orphans'])}",
        "Upload-ready reports: report_v2.7.txt / report_v2.7.md / report_v2.7.pdf",
        "Extra packs: compact_handoff.json / quick_resume_pack.json / summary_pack.json",
    ]) + '\n'


def build_txt_report(summary: Dict[str, Any], index: Dict[str, Any], integrity: Dict[str, Any], repair_summary: Dict[str, Any]) -> str:
    latest = summary.get('latest_session') or {}
    ids = sorted(index['sessions'].keys(), key=session_sort_key)
    lines = [
        f"MORPH Runtime Core {VERSION} — Final Report",
        "",
        "Project Overview",
        f"- Project ID: {summary['project_id']}",
        f"- Session count: {summary['session_count']}",
        f"- Branch counts: {summary['branch_counts']}",
        f"- Task type counts: {summary['task_type_counts']}",
        "",
        "Latest Session",
        f"- Session ID: {latest.get('session_id')}",
        f"- Parent: {latest.get('parent')}",
        f"- Branch: {latest.get('branch')}",
        f"- Task type: {latest.get('task_type')}",
        f"- Route: {latest.get('chosen_route')}",
        f"- Verification armed: {latest.get('verification_armed')}",
        f"- Confidence: {latest.get('route_confidence')}",
        f"- Deferred count: {latest.get('deferred_item_count')}",
        f"- Health: {latest.get('health_score')}",
        "",
        "Recovery / Repair",
        f"- Rebuilt missing session files: {len(repair_summary['rebuilt_missing_session_files'])}",
        f"- Detached orphan sessions: {len(repair_summary['detached_orphans'])}",
        f"- Normalized modules: {len(repair_summary['normalized_modules'])}",
        "",
        "Integrity",
        f"- OK: {integrity['ok']}",
        f"- Problem count: {integrity['problem_count']}",
        "",
        "Sessions"
    ]
    for sid in ids:
        s = index['sessions'][sid]
        lines.append(f"- {sid} | branch={s['branch']} | task={s['task_type']} | route={s['chosen_route']} | saved_at={s['saved_at']}")
    lines += [
        "",
        "Export Packs",
        "- compact_handoff.json",
        "- quick_resume_pack.json",
        "- summary_pack.json",
        "",
        "Audit Tail"
    ]
    for item in index['audit_tail'][-8:]:
        lines.append(f"- {item['event_type']} | {item['outcome']} | {item.get('session_id')}")
    return '\n'.join(lines) + '\n'


def build_md_report(summary: Dict[str, Any], integrity: Dict[str, Any], repair_summary: Dict[str, Any]) -> str:
    latest = summary.get('latest_session') or {}
    return '\n'.join([
        f"# MORPH Runtime Core {VERSION} — Final Report",
        "",
        "## Project Overview",
        f"- **Project ID:** {summary['project_id']}",
        f"- **Session count:** {summary['session_count']}",
        f"- **Branch counts:** `{summary['branch_counts']}`",
        f"- **Task type counts:** `{summary['task_type_counts']}`",
        "",
        "## Latest Session",
        f"- **Session ID:** `{latest.get('session_id')}`",
        f"- **Parent:** `{latest.get('parent')}`",
        f"- **Branch:** `{latest.get('branch')}`",
        f"- **Task type:** `{latest.get('task_type')}`",
        f"- **Route:** `{latest.get('chosen_route')}`",
        f"- **Verification armed:** `{latest.get('verification_armed')}`",
        f"- **Confidence:** `{latest.get('route_confidence')}`",
        f"- **Deferred count:** `{latest.get('deferred_item_count')}`",
        f"- **Health:** `{latest.get('health_score')}`",
        "",
        "## Recovery / Repair",
        f"- **Rebuilt missing session files:** `{len(repair_summary['rebuilt_missing_session_files'])}`",
        f"- **Detached orphan sessions:** `{len(repair_summary['detached_orphans'])}`",
        f"- **Normalized modules:** `{len(repair_summary['normalized_modules'])}`",
        "",
        "## Integrity",
        f"- **OK:** `{integrity['ok']}`",
        f"- **Problem count:** `{integrity['problem_count']}`",
        "",
        "## Export Packs",
        "- `compact_handoff.json`",
        "- `quick_resume_pack.json`",
        "- `summary_pack.json`",
        ""
    ]) + '\n'


def pdf_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def write_simple_pdf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = text.splitlines() or ['']
    page_w, page_h = 595, 842
    left, top, bottom = 50, 792, 50
    line_h, font_size = 14, 11
    max_lines = max(1, int((top - bottom) / line_h))
    pages = []
    for start in range(0, len(lines), max_lines):
        chunk = lines[start:start + max_lines]
        parts = ["BT", f"/F1 {font_size} Tf"]
        y = top
        for line in chunk:
            parts.append(f"1 0 0 1 {left} {y} Tm ({pdf_escape(line)}) Tj")
            y -= line_h
        parts.append("ET")
        pages.append("\n".join(parts))
    objects = []
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{4 + i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, page_stream in enumerate(pages):
        content_num = 4 + len(pages) + i
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_num} 0 R >>")
    for page_stream in pages:
        stream_bytes = page_stream.encode('latin-1', errors='replace')
        objects.append(f"<< /Length {len(stream_bytes)} >>\nstream\n{page_stream}\nendstream")
    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode('latin-1'))
        pdf.extend(obj.encode('latin-1', errors='replace'))
        pdf.extend(b"\nendobj\n")
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n".encode('latin-1'))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode('latin-1'))
    pdf.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode('latin-1'))
    path.write_bytes(pdf)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--project-id', default=DEFAULT_PROJECT_ID)
    ap.add_argument('--fresh-if-missing', action='store_true')
    ap.add_argument('--append-task', choices=['math', 'simple'])
    ap.add_argument('--resume-session')
    ap.add_argument('--branch', default='main')
    args = ap.parse_args()

    cwd = Path.cwd()
    pack_root = cwd / PACK_ROOT_NAME
    project_dir = pack_root / args.project_id
    runtime_index_file = project_dir / 'runtime_index.json'

    created_root = False
    if runtime_index_file.exists():
        index = read_json(runtime_index_file)
    else:
        if not args.fresh_if_missing and not args.append_task:
            raise SystemExit('No project pack found. Use --fresh-if-missing and --append-task.')
        project_dir.mkdir(parents=True, exist_ok=True)
        index = build_index(args.project_id)
        created_root = True

    repair_summary = auto_repair_project(project_dir, index)

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

    write_json(runtime_index_file, index)

    summary = summarize(index)
    integrity = build_integrity_report(project_dir, index, repair_summary)
    quick_resume_pack = build_quick_resume_pack(summary, integrity)
    summary_pack = build_summary_pack(summary, index, integrity)
    compact_handoff = build_compact_handoff(summary, integrity, quick_resume_pack)

    manifest_file = project_dir / 'project_manifest.json'
    integrity_file = project_dir / 'integrity_report.json'
    quick_report_file = project_dir / 'quick_report.txt'
    quick_resume_file = project_dir / 'quick_resume_pack.json'
    summary_pack_file = project_dir / 'summary_pack.json'
    compact_handoff_file = project_dir / 'compact_handoff.json'
    report_txt_file = project_dir / f'report_{VERSION}.txt'
    report_md_file = project_dir / f'report_{VERSION}.md'
    report_pdf_file = project_dir / f'report_{VERSION}.pdf'

    write_json(manifest_file, summary)
    write_json(integrity_file, integrity)
    write_json(quick_resume_file, quick_resume_pack)
    write_json(summary_pack_file, summary_pack)
    write_json(compact_handoff_file, compact_handoff)
    write_text(quick_report_file, build_quick_report(summary, integrity, repair_summary))
    txt_report = build_txt_report(summary, index, integrity, repair_summary)
    md_report = build_md_report(summary, integrity, repair_summary)
    write_text(report_txt_file, txt_report)
    write_text(report_md_file, md_report)
    write_simple_pdf(report_pdf_file, txt_report)

    final_bundle = project_dir / 'final_upload_bundle'
    final_bundle.mkdir(parents=True, exist_ok=True)
    for p in [report_txt_file, report_md_file, report_pdf_file, manifest_file, integrity_file, quick_report_file, quick_resume_file, summary_pack_file, compact_handoff_file]:
        shutil.copy2(p, final_bundle / p.name)
    write_text(final_bundle / 'UPLOAD_README.txt', '\n'.join([
        f'MORPH Runtime Core {VERSION}',
        f'Project: {args.project_id}',
        'Key features: compact handoff exporter / quick resume pack / summary pack'
    ]) + '\n')

    zip_path = shutil.make_archive(str(project_dir), 'zip', root_dir=project_dir.parent, base_dir=project_dir.name)

    latest = summary.get('latest_session') or {}
    print(f'=== MORPH Runtime Core {VERSION} / Summary ===')
    print(f'Project:             {args.project_id}')
    print(f'Root created:        {created_root}')
    print(f'Project dir:         {project_dir}')
    if saved_session:
        print(f'Saved session:       {saved_session["session_id"]}')
        print(f'Branch used:         {saved_session["branch"]}')
        print(f'Task type:           {saved_session["task_type"]}')
        print(f'Chosen route:        {saved_session["chosen_route"]}')
    print(f'Manifest file:       {manifest_file}')
    print(f'Integrity file:      {integrity_file}')
    print(f'Quick report:        {quick_report_file}')
    print(f'Quick resume pack:   {quick_resume_file}')
    print(f'Summary pack:        {summary_pack_file}')
    print(f'Compact handoff:     {compact_handoff_file}')
    print(f'TXT report:          {report_txt_file}')
    print(f'MD report:           {report_md_file}')
    print(f'PDF report:          {report_pdf_file}')
    print(f'Upload folder:       {final_bundle}')
    print(f'ZIP export:          {zip_path}')
    print('')
    print('=== Status Snapshot ===')
    print(json.dumps({
        'session_id': latest.get('session_id'),
        'parent': latest.get('parent'),
        'branch': latest.get('branch'),
        'task_type': latest.get('task_type'),
        'chosen_route': latest.get('chosen_route'),
        'verification_armed': latest.get('verification_armed'),
        'route_confidence': latest.get('route_confidence'),
        'deferred_item_count': latest.get('deferred_item_count'),
        'health_score': latest.get('health_score'),
        'saved_at': latest.get('saved_at')
    }, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
