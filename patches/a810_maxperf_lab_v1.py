#!/usr/bin/env python3
"""Drnas Turnip A810 MAX-PERF LAB V1.0.

Base: Drnas Turnip V59 LRZ-CLEAN.

Goal:
  Deliberately chase a larger FPS step by combining the strongest ideas from
  the A810 campaign, while accepting that this is NOT a stability build.

What stays from the proven stack:
  - V45/V47 concurrent-binning heavy-pass baseline;
  - V53 bounded depth window (16..23), because 16 beat 24 in Crysis;
  - V56 GMEM turbo architecture + V57 tail guard + V57X EDGE=1;
  - V58/V59 LRZ retention/cleanup;
  - clean-draw hot-path caches, GMEM pressure/search, sync/hang fixes.

New MAX-PERF LAB pushes:
  1) IR3 occupancy punch:
     keep the proven max window=4, but reduce the window earlier under pressure:
       <12% -> 4
       12..29% -> 3
       >=30% -> 2
     This follows the hardware trend 8 -> 6 -> 4 without blindly widening.

  2) Prefetch-use scoring ON:
     choose the most-used legal texture prefetch candidates by default.

  3) GMEM overdrive:
     keep measured GMEM winners alive deeper into PROFILED's neutral territory,
     lower structure/score admission thresholds and reduce control-probe rate.
     The final A810 GMEM safety classifier and tail guard remain authoritative.

This build intentionally does not alter GMEM offsets/packing, barriers, resolve
programming, MSAA safety, WSI, sync semantics, or undocumented registers.
"""
from pathlib import Path

ROOT = Path("mesa")
F = ROOT / "src/freedreno"
V = F / "vulkan"
I = F / "ir3"


def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"MAX-PERF LAB V1.0 source drift at {label}: "
            f"expected 1 anchor, found {n}: {old[:240]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"MAX-PERF LAB V1.0 PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# 1) PREFETCH: promote the already-implemented direct-use scorer.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.c",
    'debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false)',
    'debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", true)',
    "enable use-aware legal texture prefetch ranking",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    'options[6] = debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false);',
    'options[6] = debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", true);',
    "match Vulkan shader-cache option default",
)

