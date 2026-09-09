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
    for stable, legacy in (
        ("array_element16_overflow", "pfifo.boundary-array-element16"),
        ("array_element32_overflow", "pfifo.boundary-array-element32"),
        ("inline_array_overflow", "pfifo.boundary-inline-array"),
        ("incrementing_inline_fallback", "pfifo.incrementing-inline-fallback"),
    ):
        out.append(leaf(
            f"pfifo_packet_boundary.{stable}", "pfifo_packet_boundary",
            "PFIFOPacketBoundary", legacy,
            "Exercises xemu's controlled PFIFO/PGRAPH packet boundary path.",
            ("pfifo", "gpu", "correctness", "xemu-only")))
    simple("cpu_floating_point", "CpuFloatingPoint", [("sse_scalar", "SSEScalar"),
           ("x87_scalar", "X87Scalar")], ("cpu", "performance", "hardware-safe"))
    simple("cpu_translation_blocks", "CpuTranslationBlocks", [("direct_loop", "DirectLoop"),
           ("indirect_dispatch", "IndirectDispatch"),
           ("indirect_dispatch_stress", "IndirectDispatchStress")], ("cpu", "performance", "hardware-safe"))
    simple("fill_rate", "FillRate", [("solid", "FillRate-Solid"),
           ("textured", "FillRate-Textured")], ("gpu", "performance", "hardware-safe"))
    simple("pipeline_texture_switch", "PipelineTextureSwitch", [
        ("texture_switch", "pipeline.texture-switch"),
        ("shader_negative_control", "pipeline.shader-negative-control"),
        ("clear_texture_normal", "pipeline.clear-texture-normal"),
        ("sampler_only_identity", "pipeline.sampler-only-identity")],
        ("texture", "gpu", "performance", "hardware-safe"))
    simple("report_query", "ReportQuery", [
        ("zero_query", "report.zero-query"),
        ("single_boundary", "report.single-boundary"),
        ("clear_boundary", "report.clear-boundary"),
        ("multiple_boundaries", "report.multiple-boundaries"),
        ("dma_target_switch", "report.dma-target-switch"),
        ("fifo_producer_ordering", "report.fifo-producer-ordering")],
        ("report", "gpu", "correctness", "performance", "hardware-safe"))
    simple("report_query", "ReportQuery", [
        ("dma_descriptor_rewrite", "report.dma-descriptor-rewrite"),
        ("dma_range_guard", "report.dma-range-guard")],
        ("report", "gpu", "correctness", "xemu-only"))

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
    out.append(leaf(
        "vertex_buffer_allocation.rising_transient_growth",
        "vertex_buffer_allocation", "Vertex buffer allocation",
        "XemuRisingTransientBufferGrowth",
        "Crosses exact Vulkan transient-buffer capacities with repeated small increases and one large increase.",
        ("vertex", "allocation", "correctness", "xemu-only")))
    return out


