#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime
from pathlib import Path

VERSION = "1.1"
SCRIPT_NAME = "atlas_runtime_lab_v1_1.py"
PACK_NAME = "atlas_runtime_pack_v1_1"

ROOT = Path("/storage/emulated/0/Download")
PACK = ROOT / PACK_NAME
DATA = PACK / "data"
REPORTS = PACK / "reports"
EXPORTS = PACK / "exports"
MANIFESTS = PACK / "manifests"
MODULES = PACK / "modules"
ROADMAP = PACK / "roadmap"


def ensure_dirs():
    for path in [PACK, DATA, REPORTS, EXPORTS, MANIFESTS, MODULES, ROADMAP]:
        path.mkdir(parents=True, exist_ok=True)


def build_angles():
    return [
        {
            "id": "angle_01",
            "name": "Elastic Depth Runtime",
            "group": "A",
            "wave": 1,
            "practicality": "high",
            "potential_gain": "high",
            "complexity": "medium",
            "role": "Immediate first build",
            "summary": "Spend deep compute only where the answer can actually change.",
            "best_with": ["Memory Tiling / Active Context Geometry", "Sparse Strategic Verification", "Basic Route Memory"],
        },
        {
            "id": "angle_02",
            "name": "Memory Tiling / Active Context Geometry",
            "group": "A",
            "wave": 1,
            "practicality": "high",
            "potential_gain": "high",
            "complexity": "medium",
            "role": "Immediate first build",
            "summary": "Make context structured, not flat.",
            "best_with": ["Elastic Depth Runtime", "Internal Compression of Thought State", "Cross-Episode Cognitive Continuity"],
        },
        {
            "id": "angle_03",
            "name": "Speculative Multi-Route Inference",
            "group": "B",
            "wave": 2,
            "practicality": "medium",
            "potential_gain": "high",
            "complexity": "medium-high",
            "role": "Route quality upgrade",
            "summary": "Test a few plausible ways of thinking briefly before fully committing.",
            "best_with": ["Route Memory", "Persistent Inference Residue", "Sparse Strategic Verification"],
        },
        {
            "id": "angle_04",
            "name": "Route Memory",
            "group": "A",
            "wave": 1,
            "practicality": "high",
            "potential_gain": "medium-high",
            "complexity": "medium",
            "role": "Historical adaptation",
            "summary": "Remember which execution policies work for which problem families.",
            "best_with": ["Speculative Multi-Route Inference", "Persistent Inference Residue", "Cross-Episode Cognitive Continuity"],
        },
        {
            "id": "angle_05",
            "name": "Persistent Inference Residue",
            "group": "B",
            "wave": 2,
            "practicality": "medium",
            "potential_gain": "high",
            "complexity": "high",
            "role": "Structural accumulation",
            "summary": "Keep the smallest reusable internal structures that repeatedly create advantage.",
            "best_with": ["Route Memory", "Speculative Multi-Route Inference", "Hierarchical Cognitive Identity"],
        },
        {
            "id": "angle_06",
            "name": "Self-Optimizing Runtime Governance",
            "group": "C",
            "wave": 3,
            "practicality": "medium",
            "potential_gain": "high",
            "complexity": "high",
            "role": "Meta-control layer",
            "summary": "Let the runtime learn how to govern itself better.",
            "best_with": ["Budget-Aware Intelligence Allocation", "Sparse Strategic Verification", "Multi-Scale Cognitive Scheduling"],
        },
        {
            "id": "angle_07",
            "name": "Multi-Scale Cognitive Scheduling",
            "group": "C",
            "wave": 3,
            "practicality": "medium",
            "potential_gain": "high",
            "complexity": "high",
            "role": "Timing intelligence",
            "summary": "Different kinds of thinking belong to different internal time horizons.",
            "best_with": ["Self-Optimizing Runtime Governance", "Budget-Aware Intelligence Allocation", "Cross-Episode Cognitive Continuity"],
        },
        {
            "id": "angle_08",
            "name": "Cross-Episode Cognitive Continuity",
            "group": "C",
            "wave": 4,
            "practicality": "medium",
            "potential_gain": "high",
            "complexity": "high",
            "role": "Long-horizon cognition",
            "summary": "Do not restart the larger cognitive process every time a new episode begins.",
            "best_with": ["Hierarchical Cognitive Identity", "Route Memory", "Cognitive Program Hosting"],
        },
        {
            "id": "angle_09",
            "name": "Hierarchical Cognitive Identity",
            "group": "C",
            "wave": 4,
            "practicality": "medium-low",
            "potential_gain": "high",
            "complexity": "high",
            "role": "Large-scale organization",
            "summary": "Know what organized kind of cognition is currently being continued.",
            "best_with": ["Cross-Episode Cognitive Continuity", "Persistent Inference Residue", "Cognitive Program Hosting"],
        },
        {
            "id": "angle_10",
            "name": "Cognitive Program Hosting",
            "group": "C",
            "wave": 5,
            "practicality": "medium-low",
            "potential_gain": "very-high",
            "complexity": "very-high",
            "role": "Substrate transition",
            "summary": "Treat cognition as managed programs, not only as one-shot responses.",
            "best_with": ["Hierarchical Cognitive Identity", "Cross-Episode Cognitive Continuity", "Inter-Process Knowledge Sharing"],
        },
        {
            "id": "angle_11",
            "name": "Sparse Strategic Verification",
            "group": "A",
            "wave": 1,
            "practicality": "high",
            "potential_gain": "medium-high",
            "complexity": "low-medium",
            "role": "Reliability layer",
            "summary": "Verify sparsely, but exactly where failure would matter.",
            "best_with": ["Elastic Depth Runtime", "Speculative Multi-Route Inference", "Self-Optimizing Runtime Governance"],
        },
        {
            "id": "angle_12",
            "name": "Internal Compression of Thought State",
            "group": "B",
            "wave": 4,
            "practicality": "medium",
            "potential_gain": "high",
            "complexity": "high",
            "role": "Advanced memory layer",
            "summary": "Preserve abstract operational state, not just raw text history.",
            "best_with": ["Memory Tiling / Active Context Geometry", "Cross-Episode Cognitive Continuity", "Dynamic Internal Specialization"],
        },
        {
            "id": "angle_13",
            "name": "Dynamic Internal Specialization",
            "group": "B",
            "wave": 4,
            "practicality": "medium",
            "potential_gain": "high",
            "complexity": "high",
            "role": "Task-specific efficiency",
            "summary": "A general model should not remain internally generic for every kind of task.",
            "best_with": ["Internal Compression of Thought State", "Budget-Aware Intelligence Allocation", "Speculative Multi-Route Inference"],
        },
        {
            "id": "angle_14",
            "name": "Budget-Aware Intelligence Allocation",
            "group": "C",
            "wave": 3,
            "practicality": "high",
            "potential_gain": "medium-high",
            "complexity": "medium",
            "role": "Control efficiency",
            "summary": "Allocate intelligence as a budgeted resource, not a fixed default.",
            "best_with": ["Self-Optimizing Runtime Governance", "Elastic Depth Runtime", "Multi-Scale Cognitive Scheduling"],
        },
        {
            "id": "angle_15",
            "name": "Inter-Process Knowledge Sharing",
            "group": "C",
            "wave": 5,
            "practicality": "medium-low",
            "potential_gain": "very-high",
            "complexity": "very-high",
            "role": "Substrate-scale compounding",
            "summary": "Let active cognitive processes share value without contaminating one another.",
            "best_with": ["Cognitive Program Hosting", "Cross-Episode Cognitive Continuity", "Route Memory"],
        },
    ]


