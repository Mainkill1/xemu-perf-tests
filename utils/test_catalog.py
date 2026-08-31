#!/usr/bin/env python3
"""Generate the catalog and the guest's compact descriptor lookup table."""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Entry:
    id: str
    suite_id: str
    legacy_suite: str
    legacy_result: str
    execution_test: str
    description: str
    tags: tuple[str, ...]
    kind: str = "leaf"
    parent_id: str = ""
    selection_group: str = ""
    selection_bit: int = 0

    @property
    def legacy_id(self):
        return f"{self.legacy_suite}::{self.legacy_result}"


def leaf(id, suite_id, legacy_suite, legacy_result, description, tags,
         execution_test="", parent_id="", selection_group="", selection_bit=0):
    return Entry(id, suite_id, legacy_suite, legacy_result,
                 execution_test or legacy_result, description, tuple(tags), "leaf",
                 parent_id, selection_group, selection_bit)


def group(id, suite_id, legacy_suite, legacy_result, description, tags):
    return Entry(id, suite_id, legacy_suite, legacy_result, legacy_result,
                 description, tuple(tags), "group")


def entries():
    out = []

    def simple(sid, suite, pairs, tags):
        for stable, legacy in pairs:
            out.append(leaf(f"{sid}.{stable}", sid, suite, legacy,
                            f"Runs the {legacy} workload and records its deterministic result.", tags))

    simple("busy_pfifo", "BusyPfifo", [("pfifo_saturation", "PFIFOSaturation"),
           ("pgraph_pattern_polling", "PgraphPatternPolling")], ("pfifo", "performance", "hardware-safe"))
    simple("pfifo_array_elements", "PFIFOArrayElements", [
           ("array_element16", "pfifo.array-element16"),
           ("array_element32", "pfifo.array-element32"),
           ("array_element_pgr2", "pfifo.array-element-pgr2")],
           ("pfifo", "gpu", "performance", "hardware-safe"))
    simple("cpu_floating_point", "CpuFloatingPoint", [("sse_scalar", "SSEScalar"),
           ("x87_scalar", "X87Scalar")], ("cpu", "performance", "hardware-safe"))
    simple("cpu_translation_blocks", "CpuTranslationBlocks", [("direct_loop", "DirectLoop"),
           ("indirect_dispatch", "IndirectDispatch"),
           ("indirect_dispatch_stress", "IndirectDispatchStress")], ("cpu", "performance", "hardware-safe"))
    simple("fill_rate", "FillRate", [("solid", "FillRate-Solid"),
           ("textured", "FillRate-Textured")], ("gpu", "performance", "hardware-safe"))

    def staged(parent, legacy_parent, selection_group, stages, tags, description):
        out.append(group(parent, parent.split(".")[0], "GameLoadComposite", legacy_parent,
                         description + "; the group has no timing value.", tags + ("group",)))
        for bit, (stable, legacy) in enumerate(stages):
            out.append(leaf(f"{parent}.{stable}", parent.split(".")[0], "GameLoadComposite", legacy,
                            f"Measures the {stable.replace('_', ' ')} stage.", tags,
                            legacy_parent, parent, selection_group, bit))

    staged("game_load.long_unlocked_scene", "08-LongUnlockedScene", "long_scene", [
        ("cpu", "08-LongUnlockedScene-01-CPU"), ("pfifo", "08-LongUnlockedScene-02-PFIFO"),
        ("alpha_overdraw", "08-LongUnlockedScene-03-AlphaOverdraw"),
        ("streaming_surface_reuse", "08-LongUnlockedScene-04-StreamingSurfaceReuse"),
        ("combined", "08-LongUnlockedScene-05-Combined"),
        ("full_system", "08-LongUnlockedScene-06-FullSystem")],
        ("scenario", "performance", "hardware-safe"), "Groups the long-scene stages")
    staged("game_load.cross_title_hotpath", "09-CrossTitleHotpath", "cross_title", [
        ("queued_vertex_cpu_writes", "09-CrossTitleHotpath-01-QueuedVertexCpuWrites"),
        ("pgr2_small_draws", "09-CrossTitleHotpath-02-Pgr2SmallDraws"),
        ("texture_update_reuse", "09-CrossTitleHotpath-03-TextureUpdateReuse"),
        ("surface_reuse", "09-CrossTitleHotpath-04-SurfaceReuse"),
        ("pipeline_state_churn", "09-CrossTitleHotpath-05-PipelineStateChurn"),
        ("blend_constant_reuse", "09-CrossTitleHotpath-06-BlendConstantReuse"),
        ("texture_binding_reuse", "09-CrossTitleHotpath-07-TextureBindingReuse"),
        ("pgr2_lagspot_inline_elements", "09-CrossTitleHotpath-08-Pgr2LagspotInlineElements"),
        ("scaled_surface_pressure", "09-CrossTitleHotpath-09-ScaledSurfacePressure"),
        ("s3tc_streaming_fenced_draws", "09-CrossTitleHotpath-10-S3tcStreamingFencedDraws"),
        ("gpu_wait_control", "09-CrossTitleHotpath-11-GpuWaitControl")],
        ("scenario", "performance", "hardware-safe"), "Groups the cross-title stages")
    staged("game_load.s3tc_sync_factor", "10-S3tcSyncFactor", "s3tc_sync_factor", [
        ("dxt1_same_address_wait", "10-S3tcSyncFactor-01-Dxt1SameAddressWait"),
        ("dxt1_same_address_queued", "10-S3tcSyncFactor-02-Dxt1SameAddressQueued"),
        ("dxt1_ring_payload_generations", "10-S3tcSyncFactor-03-Dxt1RingPayloadGenerations"),
        ("dxt1_dirty_once_redraw", "10-S3tcSyncFactor-04-Dxt1DirtyOnceRedraw"),
        ("rgba8_same_address_wait", "10-S3tcSyncFactor-05-Rgba8SameAddressWait"),
        ("rgba8_same_address_queued", "10-S3tcSyncFactor-06-Rgba8SameAddressQueued"),
        ("rgba8_ring_payload_generations", "10-S3tcSyncFactor-07-Rgba8RingPayloadGenerations"),
        ("rgba8_dirty_once_redraw", "10-S3tcSyncFactor-08-Rgba8DirtyOnceRedraw"),
        ("bc2_native_eligible", "10-S3tcSyncFactor-09-Bc2NativeEligible"),
        ("bc2_bordered_fallback", "10-S3tcSyncFactor-10-Bc2BorderedFallback"),
        ("bc3_native_eligible", "10-S3tcSyncFactor-11-Bc3NativeEligible"),
        ("bc3_bordered_fallback", "10-S3tcSyncFactor-12-Bc3BorderedFallback")],
        ("texture", "correctness", "performance", "hardware-safe"), "Groups the S3TC matrix cells")

    simple("game_load", "GameLoadComposite", [("repeated_display", "12-RepeatedDisplay"),
           ("repeated_display_boosted", "12-RepeatedDisplay-Boosted")],
           ("scenario", "performance", "hardware-safe"))
    phases = [("cpu_only", "01-CPUOnly"), ("pfifo_only", "02-PFIFOOnly"),
              ("gpu_only", "03-GPUOnly"), ("streaming_only", "04-StreamingOnly"),
              ("cpu_pfifo_gpu", "05-CPUPFIFOGPU"),
              ("cpu_pfifo_gpu_streaming", "06-CPUPFIFOGPUStreaming"),
              ("full_system", "07-FullSystem")]
    for stable, legacy in [("doax_menu_representative", "DoaxMenuRepresentative"),
                           ("doax_menu_stress", "DoaxMenuStress"), ("pgr2_ai_backup", "Pgr2AiBackup")]:
        simple("game_load", "GameLoadComposite",
               [(f"{stable}.{phase}", f"{legacy}-{suffix}") for phase, suffix in phases],
               ("scenario", "performance", "hardware-safe"))

    simple("high_vertex_count", "High vertex count", [("arrays", "HighVtxCount-arrays"),
           ("inline_arrays", "HighVtxCount-inlinearrays"), ("inline_buffers", "HighVtxCount-inlinebuffers"),
           ("inline_elements", "HighVtxCount-inlineelements")], ("vertex", "performance", "hardware-safe"))
    for stable, legacy in [("line_loop", "LLoop"), ("line_strip", "LStrip"), ("lines", "Lines"),
                           ("points", "Points"), ("polygon", "Poly"), ("quad_strip", "QuadStrip"),
                           ("quads", "Quads"), ("triangle_fan", "TriFan"),
                           ("triangle_strip", "TriStrip"), ("triangles", "Tris")]:
        simple("primitive_type", "PrimitiveType", [(f"{stable}.fixed_function", f"PrimitiveType-{legacy}"),
               (f"{stable}.vertex_shader", f"PrimitiveType-{legacy}-vsh")],
               ("gpu", "primitive", "performance", "hardware-safe"))

    simple("surface", "SurfaceRendering", [("basic", "SurfaceRendering"),
           ("cpu_read_after_gpu_write", "XemuCpuReadAfterGpuWrite"),
           ("cpu_read_clean_surface", "XemuCpuReadCleanSurface"),
           ("framebuffer_working_set_002", "XemuFramebufferWorkingSet002"),
           ("framebuffer_working_set_008", "XemuFramebufferWorkingSet008"),
           ("framebuffer_working_set_032", "XemuFramebufferWorkingSet032"),
           ("framebuffer_working_set_064", "XemuFramebufferWorkingSet064"),
           ("full_clear_elision_guard", "XemuFullClearElisionGuard"),
           ("overlapping_surface_churn_representative", "XemuOverlappingSurfaceChurnRepresentative"),
           ("overlapping_surface_churn_stress", "XemuOverlappingSurfaceChurnStress"),
           ("partial_channel_clear_guard", "XemuPartialChannelClearGuard"),
           ("surface_download_path", "XemuSurfaceDownloadPath"),
           ("surface_list_lookup_002", "XemuSurfaceListLookup002"),
           ("surface_list_lookup_008", "XemuSurfaceListLookup008"),
           ("surface_list_lookup_032", "XemuSurfaceListLookup032"),
           ("surface_list_lookup_128", "XemuSurfaceListLookup128")],
           ("surface", "correctness", "performance", "hardware-safe"))
    for variant, title in (("representative", "Representative"), ("stress", "Stress")):
        parent = f"surface.vulkan_memory_pressure.{variant}"
        legacy_parent = f"XemuVulkanMemoryPressure{title}"
        out.append(group(parent, "surface", "SurfaceRendering", legacy_parent,
                         f"Groups the {variant} memory-pressure checkpoints; the group has no timing value.",
                         ("surface", "memory-pressure", "group", "xemu-only")))
        for bit, checkpoint in enumerate(("growth", "plateau", "alias_resize", "reuse", "idle_retention")):
            out.append(leaf(f"{parent}.{checkpoint}", "surface", "SurfaceRendering",
                            f"{legacy_parent}-{checkpoint}", f"Measures the {checkpoint} checkpoint.",
                            ("surface", "memory-pressure", "performance", "xemu-only"), legacy_parent,
                            parent, f"memory_pressure_{variant}", bit))

    for stable, legacy in (("arrays", "arrays"), ("inline_arrays", "inlinearrays"),
                           ("inline_buffers", "inlinebuffers"), ("inline_elements", "inlineelements")):
        simple("tiny_draw", "TinyDraw", [(f"{stable}.fixed_function", f"TinyDraw-{legacy}"),
               (f"{stable}.vertex_shader", f"TinyDraw-{legacy}-vsh")],
               ("gpu", "microbenchmark", "performance", "hardware-safe"))
    simple("uniform_thrash", "UniformThrash", [("uniform_thrash", "UniformThrash")],
           ("gpu", "performance", "hardware-safe"))
    simple("vertex_buffer_allocation", "Vertex buffer allocation", [
        ("mixed.arrays", "MixedVtxAlloc-arrays"), ("mixed.inline_arrays", "MixedVtxAlloc-inlinearrays"),
        ("mixed.inline_buffers", "MixedVtxAlloc-inlinebuffers"),
        ("mixed.inline_elements", "MixedVtxAlloc-inlineelements"), ("tiny.arrays", "TinyAlloc-arrays"),
        ("tiny.inline_arrays", "TinyAlloc-inlinearrays"), ("tiny.inline_buffers", "TinyAlloc-inlinebuffers"),
        ("tiny.inline_elements", "TinyAlloc-inlineelements"),
        ("disjoint_same_page", "XemuVertexRamDisjointSamePage")],
        ("vertex", "allocation", "performance", "hardware-safe"))
    return out