def validate(items):
    valid_tags = {"allocation", "correctness", "cpu", "gpu", "group", "hardware-safe", "memory-pressure",
                  "microbenchmark", "performance", "pfifo", "primitive", "scenario", "surface", "texture",
                  "report", "vertex", "xemu-only"}
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
        d = {"id": item.id, "revision": 2 if item.suite_id == "report_query" else 1,
             "kind": item.kind, "legacy_ids": [item.legacy_id],
             "suite_id": item.suite_id, "display_name": item.legacy_result, "description": item.description,
             "tags": list(item.tags), "supported_targets": ["xemu"] if "xemu-only" in item.tags else ["xemu", "xbox"],
             "isolation": "same_process", "timeout_ms": 300000 if item.suite_id == "pfifo_packet_boundary" else
                                                      (120000 if "stress" in item.id else 30000),
             "measurement_class": "correctness" if "performance" not in item.tags else
                                  ("scenario" if {"scenario", "memory-pressure"} & set(item.tags) else "micro")}
        if item.kind == "group":
            d.update(child_ids=children.get(item.id, []), aggregation="none", observations=[])
        else:
            d["execution"] = {"legacy_suite": item.legacy_suite, "legacy_test": item.execution_test}
            d["default_measurement"] = {
                "warmup_samples": 0,
                "measured_samples": 1 if "performance" not in item.tags else "workload_default",
            }
            d["observations"] = [{"name": "framebuffer.visible", "kind": "hash",
                                  "algorithm": "fnv1a64", "scope_version": 1}]
            if item.suite_id == "report_query":
                d["observations"].append({"name": "report.memory", "kind": "structured",
                                          "scope_version": 1})
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
        revision = 2 if x.suite_id == "report_query" else 1
        lines.append(f"  {{{q(x.id)}, {revision}, {q(x.suite_id)}, {q(x.legacy_result)}, {q(x.description)}, "
                     f"{q(x.legacy_suite)}, {q(x.legacy_result)}, "
                     f"{q(x.execution_test)}, TestKind::{x.kind.upper()}, {groups[x.selection_group]}, {x.selection_bit}}},")
    return "\n".join(lines + ["};", "static constexpr size_t kTestCatalogSize = sizeof(kTestCatalog) / sizeof(kTestCatalog[0]);",
                                f"static constexpr const char *kTestCatalogId = {json.dumps(catalog_id)};", ""])


def markdown(doc):
    lines = ["# Generated test catalog", "", f"Catalog `{doc['catalog_id']}` contains {doc['leaf_count']} leaves and {doc['group_count']} groups.", "",
             "| Stable ID | Kind | Legacy ID |", "| --- | --- | --- |"]
    lines += [f"| `{x['id']}` | {x['kind']} | `{x['legacy_ids'][0]}` |" for x in doc["tests"]]
    return "\n".join(lines) + "\n"