def build_core_modules():
    return [
        {
            "id": "module_01",
            "name": "Elastic Depth Orchestrator",
            "resolves_pain": "Uniform compute waste across trivial and critical reasoning segments.",
            "derived_from": ["Elastic Depth Runtime", "Budget-Aware Intelligence Allocation", "Sparse Strategic Verification"],
            "wow_factor": "Shows visibly different shallow/medium/deep treatment per reasoning segment.",
            "outputs": ["depth_profile.json", "depth_decisions.txt"],
        },
        {
            "id": "module_02",
            "name": "Context Geometry Engine",
            "resolves_pain": "Long-context blur, repeated rereading, weak selective recall.",
            "derived_from": ["Memory Tiling / Active Context Geometry", "Internal Compression of Thought State", "Cross-Episode Cognitive Continuity"],
            "wow_factor": "Turns context into hot/warm/cold/latent geometry instead of one flat mass.",
            "outputs": ["context_heatmap.json", "reactivation_summary.txt"],
        },
        {
            "id": "module_03",
            "name": "Multi-Route Trial Engine",
            "resolves_pain": "Premature commitment to weak inference routes.",
            "derived_from": ["Speculative Multi-Route Inference", "Sparse Strategic Verification", "Budget-Aware Intelligence Allocation"],
            "wow_factor": "Trials multiple candidate routes briefly before committing.",
            "outputs": ["route_trials.json", "route_selection.txt"],
        },
        {
            "id": "module_04",
            "name": "Route Memory + Residue Vault",
            "resolves_pain": "AI systems repeatedly rediscover good execution paths and discard useful internal structure.",
            "derived_from": ["Route Memory", "Persistent Inference Residue", "Cross-Episode Cognitive Continuity"],
            "wow_factor": "Stores route families, residue artifacts, reusable anchors and failure families.",
            "outputs": ["route_memory_registry.json", "residue_vault.json"],
        },
        {
            "id": "module_05",
            "name": "Governance & Continuity Kernel",
            "resolves_pain": "Weak runtime discipline, poor budget control, lack of identity and continuity across episodes.",
            "derived_from": [
                "Self-Optimizing Runtime Governance",
                "Multi-Scale Cognitive Scheduling",
                "Cross-Episode Cognitive Continuity",
                "Hierarchical Cognitive Identity",
                "Cognitive Program Hosting",
            ],
            "wow_factor": "Looks like the seed of a cognitive operating substrate, not just a prompt runner.",
            "outputs": ["governance_rules.json", "continuity_objects.json"],
        },
    ]