def validate(items):
    valid_tags = {"allocation", "correctness", "cpu", "gpu", "group", "hardware-safe", "memory-pressure",
                  "microbenchmark", "performance", "pfifo", "primitive", "scenario", "surface", "texture",
                  "vertex", "xemu-only"}
    ids, legacy = set(), set()
    for item in items:
        if item.id in ids or item.legacy_id in legacy:
            raise ValueError(f"duplicate descriptor: {item.id} / {item.legacy_id}")
        if not item.description or not item.tags or set(item.tags) - valid_tags:
            raise ValueError(f"invalid descriptor: {item.id}")
        ids.add(item.id); legacy.add(item.legacy_id)
    for item in items:
        if item.parent_id and item.parent_id not in ids:
            raise ValueError(f"missing parent for {item.id}")


def catalog(items):
    children = {}
    for item in items:
        children.setdefault(item.parent_id, []).append(item.id)
    tests = []
    for item in items:
        d = {"id": item.id, "revision": 1, "kind": item.kind, "legacy_ids": [item.legacy_id],
             "suite_id": item.suite_id, "display_name": item.legacy_result, "description": item.description,
             "tags": list(item.tags), "supported_targets": ["xemu"] if "xemu-only" in item.tags else ["xemu", "xbox"],
             "isolation": "same_process", "timeout_ms": 120000 if "stress" in item.id else 30000,
             "measurement_class": "scenario" if {"scenario", "memory-pressure"} & set(item.tags) else "micro"}
        if item.kind == "group":
            d.update(child_ids=children.get(item.id, []), aggregation="none", observations=[])
        else:
            d["execution"] = {"legacy_suite": item.legacy_suite, "legacy_test": item.execution_test}
            d["default_measurement"] = {"warmup_samples": 0, "measured_samples": "workload_default"}
            d["observations"] = [{"name": "framebuffer.visible", "kind": "hash",
                                  "algorithm": "fnv1a64", "scope_version": 1}]
        tests.append(d)
    raw = json.dumps(tests, sort_keys=True, separators=(",", ":")).encode()
    return {"schema_version": 1, "catalog_id": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "leaf_count": sum(x.kind == "leaf" for x in items),
            "group_count": sum(x.kind == "group" for x in items), "tests": tests}