def failure_diagnosis(test):
    """Return a catalog-specific failure meaning and first code areas to inspect."""
    test_id = test["id"]
    if test["kind"] == "group":
        return (
            "At least one child checkpoint failed, a child result is missing, or group completion was recorded incorrectly. "
            "Inspect the child records in order; the group has no independent timing oracle."
        )

    exact = {
        "busy_pfifo.pfifo_saturation":
            "PFIFO did not consume the fixed push-buffer stream or produced the wrong final image. Check DMA get/put handling, packet decode, FIFO stalls, and PFIFO/PGRAPH lock handoff.",
        "busy_pfifo.pgraph_pattern_polling":
            "The guest-observed PGRAPH completion pattern or rendered result changed. Check report/status polling, notification ordering, GPU completion waits, and busy-bit transitions.",
        "cpu_floating_point.sse_scalar":
            "SSE scalar values or flags differ from the known-answer sequence. Check TCG SSE helpers, MXCSR rounding/FTZ/DAZ state, NaN handling, and native hard-FPU shortcuts.",
        "cpu_floating_point.x87_scalar":
            "x87 values, classifications, or status differ. Check extended precision, control-word rounding, exceptions, NaN/denormal handling, and hard-FPU conversion boundaries.",
        "cpu_translation_blocks.direct_loop":
            "A direct-branch loop produced the wrong checksum or stopped making progress. Check TCG block chaining, instruction counting, interrupt exits, and translated-code invalidation.",
        "cpu_translation_blocks.indirect_dispatch":
            "The fixed indirect jump-table sequence diverged. Check indirect TB lookup, target caching, register state at exits, and branch dispatch.",
        "cpu_translation_blocks.indirect_dispatch_stress":
            "The larger indirect-target set diverged or timed out. Check TB hash/lookup behavior, eviction, chaining misses, and state restoration across repeated indirect exits.",
        "fill_rate.solid":
            "Solid fragments have wrong coverage/color or the draw does not complete. Check clear/raster state, color masks, viewport/scissor, render-pass setup, and host fill path.",
        "fill_rate.textured":
            "Textured fragments differ or texture sampling stalls. Check texture upload/layout, sampler state, coordinates, cache invalidation, and fragment-shader translation.",
        "pipeline_texture_switch.texture_switch":
            "Switching texture bindings preserved stale image/sampler state or rebuilt the wrong pipeline. Check descriptor keys, texture generations, binding dirty flags, and pipeline reuse.",
        "pipeline_texture_switch.shader_negative_control":
            "A real shader-state change was incorrectly suppressed. Check shader/pipeline key normalization and dirty-bit elision; this control must change output when shader state changes.",
        "pipeline_texture_switch.clear_texture_normal":
            "State leaked across clear, texture-only, and normal-draw boundaries. Check clear-pipeline lifetime, descriptor dirtiness, render-pass transitions, and post-clear state restoration.",
        "pipeline_texture_switch.sampler_only_identity":
            "An identical sampler write changed output or caused an invalid reuse decision. Check sampler identity keys, compare-before-dirty logic, descriptor cache lifetime, and texture-stage normalization.",
        "report_query.zero_query":
            "A disabled-ZPASS report did not publish a complete zero-valued record after ordered GPU and host-report completion. Check explicit ZPASS disable, query initialization, report completion, and timestamp/value/done stores.",
        "report_query.single_boundary":
            "A single counted draw did not publish a complete nonzero report after ordered GPU and host-report completion. Check query begin/end, GET_REPORT ordering, and timestamp/value/done stores.",
        "report_query.clear_boundary":
            "Equal counted draws separated by CLEAR_REPORT_VALUE did not produce equal complete records. Check clear ordering, cumulative query state, and report publication.",
        "report_query.multiple_boundaries":
            "Two equal counted draws did not produce the expected cumulative 1x/2x complete records. Check query boundary ordering and cumulative report state.",
        "report_query.dma_target_switch":
            "Reports queued around SET_CONTEXT_DMA_REPORT did not reach complete A0/B0 records with equal counts. Check report-context ownership and pending-report ordering.",
        "report_query.fifo_producer_ordering":
            "Producer methods or the second counted draw overtook the first report boundary. Check PFIFO method order, synchronous report completion, and query publication.",
        "report_query.dma_descriptor_rewrite":
            "The A0 positive control, pending A1 ownership, untouched B1 sentinel, or post-rewrite B0 control failed. Check queue-time DMA descriptor snapshotting, direct RAMIN mutation, and terminal completion. This is an xemu-only oracle pending hardware characterization.",
        "report_query.dma_range_guard":
            "The valid offset-0 control failed or invalid offset 16 modified the complete target record/surrounding canaries. Check inclusive DMA extent normalization and subtraction-based 16-byte report bounds. This is an xemu-only oracle pending hardware characterization.",
        "game_load.repeated_display":
            "Repeated presentation changed the deterministic scene or stopped advancing. Check flip/vblank ordering, scanout ownership, present waits, and retained renderer state.",
        "game_load.repeated_display_boosted":
            "The sustained presentation variant diverged under heavier work. Check the same flip path plus queue growth, throttling, resource lifetime, and delayed completion.",
        "surface.basic":
            "Basic render-to-surface output differs. Check surface format/pitch, attachment creation, layout transitions, viewport/scissor, and download conversion.",
        "surface.cpu_read_after_gpu_write":
            "The CPU did not observe the GPU's newest surface bytes. Check GPU-to-RAM synchronization, dirty ownership, fence waits, download range, and cache invalidation.",
        "surface.cpu_read_clean_surface":
            "Reading an already synchronized surface changed data or performed the wrong path. Check clean/dirty state, redundant download elision, RAM validity, and surface ownership epochs.",
        "surface.full_clear_elision_guard":
            "A full clear was incorrectly skipped or applied to the wrong channels. Check clear coverage proof, color/depth masks, attachment extent, and dirty-state propagation.",
        "surface.partial_channel_clear_guard":
            "A masked clear was treated as a full clear or lost untouched channels. Check channel masks, clear fast-path eligibility, blending/write masks, and surface preservation.",
        "surface.surface_download_path":
            "Downloaded RAM bytes or the post-download frame differ. Check image-to-buffer usage/layout, scaled blit, depth/stencil conversion, mapping/invalidation, pitch, and swizzle.",
        "surface.overlapping_surface_churn_representative":
            "Ordinary overlapping views retained stale data or invalidated the wrong resource. Check overlap lookup, alias ownership, format/pitch reinterpretation, and upload/download ordering.",
        "surface.overlapping_surface_churn_stress":
            "Heavy alias churn exposed stale data, unbounded resources, or a lifetime fault. Check overlap indexing, eviction, deferred destruction, fences, and conservative reconciliation.",
        "uniform_thrash.uniform_thrash":
            "Rapid constant writes produced stale shader inputs or lost a real update. Check compare-before-dirty logic, dirty-row masks, uniform packing, descriptor staging, and shader constant indexing.",
        "vertex_buffer_allocation.disjoint_same_page":
            "Two disjoint vertex ranges sharing one guest page interfered. Check byte-range versus page dirty tracking, upload offsets, cache keys, and allocation aliasing.",
        "vertex_buffer_allocation.rising_transient_growth":
            "A just-below, exact-capacity, repeated-small-growth, or large-growth phase failed. Check required-size arithmetic, paired buffer capacities, mapping restoration, command-buffer completion, and post-growth draw offsets.",
    }
    if test_id in exact:
        return exact[test_id]

    if test_id.startswith("pfifo_array_elements."):
        width = "16-bit" if "16" in test_id else "32-bit"
        shape = "the PGR2-shaped mixed packet stream" if test_id.endswith("pgr2") else f"the {width} element stream"
        return f"{shape.capitalize()} produced wrong indices, vertices, or pixels. Check non-incrementing method packet length, endian unpacking, index expansion, bounds growth, and bulk PFIFO dispatch."

    if test_id.startswith("pfifo_packet_boundary."):
        return "xemu aborted, consumed the wrong word count, partially applied an oversized packet, or failed to resume after controlled rejection. Check preflight capacity arithmetic, scalar/bulk mode selection, PFIFO method-count updates, and destination-state mutation order."

    if test_id.startswith("high_vertex_count."):
        mode = test_id.rsplit(".", 1)[-1].replace("_", " ")
        return f"The large {mode} submission lost or reordered vertices. Check packet capacity growth, vertex/index conversion, draw splitting, buffer offsets, and allocation rollover."

    if test_id.startswith("primitive_type."):
        parts = test_id.split(".")
        topology = parts[1].replace("_", " ")
        path = "fixed-function" if parts[2] == "fixed_function" else "vertex-shader"
        return f"{topology.title()} assembly or raster coverage differs on the {path} path. Check topology conversion, closure/restart vertices, provoking vertex, clipping, attribute fetch, and viewport rules."

    if test_id.startswith("tiny_draw."):
        parts = test_id.split(".")
        mode = parts[1].replace("_", " ")
        path = "fixed-function" if parts[2] == "fixed_function" else "vertex-shader"
        return f"Tiny {mode} draws differ or lose state on the {path} path. Check per-packet dispatch, small-buffer allocation, state carry-over, draw batching, attribute fetch, and pipeline binding."

    if test_id.startswith("vertex_buffer_allocation."):
        _, size_class, mode = test_id.split(".")
        return f"The {size_class} {mode.replace('_', ' ')} allocation sequence reused or addressed the wrong vertex data. Check alignment, ring wrap, allocation lifetime, upload offsets, cache invalidation, and fence protection."

    if test_id.startswith("surface.framebuffer_working_set_"):
        count = test_id.rsplit("_", 1)[-1].lstrip("0") or "0"
        return f"The {count}-surface framebuffer working set changed output or resource lifetime. Check surface-cache capacity, eviction safety, attachment reuse, dirty ownership, and deferred destruction."

    if test_id.startswith("surface.surface_list_lookup_"):
        count = test_id.rsplit("_", 1)[-1].lstrip("0") or "0"
        return f"Lookup among {count} active surfaces selected or skipped the wrong overlap. Check address-range boundaries, interval/list ordering, pitch/extent calculation, and stale-list removal."

    if test_id.startswith("surface.vulkan_memory_pressure."):
        checkpoint = test_id.rsplit(".", 1)[-1]
        meanings = {
            "growth": "live Vulkan memory did not grow only as the fixed working set was created",
            "plateau": "memory failed to stabilize after the working set became steady",
            "alias_resize": "resized or aliased views retained stale allocations/data",
            "reuse": "compatible resources were not safely reused",
            "idle_retention": "idle resources were retained or reclaimed outside the declared policy",
        }
        return f"The {checkpoint.replace('_', ' ')} checkpoint failed: {meanings[checkpoint]}. Check allocation counters, cache keys, fence-complete retirement, eviction policy, and host-memory accounting."

    if test_id.startswith("game_load.s3tc_sync_factor."):
        cell = test_id.split(".")[-1]
        fmt = "DXT1" if cell.startswith("dxt1") else "RGBA8" if cell.startswith("rgba8") else "BC2" if cell.startswith("bc2") else "BC3"
        if "same_address_wait" in cell:
            behavior = "same-address rewrite followed by an explicit GPU wait"
            checks = "dirty-generation detection, synchronized replacement, upload bytes, and fence completion"
        elif "same_address_queued" in cell:
            behavior = "same-address rewrite while work remains queued"
            checks = "queued resource generations, staging lifetime, write-after-read hazards, and submission ordering"
        elif "ring_payload_generations" in cell:
            behavior = "rotating payload generations in a fixed address ring"
            checks = "generation keys, ring wrap, stale descriptor reuse, and in-flight allocation protection"
        elif "dirty_once_redraw" in cell:
            behavior = "one dirty upload followed by unchanged redraws"
            checks = "dirty-bit clearing, unchanged-upload elision, hash/cache reuse, and retained texture validity"
        elif "native_eligible" in cell:
            behavior = "a block-compressed texture eligible for native host upload"
            checks = "compressed-format capability, mip/block dimensions, native upload selection, and sampled texel decoding"
        else:
            behavior = "a bordered block-compressed texture that must take the fallback path"
            checks = "native-path rejection, CPU decompression, border fixup, expanded format, and fallback upload lifetime"
        return f"The {fmt} {behavior} cell produced the wrong KAT/frame. Check {checks}."

    if test_id.startswith("game_load.cross_title_hotpath."):
        stage = test_id.rsplit(".", 1)[-1]
        causes = {
            "queued_vertex_cpu_writes": "CPU-written vertex generations, dirty ranges, queued uploads, and host-buffer lifetime",
            "pgr2_small_draws": "tiny-draw dispatch, redundant state suppression, vertex allocation, and pipeline binding",
            "texture_update_reuse": "texture dirty tracking, same-address replacement, cache keys, and upload reuse",
            "surface_reuse": "surface compatibility keys, attachment ownership, dirty transitions, and fence-safe reuse",
            "pipeline_state_churn": "shader/pipeline key normalization, cache invalidation, and redundant bind suppression",
            "blend_constant_reuse": "blend-constant comparison, dynamic-state dirtiness, and command emission",
            "texture_binding_reuse": "descriptor identity, texture-stage dirtiness, and stale binding reuse",
            "pgr2_lagspot_inline_elements": "inline element packet decode, bulk method handling, index expansion, and small-draw submission",
            "scaled_surface_pressure": "scaled extent math, surface copies, aliasing, attachment cache pressure, and readback",
            "s3tc_streaming_fenced_draws": "compressed upload/fallback selection, staging lifetime, fences, and repeated streaming generations",
            "gpu_wait_control": "finish reason, report/fence completion, queue submission, and CPU wait accounting",
        }
        return f"The {stage.replace('_', ' ')} stage diverged. Check {causes[stage]}."

    if test_id.startswith("game_load.long_unlocked_scene."):
        stage = test_id.rsplit(".", 1)[-1]
        causes = {
            "cpu": "TCG execution, branches, MMIO callbacks, and guest timing",
            "pfifo": "push-buffer decode, method dispatch, FIFO stalls, and PFIFO/PGRAPH locks",
            "alpha_overdraw": "blend state, depth ordering, fragment coverage, and fill/host-GPU execution",
            "streaming_surface_reuse": "surface/texture generations, uploads, alias ownership, and cache reuse",
            "combined": "CPU-to-PFIFO overlap, renderer synchronization, and critical-path lock waits",
            "full_system": "combined CPU, PFIFO, renderer, streaming, completion, and lifecycle interactions",
        }
        return f"The sustained {stage.replace('_', ' ')} phase failed or stopped advancing. Check {causes[stage]}."

    if test_id.startswith("game_load."):
        phase = test_id.rsplit(".", 1)[-1]
        workload = test_id.split(".")[1].replace("_", " ")
        causes = {
            "cpu_only": "TCG/TB execution, branches, MMIO, and guest timer behavior",
            "pfifo_only": "push-buffer parsing, method dispatch, FIFO progress, and PFIFO/PGRAPH locking",
            "gpu_only": "draw state, shader/pipeline translation, attachments, and host GPU completion",
            "streaming_only": "dirty ranges, texture/surface uploads, cache reuse, and memory ownership",
            "cpu_pfifo_gpu": "CPU/PFIFO/renderer scheduling, synchronization, and critical-path lock handoffs",
            "cpu_pfifo_gpu_streaming": "combined scheduling plus resource generations, transfers, and alias hazards",
            "full_system": "all prior domains plus lifecycle, pacing, and accumulated state between phases",
        }
        if phase in causes:
            return f"The {workload} {phase.replace('_', ' ')} phase changed its deterministic result. Check {causes[phase]}."

    return "The deterministic output or completion contract changed. Compare the first failed check and framebuffer hash, then inspect the test's tagged subsystem and the first divergence before changing an oracle."