def build_scoring_schema():
    return {
        "fields": [
            "practicality_score",
            "gain_score",
            "complexity_score",
            "testability_score",
            "dependency_readiness_score",
            "continuity_value_score",
            "governance_risk_score",
        ],
        "scale": "1-10",
        "notes": {
            "higher_is_better": [
                "practicality_score",
                "gain_score",
                "testability_score",
                "dependency_readiness_score",
                "continuity_value_score",
            ],
            "lower_is_better": ["complexity_score", "governance_risk_score"],
        },
        "verdicts": ["keep", "refine", "merge", "archive", "split_subtrack"],
    }


def build_dependency_map():
    return {
        "Elastic Depth Orchestrator": {
            "depends_on": ["Budget-Aware Intelligence Allocation"],
            "amplifies": ["Sparse Strategic Verification", "Multi-Route Trial Engine"],
            "best_after": [],
        },
        "Context Geometry Engine": {
            "depends_on": [],
            "amplifies": ["Cross-Episode Cognitive Continuity", "Internal Compression of Thought State"],
            "best_after": [],
        },
        "Multi-Route Trial Engine": {
            "depends_on": ["Elastic Depth Orchestrator"],
            "amplifies": ["Route Memory + Residue Vault", "Sparse Strategic Verification"],
            "best_after": ["Elastic Depth Orchestrator"],
        },
        "Route Memory + Residue Vault": {
            "depends_on": ["Multi-Route Trial Engine"],
            "amplifies": ["Governance & Continuity Kernel", "Cross-Episode Cognitive Continuity"],
            "best_after": ["Multi-Route Trial Engine"],
        },
        "Governance & Continuity Kernel": {
            "depends_on": ["Context Geometry Engine", "Route Memory + Residue Vault"],
            "amplifies": ["Cognitive Program Hosting", "Inter-Process Knowledge Sharing"],
            "best_after": ["Route Memory + Residue Vault"],
        },
    }


def build_wave_map():
    return {
        "wave_1_runtime_core": [
            "Elastic Depth Runtime",
            "Memory Tiling / Active Context Geometry",
            "Sparse Strategic Verification",
            "Route Memory",
        ],
        "wave_2_route_quality_and_accumulation": [
            "Speculative Multi-Route Inference",
            "Persistent Inference Residue",
        ],
        "wave_3_runtime_self_organization": [
            "Self-Optimizing Runtime Governance",
            "Multi-Scale Cognitive Scheduling",
            "Budget-Aware Intelligence Allocation",
        ],
        "wave_4_long_horizon_cognition": [
            "Cross-Episode Cognitive Continuity",
            "Hierarchical Cognitive Identity",
            "Internal Compression of Thought State",
            "Dynamic Internal Specialization",
        ],
        "wave_5_cognitive_operating_substrate": [
            "Cognitive Program Hosting",
            "Inter-Process Knowledge Sharing",
        ],
    }


