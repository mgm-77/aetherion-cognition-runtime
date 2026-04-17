#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from datetime import datetime
from pathlib import Path
from statistics import mean

VERSION = "1.2"
SCRIPT_NAME = "atlas_runtime_lab_v1_2.py"
PACK_NAME = "atlas_runtime_pack_v1_2"

ROOT = Path("/storage/emulated/0/Download")
PACK = ROOT / PACK_NAME
DATA = PACK / "data"
REPORTS = PACK / "reports"
EXPORTS = PACK / "exports"
MANIFESTS = PACK / "manifests"
MODULES = PACK / "modules"
ROADMAP = PACK / "roadmap"
MATRIX = PACK / "matrix"
VERDICTS = PACK / "verdicts"


def ensure_dirs():
    for path in [PACK, DATA, REPORTS, EXPORTS, MANIFESTS, MODULES, ROADMAP, MATRIX, VERDICTS]:
        path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def build_angles():
    return [
        {"id": "angle_01", "name": "Elastic Depth Runtime", "group": "A", "wave": 1, "practicality": "high", "potential_gain": "high", "complexity": "medium", "role": "Immediate first build", "summary": "Spend deep compute only where the answer can actually change.", "best_with": ["Memory Tiling / Active Context Geometry", "Sparse Strategic Verification", "Route Memory"]},
        {"id": "angle_02", "name": "Memory Tiling / Active Context Geometry", "group": "A", "wave": 1, "practicality": "high", "potential_gain": "high", "complexity": "medium", "role": "Immediate first build", "summary": "Make context structured, not flat.", "best_with": ["Elastic Depth Runtime", "Internal Compression of Thought State", "Cross-Episode Cognitive Continuity"]},
        {"id": "angle_03", "name": "Speculative Multi-Route Inference", "group": "B", "wave": 2, "practicality": "medium", "potential_gain": "high", "complexity": "medium-high", "role": "Route quality upgrade", "summary": "Test a few plausible ways of thinking briefly before fully committing.", "best_with": ["Route Memory", "Persistent Inference Residue", "Sparse Strategic Verification"]},
        {"id": "angle_04", "name": "Route Memory", "group": "A", "wave": 1, "practicality": "high", "potential_gain": "medium-high", "complexity": "medium", "role": "Historical adaptation", "summary": "Remember which execution policies work for which problem families.", "best_with": ["Speculative Multi-Route Inference", "Persistent Inference Residue", "Cross-Episode Cognitive Continuity"]},
        {"id": "angle_05", "name": "Persistent Inference Residue", "group": "B", "wave": 2, "practicality": "medium", "potential_gain": "high", "complexity": "high", "role": "Structural accumulation", "summary": "Keep the smallest reusable internal structures that repeatedly create advantage.", "best_with": ["Route Memory", "Speculative Multi-Route Inference", "Hierarchical Cognitive Identity"]},
        {"id": "angle_06", "name": "Self-Optimizing Runtime Governance", "group": "C", "wave": 3, "practicality": "medium", "potential_gain": "high", "complexity": "high", "role": "Meta-control layer", "summary": "Let the runtime learn how to govern itself better.", "best_with": ["Budget-Aware Intelligence Allocation", "Sparse Strategic Verification", "Multi-Scale Cognitive Scheduling"]},
        {"id": "angle_07", "name": "Multi-Scale Cognitive Scheduling", "group": "C", "wave": 3, "practicality": "medium", "potential_gain": "high", "complexity": "high", "role": "Timing intelligence", "summary": "Different kinds of thinking belong to different internal time horizons.", "best_with": ["Self-Optimizing Runtime Governance", "Budget-Aware Intelligence Allocation", "Cross-Episode Cognitive Continuity"]},
        {"id": "angle_08", "name": "Cross-Episode Cognitive Continuity", "group": "C", "wave": 4, "practicality": "medium", "potential_gain": "high", "complexity": "high", "role": "Long-horizon cognition", "summary": "Do not restart the larger cognitive process every time a new episode begins.", "best_with": ["Hierarchical Cognitive Identity", "Route Memory", "Cognitive Program Hosting"]},
        {"id": "angle_09", "name": "Hierarchical Cognitive Identity", "group": "C", "wave": 4, "practicality": "medium-low", "potential_gain": "high", "complexity": "high", "role": "Large-scale organization", "summary": "Know what organized kind of cognition is currently being continued.", "best_with": ["Cross-Episode Cognitive Continuity", "Persistent Inference Residue", "Cognitive Program Hosting"]},
        {"id": "angle_10", "name": "Cognitive Program Hosting", "group": "C", "wave": 5, "practicality": "medium-low", "potential_gain": "very-high", "complexity": "very-high", "role": "Substrate transition", "summary": "Treat cognition as managed programs, not only as one-shot responses.", "best_with": ["Hierarchical Cognitive Identity", "Cross-Episode Cognitive Continuity", "Inter-Process Knowledge Sharing"]},
        {"id": "angle_11", "name": "Sparse Strategic Verification", "group": "A", "wave": 1, "practicality": "high", "potential_gain": "medium-high", "complexity": "low-medium", "role": "Reliability layer", "summary": "Verify sparsely, but exactly where failure would matter.", "best_with": ["Elastic Depth Runtime", "Speculative Multi-Route Inference", "Self-Optimizing Runtime Governance"]},
        {"id": "angle_12", "name": "Internal Compression of Thought State", "group": "B", "wave": 4, "practicality": "medium", "potential_gain": "high", "complexity": "high", "role": "Advanced memory layer", "summary": "Preserve abstract operational state, not just raw text history.", "best_with": ["Memory Tiling / Active Context Geometry", "Cross-Episode Cognitive Continuity", "Dynamic Internal Specialization"]},
        {"id": "angle_13", "name": "Dynamic Internal Specialization", "group": "B", "wave": 4, "practicality": "medium", "potential_gain": "high", "complexity": "high", "role": "Task-specific efficiency", "summary": "A general model should not remain internally generic for every kind of task.", "best_with": ["Internal Compression of Thought State", "Budget-Aware Intelligence Allocation", "Speculative Multi-Route Inference"]},
        {"id": "angle_14", "name": "Budget-Aware Intelligence Allocation", "group": "C", "wave": 3, "practicality": "high", "potential_gain": "medium-high", "complexity": "medium", "role": "Control efficiency", "summary": "Allocate intelligence as a budgeted resource, not a fixed default.", "best_with": ["Self-Optimizing Runtime Governance", "Elastic Depth Runtime", "Multi-Scale Cognitive Scheduling"]},
        {"id": "angle_15", "name": "Inter-Process Knowledge Sharing", "group": "C", "wave": 5, "practicality": "medium-low", "potential_gain": "very-high", "complexity": "very-high", "role": "Substrate-scale compounding", "summary": "Let active cognitive processes share value without contaminating one another.", "best_with": ["Cognitive Program Hosting", "Cross-Episode Cognitive Continuity", "Route Memory"]},
    ]