def cpp(items, catalog_id):
    groups = {"": 0, "long_scene": 1, "cross_title": 2, "s3tc_sync_factor": 3,
              "memory_pressure_representative": 4, "memory_pressure_stress": 5}
    lines = ["// Generated by utils/test_catalog.py. Do not edit.", "static const TestDescriptor kTestCatalog[] = {"]
    for x in items:
        q = json.dumps
        lines.append(f"  {{{q(x.id)}, 1, {q(x.suite_id)}, {q(x.legacy_suite)}, {q(x.legacy_result)}, "
                     f"{q(x.execution_test)}, TestKind::{x.kind.upper()}, {groups[x.selection_group]}, {x.selection_bit}}},")
    return "\n".join(lines + ["};", "static constexpr size_t kTestCatalogSize = sizeof(kTestCatalog) / sizeof(kTestCatalog[0]);",
                                f"static constexpr const char *kTestCatalogId = {json.dumps(catalog_id)};", ""])


def markdown(doc):
    lines = ["# Generated test catalog", "", f"Catalog `{doc['catalog_id']}` contains {doc['leaf_count']} leaves and {doc['group_count']} groups.", "",
             "| Stable ID | Kind | Legacy ID |", "| --- | --- | --- |"]
    lines += [f"| `{x['id']}` | {x['kind']} | `{x['legacy_ids'][0]}` |" for x in doc["tests"]]
    return "\n".join(lines) + "\n"