def build_candidate_profiles():
    return [
        {
            "id": "candidate_001",
            "name": "Elastic Depth Starter",
            "angle": "elastic depth runtime",
            "status": "seed",
            "wave": 1,
            "tags": ["depth", "runtime", "adaptive"],
            "next_experiment": "Attach budget rules and sparse verification pivots.",
        },
        {
            "id": "candidate_002",
            "name": "Route Memory Seed",
            "angle": "speculative multi-route inference + route memory",
            "status": "seed",
            "wave": 2,
            "tags": ["routing", "memory", "speculation"],
            "next_experiment": "Store route trials and preserve minimal route residue records.",
        },
        {
            "id": "candidate_003",
            "name": "Unified Five-Module Core",
            "angle": "integrated atlas manifest",
            "status": "active",
            "wave": 1,
            "tags": ["manifest", "modules", "roadmap", "integration"],
            "next_experiment": "Promote each core module into experiment records with scoring.",
        },
    ]


def build_experiment_registry(modules):
    records = []
    for i, module in enumerate(modules, start=1):
        records.append(
            {
                "experiment_id": f"exp_{i:03d}",
                "target_module": module["name"],
                "hypothesis": f"{module['name']} can reduce a major runtime pain point while remaining buildable in the Atlas track.",
                "minimal_test": f"Create seed structures and exports for {module['name']} and verify pack/report consistency.",
                "expected_gain": "high" if i in (1, 2, 3, 4) else "very-high",
                "failure_signal": "Outputs remain descriptive only and cannot be compared, scored, or advanced.",
                "next_decision": "keep",
            }
        )
    return records


def build_unified_manifest(angles, modules, wave_map, scoring_schema):
    return {
        "project_name": "Atlas of Same-Hardware Cognitive Architecture Leaps",
        "lab_name": "ATLAS RUNTIME LAB",
        "version": VERSION,
        "separation_rule": "Separate track from MORPH Runtime Core.",
        "mission": "Build a practical architecture lab for same-hardware cognitive leaps.",
        "central_thesis": (
            "Major gains may still be available on the same hardware if model execution is reorganized as cognition rather than treated as a mostly fixed inference path."
        ),
        "unified_principle": (
            "Do not hunt only one winning idea. Build a portfolio of combinable, testable architectural levers and advance the best buildable stack."
        ),
        "five_core_modules": [m["name"] for m in modules],
        "all_atlas_angles_count": len(angles),
        "wave_map": wave_map,
        "scoring_schema": scoring_schema,
        "canonical_objects": [
            "angle",
            "candidate_profile",
            "route_record",
            "residue_record",
            "continuity_object",
            "governance_rule",
            "experiment_record",
            "wave_record",
            "report",
            "export_pack",
        ],
        "build_rule": {
            "v1x": "registry + manifest + scoring + architecture comparison",
            "v2x": "micro-simulation and orchestration logic",
            "v3x": "continuity substrate and cognitive program hosting",
        },
    }