def build_core_modules():
    return [
        {"id": "module_01", "name": "Elastic Depth Orchestrator", "wave": 1, "resolves_pain": "Uniform compute waste across trivial and critical reasoning segments.", "derived_from": ["Elastic Depth Runtime", "Budget-Aware Intelligence Allocation", "Sparse Strategic Verification"], "wow_factor": "Shows visibly different shallow/medium/deep treatment per reasoning segment."},
        {"id": "module_02", "name": "Context Geometry Engine", "wave": 1, "resolves_pain": "Long-context blur, repeated rereading, weak selective recall.", "derived_from": ["Memory Tiling / Active Context Geometry", "Internal Compression of Thought State", "Cross-Episode Cognitive Continuity"], "wow_factor": "Turns context into hot/warm/cold/latent geometry instead of one flat mass."},
        {"id": "module_03", "name": "Multi-Route Trial Engine", "wave": 2, "resolves_pain": "Premature commitment to weak inference routes.", "derived_from": ["Speculative Multi-Route Inference", "Sparse Strategic Verification", "Budget-Aware Intelligence Allocation"], "wow_factor": "Trials multiple candidate routes briefly before committing."},
        {"id": "module_04", "name": "Route Memory + Residue Vault", "wave": 2, "resolves_pain": "AI systems repeatedly rediscover good execution paths and discard useful internal structure.", "derived_from": ["Route Memory", "Persistent Inference Residue", "Cross-Episode Cognitive Continuity"], "wow_factor": "Stores route families, residue artifacts, reusable anchors and failure families."},
        {"id": "module_05", "name": "Governance & Continuity Kernel", "wave": 3, "resolves_pain": "Weak runtime discipline, poor budget control, lack of identity and continuity across episodes.", "derived_from": ["Self-Optimizing Runtime Governance", "Multi-Scale Cognitive Scheduling", "Cross-Episode Cognitive Continuity", "Hierarchical Cognitive Identity", "Cognitive Program Hosting"], "wow_factor": "Looks like the seed of a cognitive operating substrate, not just a prompt runner."},
    ]