def failure_guide_markdown(doc):
    lines = [
        "# Test failure guide",
        "",
        f"Generated from catalog `{doc['catalog_id']}`. It covers all {len(doc['tests'])} entries; do not edit this file directly.",
        "",
        "## Reading a failure",
        "",
        "- `outcome: FAIL` means a guest known-answer, invariant, or semantic check failed. A soft failure continues the suite but still fails the run.",
        "- A framebuffer mismatch with passing internal checks usually points to rendering, readback, undefined pixels, or an unapproved oracle—not automatically to the measured hot path.",
        "- A passing result that is slower is a performance regression, not a functional failure. Compare identical work, completion mode, backend, scale, and warm state.",
        "- If upstream and candidate fail identically, investigate the test/oracle or a shared upstream defect before blaming the patch.",
        "- Group entries summarize children. Diagnose the first failing child; groups intentionally have no timing measurement.",
        "- Never replace a golden because one build disagrees. Retail-hardware evidence or a proven specification establishes correctness.",
        "",
    ]
    suites = {}
    for test in doc["tests"]:
        suites.setdefault(test["suite_id"], []).append(test)
    for suite_id, tests in suites.items():
        lines += [f"## `{suite_id}`", "", "| Stable ID | Kind | Likely failure cause and first checks |", "| --- | --- | --- |"]
        for test in tests:
            diagnosis = failure_diagnosis(test).replace("|", "\\|")
            lines.append(f"| `{test['id']}` | {test['kind']} | {diagnosis} |")
        lines.append("")
    return "\n".join(lines)