def build_master_roadmap():
    return {
        "v1.1": {
            "title": "Unified Manifest Core",
            "contains": [
                "unified manifest",
                "all atlas angles reintegrated",
                "five wow modules",
                "scoring schema",
                "dependency schema",
                "wave map",
                "extended report",
            ],
            "result": "Atlas becomes a coherent architecture lab instead of only a strategic document.",
        },
        "v1.2": {
            "title": "Atlas Registry & Experiment Layer",
            "contains": [
                "full angle registry",
                "candidate profile extension",
                "experiment records",
                "minimal tests",
                "failure signals",
                "verdict engine",
            ],
            "result": "The system can compare, prioritize and decide what to advance.",
        },
        "v1.3": {
            "title": "Route Memory / Residue / Verification Layer",
            "contains": [
                "route record schema",
                "residue record schema",
                "sparse verification rules",
                "route reuse score",
                "failure family registry",
            ],
            "result": "The lab gains operational memory instead of storing only notes.",
        },
        "v1.4": {
            "title": "Governance / Budget / Scheduling Layer",
            "contains": [
                "budget-aware allocation",
                "branching caps",
                "fallback rules",
                "verification triggers",
                "governance envelope",
                "multi-scale scheduling seeds",
            ],
            "result": "The runtime starts distributing intelligence and risk more deliberately.",
        },
        "v1.5": {
            "title": "Continuity / Identity Layer",
            "contains": [
                "continuity objects",
                "unresolved loops",
                "family identity",
                "project identity",
                "thread identity",
                "mode identity",
            ],
            "result": "Execution becomes a continuing cognitive process.",
        },
        "v1.6": {
            "title": "Compression / Specialization Layer",
            "contains": [
                "internal compression of thought state",
                "dynamic internal specialization",
                "abstract state maps",
                "task-family mode shifts",
            ],
            "result": "The system starts reconfiguring itself per problem class.",
        },
        "v1.7": {
            "title": "Cognitive Program Hosting Seed",
            "contains": [
                "program objects",
                "suspend/resume",
                "split/merge",
                "priority",
                "archive/revive",
                "continuity handoff",
            ],
            "result": "The lab begins treating cognition as managed programs.",
        },
        "v1.8": {
            "title": "Inter-Process Knowledge Sharing Seed",
            "contains": [
                "route lesson sharing",
                "verified anchor sharing",
                "residue relay",
                "conflict alerts",
                "contamination guardrails",
            ],
            "result": "Active processes begin compounding advantage together.",
        },
        "v1.9": {
            "title": "Atlas Comparison Dashboard",
            "contains": [
                "top current bets",
                "buildability vs upside matrix",
                "strongest portfolios",
                "risk view",
                "recommended next wave",
            ],
            "result": "The lab becomes a decision instrument, not only a container.",
        },
        "v2.0": {
            "title": "First Practical Architecture Lab",
            "contains": [
                "runtime simulation hooks",
                "atlas-wide comparison",
                "integrated continuity + governance + route memory",
                "candidate promotion logic",
                "subtrack split logic",
            ],
            "result": "The first mature Atlas lab ready for deeper practical prototyping.",
        },
    }


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