def build_wave_map():
    return {
        "wave_1_runtime_core": ["Elastic Depth Runtime", "Memory Tiling / Active Context Geometry", "Sparse Strategic Verification", "Route Memory"],
        "wave_2_route_quality_and_accumulation": ["Speculative Multi-Route Inference", "Persistent Inference Residue"],
        "wave_3_runtime_self_organization": ["Self-Optimizing Runtime Governance", "Multi-Scale Cognitive Scheduling", "Budget-Aware Intelligence Allocation"],
        "wave_4_long_horizon_cognition": ["Cross-Episode Cognitive Continuity", "Hierarchical Cognitive Identity", "Internal Compression of Thought State", "Dynamic Internal Specialization"],
        "wave_5_cognitive_operating_substrate": ["Cognitive Program Hosting", "Inter-Process Knowledge Sharing"],
    }


def build_scoring_schema():
    return {
        "scale": "1-10",
        "fields": [
            "practicality_score",
            "gain_score",
            "complexity_score",
            "testability_score",
            "dependency_readiness_score",
            "continuity_value_score",
            "governance_risk_score",
        ],
        "composite_formula": "priority_score = practicality + gain + testability + dependency_readiness + continuity_value - 0.5*complexity - 0.5*governance_risk",
        "verdicts": ["keep", "refine", "merge", "archive", "split_subtrack"],
    }


def build_dependency_map(modules):
    return {
        modules[0]["name"]: {"depends_on": ["Budget-Aware Intelligence Allocation"], "amplifies": [modules[2]["name"], "Sparse Strategic Verification"], "best_after": []},
        modules[1]["name"]: {"depends_on": [], "amplifies": ["Cross-Episode Cognitive Continuity", "Internal Compression of Thought State"], "best_after": []},
        modules[2]["name"]: {"depends_on": [modules[0]["name"]], "amplifies": [modules[3]["name"], "Sparse Strategic Verification"], "best_after": [modules[0]["name"]]},
        modules[3]["name"]: {"depends_on": [modules[2]["name"]], "amplifies": [modules[4]["name"], "Cross-Episode Cognitive Continuity"], "best_after": [modules[2]["name"]]},
        modules[4]["name"]: {"depends_on": [modules[1]["name"], modules[3]["name"]], "amplifies": ["Cognitive Program Hosting", "Inter-Process Knowledge Sharing"], "best_after": [modules[3]["name"]]},
    }


def scores_for_angle(angle):
    practical = {"high": 9, "medium": 7, "medium-high": 8, "medium-low": 5, "low": 3}[angle["practicality"]]
    gain = {"very-high": 10, "high": 9, "medium-high": 8, "medium": 6, "low": 3}[angle["potential_gain"]]
    complexity = {"low-medium": 4, "medium": 5, "medium-high": 7, "high": 8, "very-high": 10}[angle["complexity"]]
    testability = max(3, 10 - (angle["wave"] - 1) * 2)
    dependency_readiness = max(3, 10 - (angle["wave"] - 1))
    continuity = {1: 4, 2: 6, 3: 7, 4: 9, 5: 10}[angle["wave"]]
    governance_risk = min(10, complexity + (1 if angle["group"] == "C" else 0))
    priority = round(practical + gain + testability + dependency_readiness + continuity - 0.5 * complexity - 0.5 * governance_risk, 2)
    return {
        "practicality_score": practical,
        "gain_score": gain,
        "complexity_score": complexity,
        "testability_score": testability,
        "dependency_readiness_score": dependency_readiness,
        "continuity_value_score": continuity,
        "governance_risk_score": governance_risk,
        "priority_score": priority,
    }