def catalog_json(doc):
    lines = ["{", f'  "schema_version": {doc["schema_version"]},',
             f'  "catalog_id": {json.dumps(doc["catalog_id"])},',
             f'  "leaf_count": {doc["leaf_count"]},', f'  "group_count": {doc["group_count"]},',
             '  "tests": [']
    for index, test in enumerate(doc["tests"]):
        lines.append("    " + json.dumps(test, separators=(",", ":")) +
                     ("," if index + 1 < len(doc["tests"]) else ""))
    return "\n".join(lines + ["  ]", "}", ""])


def render():
    items = entries(); validate(items); doc = catalog(items)

    def resolved_plan(ids, settings):
        plan_contract = {"catalog_id": doc["catalog_id"],
                         "tests": [{"id": x} for x in ids]}
        plan_id = "sha256:" + hashlib.sha256(json.dumps(
            plan_contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {"settings": settings,
                "resolved_plan": {"schema_version": 2, "plan_id": plan_id,
                                  "catalog_id": doc["catalog_id"],
                                  "selected_leaf_count": len(ids),
                                  "tests": [{"id": x} for x in ids]}}

    smoke_ids = ["busy_pfifo.pgraph_pattern_polling", "surface.cpu_read_clean_surface",
                 "game_load.s3tc_sync_factor.dxt1_dirty_once_redraw"]
    smoke_plan = resolved_plan(smoke_ids, {"enable_autorun_immediately": True})
    pfifo_ids = ["pfifo_array_elements.array_element16",
                 "pfifo_array_elements.array_element32",
                 "pfifo_array_elements.array_element_pgr2"]
    pfifo_smoke = resolved_plan(pfifo_ids, {
        "enable_autorun_immediately": True, "warmup_iterations": 1,
        "measurement_iterations_multiplier": 1, "gpu_completion_mode": "enqueue",
        "output_directory_path": "e:/xemu_perf_tests"})
    pfifo_quick = resolved_plan(pfifo_ids, {
        "enable_autorun_immediately": True, "warmup_iterations": 300,
        "measurement_iterations_multiplier": 150, "gpu_completion_mode": "batch_complete",
        "output_directory_path": "e:/xemu_perf_tests"})
    pfifo_sustained = resolved_plan(pfifo_ids, {
        "enable_autorun_immediately": True, "warmup_iterations": 750,
        "measurement_iterations_multiplier": 375, "gpu_completion_mode": "batch_complete",
        "output_directory_path": "e:/xemu_perf_tests"})
    return {ROOT / "resources/catalog.json": catalog_json(doc),
            ROOT / "resources/plans/smoke.json": json.dumps(smoke_plan, indent=2) + "\n",
            ROOT / "resources/pfifo-array-elements-fast-smoke.json": json.dumps(pfifo_smoke, indent=2) + "\n",
            ROOT / "resources/pfifo-array-elements-quick.json": json.dumps(pfifo_quick, indent=2) + "\n",
            ROOT / "resources/pfifo-array-elements-sustained.json": json.dumps(pfifo_sustained, indent=2) + "\n",
            ROOT / "docs/generated/test-catalog.md": markdown(doc),
            ROOT / "src/generated/test_catalog.inc": cpp(items, doc["catalog_id"])}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--check", action="store_true"); args = p.parse_args()
    stale = []
    for path, content in render().items():
        if path.exists() and path.read_text(encoding="utf-8") == content: continue
        stale.append(path)
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")
    if stale and args.check:
        print("stale: " + ", ".join(str(x.relative_to(ROOT)) for x in stale)); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