def render_txt_report(manifest, modules, roadmap):
    lines = []
    lines.append("Atlas Runtime Lab v1.1 Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("Purpose: unified manifest core for the Atlas architecture lab")
    lines.append("")
    lines.append("Mission")
    lines.append(f"- {manifest['mission']}")
    lines.append("")
    lines.append("Central Thesis")
    lines.append(f"- {manifest['central_thesis']}")
    lines.append("")
    lines.append("Five Core Modules")
    for module in modules:
        lines.append(f"- {module['name']}: {module['resolves_pain']}")
    lines.append("")
    lines.append("Roadmap Snapshot")
    for version, block in roadmap.items():
        lines.append(f"- {version} — {block['title']}")
    lines.append("")
    lines.append("Immediate Next Upgrade Direction")
    lines.append("- promote core modules into scored experiment records")
    lines.append("- add verdict engine and comparison matrix")
    lines.append("- deepen route memory / residue / verification integration")
    return "\n".join(lines) + "\n"


def render_md_report(manifest, modules, roadmap):
    lines = []
    lines.append("# Atlas Runtime Lab v1.1 Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("- Purpose: unified manifest core for the Atlas architecture lab")
    lines.append("")
    lines.append("## Mission")
    lines.append(manifest["mission"])
    lines.append("")
    lines.append("## Central Thesis")
    lines.append(manifest["central_thesis"])
    lines.append("")
    lines.append("## Five Core Modules")
    for module in modules:
        lines.append(f"- **{module['name']}** — {module['resolves_pain']}")
    lines.append("")
    lines.append("## Roadmap Snapshot")
    for version, block in roadmap.items():
        lines.append(f"- **{version}** — {block['title']}")
    lines.append("")
    lines.append("## Immediate Next Upgrade Direction")
    lines.append("- promote core modules into scored experiment records")
    lines.append("- add verdict engine and comparison matrix")
    lines.append("- deepen route memory / residue / verification integration")
    return "\n".join(lines) + "\n"


def render_summary(manifest, modules):
    lines = []
    lines.append("ATLAS RUNTIME LAB v1.1 SUMMARY")
    lines.append("")
    lines.append(f"Project: {manifest['project_name']}")
    lines.append(f"Version: {manifest['version']}")
    lines.append("")
    lines.append("Unified core now includes:")
    for module in modules:
        lines.append(f"- {module['name']}")
    lines.append("")
    lines.append("This version unifies:")
    lines.append("- the full Atlas angles")
    lines.append("- the five wow modules")
    lines.append("- the operational manifest")
    lines.append("- the master roadmap")
    return "\n".join(lines) + "\n"


def render_manifest_md(manifest, modules, wave_map):
    lines = []
    lines.append("# ATLAS RUNTIME LAB — UNIFIED MANIFEST v1.1")
    lines.append("")
    lines.append(f"**Mission:** {manifest['mission']}")
    lines.append("")
    lines.append(f"**Central Thesis:** {manifest['central_thesis']}")
    lines.append("")
    lines.append("## Five Core Modules")
    for module in modules:
        lines.append(f"- **{module['name']}**")
    lines.append("")
    lines.append("## Wave Map")
    for wave, items in wave_map.items():
        lines.append(f"### {wave}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_roadmap_md(roadmap):
    lines = ["# ATLAS RUNTIME LAB — MASTER UNIFIED ROADMAP", ""]
    for version, block in roadmap.items():
        lines.append(f"## {version} — {block['title']}")
        for item in block["contains"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append(f"**Result:** {block['result']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    ensure_dirs()

    angles = build_angles()
    modules = build_core_modules()
    scoring_schema = build_scoring_schema()
    dependency_map = build_dependency_map()
    wave_map = build_wave_map()
    candidate_profiles = build_candidate_profiles()
    experiment_registry = build_experiment_registry(modules)
    manifest = build_unified_manifest(angles, modules, wave_map, scoring_schema)
    roadmap = build_master_roadmap()

    write_json(DATA / "atlas_angles_v1_1.json", angles)
    write_json(DATA / "candidate_profiles_v1_1.json", candidate_profiles)
    write_json(DATA / "experiment_registry_v1_1.json", experiment_registry)
    write_json(MANIFESTS / "atlas_manifest_v1_1.json", manifest)
    write_json(MANIFESTS / "scoring_schema_v1_1.json", scoring_schema)
    write_json(MANIFESTS / "dependency_map_v1_1.json", dependency_map)
    write_json(MANIFESTS / "wave_map_v1_1.json", wave_map)
    write_json(MODULES / "core_modules_v1_1.json", modules)
    write_json(ROADMAP / "master_unified_roadmap_v1_1.json", roadmap)

    write_text(EXPORTS / "summary_v1.1.txt", render_summary(manifest, modules))
    write_text(EXPORTS / "atlas_unified_manifest_v1.1.md", render_manifest_md(manifest, modules, wave_map))
    write_text(ROADMAP / "master_unified_roadmap_v1_1.md", render_roadmap_md(roadmap))
    write_text(REPORTS / "report_v1.1.txt", render_txt_report(manifest, modules, roadmap))
    write_text(REPORTS / "report_v1.1.md", render_md_report(manifest, modules, roadmap))

    console = []
    console.append("=" * 68)
    console.append("ATLAS RUNTIME LAB v1.1")
    console.append("Unified Manifest Core created successfully")
    console.append("=" * 68)
    console.append(f"Pack: {PACK}")
    console.append("")
    console.append("Created files:")
    console.append(f"- {MANIFESTS / 'atlas_manifest_v1_1.json'}")
    console.append(f"- {MODULES / 'core_modules_v1_1.json'}")
    console.append(f"- {ROADMAP / 'master_unified_roadmap_v1_1.json'}")
    console.append(f"- {REPORTS / 'report_v1.1.txt'}")
    console.append(f"- {REPORTS / 'report_v1.1.md'}")
    console.append(f"- {EXPORTS / 'summary_v1.1.txt'}")
    console.append("")
    console.append("Next suggestion:")
    console.append("- move to v1.2 Atlas Registry & Experiment Layer")
    print("\n".join(console))


if __name__ == "__main__":
    main()