def verdict_from_scores(score):
    p = score["priority_score"]
    complexity = score["complexity_score"]
    risk = score["governance_risk_score"]
    dep = score["dependency_readiness_score"]
    if p >= 34 and complexity <= 7 and risk <= 7:
        return "keep"
    if p >= 31 and dep >= 7:
        return "refine"
    if p >= 28 and complexity >= 8:
        return "merge"
    if p < 24 and risk >= 8:
        return "split_subtrack"
    return "archive"


def bucket_from_scores(score):
    buildability = mean([score["practicality_score"], score["testability_score"], score["dependency_readiness_score"]])
    upside = mean([score["gain_score"], score["continuity_value_score"]])
    if buildability >= 8 and upside >= 8:
        return "easy_high_upside"
    if buildability >= 8 and upside < 8:
        return "easy_medium_upside"
    if buildability < 8 and upside >= 8:
        return "hard_high_upside"
    return "hard_transformative"


def build_angle_registry(angles):
    registry = []
    for angle in angles:
        score = scores_for_angle(angle)
        entry = dict(angle)
        entry.update(score)
        entry["verdict"] = verdict_from_scores(score)
        entry["matrix_bucket"] = bucket_from_scores(score)
        registry.append(entry)
    return registry


def build_candidate_profiles(modules, angle_registry):
    profiles = []
    angle_lookup = {a["name"]: a for a in angle_registry}
    for i, module in enumerate(modules, start=1):
        derived_scores = [angle_lookup[name]["priority_score"] for name in module["derived_from"] if name in angle_lookup]
        profile_score = round(mean(derived_scores), 2) if derived_scores else 0
        profiles.append({
            "candidate_id": f"candidate_{i:03d}",
            "name": module["name"],
            "status": "active",
            "wave": module["wave"],
            "derived_from": module["derived_from"],
            "resolves_pain": module["resolves_pain"],
            "candidate_score": profile_score,
            "recommended_next_experiment": f"Promote {module['name']} into a scored experiment with verdict tracking.",
        })
    return profiles


def build_experiment_registry(modules, angle_registry):
    angle_lookup = {a["name"]: a for a in angle_registry}
    experiments = []
    for i, module in enumerate(modules, start=1):
        scores = [angle_lookup[name]["priority_score"] for name in module["derived_from"] if name in angle_lookup]
        avg_score = round(mean(scores), 2) if scores else 0
        experiments.append({
            "experiment_id": f"exp_module_{i:03d}",
            "kind": "core_module",
            "target": module["name"],
            "hypothesis": f"{module['name']} can resolve a major AI runtime pain while remaining buildable inside the Atlas track.",
            "minimal_test": f"Generate registry objects, scoring, matrix placement and verdict for {module['name']}.",
            "expected_gain": "very-high" if avg_score >= 33 else "high",
            "failure_signal": "Module stays descriptive and cannot drive comparisons or next-wave decisions.",
            "score_proxy": avg_score,
            "verdict": "keep" if avg_score >= 33 else "refine",
            "next_decision": "advance_to_v1.3" if avg_score >= 33 else "deepen_in_v1.2",
        })
    for idx, angle in enumerate(angle_registry, start=1):
        experiments.append({
            "experiment_id": f"exp_angle_{idx:03d}",
            "kind": "atlas_angle",
            "target": angle["name"],
            "wave": angle["wave"],
            "hypothesis": f"{angle['name']} can contribute measurable same-hardware gains inside its wave.",
            "minimal_test": f"Score {angle['name']} for buildability, upside, continuity and governance risk.",
            "expected_gain": angle["potential_gain"],
            "failure_signal": "Angle remains ungrouped, unscored, or disconnected from wave execution.",
            "score_proxy": angle["priority_score"],
            "verdict": angle["verdict"],
            "next_decision": f"consider_in_wave_{angle['wave']}",
        })
    return experiments


def build_verdict_engine_description():
    return {
        "inputs": ["priority_score", "complexity_score", "dependency_readiness_score", "governance_risk_score"],
        "outputs": ["keep", "refine", "merge", "archive", "split_subtrack"],
        "meaning": {
            "keep": "Advance directly in the next build wave.",
            "refine": "Worth continuing, but needs stronger scaffolding or narrower tests.",
            "merge": "Should be advanced together with another angle/module.",
            "archive": "Not a near-term priority.",
            "split_subtrack": "Powerful but too heavy/risky for the current core track.",
        },
    }


