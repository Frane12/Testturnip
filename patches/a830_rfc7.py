#!/usr/bin/env python3
"""A830 RFC7 diagnostic-only attachment traffic + GPU stage telemetry.
Applies AFTER RFC6 on pinned Mesa. Does not change mode policy, query
allocation, shader compilation, GMEM layout or Vulkan synchronization.
"""
from pathlib import Path
import hashlib, shutil
ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}
def edit(path,old,new,label):
    s=path.read_text()
    n=s.count(old)
    if n != 1:raise SystemExit(f"RFC7 source drift {label}: {n} matches")
    path.write_text(s.replace(old,new,1))
    print(f"RFC7 PASS {label}",flush=True)

shutil.copyfile("patches/frane_a830_rfc7.h",V/"frane_a830_rfc7.h")
auto=V/"tu_autotune.cc"
edit(auto,
     '#include "frane_a830_rfc6.h"',
     '#include "frane_a830_rfc6.h"\n#include "frane_a830_rfc7.h"',
     "include opt-in buffered profiler")

edit(auto,
     """      if (trace_rfc2) {
         /* Snapshot only for diagnostic rows; mode was already selected.""",
     """      /* RFC7 is read-only diagnostic data. The decision was already
       * made by unchanged RFC6 / BW2 / Mesa policy. These are modeled
       * attachment-byte estimates, NOT DRAM hardware counters.
       */
      if (runtime_input.a830_bw2 && frane_a830_rfc7_path() &&
          ((occurrence - 1u) & 7u) == 0u) {
         frane_a830_rfc7_row row{};
         row.rp_hash = history.hash;
         row.occurrence = occurrence;
         row.sysmem = mode == render_mode::SYSMEM;
         row.measure = measure;
         row.pass_pixels = runtime_input.layout.pass_pixels;
         row.tile_pixels = runtime_input.selected_tile_pixels;
         row.tiles = row.tile_pixels
             ? (row.pass_pixels / row.tile_pixels +
                uint64_t(row.pass_pixels % row.tile_pixels != 0)) : 0;
         row.drawcalls = rp_state->drawcall_count;
         row.draw_bw_sample_sum =
            rp_state->drawcall_bandwidth_per_sample_sum;
         row.attachments = pass->attachment_count;
         row.sys_cpp = pass->sysmem_bandwidth_per_pixel;
         row.gmem_cpp = pass->gmem_bandwidth_per_pixel;
         row.physical_gmem_bytes = runtime_input.layout.physical_gmem;
         row.usable_gmem_bytes = runtime_input.layout.usable_gmem;
         for (uint32_t i = 0; i < pass->attachment_count; i++) {
            const auto &att = pass->attachments[i];
            if (att.load)
               row.load_cpp += att.cpp;
            if (att.store)
               row.store_cpp += att.cpp;
            if (att.clear_mask)
               row.clear_cpp += att.cpp;
            if (att.will_be_resolved && att.samples)
               row.resolve_cpp += att.cpp + att.cpp / att.samples;
         }
         frane_a830_rfc7_emit(row);
      }
      if (trace_rfc2) {
         /* Snapshot only for diagnostic rows; mode was already selected.""",
     "log per-RP attachment and draw traffic estimates after actual final mode")

edit(auto,
     """         if (entry.frane_smart_sample &&
             frane_a830_rfc2_trace_path()) {""",
     """         /* Existing PROFILED timestamps: render and HW binning are
          * separate fields. No new GPU timestamp queries or fences.
          * Tile max is only readable when TS_TILE was already selected.
          */
         if (entry.frane_smart_sample &&
             frane_a830_s2bw2_enabled(at.device) &&
             frane_a830_rfc7_path()) {
            frane_a830_rfc7_row row{};
            row.timing = true;
            row.rp_hash = hash;
            row.occurrence = entry.frane_smart_occurrence;
            row.sysmem = entry.sysmem;
            row.measure = true;
            row.drawcalls = entry.draw_count;
            row.tiles = entry.tile_count;
            const auto &gpu = entry.get_gpu_data();
            row.render_ticks = gpu.ts_end >= gpu.ts_start ?
                gpu.ts_end - gpu.ts_start : 0;
            row.binning_ticks =
                gpu.ts_binning_end >= gpu.ts_binning_start ?
                gpu.ts_binning_end - gpu.ts_binning_start : 0;
            row.gpu_ticks = rp_duration;
            if (entry.config.test(metric_flag::TS_TILE) && !entry.sysmem) {
               row.max_tile_ticks = entry.get_max_tile_duration();
               row.has_tile_ticks = true;
            }
            if (entry.config.test(metric_flag::SAMPLES)) {
               row.samples_passed = entry.get_samples_passed();
               row.has_samples = true;
            }
            frane_a830_rfc7_emit(row);
         }
         if (entry.frane_smart_sample &&
             frane_a830_rfc2_trace_path()) {""",
     "read measured GPU binning/draw/tile timing and optional samples in submit path")

edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-RFC6 Confidence Learning / Mesa ",
     "Turnip-Drnas A830 S2-RFC7 Bandwidth Profiler / Mesa ",
     "new driver identifier")

src=auto.read_text()
assert 'TU_FRANE_A830_RFC7_PATH' in (V/"frane_a830_rfc7.h").read_text()
assert 'frane_a830_rfc7_emit(row)' in src
assert 'row.draw_bw_sample_sum' in src
assert 'row.binning_ticks' in src and 'row.max_tile_ticks' in src
assert 'row.load_cpp += att.cpp;' in src
assert 'row.resolve_cpp += att.cpp + att.cpp / att.samples;' in src
assert 'if (trusted.accepted)' in src
assert "Turnip-Drnas A830 S2-RFC7 Bandwidth Profiler / Mesa " in (V/"tu_device.cc").read_text()
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a830_rfc7.h","vulkan/tu_autotune.cc","vulkan/tu_device.cc"}
assert changed==expected,("RFC7 touched unexpected files",changed^expected)
print("RFC7 PASS read-only profiling, no policy changes, exact source scope",flush=True)
