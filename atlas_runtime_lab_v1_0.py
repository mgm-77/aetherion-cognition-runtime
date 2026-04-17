#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import textwrap
from datetime import datetime
from pathlib import Path

VERSION = "v1.0"
SCRIPT_NAME = "atlas_runtime_lab_v1_0.py"
PROJECT_SLUG = "atlas_runtime_lab"
PACK_DIRNAME = "atlas_runtime_pack_v1_0"

DEFAULT_ARCHITECTURE_CANDIDATES = [
    {
        "id": "candidate_001",
        "title": "Elastic Depth Starter",
        "angle": "elastic depth runtime",
        "status": "seed",
        "notes": [
            "Focus on variable-depth execution instead of fixed-pass execution.",
            "Useful as a base path for same-hardware cognitive expansion.",
        ],
        "tags": ["depth", "runtime", "adaptive"],
    },
    {
        "id": "candidate_002",
        "title": "Route Memory Seed",
        "angle": "speculative multi-route inference + route memory",
        "status": "seed",
        "notes": [
            "Tracks alternative inference routes and preserves route residue.",
            "Good candidate for future multi-route scheduling experiments.",
        ],
        "tags": ["routing", "memory", "speculation"],
    },
]

README_TEXT = """\
Atlas Runtime Lab — v1.0

Purpose:
A separate architecture-lab track for experimenting with same-hardware cognitive architecture leaps.

This build does:
- creates a dedicated project pack
- stores architecture angles/candidates
- saves 2 starter candidate profiles
- generates automatic reports
- exports summary files for next iteration

Designed for Android / Termux usage.
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_existing_candidates(path: Path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def merge_candidates(existing, defaults):
    merged = {item.get("id", f"item_{i}"): item for i, item in enumerate(existing)}
    for item in defaults:
        merged[item["id"]] = item
    return list(merged.values())


def build_summary(candidates):
    lines = []
    lines.append(f"Atlas Runtime Lab {VERSION} Summary")
    lines.append(f"Generated: {now_iso()}")
    lines.append("")
    lines.append(f"Total architecture candidates: {len(candidates)}")
    lines.append("")
    for idx, candidate in enumerate(candidates, start=1):
        lines.append(f"{idx}. {candidate.get('title', 'Untitled')}")
        lines.append(f"   id: {candidate.get('id', '-')}")
        lines.append(f"   angle: {candidate.get('angle', '-')}")
        lines.append(f"   status: {candidate.get('status', '-')}")
        tags = ", ".join(candidate.get("tags", [])) or "-"
        lines.append(f"   tags: {tags}")
        notes = candidate.get("notes", [])
        if notes:
            lines.append(f"   note: {notes[0]}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_report(base_dir: Path, candidates):
    report_lines = []
    report_lines.append("=" * 72)
    report_lines.append("ATLAS RUNTIME LAB REPORT")
    report_lines.append("=" * 72)
    report_lines.append(f"Version: {VERSION}")
    report_lines.append(f"Script: {SCRIPT_NAME}")
    report_lines.append(f"Generated: {now_iso()}")
    report_lines.append(f"Base directory: {base_dir}")
    report_lines.append("")
    report_lines.append("MISSION SNAPSHOT")
    report_lines.append("- separate track for same-hardware cognitive architecture experiments")
    report_lines.append("- first stable storage/reporting nucleus")
    report_lines.append("")
    report_lines.append("CREATED STRUCTURE")
    for rel in [
        "atlas_runtime_pack_v1_0/",
        "atlas_runtime_pack_v1_0/data/",
        "atlas_runtime_pack_v1_0/reports/",
        "atlas_runtime_pack_v1_0/exports/",
        "atlas_runtime_pack_v1_0/notes/",
        "atlas_runtime_pack_v1_0/README.txt",
        "atlas_runtime_pack_v1_0/data/architecture_candidates.json",
        "atlas_runtime_pack_v1_0/exports/summary_v1.0.txt",
        "atlas_runtime_pack_v1_0/reports/report_v1.0.txt",
        "atlas_runtime_pack_v1_0/reports/report_v1.0.md",
    ]:
        report_lines.append(f"- {rel}")
    report_lines.append("")
    report_lines.append("CANDIDATE ARCHITECTURE PROFILES")
    for candidate in candidates:
        report_lines.append(f"- {candidate['id']} :: {candidate['title']}")
        report_lines.append(f"  angle: {candidate['angle']}")
        report_lines.append(f"  status: {candidate['status']}")
        report_lines.append(f"  tags: {', '.join(candidate.get('tags', []))}")
    report_lines.append("")
    report_lines.append("NEXT UPGRADE IDEAS")
    report_lines.append("- add architecture angle ingestion from custom user notes")
    report_lines.append("- add candidate scoring / maturity field")
    report_lines.append("- add route-memory experiment registry")
    report_lines.append("- add pack export manifest")
    report_lines.append("")
    report_lines.append("STATUS")
    report_lines.append("v1.0 completed successfully.")
    report_lines.append("=" * 72)
    return "\n".join(report_lines) + "\n"


def build_markdown_report(candidates):
    lines = []
    lines.append(f"# Atlas Runtime Lab {VERSION} Report")
    lines.append("")
    lines.append(f"- Generated: {now_iso()}")
    lines.append(f"- Purpose: same-hardware cognitive architecture lab nucleus")
    lines.append("")
    lines.append("## Stored Candidates")
    lines.append("")
    for candidate in candidates:
        lines.append(f"### {candidate['title']}")
        lines.append(f"- id: `{candidate['id']}`")
        lines.append(f"- angle: {candidate['angle']}")
        lines.append(f"- status: {candidate['status']}")
        lines.append(f"- tags: {', '.join(candidate.get('tags', []))}")
        for note in candidate.get("notes", []):
            lines.append(f"- note: {note}")
        lines.append("")
    lines.append("## Upgrade Direction")
    lines.append("")
    lines.append("- architecture scoring")
    lines.append("- route memory registry")
    lines.append("- runtime governance seed")
    lines.append("- summary/export expansion")
    lines.append("")
    return "\n".join(lines)


def main():
    base_dir = Path("/storage/emulated/0/Download")
    pack_dir = base_dir / PACK_DIRNAME
    data_dir = pack_dir / "data"
    reports_dir = pack_dir / "reports"
    exports_dir = pack_dir / "exports"
    notes_dir = pack_dir / "notes"

    for path in [pack_dir, data_dir, reports_dir, exports_dir, notes_dir]:
        ensure_dir(path)

    write_text(pack_dir / "README.txt", textwrap.dedent(README_TEXT).strip() + "\n")

    candidates_path = data_dir / "architecture_candidates.json"
    existing = load_existing_candidates(candidates_path)
    merged_candidates = merge_candidates(existing, DEFAULT_ARCHITECTURE_CANDIDATES)
    write_json(candidates_path, merged_candidates)

    summary_txt = build_summary(merged_candidates)
    write_text(exports_dir / "summary_v1.0.txt", summary_txt)

    report_txt = build_report(base_dir, merged_candidates)
    write_text(reports_dir / "report_v1.0.txt", report_txt)

    report_md = build_markdown_report(merged_candidates)
    write_text(reports_dir / "report_v1.0.md", report_md)

    console = []
    console.append("Atlas Runtime Lab v1.0 completed.")
    console.append(f"Pack created at: {pack_dir}")
    console.append(f"Candidates stored: {len(merged_candidates)}")
    console.append(f"Report: {reports_dir / 'report_v1.0.txt'}")
    console.append(f"Summary: {exports_dir / 'summary_v1.0.txt'}")
    print("\n".join(console))


if __name__ == "__main__":
    main()
