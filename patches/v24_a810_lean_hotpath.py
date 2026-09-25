#!/usr/bin/env python3
"""A810 V24: strictly scoped CPU hot-path reductions on top of V23.

No changes to shader compilation, DiskDVD descriptor workaround, render
commands, WSI presentation, memory ownership, GPU wait or cache barriers.
Opt-out TU_A810_V24_FASTPATH=0 for a V23-equivalent A/B test.
"""
from pathlib import Path
import shutil

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def edit(old, new, label):
    global s
    hits = s.count(old)
    if hits != 1:
        raise SystemExit(f"V24 source drift at {label}: expected 1, found {hits}: {old[:100]!r}")
    s = s.replace(old, new, 1)
    print(f"V24 PASS {label}", flush=True)

edit('#include "frane_profiled_sampling.h"',
     '#include "frane_profiled_sampling.h"\n#include "frane_v24_fastpath.h"',
     "include pure decision helpers")

edit('''static bool
frane_a810_lean_profiled()
{''', '''static bool
frane_a810_v24_fastpath()
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_V24_FASTPATH", true);
   return enabled;
}

static bool
frane_a810_lean_profiled()
{''', "read opt-out once per process")

# V22's original mode/RNG is untouched for all other paths, and used exactly
# when TU_A810_V24_FASTPATH=0. A 0/100 probability in plain PROFILED is a
# permanent lock; the renderer outcome cannot depend on the random draw.
# The immediate profiler uses the original V23 path (measure == nullptr).
edit('''      render_mode get_optimal_mode(rp_history &history, bool *measure = nullptr)
      {
         uint32_t l_sysmem_probability = sysmem_probability.load(std::memory_order_relaxed);
         bool select_sysmem = (rand_xorshift128plus(seed) % PROBABILITY_MAX) < l_sysmem_probability;
         render_mode mode = select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;

         if (measure) {
            const uint32_t period = frane_profiled_sample_period(
               l_sysmem_probability, select_sysmem, frane_a810_sample_interval());
            *measure = period == 1;
            if (period > 1) {
               const uint32_t ticket = measurement_ticket.fetch_add(1, std::memory_order_relaxed);
               *measure = (ticket & (period - 1)) == 0;
            }
         }''',
'''      render_mode get_optimal_mode(rp_history &history, bool *measure = nullptr,
                                   bool lean_fastpath = false)
      {
         const uint32_t l_sysmem_probability =
            sysmem_probability.load(std::memory_order_relaxed);
         /* A locked 0/100 probability cannot change in plain PROFILED.
          * Do not advance per-history RNG for deterministic locked choices.
          * In particular, never take this shortcut for PROFILED_IMM,
          * reusable CBs or externally overridden render modes.
          */
         const bool definite = measure && lean_fastpath &&
            frane_v24_is_definite(l_sysmem_probability);
         const bool select_sysmem = definite
            ? frane_v24_definite_sysmem(l_sysmem_probability)
            : (rand_xorshift128plus(seed) % PROBABILITY_MAX) <
                 l_sysmem_probability;
         const render_mode mode =
            select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;

         if (measure) {
            if (definite) {
               /* V22 already skipped instrumentation on permanently locked
                * histories. V24 also skips the unused RNG and interval read.
                */
               *measure = false;
            } else {
               /* During uncertain/losing-mode draws, measure every time.
                * Avoid the static interval getter until a preferred-mode
                * observation actually needs sampling.
                */
               const bool full_measure = lean_fastpath &&
                  !frane_v24_is_preferred(l_sysmem_probability, select_sysmem);
               const uint32_t period = full_measure ? 1 :
                  frane_profiled_sample_period(
                     l_sysmem_probability, select_sysmem,
                     frane_a810_sample_interval());
               *measure = period == 1;
               if (period > 1) {
                  const uint32_t ticket =
                     measurement_ticket.fetch_add(1, std::memory_order_relaxed);
                  *measure = (ticket & (period - 1)) == 0;
               }
            }
         }''', "avoid RNG for permanent locks and interval lookup on full sampling")

edit('''      const render_mode mode = history.profiled.get_optimal_mode(history, &measure);
      if (measure)''', '''      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath());
      if (measure)''', "enable fastpath only in V22 one-time A810 plain-PROFILED branch")

edit('''void
tu_autotune::process_entries()
{
   uint32_t current_fence = device->global_bo_map->autotune_fence;''',
'''void
tu_autotune::process_entries()
{
   /* V22 often skips measurement after learning. Do not read a mapped GPU
    * fence merely to discover that there are zero pending result batches.
    * No blocking/synchronization or completed-batch semantics are changed.
    */
   if (frane_a810_gpu(device) && frane_a810_v24_fastpath() &&
       active_batches.empty())
      return;
   uint32_t current_fence = device->global_bo_map->autotune_fence;''',
"avoid needless fence BO read on empty A810 results queue")

p.write_text(s)
shutil.copyfile("patches/frane_v24_fastpath.h",
                "mesa/src/freedreno/vulkan/frane_v24_fastpath.h")
p = Path("mesa/src/freedreno/vulkan/tu_device.cc")
s = p.read_text()
old = "Frane A810 V23-LEAN-WSI / Mesa "
assert s.count(old) == 1, "V23 driver identity drift"
p.write_text(s.replace(old, "Frane A810 V24-LEAN-HOTPATH / Mesa ", 1))
print("V24 A810: DiskDVD IR3/WSI preserved; CPU-only profiled/fence paths", flush=True)
