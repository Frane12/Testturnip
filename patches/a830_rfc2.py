#!/usr/bin/env python3
"""RFC2: use real GPU timestamp results already gathered by Turnip PROFILED,
plus identify which mode-selector actually overrode the base decision.
A830 only. No extra GPU timestamp query, policy change or memory allocation.
Requires RFC1 patch applied first.
"""
from pathlib import Path
import hashlib, shutil

ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}

def edit(path,old,new,name):
    src=path.read_text()
    count=src.count(old)
    if count!=1:
        raise SystemExit(f"RFC2 source drift/collision {name}: {count} matches")
    path.write_text(src.replace(old,new,1))
    print(f"RFC2 PASS {name}",flush=True)

shutil.copyfile("patches/frane_a830_rfc2.h",V/"frane_a830_rfc2.h")
auto=V/"tu_autotune.cc"

edit(auto,
     '#include "frane_a830_rfc1.h"',
     '#include "frane_a830_rfc1.h"\n#include "frane_a830_rfc2.h"',
     "include standalone native trace")

edit(auto,
     "         bool tail_risk = false)",
     "         bool tail_risk = false, uint8_t *rfc2_reason = nullptr)",
     "mode selection optional source output; no added GPU path")

edit(auto,
     """            if (d.owns) {
               *measure = d.measure;
               return d.sysmem ? render_mode::SYSMEM : render_mode::GMEM;
            }""",
     """            if (d.owns) {
               *measure = d.measure;
               if (rfc2_reason)
                  *rfc2_reason = FRANE_A830_RFC2_SMART_V2;
               return d.sysmem ? render_mode::SYSMEM : render_mode::GMEM;
            }""",
     "identify SMART_V2 early mode")

edit(auto,
     """         const uint64_t decision_word =
            definite ? 0 : frane_2633_decision_draw(history.hash);""",
     """         if (definite && rfc2_reason)
            *rfc2_reason = FRANE_A830_RFC2_LOCKED;
         const uint64_t decision_word =
            definite ? 0 : frane_2633_decision_draw(history.hash);""",
     "identify locked PROFILED choice")

edit(auto,
     """                  if (adaptive.override_mode) {
                     smart_decision.override_mode = true;
                     smart_decision.select_sysmem = adaptive.select_sysmem;
                     smart_decision.force_measure = adaptive.force_measure;
                  }
               }

               runtime_decision.override_mode = smart_decision.override_mode;""",
     """                  if (adaptive.override_mode) {
                     smart_decision.override_mode = true;
                     smart_decision.select_sysmem = adaptive.select_sysmem;
                     smart_decision.force_measure = adaptive.force_measure;
                     if (rfc2_reason) {
                        const bool measured_bw2_rollback =
                           gmem_runtime_input->a830_rfc_has_cache &&
                           gmem_runtime_input->a830_rfc_cached_bw2.valid &&
                           gmem_runtime_input->a830_rfc_cached_bw2.rollback_sysmem;
                        *rfc2_reason = measured_bw2_rollback
                           ? FRANE_A830_RFC2_BW2_ROLLBACK
                           : FRANE_A830_RFC2_ADAPTIVE;
                     }
                  }
               }

               if (smart_decision.override_mode && rfc2_reason &&
                   *rfc2_reason == FRANE_A830_RFC2_PROFILED)
                  *rfc2_reason = FRANE_A830_RFC2_SMART_GMEM;
               runtime_decision.override_mode = smart_decision.override_mode;""",
     "separate SMART GMEM, adaptive learner and BW2 rollback source")

edit(auto,
     """            if (runtime_decision.override_mode) {
               select_sysmem = runtime_decision.select_sysmem;
               runtime_force_measure = runtime_decision.force_measure;
            }""",
     """            if (runtime_decision.override_mode) {
               select_sysmem = runtime_decision.select_sysmem;
               runtime_force_measure = runtime_decision.force_measure;
               if (!smart_gmem && rfc2_reason)
                  *rfc2_reason = FRANE_A830_RFC2_RUNTIME;
            }""",
     "non-SMART runtime override source")

