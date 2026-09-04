# Generated test catalog

Catalog `sha256:4c35da004c5858c0f7e8b9fc74d2789add026cfdc40a693fdd4dcb3291e6e1b1` contains 144 leaves and 5 groups.

This table is documentation generated from stable IDs. `Use` describes the workload; use the [failure guide](test-failure-guide.md) for failure meaning and first code checks.

| Stable ID | Kind | Use | Legacy ID |
| --- | --- | --- | --- |
| `busy_pfifo.pfifo_saturation` | leaf | Saturates a fixed PFIFO packet stream and verifies progress. | `BusyPfifo::PFIFOSaturation` |
| `busy_pfifo.pgraph_pattern_polling` | leaf | Polls a guest-visible PGRAPH completion pattern. | `BusyPfifo::PgraphPatternPolling` |
| `pfifo_array_elements.array_element16` | leaf | Decodes and expands non-incrementing 16-bit PFIFO array elements. | `PFIFOArrayElements::pfifo.array-element16` |
| `pfifo_array_elements.array_element32` | leaf | Decodes and expands non-incrementing 32-bit PFIFO array elements. | `PFIFOArrayElements::pfifo.array-element32` |
| `pfifo_array_elements.array_element_pgr2` | leaf | Runs a PGR2-shaped mixed-width PFIFO array-element packet stream. | `PFIFOArrayElements::pfifo.array-element-pgr2` |
| `cpu_floating_point.sse_scalar` | leaf | Runs fixed SSE scalar arithmetic and flag known-answer checks. | `CpuFloatingPoint::SSEScalar` |
| `cpu_floating_point.x87_scalar` | leaf | Runs fixed x87 scalar arithmetic and status known-answer checks. | `CpuFloatingPoint::X87Scalar` |
| `cpu_translation_blocks.direct_loop` | leaf | Exercises direct-loop translation-block chaining. | `CpuTranslationBlocks::DirectLoop` |
| `cpu_translation_blocks.indirect_dispatch` | leaf | Exercises deterministic indirect translation-block dispatch. | `CpuTranslationBlocks::IndirectDispatch` |
| `cpu_translation_blocks.indirect_dispatch_stress` | leaf | Stresses a larger deterministic indirect-target set. | `CpuTranslationBlocks::IndirectDispatchStress` |
| `fill_rate.solid` | leaf | Measures sustained solid-fragment raster work. | `FillRate::FillRate-Solid` |
| `fill_rate.textured` | leaf | Measures sustained textured-fragment raster and sampling work. | `FillRate::FillRate-Textured` |
| `pipeline_texture_switch.texture_switch` | leaf | Switches texture bindings to test descriptor and texture-generation invalidation. | `PipelineTextureSwitch::pipeline.texture-switch` |
| `pipeline_texture_switch.shader_negative_control` | leaf | Changes shader state to prove state-elision does not suppress a real update. | `PipelineTextureSwitch::pipeline.shader-negative-control` |
| `pipeline_texture_switch.clear_texture_normal` | leaf | Crosses clear, texture-only, and normal-draw boundaries to detect state leakage. | `PipelineTextureSwitch::pipeline.clear-texture-normal` |
| `pipeline_texture_switch.sampler_only_identity` | leaf | Repeats an identical sampler write to test identity-based dirty elision. | `PipelineTextureSwitch::pipeline.sampler-only-identity` |
| `report_query.zero_query` | leaf | Checks an empty query boundary and zero-result DMA write. | `ReportQuery::report.zero-query` |
| `report_query.single_boundary` | leaf | Checks one query report at a guest-visible GET boundary. | `ReportQuery::report.single-boundary` |
| `report_query.clear_boundary` | leaf | Checks a clear operation's query-report accumulation boundary. | `ReportQuery::report.clear-boundary` |
| `report_query.multiple_boundaries` | leaf | Checks ordering across several query-report GET boundaries. | `ReportQuery::report.multiple-boundaries` |
| `report_query.dma_target_switch` | leaf | Switches query-report DMA targets while work is queued. | `ReportQuery::report.dma-target-switch` |
| `report_query.fifo_producer_ordering` | leaf | Checks report visibility while producer FIFO work continues. | `ReportQuery::report.fifo-producer-ordering` |
| `report_query.dma_descriptor_rewrite` | leaf | Rewrites a queued report DMA descriptor to test immutable ownership. | `ReportQuery::report.dma-descriptor-rewrite` |
| `report_query.dma_range_guard` | leaf | Rejects an out-of-range report DMA target without corrupting VRAM. | `ReportQuery::report.dma-range-guard` |
| `game_load.long_unlocked_scene` | group | Groups ordered child checkpoints; it has no independent timing result. | `GameLoadComposite::08-LongUnlockedScene` |
| `game_load.long_unlocked_scene.cpu` | leaf | Runs the title-shaped game-load stage long unlocked scene.cpu. | `GameLoadComposite::08-LongUnlockedScene-01-CPU` |
| `game_load.long_unlocked_scene.pfifo` | leaf | Runs the title-shaped game-load stage long unlocked scene.pfifo. | `GameLoadComposite::08-LongUnlockedScene-02-PFIFO` |
| `game_load.long_unlocked_scene.alpha_overdraw` | leaf | Runs the title-shaped game-load stage long unlocked scene.alpha overdraw. | `GameLoadComposite::08-LongUnlockedScene-03-AlphaOverdraw` |
| `game_load.long_unlocked_scene.streaming_surface_reuse` | leaf | Runs the title-shaped game-load stage long unlocked scene.streaming surface reuse. | `GameLoadComposite::08-LongUnlockedScene-04-StreamingSurfaceReuse` |
| `game_load.long_unlocked_scene.combined` | leaf | Runs the title-shaped game-load stage long unlocked scene.combined. | `GameLoadComposite::08-LongUnlockedScene-05-Combined` |
| `game_load.long_unlocked_scene.full_system` | leaf | Runs the title-shaped game-load stage long unlocked scene.full system. | `GameLoadComposite::08-LongUnlockedScene-06-FullSystem` |
| `game_load.cross_title_hotpath` | group | Groups ordered child checkpoints; it has no independent timing result. | `GameLoadComposite::09-CrossTitleHotpath` |
| `game_load.cross_title_hotpath.queued_vertex_cpu_writes` | leaf | Runs the title-shaped game-load stage cross title hotpath.queued vertex cpu writes. | `GameLoadComposite::09-CrossTitleHotpath-01-QueuedVertexCpuWrites` |
| `game_load.cross_title_hotpath.pgr2_small_draws` | leaf | Runs the title-shaped game-load stage cross title hotpath.pgr2 small draws. | `GameLoadComposite::09-CrossTitleHotpath-02-Pgr2SmallDraws` |
| `game_load.cross_title_hotpath.texture_update_reuse` | leaf | Runs the title-shaped game-load stage cross title hotpath.texture update reuse. | `GameLoadComposite::09-CrossTitleHotpath-03-TextureUpdateReuse` |
| `game_load.cross_title_hotpath.surface_reuse` | leaf | Runs the title-shaped game-load stage cross title hotpath.surface reuse. | `GameLoadComposite::09-CrossTitleHotpath-04-SurfaceReuse` |
| `game_load.cross_title_hotpath.pipeline_state_churn` | leaf | Runs the title-shaped game-load stage cross title hotpath.pipeline state churn. | `GameLoadComposite::09-CrossTitleHotpath-05-PipelineStateChurn` |
| `game_load.cross_title_hotpath.blend_constant_reuse` | leaf | Runs the title-shaped game-load stage cross title hotpath.blend constant reuse. | `GameLoadComposite::09-CrossTitleHotpath-06-BlendConstantReuse` |
| `game_load.cross_title_hotpath.texture_binding_reuse` | leaf | Runs the title-shaped game-load stage cross title hotpath.texture binding reuse. | `GameLoadComposite::09-CrossTitleHotpath-07-TextureBindingReuse` |
| `game_load.cross_title_hotpath.pgr2_lagspot_inline_elements` | leaf | Runs the title-shaped game-load stage cross title hotpath.pgr2 lagspot inline elements. | `GameLoadComposite::09-CrossTitleHotpath-08-Pgr2LagspotInlineElements` |
| `game_load.cross_title_hotpath.scaled_surface_pressure` | leaf | Runs the title-shaped game-load stage cross title hotpath.scaled surface pressure. | `GameLoadComposite::09-CrossTitleHotpath-09-ScaledSurfacePressure` |
| `game_load.cross_title_hotpath.s3tc_streaming_fenced_draws` | leaf | Runs the title-shaped game-load stage cross title hotpath.s3tc streaming fenced draws. | `GameLoadComposite::09-CrossTitleHotpath-10-S3tcStreamingFencedDraws` |
| `game_load.cross_title_hotpath.gpu_wait_control` | leaf | Runs the title-shaped game-load stage cross title hotpath.gpu wait control. | `GameLoadComposite::09-CrossTitleHotpath-11-GpuWaitControl` |
| `game_load.s3tc_sync_factor` | group | Groups ordered child checkpoints; it has no independent timing result. | `GameLoadComposite::10-S3tcSyncFactor` |
| `game_load.s3tc_sync_factor.dxt1_same_address_wait` | leaf | Runs the title-shaped game-load stage s3tc sync factor.dxt1 same address wait. | `GameLoadComposite::10-S3tcSyncFactor-01-Dxt1SameAddressWait` |
| `game_load.s3tc_sync_factor.dxt1_same_address_queued` | leaf | Runs the title-shaped game-load stage s3tc sync factor.dxt1 same address queued. | `GameLoadComposite::10-S3tcSyncFactor-02-Dxt1SameAddressQueued` |
| `game_load.s3tc_sync_factor.dxt1_ring_payload_generations` | leaf | Runs the title-shaped game-load stage s3tc sync factor.dxt1 ring payload generations. | `GameLoadComposite::10-S3tcSyncFactor-03-Dxt1RingPayloadGenerations` |
| `game_load.s3tc_sync_factor.dxt1_dirty_once_redraw` | leaf | Runs the title-shaped game-load stage s3tc sync factor.dxt1 dirty once redraw. | `GameLoadComposite::10-S3tcSyncFactor-04-Dxt1DirtyOnceRedraw` |
| `game_load.s3tc_sync_factor.rgba8_same_address_wait` | leaf | Runs the title-shaped game-load stage s3tc sync factor.rgba8 same address wait. | `GameLoadComposite::10-S3tcSyncFactor-05-Rgba8SameAddressWait` |
| `game_load.s3tc_sync_factor.rgba8_same_address_queued` | leaf | Runs the title-shaped game-load stage s3tc sync factor.rgba8 same address queued. | `GameLoadComposite::10-S3tcSyncFactor-06-Rgba8SameAddressQueued` |
| `game_load.s3tc_sync_factor.rgba8_ring_payload_generations` | leaf | Runs the title-shaped game-load stage s3tc sync factor.rgba8 ring payload generations. | `GameLoadComposite::10-S3tcSyncFactor-07-Rgba8RingPayloadGenerations` |
| `game_load.s3tc_sync_factor.rgba8_dirty_once_redraw` | leaf | Runs the title-shaped game-load stage s3tc sync factor.rgba8 dirty once redraw. | `GameLoadComposite::10-S3tcSyncFactor-08-Rgba8DirtyOnceRedraw` |
| `game_load.s3tc_sync_factor.bc2_native_eligible` | leaf | Runs the title-shaped game-load stage s3tc sync factor.bc2 native eligible. | `GameLoadComposite::10-S3tcSyncFactor-09-Bc2NativeEligible` |
| `game_load.s3tc_sync_factor.bc2_bordered_fallback` | leaf | Runs the title-shaped game-load stage s3tc sync factor.bc2 bordered fallback. | `GameLoadComposite::10-S3tcSyncFactor-10-Bc2BorderedFallback` |
| `game_load.s3tc_sync_factor.bc3_native_eligible` | leaf | Runs the title-shaped game-load stage s3tc sync factor.bc3 native eligible. | `GameLoadComposite::10-S3tcSyncFactor-11-Bc3NativeEligible` |
| `game_load.s3tc_sync_factor.bc3_bordered_fallback` | leaf | Runs the title-shaped game-load stage s3tc sync factor.bc3 bordered fallback. | `GameLoadComposite::10-S3tcSyncFactor-12-Bc3BorderedFallback` |
| `game_load.repeated_display` | leaf | Runs the title-shaped game-load stage repeated display. | `GameLoadComposite::12-RepeatedDisplay` |
| `game_load.repeated_display_boosted` | leaf | Runs the title-shaped game-load stage repeated display boosted. | `GameLoadComposite::12-RepeatedDisplay-Boosted` |
| `game_load.doax_menu_representative.cpu_only` | leaf | Runs the title-shaped game-load stage doax menu representative.cpu only. | `GameLoadComposite::DoaxMenuRepresentative-01-CPUOnly` |
| `game_load.doax_menu_representative.pfifo_only` | leaf | Runs the title-shaped game-load stage doax menu representative.pfifo only. | `GameLoadComposite::DoaxMenuRepresentative-02-PFIFOOnly` |
| `game_load.doax_menu_representative.gpu_only` | leaf | Runs the title-shaped game-load stage doax menu representative.gpu only. | `GameLoadComposite::DoaxMenuRepresentative-03-GPUOnly` |
| `game_load.doax_menu_representative.streaming_only` | leaf | Runs the title-shaped game-load stage doax menu representative.streaming only. | `GameLoadComposite::DoaxMenuRepresentative-04-StreamingOnly` |
| `game_load.doax_menu_representative.cpu_pfifo_gpu` | leaf | Runs the title-shaped game-load stage doax menu representative.cpu pfifo gpu. | `GameLoadComposite::DoaxMenuRepresentative-05-CPUPFIFOGPU` |
| `game_load.doax_menu_representative.cpu_pfifo_gpu_streaming` | leaf | Runs the title-shaped game-load stage doax menu representative.cpu pfifo gpu streaming. | `GameLoadComposite::DoaxMenuRepresentative-06-CPUPFIFOGPUStreaming` |
| `game_load.doax_menu_representative.full_system` | leaf | Runs the title-shaped game-load stage doax menu representative.full system. | `GameLoadComposite::DoaxMenuRepresentative-07-FullSystem` |
| `game_load.doax_menu_stress.cpu_only` | leaf | Runs the title-shaped game-load stage doax menu stress.cpu only. | `GameLoadComposite::DoaxMenuStress-01-CPUOnly` |
| `game_load.doax_menu_stress.pfifo_only` | leaf | Runs the title-shaped game-load stage doax menu stress.pfifo only. | `GameLoadComposite::DoaxMenuStress-02-PFIFOOnly` |
| `game_load.doax_menu_stress.gpu_only` | leaf | Runs the title-shaped game-load stage doax menu stress.gpu only. | `GameLoadComposite::DoaxMenuStress-03-GPUOnly` |
| `game_load.doax_menu_stress.streaming_only` | leaf | Runs the title-shaped game-load stage doax menu stress.streaming only. | `GameLoadComposite::DoaxMenuStress-04-StreamingOnly` |
| `game_load.doax_menu_stress.cpu_pfifo_gpu` | leaf | Runs the title-shaped game-load stage doax menu stress.cpu pfifo gpu. | `GameLoadComposite::DoaxMenuStress-05-CPUPFIFOGPU` |
| `game_load.doax_menu_stress.cpu_pfifo_gpu_streaming` | leaf | Runs the title-shaped game-load stage doax menu stress.cpu pfifo gpu streaming. | `GameLoadComposite::DoaxMenuStress-06-CPUPFIFOGPUStreaming` |
| `game_load.doax_menu_stress.full_system` | leaf | Runs the title-shaped game-load stage doax menu stress.full system. | `GameLoadComposite::DoaxMenuStress-07-FullSystem` |
| `game_load.pgr2_ai_backup.cpu_only` | leaf | Runs the title-shaped game-load stage pgr2 ai backup.cpu only. | `GameLoadComposite::Pgr2AiBackup-01-CPUOnly` |
| `game_load.pgr2_ai_backup.pfifo_only` | leaf | Runs the title-shaped game-load stage pgr2 ai backup.pfifo only. | `GameLoadComposite::Pgr2AiBackup-02-PFIFOOnly` |
| `game_load.pgr2_ai_backup.gpu_only` | leaf | Runs the title-shaped game-load stage pgr2 ai backup.gpu only. | `GameLoadComposite::Pgr2AiBackup-03-GPUOnly` |
| `game_load.pgr2_ai_backup.streaming_only` | leaf | Runs the title-shaped game-load stage pgr2 ai backup.streaming only. | `GameLoadComposite::Pgr2AiBackup-04-StreamingOnly` |
| `game_load.pgr2_ai_backup.cpu_pfifo_gpu` | leaf | Runs the title-shaped game-load stage pgr2 ai backup.cpu pfifo gpu. | `GameLoadComposite::Pgr2AiBackup-05-CPUPFIFOGPU` |
| `game_load.pgr2_ai_backup.cpu_pfifo_gpu_streaming` | leaf | Runs the title-shaped game-load stage pgr2 ai backup.cpu pfifo gpu streaming. | `GameLoadComposite::Pgr2AiBackup-06-CPUPFIFOGPUStreaming` |
| `game_load.pgr2_ai_backup.full_system` | leaf | Runs the title-shaped game-load stage pgr2 ai backup.full system. | `GameLoadComposite::Pgr2AiBackup-07-FullSystem` |
| `high_vertex_count.arrays` | leaf | Submits a high vertex-count arrays path. | `High vertex count::HighVtxCount-arrays` |
| `high_vertex_count.inline_arrays` | leaf | Submits a high vertex-count inline arrays path. | `High vertex count::HighVtxCount-inlinearrays` |
| `high_vertex_count.inline_buffers` | leaf | Submits a high vertex-count inline buffers path. | `High vertex count::HighVtxCount-inlinebuffers` |
| `high_vertex_count.inline_elements` | leaf | Submits a high vertex-count inline elements path. | `High vertex count::HighVtxCount-inlineelements` |
| `primitive_type.line_loop.fixed_function` | leaf | Renders line loop through the fixed function path. | `PrimitiveType::PrimitiveType-LLoop` |
| `primitive_type.line_loop.vertex_shader` | leaf | Renders line loop through the vertex shader path. | `PrimitiveType::PrimitiveType-LLoop-vsh` |
| `primitive_type.line_strip.fixed_function` | leaf | Renders line strip through the fixed function path. | `PrimitiveType::PrimitiveType-LStrip` |
| `primitive_type.line_strip.vertex_shader` | leaf | Renders line strip through the vertex shader path. | `PrimitiveType::PrimitiveType-LStrip-vsh` |
| `primitive_type.lines.fixed_function` | leaf | Renders lines through the fixed function path. | `PrimitiveType::PrimitiveType-Lines` |
| `primitive_type.lines.vertex_shader` | leaf | Renders lines through the vertex shader path. | `PrimitiveType::PrimitiveType-Lines-vsh` |
| `primitive_type.points.fixed_function` | leaf | Renders points through the fixed function path. | `PrimitiveType::PrimitiveType-Points` |
| `primitive_type.points.vertex_shader` | leaf | Renders points through the vertex shader path. | `PrimitiveType::PrimitiveType-Points-vsh` |
| `primitive_type.polygon.fixed_function` | leaf | Renders polygon through the fixed function path. | `PrimitiveType::PrimitiveType-Poly` |
| `primitive_type.polygon.vertex_shader` | leaf | Renders polygon through the vertex shader path. | `PrimitiveType::PrimitiveType-Poly-vsh` |
| `primitive_type.quad_strip.fixed_function` | leaf | Renders quad strip through the fixed function path. | `PrimitiveType::PrimitiveType-QuadStrip` |
| `primitive_type.quad_strip.vertex_shader` | leaf | Renders quad strip through the vertex shader path. | `PrimitiveType::PrimitiveType-QuadStrip-vsh` |
| `primitive_type.quads.fixed_function` | leaf | Renders quads through the fixed function path. | `PrimitiveType::PrimitiveType-Quads` |
| `primitive_type.quads.vertex_shader` | leaf | Renders quads through the vertex shader path. | `PrimitiveType::PrimitiveType-Quads-vsh` |
| `primitive_type.triangle_fan.fixed_function` | leaf | Renders triangle fan through the fixed function path. | `PrimitiveType::PrimitiveType-TriFan` |
| `primitive_type.triangle_fan.vertex_shader` | leaf | Renders triangle fan through the vertex shader path. | `PrimitiveType::PrimitiveType-TriFan-vsh` |
| `primitive_type.triangle_strip.fixed_function` | leaf | Renders triangle strip through the fixed function path. | `PrimitiveType::PrimitiveType-TriStrip` |
| `primitive_type.triangle_strip.vertex_shader` | leaf | Renders triangle strip through the vertex shader path. | `PrimitiveType::PrimitiveType-TriStrip-vsh` |
| `primitive_type.triangles.fixed_function` | leaf | Renders triangles through the fixed function path. | `PrimitiveType::PrimitiveType-Tris` |
| `primitive_type.triangles.vertex_shader` | leaf | Renders triangles through the vertex shader path. | `PrimitiveType::PrimitiveType-Tris-vsh` |
| `surface.basic` | leaf | Exercises render-surface basic behavior. | `SurfaceRendering::SurfaceRendering` |
| `surface.cpu_read_after_gpu_write` | leaf | Exercises render-surface cpu read after gpu write behavior. | `SurfaceRendering::XemuCpuReadAfterGpuWrite` |
| `surface.cpu_read_clean_surface` | leaf | Exercises render-surface cpu read clean surface behavior. | `SurfaceRendering::XemuCpuReadCleanSurface` |
| `surface.framebuffer_working_set_002` | leaf | Exercises render-surface framebuffer working set 002 behavior. | `SurfaceRendering::XemuFramebufferWorkingSet002` |
| `surface.framebuffer_working_set_008` | leaf | Exercises render-surface framebuffer working set 008 behavior. | `SurfaceRendering::XemuFramebufferWorkingSet008` |
| `surface.framebuffer_working_set_032` | leaf | Exercises render-surface framebuffer working set 032 behavior. | `SurfaceRendering::XemuFramebufferWorkingSet032` |
| `surface.framebuffer_working_set_064` | leaf | Exercises render-surface framebuffer working set 064 behavior. | `SurfaceRendering::XemuFramebufferWorkingSet064` |
| `surface.full_clear_elision_guard` | leaf | Exercises render-surface full clear elision guard behavior. | `SurfaceRendering::XemuFullClearElisionGuard` |
| `surface.overlapping_surface_churn_representative` | leaf | Exercises render-surface overlapping surface churn representative behavior. | `SurfaceRendering::XemuOverlappingSurfaceChurnRepresentative` |
| `surface.overlapping_surface_churn_stress` | leaf | Exercises render-surface overlapping surface churn stress behavior. | `SurfaceRendering::XemuOverlappingSurfaceChurnStress` |
| `surface.partial_channel_clear_guard` | leaf | Exercises render-surface partial channel clear guard behavior. | `SurfaceRendering::XemuPartialChannelClearGuard` |
| `surface.surface_download_path` | leaf | Exercises render-surface surface download path behavior. | `SurfaceRendering::XemuSurfaceDownloadPath` |
| `surface.surface_list_lookup_002` | leaf | Exercises render-surface surface list lookup 002 behavior. | `SurfaceRendering::XemuSurfaceListLookup002` |
| `surface.surface_list_lookup_008` | leaf | Exercises render-surface surface list lookup 008 behavior. | `SurfaceRendering::XemuSurfaceListLookup008` |
| `surface.surface_list_lookup_032` | leaf | Exercises render-surface surface list lookup 032 behavior. | `SurfaceRendering::XemuSurfaceListLookup032` |
| `surface.surface_list_lookup_128` | leaf | Exercises render-surface surface list lookup 128 behavior. | `SurfaceRendering::XemuSurfaceListLookup128` |
| `surface.vulkan_memory_pressure.representative` | group | Groups ordered child checkpoints; it has no independent timing result. | `SurfaceRendering::XemuVulkanMemoryPressureRepresentative` |
| `surface.vulkan_memory_pressure.representative.growth` | leaf | Exercises render-surface vulkan memory pressure.representative.growth behavior. | `SurfaceRendering::XemuVulkanMemoryPressureRepresentative-growth` |
| `surface.vulkan_memory_pressure.representative.plateau` | leaf | Exercises render-surface vulkan memory pressure.representative.plateau behavior. | `SurfaceRendering::XemuVulkanMemoryPressureRepresentative-plateau` |
| `surface.vulkan_memory_pressure.representative.alias_resize` | leaf | Exercises render-surface vulkan memory pressure.representative.alias resize behavior. | `SurfaceRendering::XemuVulkanMemoryPressureRepresentative-alias_resize` |
| `surface.vulkan_memory_pressure.representative.reuse` | leaf | Exercises render-surface vulkan memory pressure.representative.reuse behavior. | `SurfaceRendering::XemuVulkanMemoryPressureRepresentative-reuse` |
| `surface.vulkan_memory_pressure.representative.idle_retention` | leaf | Exercises render-surface vulkan memory pressure.representative.idle retention behavior. | `SurfaceRendering::XemuVulkanMemoryPressureRepresentative-idle_retention` |
| `surface.vulkan_memory_pressure.stress` | group | Groups ordered child checkpoints; it has no independent timing result. | `SurfaceRendering::XemuVulkanMemoryPressureStress` |
| `surface.vulkan_memory_pressure.stress.growth` | leaf | Exercises render-surface vulkan memory pressure.stress.growth behavior. | `SurfaceRendering::XemuVulkanMemoryPressureStress-growth` |
| `surface.vulkan_memory_pressure.stress.plateau` | leaf | Exercises render-surface vulkan memory pressure.stress.plateau behavior. | `SurfaceRendering::XemuVulkanMemoryPressureStress-plateau` |
| `surface.vulkan_memory_pressure.stress.alias_resize` | leaf | Exercises render-surface vulkan memory pressure.stress.alias resize behavior. | `SurfaceRendering::XemuVulkanMemoryPressureStress-alias_resize` |
| `surface.vulkan_memory_pressure.stress.reuse` | leaf | Exercises render-surface vulkan memory pressure.stress.reuse behavior. | `SurfaceRendering::XemuVulkanMemoryPressureStress-reuse` |
| `surface.vulkan_memory_pressure.stress.idle_retention` | leaf | Exercises render-surface vulkan memory pressure.stress.idle retention behavior. | `SurfaceRendering::XemuVulkanMemoryPressureStress-idle_retention` |
| `tiny_draw.arrays.fixed_function` | leaf | Exercises a small-draw fixed function state pattern. | `TinyDraw::TinyDraw-arrays` |
| `tiny_draw.arrays.vertex_shader` | leaf | Exercises a small-draw vertex shader state pattern. | `TinyDraw::TinyDraw-arrays-vsh` |
| `tiny_draw.inline_arrays.fixed_function` | leaf | Exercises a small-draw fixed function state pattern. | `TinyDraw::TinyDraw-inlinearrays` |
| `tiny_draw.inline_arrays.vertex_shader` | leaf | Exercises a small-draw vertex shader state pattern. | `TinyDraw::TinyDraw-inlinearrays-vsh` |
| `tiny_draw.inline_buffers.fixed_function` | leaf | Exercises a small-draw fixed function state pattern. | `TinyDraw::TinyDraw-inlinebuffers` |
| `tiny_draw.inline_buffers.vertex_shader` | leaf | Exercises a small-draw vertex shader state pattern. | `TinyDraw::TinyDraw-inlinebuffers-vsh` |
| `tiny_draw.inline_elements.fixed_function` | leaf | Exercises a small-draw fixed function state pattern. | `TinyDraw::TinyDraw-inlineelements` |
| `tiny_draw.inline_elements.vertex_shader` | leaf | Exercises a small-draw vertex shader state pattern. | `TinyDraw::TinyDraw-inlineelements-vsh` |
| `uniform_thrash.uniform_thrash` | leaf | Repeatedly changes shader constants to test dirty-row synchronization. | `UniformThrash::UniformThrash` |
| `vertex_buffer_allocation.mixed.arrays` | leaf | Exercises vertex-buffer allocation arrays behavior. | `Vertex buffer allocation::MixedVtxAlloc-arrays` |
| `vertex_buffer_allocation.mixed.inline_arrays` | leaf | Exercises vertex-buffer allocation inline arrays behavior. | `Vertex buffer allocation::MixedVtxAlloc-inlinearrays` |
| `vertex_buffer_allocation.mixed.inline_buffers` | leaf | Exercises vertex-buffer allocation inline buffers behavior. | `Vertex buffer allocation::MixedVtxAlloc-inlinebuffers` |
| `vertex_buffer_allocation.mixed.inline_elements` | leaf | Exercises vertex-buffer allocation inline elements behavior. | `Vertex buffer allocation::MixedVtxAlloc-inlineelements` |
| `vertex_buffer_allocation.tiny.arrays` | leaf | Exercises vertex-buffer allocation arrays behavior. | `Vertex buffer allocation::TinyAlloc-arrays` |
| `vertex_buffer_allocation.tiny.inline_arrays` | leaf | Exercises vertex-buffer allocation inline arrays behavior. | `Vertex buffer allocation::TinyAlloc-inlinearrays` |
| `vertex_buffer_allocation.tiny.inline_buffers` | leaf | Exercises vertex-buffer allocation inline buffers behavior. | `Vertex buffer allocation::TinyAlloc-inlinebuffers` |
| `vertex_buffer_allocation.tiny.inline_elements` | leaf | Exercises vertex-buffer allocation inline elements behavior. | `Vertex buffer allocation::TinyAlloc-inlineelements` |
| `vertex_buffer_allocation.disjoint_same_page` | leaf | Exercises vertex-buffer allocation disjoint same page behavior. | `Vertex buffer allocation::XemuVertexRamDisjointSamePage` |