def build_comparison_matrix(angle_registry):
    buckets = {"easy_high_upside": [], "easy_medium_upside": [], "hard_high_upside": [], "hard_transformative": []}
    for angle in angle_registry:
        buckets[angle["matrix_bucket"]].append({
            "name": angle["name"],
            "priority_score": angle["priority_score"],
            "verdict": angle["verdict"],
            "wave": angle["wave"],
        })
    for key in buckets:
        buckets[key] = sorted(buckets[key], key=lambda x: x["priority_score"], reverse=True)
    return buckets


def build_recommended_next_wave(angle_registry, modules):
    wave_scores = {}
    for wave in range(1, 6):
        scores = [a["priority_score"] for a in angle_registry if a["wave"] == wave]
        wave_scores[f"wave_{wave}"] = round(mean(scores), 2) if scores else 0
    best_wave_number = max(range(1, 6), key=lambda w: wave_scores[f"wave_{w}"])
    promoted_modules = [m["name"] for m in modules if m["wave"] <= best_wave_number][:3]
    return {
        "recommended_wave": best_wave_number,
        "wave_scores": wave_scores,
        "why": "Wave chosen by highest average priority across its current angle set.",
        "promote_first": promoted_modules,
    }


def build_unified_manifest(angles, modules, scoring_schema, wave_map, dependency_map):
    return {
        "project_name": "Atlas of Same-Hardware Cognitive Architecture Leaps",
        "lab_name": "ATLAS RUNTIME LAB",
        "version": VERSION,
        "script_name": SCRIPT_NAME,
        "separation_rule": "Separate track from MORPH Runtime Core.",
        "mission": "Build a practical architecture lab for same-hardware cognitive leaps.",
        "central_thesis": "Major gains may still be available on the same hardware if model execution is reorganized as cognition rather than treated as a mostly fixed inference path.",
        "unified_principle": "Do not hunt only one winning idea. Build a portfolio of combinable, testable architectural levers and advance the best buildable stack.",
        "five_core_modules": [m["name"] for m in modules],
        "all_atlas_angles_count": len(angles),
        "wave_map": wave_map,
        "dependency_map_keys": list(dependency_map.keys()),
        "scoring_schema": scoring_schema,
        "canonical_objects": ["angle", "candidate_profile", "route_record", "residue_record", "continuity_object", "governance_rule", "experiment_record", "wave_record", "report", "export_pack"],
        "build_rule": {"v1x": "registry + manifest + scoring + architecture comparison", "v2x": "micro-simulation and orchestration logic", "v3x": "continuity substrate and cognitive program hosting"},
    }


def build_master_roadmap():
    return {
        "v1.1": "Unified Manifest Core",
        "v1.2": "Registry & Experiment Engine",
        "v1.3": "Route Memory / Residue / Verification Layer",
        "v1.4": "Governance / Budget / Scheduling Layer",
        "v1.5": "Continuity / Identity Layer",
        "v1.6": "Compression / Specialization Layer",
        "v1.7": "Cognitive Program Hosting Seed",
        "v1.8": "Inter-Process Knowledge Sharing Seed",
        "v1.9": "Atlas Comparison Dashboard",
        "v2.0": "First Practical Architecture Lab",
    }


def build_summary_text(next_wave, module_experiments):
    promoted = ", ".join(next_wave["promote_first"])
    top_module = sorted(module_experiments, key=lambda x: x["score_proxy"], reverse=True)[0]
    return (
        f"Atlas Runtime Lab v{VERSION} summary\n"
        f"Recommended next wave: Wave {next_wave['recommended_wave']}\n"
        f"Promote first: {promoted}\n"
        f"Top core module experiment: {top_module['target']} (score proxy {top_module['score_proxy']})\n"
        f"This version upgrades Atlas from unified manifest to scored comparative lab nucleus.\n"
    )


