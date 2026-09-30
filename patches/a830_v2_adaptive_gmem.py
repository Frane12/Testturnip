#!/usr/bin/env python3
"""Drnas Turnip A830 V2 ADAPTIVE-GMEM.

Layered strictly on the validated 26.3.20 A830 PORT-BOOST.

Portable ideas taken from the later A810 work:
- stronger GMEM hold only after measured timing confidence already exists;
- per-render-pass tail-aware learning using Mesa's existing RP timestamps;
- hysteresis and sparse measured loser probes;
- real Mesa GMEM layout metadata instead of hardcoded A810 GMEM assumptions.

Deliberately NOT ported:
- A810 depth draw windows;
- A810 sampled-depth diagnostics;
- A810-specific GMEM safety/packing experiments;
- A810 KGSL power controls;
- A810 fixed replay/tile thresholds from V57.

Defaults:
  TU_FRANE_A830_BOOST=1
  TU_FRANE_A830_LEARN=1

Either feature can be disabled independently for A/B testing.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"A830 V2 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:220]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"A830 V2 PASS {label}", flush=True)


shutil.copyfile(
    "patches/frane_a830_v2_adaptive_gmem.h",
    V / "frane_a830_v2_adaptive_gmem.h",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_26319_memory_audit.h"',
    '#include "frane_mesa_26319_memory_audit.h"\n'
    '#include "frane_a830_v2_adaptive_gmem.h"',
    "include A830 V2 policy",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_26320_a830_smart_gmem_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A830_26320_SMART_GMEM", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a810_lean_profiled()
{""",
    """static bool
frane_26320_a830_smart_gmem_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A830_26320_SMART_GMEM", true);
   return enabled && frane_26320_a830_gpu(device);
}

static uint32_t
frane_a830_v2_flags(const struct tu_device *device)
{
   if (!frane_26320_a830_gpu(device))
      return 0;

   static const bool boost =
      debug_get_bool_option("TU_FRANE_A830_BOOST", true);
   static const bool learn =
      debug_get_bool_option("TU_FRANE_A830_LEARN", true);

   return (boost ? FRANE_A830_V2_BOOST : 0u) |
          (learn ? FRANE_A830_V2_LEARN : 0u);
}

static bool
frane_a810_lean_profiled()
{""",
    "add exact-device A830 V2 feature flags",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };""",
    """   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };

   /* Submit thread owns the learner state. Recording threads only consume a
    * compact relaxed-atomic snapshot, matching the existing GMEM runtime.
    */
   frane_a830_v2_tail_state frane_a830_v2_tail {};
   std::atomic<uint32_t> frane_a830_v2_tail_word { 0 };""",
    "add per-RP A830 tail learner state",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         const frane_26318_smart_gmem_input *gmem_runtime_input = nullptr,
         bool smart_gmem = false)
      {""",
    """         const frane_26318_smart_gmem_input *gmem_runtime_input = nullptr,
         bool smart_gmem = false,
         uint32_t a830_v2_flags = 0)
      {""",
    "extend PROFILED decision with A830 V2 flags",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            if (smart_gmem) {
               const auto smart_decision = frane_26318_decide_smart_gmem(
                  true, *gmem_runtime_input, runtime_state,
                  l_sysmem_probability, decision_word);
               runtime_decision.override_mode = smart_decision.override_mode;
               runtime_decision.select_sysmem = smart_decision.select_sysmem;
               runtime_decision.force_measure = smart_decision.force_measure;
            } else {""",
    """            if (smart_gmem) {
               auto smart_decision = frane_26318_decide_smart_gmem(
                  true, *gmem_runtime_input, runtime_state,
                  l_sysmem_probability, decision_word);

               if (a830_v2_flags) {
                  const auto tail = frane_a830_v2_unpack_tail(
                     history.frane_a830_v2_tail_word.load(
                        std::memory_order_relaxed));
                  const auto adaptive = frane_a830_v2_decide(
                     a830_v2_flags, *gmem_runtime_input, runtime_state,
                     tail, l_sysmem_probability, decision_word);

                  if (adaptive.override_mode) {
                     smart_decision.override_mode = true;
                     smart_decision.select_sysmem = adaptive.select_sysmem;
                     smart_decision.force_measure = adaptive.force_measure;
                  }
               }

               runtime_decision.override_mode = smart_decision.override_mode;
               runtime_decision.select_sysmem = smart_decision.select_sysmem;
               runtime_decision.force_measure = smart_decision.force_measure;
            } else {""",
    "layer measured A830 policy over SMART-GMEM",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
""",
    """            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (frane_a830_v2_flags(at.device) & FRANE_A830_V2_LEARN) {
            frane_a830_v2_tail = frane_a830_v2_update_tail(
               frane_a830_v2_tail, entry.sysmem, rp_duration);
            frane_a830_v2_tail_word.store(
               frane_a830_v2_pack_tail(frane_a830_v2_tail),
               std::memory_order_relaxed);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
""",
    "learn from existing measured A830 render-pass durations",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_26320_a830_smart_gmem_enabled(device));""",
    """         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_26320_a830_smart_gmem_enabled(device),
         frane_a830_v2_flags(device));""",
    "wire A830 V2 into one-time PROFILED hot path",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.20 A830 PORT-BOOST / Mesa ",
    "Drnas Turnip A830 V2 / Mesa ",
    "A830 V2 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h = (V / "frane_a830_v2_adaptive_gmem.h").read_text()
d = (V / "tu_device.cc").read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
img = (V / "tu_image.cc").read_text()

for needle in (
    "frane_a830_v2_flags",
    'TU_FRANE_A830_BOOST", true',
    'TU_FRANE_A830_LEARN", true',
    "frane_a830_v2_tail_word",
    "frane_a830_v2_update_tail",
    "frane_a830_v2_decide",
):
    assert needle in a, needle

for needle in (
    "FRANE_A830_V2_BOOST",
    "FRANE_A830_V2_LEARN",
    "paired_samples < 8",
    "layout.structure_score >= 80",
    "layout.structure_score >= 70",
    "layout.structure_score >= 64",
    "sysmem_probability <= 50",
):
    assert needle in h, needle

# Preserve the validated A830 base.
for needle in (
    "TU_A830_26320_PROFILED_GMEM",
    "TU_A830_26320_SMART_GMEM",
    "TU_A830_26320_CORE_FASTPATH",
):
    assert needle in a, needle

# Do not accidentally retarget A810-only risky mechanisms.
assert "TU_A810_PWR_MAX" in kg
assert "TU_A830_PWR_MAX" not in kg
assert "TU_A810_SAMPLED_DEPTH_DIAG" in img
assert "TU_A830_SAMPLED_DEPTH_DIAG" not in img

# Exact A830 IDs remain the only device gate.
for chip in ("0x44050000", "0x44050001", "0xffff44050000"):
    assert chip in a

assert "Drnas Turnip A830 V2 / Mesa " in d

print("Drnas Turnip A830 V2 ADAPTIVE-GMEM applied", flush=True)
