#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

VERSION = 'v2.5'
PACK_ROOT_NAME = 'morph_runtime_core_v2_5'
DEFAULT_PROJECT_ID = 'project_math_lab'

MODULES_BY_TASK = {
    'math': ['RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
             'ComparativeResumeEngine','HandoffExporter','PackValidator','IntegrityGuard','RecoveryEngine',
             'FabricOrchestratorV25','ReportBuilder','FinalUploadBundler','UploadOnlyRebuilder','CustomReportExporter','PdfReportExporter'],
    'simple': ['RuntimeKernel','RuntimeStateManager','RuntimeIndexManager','ContinuityPackManager','SessionStateAdapter',
               'ComparativeResumeEngine','HandoffExporter','PackValidator','IntegrityGuard','RecoveryEngine',
               'FabricOrchestratorV25','ReportBuilder','FinalUploadBundler','UploadOnlyRebuilder','CustomReportExporter','PdfReportExporter']
}

TASK_DEFAULTS = {
    'math': {
        'chosen_route': 'math_deep_verify','verification_armed': True,'route_confidence': 1.0,
        'deferred_item_count': 1,'health_score': 0.9,
        'hot_memory_ids': ['math_simulator','beal_method','morph_v05'],
        'warm_memory_ids': ['flux_programming','morph_v07','activation_pack'],
        'cold_memory_ids': ['long_context_notes'],
        'last_schedule': {'immediate_queue': ['route_commit'],'short_queue': ['core_claim_pass'],
                          'medium_queue': ['structural_consistency_pass'],'deep_queue': ['proof_pressure_pass','route_deepening']}
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
    index['audit_tail'] = index['audit_tail'][-20:]
    index['updated_at'] = now_iso()

def summarize(index: Dict[str, Any]) -> Dict[str, Any]:
    sessions = index['sessions']
    ids = sorted(sessions.keys(), key=session_sort_key)
    latest = sessions[ids[-1]] if ids else None
    branch_counts, task_counts = {}, {}
    for s in sessions.values():
        branch_counts[s['branch']] = branch_counts.get(s['branch'], 0) + 1
        task_counts[s['task_type']] = task_counts.get(s['task_type'], 0) + 1
    return {'project_id': index['project_id'],'session_count': len(ids),'branch_counts': branch_counts,
            'task_type_counts': task_counts,'latest_session': latest,'integrity_ok': True,'problem_count': 0}

def build_quick_report(summary: Dict[str, Any]) -> str:
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
        'Upload folder: final_upload_bundle/',
        'Rebuild upload only: python morph_runtime_core_v2_5.py --build-upload-only',
        'Custom report: python morph_runtime_core_v2_5.py --export-report-only my_report.txt',
        'Custom pdf: python morph_runtime_core_v2_5.py --export-pdf-only my_report.pdf',
    ]) + '\n'

def build_txt_report(summary: Dict[str, Any], index: Dict[str, Any]) -> str:
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
        '- final_upload_bundle/report_v2.5.txt',
        '- final_upload_bundle/report_v2.5.md',
        '- final_upload_bundle/report_v2.5.pdf',
        '- final_upload_bundle/compact_handoff.json',
        '- final_upload_bundle/project_manifest.json',
        '- final_upload_bundle/integrity_report.json',
        '- final_upload_bundle/quick_report.txt',
        '- final_upload_bundle/UPLOAD_README.txt',
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
        '', '## Upload Ready',
        '- `final_upload_bundle/report_v2.5.txt`',
        '- `final_upload_bundle/report_v2.5.md`',
        '- `final_upload_bundle/report_v2.5.pdf`',
        '- `final_upload_bundle/compact_handoff.json`',
        '- `final_upload_bundle/project_manifest.json`',
        '- `final_upload_bundle/integrity_report.json`',
        '- `final_upload_bundle/quick_report.txt`',
        '- `final_upload_bundle/UPLOAD_README.txt`',
    ]
    return '\n'.join(lines) + '\n'