edit(auto,
     """      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_26320_a830_smart_gmem_enabled(device),
         frane_a830_v2_flags(device), smart, occurrence, tail_risk);""",
     """      const bool trace_rfc2 =
         runtime_input.a830_bw2 && frane_a830_rfc2_trace_path();
      uint8_t rfc2_source = FRANE_A830_RFC2_PROFILED;
      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_26320_a830_smart_gmem_enabled(device),
         frane_a830_v2_flags(device), smart, occurrence, tail_risk,
         trace_rfc2 ? &rfc2_source : nullptr);
      if (trace_rfc2) {
         /* Snapshot only for diagnostic rows; mode was already selected.
          * Mirrors RFC1 but does not change runtime policy.
          */
         frane_26318_smart_gmem_input sampled = runtime_input;
         sampled.a830_rfc_cached_bw2 = frane_a830_s2bw2_evaluate(
            sampled.layout.pass_pixels, sampled.selected_tile_pixels,
            sampled.allocator_capacity_pixels, sampled.layout.drawcalls,
            sampled.sysmem_bandwidth_per_pixel,
            sampled.gmem_bandwidth_per_pixel, sampled.peak_live_cpp,
            uint32_t(std::min<uint64_t>(
               sampled.layout.usable_gmem, UINT32_MAX)),
            sampled.peak_live_planes, sampled.a830_history_score,
            sampled.a830_history_pairs, sampled.a830_history_ready,
            sampled.a830_measured_score, sampled.a830_measured_armed);
         sampled.a830_rfc_has_cache = true;
         frane_a830_rfc2_decision(history.hash, occurrence, sampled,
             rfc2_source, mode == render_mode::SYSMEM, measure);
      }""",
     "trace actual selected mode, selector source and original BW2 feature values")

edit(auto,
     """            frane_a830_v2_tail_word.store(
               frane_a830_v2_pack_tail(frane_a830_v2_tail),
               std::memory_order_relaxed);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {""",
     """            frane_a830_v2_tail_word.store(
               frane_a830_v2_pack_tail(frane_a830_v2_tail),
               std::memory_order_relaxed);
         }

         /* Actual completed GPU duration in the existing submit-thread
          * timestamp-result path. No new query, fence or GPU work. The
          * occurrence and RP hash join to a previously logged decision.
          */
         if (entry.frane_smart_sample &&
             frane_a830_rfc2_trace_path()) {
            const auto tail = frane_a830_v2_unpack_tail(
               frane_a830_v2_tail_word.load(std::memory_order_relaxed));
            frane_a830_rfc2_timing(
               hash, entry.frane_smart_occurrence, entry.sysmem,
               rp_duration, sysmem_rp_average.get(), gmem_rp_average.get(),
               sysmem_rp_average.count, gmem_rp_average.count,
               tail.score, tail.paired_samples);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {""",
     "read actual completed GPU timestamp into diagnostic log")

edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-RFC1 Render Features / Mesa ",
     "Turnip-Drnas A830 S2-RFC2 Measured Render / Mesa ",
     "driver identity")

src=auto.read_text()
assert 'TU_FRANE_A830_RFC2_TRACE_PATH' in (V/"frane_a830_rfc2.h").read_text()
for token in ("frane_a830_rfc2_decision(", "frane_a830_rfc2_timing(",
              "FRANE_A830_RFC2_SMART_V2", "FRANE_A830_RFC2_BW2_ROLLBACK",
              "FRANE_A830_RFC2_ADAPTIVE", "rfc2_reason = nullptr",
              "entry.frane_smart_occurrence", "rp_duration",
              "runtime_input.a830_bw2 && frane_a830_rfc2_trace_path()"):
    assert token in src,token
assert "Turnip-Drnas A830 S2-RFC2 Measured Render / Mesa " in (V/"tu_device.cc").read_text()
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a830_rfc2.h","vulkan/tu_autotune.cc","vulkan/tu_device.cc"}
if changed!=expected:
    raise SystemExit(f"RFC2 unexpected source scope {sorted(changed ^ expected)}")
print("A830 RFC2 GPU timestamp, source tracing and safety isolation PASS",flush=True)