# ---------------------------------------------------------------------------
# 2) SCHEDULER: continue the tested 8 -> 6 -> 4 direction, but only where
# pressure says occupancy is actually threatened.  Do not change max=4 itself.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   /* 26.3.25 A810 hardware-guided ladder.
    * The default max=4 path is 4/4/3/2/2.  Larger env overrides are kept only
    * for A/B comparison; pressure rapidly pulls them back toward short live
    * ranges.  The adaptive opt-out remains upstream fixed sy=8.
    */
   if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 4u);
   if (p < 50)
      return MIN2(max_window, 3u);
   if (p < 65)
      return MIN2(max_window, 2u);
   return MIN2(max_window, 2u);""",
    """   /* MAX-PERF LAB V1.0 occupancy punch.
    * Hardware moved monotonically in the right direction from 8 -> 6 -> 4.
    * Keep 4 only for genuinely low pressure; shorten live ranges earlier once
    * pressure rises instead of increasing the low-pressure window again.
    */
   if (p < 12)
      return max_window;
   if (p < 30)
      return MIN2(max_window, 3u);
   return MIN2(max_window, 2u);""",
    "tighten pressure scheduler to 4/3/2",
)

# Scheduler source policy changed even with the same env fields, so bump both
# custom cache namespaces to prevent reuse of shaders compiled by stable V59.
edit(
    "src/freedreno/vulkan/tu_device.cc",
    'static const char schema[] = "frane-a810-compile-options-v1";',
    'static const char schema[] = "frane-a810-compile-options-lab-v1";',
    "isolate Vulkan compiler cache namespace",
)

edit(
    "src/freedreno/ir3/ir3_disk_cache.c",
    'static const char schema[] = "frane-a810-compile-options-v1";',
    'static const char schema[] = "frane-a810-compile-options-lab-v1";',
    "isolate IR3 disk-cache namespace",
)

# ---------------------------------------------------------------------------
# 3) GMEM OVERDRIVE: push only the selector.  Safety/tail checks happen before
# these thresholds and remain untouched.
# ---------------------------------------------------------------------------
H = "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h"

edit(
    H,
    """   if (state.armed) {
      /* V56 hard-push: let an already measured winner challenge much more of
       * PROFILED's neutral/SYSMEM territory. The final A810 GMEM safety gate
       * remains authoritative after this selector.
       */
      if (sysmem_probability > 55)
         return out;

      uint8_t probe_log2 = 0;
      if (state.score >= 8 && eval.structure_score >= 76 &&
          sysmem_probability <= 30) {
         probe_log2 = 9; /* 1/512 */
      } else if (state.score >= 7 && eval.structure_score >= 66 &&
                 sysmem_probability <= 40) {
         probe_log2 = 8; /* 1/256 */
      } else if (state.score >= 5 && eval.structure_score >= 58) {
         probe_log2 = 7; /* 1/128 */
      } else {
         return out;
      }
""",
    """   if (state.armed) {
      /* MAX-PERF LAB V1.0:
       * Once timings have actually armed a GMEM winner, let it hold farther
       * into neutral territory. The tail guard and final safety classifier are
       * still evaluated before/after this selector respectively.
       */
      if (sysmem_probability > 65)
         return out;

      uint8_t probe_log2 = 0;
      if (state.score >= 8 && eval.structure_score >= 72 &&
          sysmem_probability <= 35) {
         probe_log2 = 10; /* 1/1024 */
      } else if (state.score >= 6 && eval.structure_score >= 62 &&
                 sysmem_probability <= 50) {
         probe_log2 = 9; /* 1/512 */
      } else if (state.score >= 4 && eval.structure_score >= 54) {
         probe_log2 = 8; /* 1/256 */
      } else {
         return out;
      }
""",
    "extend armed measured GMEM winner hold",
)

edit(
    H,
    """   if (sysmem_probability > 65 || eval.structure_score < 62)
      return out;

   /* V56 also pushes the cold-start prior harder, but it still leaves a
    * non-zero SYSMEM share and doubles measurement cadence so a bad guess is
    * corrected quickly instead of becoming sticky.
    */
   uint32_t reduction = 24;
   if (eval.structure_score >= 88)
      reduction = 44;
   else if (eval.structure_score >= 78)
      reduction = 34;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;
   effective = std::max(effective, 2u);

   out.override_mode = true;
   out.probe_log2 = 0;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;
   out.force_measure = ((decision_word >> 8) & 3u) == 0u; /* 1/4 */
""",
    """   if (sysmem_probability > 75 || eval.structure_score < 56)
      return out;

   /* MAX-PERF LAB cold-start prior: spend less time sampling SYSMEM and bias
    * earlier toward GMEM when structure already looks favorable.
    */
   uint32_t reduction = 32;
   if (eval.structure_score >= 88)
      reduction = 52;
   else if (eval.structure_score >= 76)
      reduction = 42;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;
   effective = std::max(effective, 1u);

   out.override_mode = true;
   out.probe_log2 = 0;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;
   out.force_measure = ((decision_word >> 8) & 7u) == 0u; /* 1/8 */
""",
    "strengthen cold-start GMEM bias",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V59 / Mesa ",
    "Drnas Turnip A810 MAX-PERF LAB V1.0 / Mesa ",
    "LAB display identity",
)

# ---------------------------------------------------------------------------
# Audit: preserve the best-known choices instead of indiscriminately changing
# everything just because this is an unstable build.
# ---------------------------------------------------------------------------
compiler = (I / "ir3_compiler.c").read_text()
sched = (I / "ir3_sched.c").read_text()
disk = (I / "ir3_disk_cache.c").read_text()
device = (V / "tu_device.cc").read_text()
auto = (V / "tu_autotune.cc").read_text()
turbo = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
lrz = (V / "tu_lrz.cc").read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
queue = (V / "tu_queue.cc").read_text()

# New lab policy.
assert 'TU_A810_26316_PREFETCH_USE_SCORE", true' in compiler
assert "if (p < 12)" in sched
assert "if (p < 30)" in sched
assert "frane-a810-compile-options-lab-v1" in disk
assert "frane-a810-compile-options-lab-v1" in device
for needle in (
    "sysmem_probability > 65",
    "eval.structure_score >= 72",
    "eval.structure_score >= 62",
    "state.score >= 4",
    "probe_log2 = 10",
    "sysmem_probability > 75",
    "eval.structure_score < 56",
    "std::max(effective, 1u)",
    "& 7u",
):
    assert needle in turbo, needle

# Keep hardware-tested/recent winners intact.
assert 'TU_A810_26317_TEX_WINDOW_MAX", 4' in compiler
assert 'TU_FRANE_DEPTH_DRAWS", 16' in auto
assert 'TU_FRANE_DEPTH_MAX", 23' in auto
assert 'TU_FRANE_EDGE", 1' in auto
assert 'TU_FRANE_TAIL", true' in auto
assert 'TU_FRANE_GMEM_TURBO", true' in auto
assert 'TU_A810_26347_CB_PROFILE_MODE", 1' in cmd

# Keep all correctness/safety layers.
assert "frane_a810_gmem_pass_safe" in auto
assert "subpass.resolve_depth_stencil" in auto
assert "subpass.feedback_loop_ds" in auto
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in auto
assert "V58 A810/A8XX LRZ-KEEP" in lrz
assert "V59 A8XX LRZ-CLEAN" in lrz
assert "FRANE_2631_POLL_READY" in kg
assert "frane_2631_deadline_ns" in kg
assert "pthread_mutex_unlock(&device->submit_mutex);" in queue
assert "Drnas Turnip A810 MAX-PERF LAB V1.0 / Mesa " in device

print("Drnas Turnip A810 MAX-PERF LAB V1.0 applied and audited", flush=True)