def catalog_json(doc):
    lines = ["{", f'  "schema_version": {doc["schema_version"]},',
             f'  "catalog_id": {json.dumps(doc["catalog_id"])},',
             f'  "leaf_count": {doc["leaf_count"]},', f'  "group_count": {doc["group_count"]},',
             '  "tests": [']
    for index, test in enumerate(doc["tests"]):
        lines.append("    " + json.dumps(test, separators=(",", ":")) +
                     ("," if index + 1 < len(doc["tests"]) else ""))
    return "\n".join(lines + ["  ]", "}", ""])


def resolved_plan(doc, settings, ids):
    tests = [{"id": test_id} for test_id in ids]
    contract = {"catalog_id": doc["catalog_id"], "tests": tests}
    plan_id = "sha256:" + hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return json.dumps({
        "settings": settings,
        "resolved_plan": {
            "schema_version": 2,
            "plan_id": plan_id,
            "catalog_id": doc["catalog_id"],
            "selected_leaf_count": len(ids),
            "tests": tests,
        },
    }, indent=2) + "\n"


def render():
    items = entries(); validate(items); doc = catalog(items)
    smoke_ids = ["busy_pfifo.pgraph_pattern_polling", "surface.cpu_read_clean_surface",
                 "game_load.s3tc_sync_factor.dxt1_dirty_once_redraw"]
    smoke_plan = resolved_plan(doc, {"enable_autorun_immediately": True}, smoke_ids)
    pfifo_ids = ["pfifo_array_elements.array_element16",
                 "pfifo_array_elements.array_element32",
                 "pfifo_array_elements.array_element_pgr2"]
    pfifo_smoke = resolved_plan(doc, {
        "enable_autorun_immediately": True, "warmup_iterations": 1,
        "measurement_iterations_multiplier": 1, "gpu_completion_mode": "enqueue",
        "output_directory_path": "e:/xemu_perf_tests"}, pfifo_ids)
    pfifo_quick = resolved_plan(doc, {
        "enable_autorun_immediately": True, "warmup_iterations": 300,
        "measurement_iterations_multiplier": 150, "gpu_completion_mode": "batch_complete",
        "output_directory_path": "e:/xemu_perf_tests"}, pfifo_ids)
    pfifo_sustained = resolved_plan(doc, {
        "enable_autorun_immediately": True, "warmup_iterations": 750,
        "measurement_iterations_multiplier": 375, "gpu_completion_mode": "batch_complete",
        "output_directory_path": "e:/xemu_perf_tests"}, pfifo_ids)
    pfifo_boundary_ids = [
        "pfifo_packet_boundary.array_element16_overflow",
        "pfifo_packet_boundary.array_element32_overflow",
        "pfifo_packet_boundary.inline_array_overflow",
        "pfifo_packet_boundary.incrementing_inline_fallback",
    ]
    pfifo_boundary = resolved_plan(doc, {
        "enable_autorun_immediately": True, "warmup_iterations": 0,
        "measurement_iterations_multiplier": 1,
        "gpu_completion_mode": "per_iteration",
        "output_directory_path": "e:/xemu_perf_tests"},
        pfifo_boundary_ids)
    output = {ROOT / "resources/catalog.json": catalog_json(doc),
            ROOT / "resources/plans/smoke.json": smoke_plan,
            ROOT / "resources/pfifo-array-elements-fast-smoke.json": pfifo_smoke,
            ROOT / "resources/pfifo-array-elements-quick.json": pfifo_quick,
            ROOT / "resources/pfifo-array-elements-sustained.json": pfifo_sustained,
            ROOT / "resources/pfifo-packet-boundary.json": pfifo_boundary,
            ROOT / "docs/generated/test-catalog.md": markdown(doc),
            ROOT / "docs/generated/test-failure-guide.md": failure_guide_markdown(doc),
            ROOT / "src/generated/test_catalog.inc": cpp(items, doc["catalog_id"])}
    growth_settings = {
        "skip_tests_by_default": True,
        "warmup_iterations": 0,
        "measurement_iterations_multiplier": 1,
        "gpu_completion_mode": "per_iteration",
        "output_directory_path": "e:/xemu_perf_tests",
    }
    output[ROOT / "resources/transient-buffer-growth.json"] = resolved_plan(
        doc, growth_settings,
        ["vertex_buffer_allocation.rising_transient_growth"])
    base_settings = {
        "skip_tests_by_default": True,
        "output_directory_path": "e:/xemu_perf_tests",
    }
    profiles = {
        "fast-smoke": (1, 1, "enqueue"),
        "quick": (128, 64, "batch_complete"),
        "sustained": (320, 160, "batch_complete"),
    }
    texture_ids = [
        "pipeline_texture_switch.texture_switch",
        "pipeline_texture_switch.shader_negative_control",
        "pipeline_texture_switch.sampler_only_identity",
    ]
    for profile, (warmup, multiplier, completion) in profiles.items():
        settings = dict(base_settings, warmup_iterations=warmup,
                        measurement_iterations_multiplier=multiplier,
                        gpu_completion_mode=completion)
        output[ROOT / f"resources/pipeline-texture-switch-{profile}.json"] = \
            resolved_plan(doc, settings, texture_ids)
    specialized = {
        "pipeline-clear-texture-normal": "pipeline_texture_switch.clear_texture_normal",
        "pipeline-sampler-only-identity": "pipeline_texture_switch.sampler_only_identity",
    }
    specialized_profiles = {
        "fast-smoke": (1, 1, "enqueue"),
        "quick": (64, 32, "batch_complete"),
        "sustained": (160, 80, "batch_complete"),
    }
    for prefix, stable_id in specialized.items():
        for profile, (warmup, multiplier, completion) in specialized_profiles.items():
            settings = dict(base_settings, warmup_iterations=warmup,
                            measurement_iterations_multiplier=multiplier,
                            gpu_completion_mode=completion)
            output[ROOT / f"resources/{prefix}-{profile}.json"] = \
                resolved_plan(doc, settings, [stable_id])
    report_ids = [
        "report_query.zero_query",
        "report_query.single_boundary",
        "report_query.clear_boundary",
        "report_query.multiple_boundaries",
        "report_query.dma_target_switch",
        "report_query.fifo_producer_ordering",
        "report_query.dma_descriptor_rewrite",
        "report_query.dma_range_guard",
    ]
    report_profiles = {
        "fast-smoke": (0, 1, "batch_complete"),
        "quick": (4, 4, "batch_complete"),
        "sustained": (16, 16, "batch_complete"),
    }
    for profile, (warmup, multiplier, completion) in report_profiles.items():
        settings = dict(base_settings, warmup_iterations=warmup,
                        measurement_iterations_multiplier=multiplier,
                        gpu_completion_mode=completion)
        output[ROOT / f"resources/report-query-{profile}.json"] = \
            resolved_plan(doc, settings, report_ids)
    submission_ids = [
        "game_load.cross_title_hotpath.queued_vertex_cpu_writes",
        "game_load.cross_title_hotpath.pgr2_small_draws",
        "game_load.cross_title_hotpath.surface_reuse",
        "game_load.cross_title_hotpath.pipeline_state_churn",
        "game_load.cross_title_hotpath.texture_binding_reuse",
        "game_load.cross_title_hotpath.s3tc_streaming_fenced_draws",
        "game_load.cross_title_hotpath.gpu_wait_control",
        "surface.cpu_read_after_gpu_write",
        "surface.surface_download_path",
        "vertex_buffer_allocation.disjoint_same_page",
        "tiny_draw.inline_buffers.vertex_shader",
    ]
    profiles = {
        "fast-smoke": (0, 1, "per_iteration"),
        "quick": (1, 4, "batch_complete"),
        "sustained": (2, 16, "batch_complete"),
    }
    for profile, (warmup, multiplier, completion) in profiles.items():
        settings = {
            "skip_tests_by_default": True,
            "warmup_iterations": warmup,
            "measurement_iterations_multiplier": multiplier,
            "gpu_completion_mode": completion,
            "output_directory_path": "e:/xemu_perf_tests",
        }
        output[ROOT / f"resources/vulkan-submission-lifetimes-{profile}.json"] = \
            resolved_plan(doc, settings, submission_ids)
    return output


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