def build_upload_readme(summary: Dict[str, Any]) -> str:
    latest = summary.get('latest_session') or {}
    return '\n'.join([
        f"MORPH Runtime Core {VERSION} Upload Bundle",'',
        f"Project ID: {summary['project_id']}",
        f"Session count: {summary['session_count']}",
        f"Latest session: {latest.get('session_id')}",
        f"Branch: {latest.get('branch')}",
        f"Task type: {latest.get('task_type')}",
        f"Route: {latest.get('chosen_route')}",'',
        'Included files:',
        '- report_v2.5.txt','- report_v2.5.md','- report_v2.5.pdf','- compact_handoff.json',
        '- project_manifest.json','- integrity_report.json','- quick_report.txt','- UPLOAD_README.txt'
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

def export_custom_report(project_dir: Path, report_txt: Path, report_md: Path, report_pdf: Path,
                         custom_name: Optional[str], pdf_mode: bool = False) -> Optional[Path]:
    if not custom_name:
        return None
    custom_path = project_dir / custom_name
    suffix = custom_path.suffix.lower()
    if pdf_mode or suffix == '.pdf':
        if suffix != '.pdf':
            custom_path = project_dir / f'{custom_name}.pdf'
        shutil.copy2(report_pdf, custom_path)
        return custom_path
    if suffix == '.md':
        shutil.copy2(report_md, custom_path)
    else:
        if suffix != '.txt':
            custom_path = project_dir / f'{custom_name}.txt'
        shutil.copy2(report_txt, custom_path)
    return custom_path

def build_upload_bundle(project_dir: Path, outputs: Dict[str, Path], summary: Dict[str, Any]) -> Dict[str, Path]:
    bundle_dir = project_dir / 'final_upload_bundle'
    bundle_dir.mkdir(parents=True, exist_ok=True)
    selected = {
        'report_v2.5.txt': outputs['report_txt'],
        'report_v2.5.md': outputs['report_md'],
        'report_v2.5.pdf': outputs['report_pdf'],
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

def save_outputs(project_dir: Path, index: Dict[str, Any], custom_report_name: Optional[str], custom_pdf_name: Optional[str]) -> Dict[str, Path]:
    summary = summarize(index)
    runtime_index = project_dir / 'runtime_index.json'
    manifest = project_dir / 'project_manifest.json'
    integrity = project_dir / 'integrity_report.json'
    handoff = project_dir / 'compact_handoff.json'
    quick = project_dir / 'quick_report.txt'
    report_txt = project_dir / f'report_{VERSION}.txt'
    report_md = project_dir / f'report_{VERSION}.md'
    report_pdf = project_dir / f'report_{VERSION}.pdf'
    txt_content = build_txt_report(summary, index)
    md_content = build_md_report(summary, index)
    write_json(runtime_index, index)
    write_json(manifest, summary)
    write_json(integrity, {'checked_at': now_iso(),'project_dir': str(project_dir),'session_count': len(index['sessions']),
                           'problem_count': 0,'ok': True,'session_ids': sorted(index['sessions'].keys(), key=session_sort_key)})
    write_json(handoff, summary)
    write_text(quick, build_quick_report(summary))
    write_text(report_txt, txt_content)
    write_text(report_md, md_content)
    write_simple_pdf(report_pdf, txt_content)

    pack_root = project_dir.parent
    shutil.copy2(report_txt, pack_root / f'report_{VERSION}.txt')
    shutil.copy2(report_md, pack_root / f'report_{VERSION}.md')
    shutil.copy2(report_pdf, pack_root / f'report_{VERSION}.pdf')

    custom_report = export_custom_report(project_dir, report_txt, report_md, report_pdf, custom_report_name, pdf_mode=False)
    custom_pdf = export_custom_report(project_dir, report_txt, report_md, report_pdf, custom_pdf_name, pdf_mode=True)
    if custom_report:
        shutil.copy2(custom_report, pack_root / custom_report.name)
    if custom_pdf:
        shutil.copy2(custom_pdf, pack_root / custom_pdf.name)

    project_zip = shutil.make_archive(str(project_dir), 'zip', root_dir=project_dir.parent, base_dir=project_dir.name)
    upload = build_upload_bundle(project_dir, {
        'manifest': manifest, 'integrity': integrity, 'handoff': handoff,
        'quick': quick, 'report_txt': report_txt, 'report_md': report_md, 'report_pdf': report_pdf
    }, summary)

    return {'runtime_index': runtime_index,'manifest': manifest,'integrity': integrity,'handoff': handoff,
            'quick': quick,'report_txt': report_txt,'report_md': report_md,'report_pdf': report_pdf,
            'project_zip': Path(project_zip),'bundle_dir': upload['bundle_dir'],'bundle_zip': upload['bundle_zip'],
            'bundle_readme': upload['bundle_readme'],'custom_report': custom_report,'custom_pdf': custom_pdf}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project-id', default=DEFAULT_PROJECT_ID)
    ap.add_argument('--fresh-if-missing', action='store_true')
    ap.add_argument('--append-task', choices=['math','simple'])
    ap.add_argument('--resume-session')
    ap.add_argument('--branch', default='main')
    ap.add_argument('--build-upload-only', action='store_true')
    ap.add_argument('--export-report-only', help='custom report filename, e.g. my_report.txt or my_report.md')
    ap.add_argument('--export-pdf-only', help='custom pdf filename, e.g. my_report.pdf')
    args = ap.parse_args()

    cwd = Path.cwd()
    pack_root = cwd / PACK_ROOT_NAME
    project_dir = pack_root / args.project_id
    runtime_index = project_dir / 'runtime_index.json'

    if args.build_upload_only or args.export_report_only or args.export_pdf_only:
        if not runtime_index.exists():
            raise SystemExit('No existing project pack found.')
        index = read_json(runtime_index)
        append_audit(index, 'export_mode', 'rebuilt', None, {'report': args.export_report_only, 'pdf': args.export_pdf_only})
        outputs = save_outputs(project_dir, index, args.export_report_only, args.export_pdf_only)
        summary = summarize(index)
        latest = summary.get('latest_session') or {}
        print(f'=== MORPH Runtime Core {VERSION} / Export Mode ===')
        print(f'Project:         {args.project_id}')
        print(f'Project dir:     {project_dir}')
        print(f'Quick report:    {outputs["quick"]}')
        print(f'TXT report:      {outputs["report_txt"]}')
        print(f'MD report:       {outputs["report_md"]}')
        print(f'PDF report:      {outputs["report_pdf"]}')
        if outputs["custom_report"]:
            print(f'Custom report:   {outputs["custom_report"]}')
        if outputs["custom_pdf"]:
            print(f'Custom pdf:      {outputs["custom_pdf"]}')
        print(f'Upload folder:   {outputs["bundle_dir"]}')
        print(f'Upload zip:      {outputs["bundle_zip"]}')
        print('\\n=== Status Snapshot ===')
        print(json.dumps({'session_id': latest.get('session_id'),'branch': latest.get('branch'),
                          'task_type': latest.get('task_type'),'chosen_route': latest.get('chosen_route'),
                          'route_confidence': latest.get('route_confidence'),'health_score': latest.get('health_score')},
                         indent=2, ensure_ascii=False))
        return

    created_root = False
    if not runtime_index.exists():
        if not args.fresh_if_missing and not args.append_task:
            raise SystemExit('No project pack found. Use --fresh-if-missing, --append-task, --build-upload-only, --export-report-only or --export-pdf-only.')
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

    outputs = save_outputs(project_dir, index, None, None)
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
    print(f"PDF report:      {outputs['report_pdf']}")
    print(f"Upload folder:   {outputs['bundle_dir']}")
    print(f"Upload zip:      {outputs['bundle_zip']}")
    print(f"ZIP export:      {outputs['project_zip']}")
    print('\\n=== Status Snapshot ===')
    print(json.dumps({'session_id': latest.get('session_id'),'parent': latest.get('parent'),'branch': latest.get('branch'),
                      'task_type': latest.get('task_type'),'chosen_route': latest.get('chosen_route'),
                      'verification_armed': latest.get('verification_armed'),'route_confidence': latest.get('route_confidence'),
                      'deferred_item_count': latest.get('deferred_item_count'),'health_score': latest.get('health_score'),
                      'saved_at': latest.get('saved_at')}, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