def build_report_txt(manifest, modules, next_wave, module_experiments, matrix):
    lines = []
    lines.append(f"Atlas Runtime Lab v{VERSION} Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("Purpose: registry and experiment engine for the Atlas architecture lab")
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
    lines.append("Experiment Promotion Snapshot")
    for exp in module_experiments:
        lines.append(f"- {exp['target']}: score_proxy={exp['score_proxy']} verdict={exp['verdict']} next={exp['next_decision']}")
    lines.append("")
    lines.append("Comparison Matrix Snapshot")
    for bucket, items in matrix.items():
        names = ", ".join([f"{item['name']} ({item['priority_score']})" for item in items[:4]]) if items else "none"
        lines.append(f"- {bucket}: {names}")
    lines.append("")
    lines.append("Recommended Next Wave")
    lines.append(f"- wave_{next_wave['recommended_wave']}")
    lines.append(f"- promote_first: {', '.join(next_wave['promote_first'])}")
    lines.append(f"- why: {next_wave['why']}")
    lines.append("")
    lines.append("Immediate Next Upgrade Direction")
    lines.append("- deepen route memory / residue structures into operational records")
    lines.append("- attach sparse verification pivots to module experiments")
    lines.append("- add reusable failure-family registry")
    lines.append("- begin v1.3 route/residue/verification integration")
    return "\n".join(lines) + "\n"


def build_report_md(report_txt):
    sections = report_txt.strip().split("\n\n")
    md = [f"# Atlas Runtime Lab v{VERSION} Report"]
    for sec in sections[1:]:
        lines = sec.splitlines()
        if not lines:
            continue
        title = lines[0]
        md.append(f"\n## {title}\n")
        for line in lines[1:]:
            if line.startswith("-"):
                md.append(line)
            else:
                md.append(line)
    return "\n".join(md) + "\n"


def main():
    ensure_dirs()
    angles = build_angles()
    modules = build_core_modules()
    wave_map = build_wave_map()
    scoring_schema = build_scoring_schema()
    dependency_map = build_dependency_map(modules)
    angle_registry = build_angle_registry(angles)
    candidate_profiles = build_candidate_profiles(modules, angle_registry)
    experiment_registry = build_experiment_registry(modules, angle_registry)
    verdict_engine = build_verdict_engine_description()
    comparison_matrix = build_comparison_matrix(angle_registry)
    next_wave = build_recommended_next_wave(angle_registry, modules)
    manifest = build_unified_manifest(angles, modules, scoring_schema, wave_map, dependency_map)
    roadmap = build_master_roadmap()
    module_experiments = [e for e in experiment_registry if e["kind"] == "core_module"]
    summary_txt = build_summary_text(next_wave, module_experiments)
    report_txt = build_report_txt(manifest, modules, next_wave, module_experiments, comparison_matrix)
    report_md = build_report_md(report_txt)

    write_json(MANIFESTS / "atlas_manifest_v1_2.json", manifest)
    write_json(MANIFESTS / "scoring_schema_v1_2.json", scoring_schema)
    write_json(MANIFESTS / "dependency_map_v1_2.json", dependency_map)
    write_json(MANIFESTS / "wave_map_v1_2.json", wave_map)
    write_json(MODULES / "core_modules_v1_2.json", modules)
    write_json(DATA / "atlas_angles_v1_2.json", angle_registry)
    write_json(DATA / "candidate_profiles_v1_2.json", candidate_profiles)
    write_json(DATA / "experiment_registry_v1_2.json", experiment_registry)
    write_json(VERDICTS / "verdict_engine_v1_2.json", verdict_engine)
    write_json(MATRIX / "comparison_matrix_v1_2.json", comparison_matrix)
    write_json(ROADMAP / "master_unified_roadmap_v1_2.json", roadmap)
    write_json(ROADMAP / "recommended_next_wave_v1_2.json", next_wave)
    write_text(EXPORTS / "summary_v1.2.txt", summary_txt)
    write_text(EXPORTS / "atlas_unified_manifest_v1.2.md", json.dumps(manifest, indent=2, ensure_ascii=False))
    write_text(REPORTS / "report_v1.2.txt", report_txt)
    write_text(REPORTS / "report_v1.2.md", report_md)

    print(f"[OK] {SCRIPT_NAME} completed")
    print(f"[PACK] {PACK}")
    print(f"[REPORT] {REPORTS / 'report_v1.2.txt'}")
    print(f"[NEXT] recommended wave: wave_{next_wave['recommended_wave']}")


if __name__ == "__main__":
    main()
