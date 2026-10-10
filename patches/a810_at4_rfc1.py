#!/usr/bin/env python3
"""Read-only A810 AT4 RFC1 diagnostics atop the pinned, fully applied AT4 patch.

Guard every upstream anchor and every changed path: fail closed on Mesa drift.
No render-mode, shader, GMEM or GPU timestamp query changes.
"""
from pathlib import Path
import hashlib
import shutil

ROOT = Path("mesa/src/freedreno")
V = ROOT / "vulkan"
def digest():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.rglob("*") if p.is_file()}
before = digest()

def edit(path, old, new, label):
    text = path.read_text()
    occurrences = text.count(old)
    if occurrences != 1:
        raise SystemExit(f"A810 RFC1 source drift/collision {label}: {occurrences}")
    path.write_text(text.replace(old, new, 1))
    print("RFC1 PASS", label, flush=True)

shutil.copyfile("patches/frane_a810_at4_rfc1.h", V / "frane_a810_at4_rfc1.h")
auto = V / "tu_autotune.cc"
edit(auto,
     '#include "frane_a810_at4.h"',
     '#include "frane_a810_at4.h"\n#include "frane_a810_at4_rfc1.h"',
     "native CSV trace header")

edit(auto,
     "   std::atomic<uint64_t> frane_s1at3_evictions { 0 };",
     """   std::atomic<uint64_t> frane_s1at3_evictions { 0 };
   /* Only increment when RFC1 CSV trace is configured. */
   std::atomic<uint32_t> frane_a810_rfc_occurrence { 0 };""",
     "per-history join occurrence")

edit(auto,
     "   uint16_t frane_s1at1_signature = 0;",
     """   uint16_t frane_s1at1_signature = 0;
   uint32_t frane_a810_rfc_occurrence = 0;""",
     "GPU entry keeps its own decision ID across asynchronous submit")

edit(auto,
     "         bool *at3_controlled = nullptr)",
     "         bool *at3_controlled = nullptr,\n         bool *at4_applied = nullptr)",
     "optional AT4 decision attribution")

edit(auto,
     """               if (at1.override_mode) {
                  runtime_decision.override_mode = true;""",
     """               if (at1.override_mode) {
                  if (at4_applied && at4_active)
                     *at4_applied = true;
                  runtime_decision.override_mode = true;""",
     "attribute only actual AT4 override, not mere eligibility")

edit(auto,
     """      bool at3_controlled = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     """      bool at3_controlled = false;
      bool at4_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     "collect actual context override")

edit(auto,
     """         at4 && context_eligible, &at3_controlled);

      if (!at3_controlled)
         mode = frane_26350_depth_frontier(
            device, cmd_state, pass, framebuffer, mode,
            rp_state->drawcall_count, &measure);

      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)) {
         mode = render_mode::SYSMEM;
         measure = false;
      }
""",
     """         at4 && context_eligible, &at3_controlled, &at4_applied);

      bool depth_overrode = false;
      if (!at3_controlled) {
         const render_mode before_frontier = mode;
         mode = frane_26350_depth_frontier(
            device, cmd_state, pass, framebuffer, mode,
            rp_state->drawcall_count, &measure);
         depth_overrode = mode != before_frontier;
      }

      bool safety_forced = false;
      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)) {
         mode = render_mode::SYSMEM;
         measure = false;
         safety_forced = true;
      }

      const bool trace_rfc1 = frane_a810_gpu(device) && frane_a810_rfc1_path();
      const uint32_t rfc_occurrence = trace_rfc1 ?
         history.frane_a810_rfc_occurrence.fetch_add(
            1, std::memory_order_relaxed) + 1u : 0u;
""",
     "capture final mode after depth/safety without changing either")

edit(auto,
     """            (*rp_ctx)->frane_s1at1_signature =
               frane_s1at1_catalog_for(at1_in).signature;
         }
      }
      return mode;""",
     """            (*rp_ctx)->frane_s1at1_signature =
               frane_s1at1_catalog_for(at1_in).signature;
         }
         if (trace_rfc1 && *rp_ctx)
            (*rp_ctx)->frane_a810_rfc_occurrence = rfc_occurrence;
      }
      if (trace_rfc1) {
         const uint16_t signature = measure && *rp_ctx ?
            (*rp_ctx)->frane_s1at1_signature : 0;
         const char *source = safety_forced ? "GMEM_SAFETY" :
            depth_overrode ? "DEPTH_FRONTIER" :
            at4_applied ? "AT4_OVERRIDE" :
            at3_controlled ? "AT3_CONTEXT" : "PROFILED_OR_S1";
         frane_a810_rfc1_decision(
            history.hash, rfc_occurrence, signature, source,
            mode == render_mode::SYSMEM, measure, context_eligible,
            at4, history.profiled.probability(),
            runtime_input.layout.pass_pixels,
            runtime_input.layout.selected_tile_count,
            runtime_input.layout.drawcalls,
            runtime_input.sysmem_bandwidth_per_pixel,
            runtime_input.gmem_bandwidth_per_pixel,
            runtime_input.layout.usable_gmem);
      }
      return mode;""",
     "emit sampled post-safety decision and match measured entry")

edit(auto,
     """            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (frane_a810_tail_learner_enabled(at.device)) {""",
     """            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         /* Existing completed GPU timestamp on the submit thread: do not
          * add a GPU query or read submit-owned EMA on recording threads. */
         if (frane_a810_gpu(at.device) &&
             entry.frane_a810_rfc_occurrence && frane_a810_rfc1_path()) {
            frane_a810_rfc1_timing(
               hash, entry.frane_a810_rfc_occurrence,
               entry.frane_s1at1_signature, entry.sysmem, rp_duration,
               sysmem_rp_average.get(), gmem_rp_average.get(),
               sysmem_rp_average.count, gmem_rp_average.count);
         }

         if (frane_a810_tail_learner_enabled(at.device)) {""",
     "capture measured GPU duration in existing submit path")

edit(V / "tu_device.cc",
     "Drnas-Turnip AT4 S1Guard A810 / Mesa ",
     "Drnas-Turnip A810 AT4-RFC1 Trace / Mesa ",
     "distinct driver identity")

source = auto.read_text()
for word in ("frane_a810_rfc1_decision(", "frane_a810_rfc1_timing(",
             "entry.frane_a810_rfc_occurrence", "GMEM_SAFETY",
             "at4_applied", "rp_duration", "sysmem_rp_average.get()"):
    assert word in source, word
assert 'TU_FRANE_A810_RFC1_TRACE_PATH' in (V / "frane_a810_at4_rfc1.h").read_text()
assert 'A810 AT4-RFC1 Trace / Mesa' in (V / "tu_device.cc").read_text()
after = digest()
changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
expected = {"vulkan/frane_a810_at4_rfc1.h", "vulkan/tu_autotune.cc",
            "vulkan/tu_device.cc"}
if changed != expected:
    raise SystemExit(f"A810 RFC1 unexpected source edits: {sorted(changed ^ expected)}")
print("A810 AT4 RFC1: policy unchanged; bounded CSV real-GPU timing hooked PASS")
