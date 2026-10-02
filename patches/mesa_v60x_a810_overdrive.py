#!/usr/bin/env python3
"""Drnas Turnip A810 V60X OVERDRIVE.

Internal boundary-push build based on V59 LRZ-CLEAN.

This deliberately combines the strongest hardware signals we have with a few
controlled high-risk extensions.  The goal is not release stability; it is to
create a wider performance delta that we can later bisect and stabilize.

Changes:
  1) Scheduler: promote the hardware-tested 8 -> 6 -> 4 trend one step further
     and make sy window 2 the default. Existing 2..8 A/B range remains.
  2) Prefetch: enable the existing quad/diversity use-score selector by default
     so the short scheduler window prioritizes fetches with the most direct SSA
     reuse.
  3) GMEM: widen V56 measured/cold-start GMEM hold substantially, while keeping
     the final A810 GMEM safety classifier authoritative.
  4) Tail edge: restore V57X mode 2 by default (hard-tail protection + bounded
     medium-tail reopening), while V59 LRZ-CLEAN stays intact.

Intentionally unchanged:
  - GMEM offsets/packing and attachment programming
  - V53 primary 16..23 depth window and V55 secondary-band structure
  - V47 concurrent-binning baseline
  - barriers, resolves/MSAA correctness, KGSL sync/waits, WSI
  - V58/V59 LRZ correctness rules

Existing opt-outs still work:
  TU_A810_26317_TEX_WINDOW_MAX=4  -> stable scheduler reference
  TU_A810_26316_PREFETCH_USE_SCORE=0 -> stable prefetch reference
  TU_FRANE_EDGE=1                -> V59 hard-tail-only edge reference
  TU_FRANE_GMEM_TURBO=0          -> bypass V56/V60X turbo path
"""
from pathlib import Path

ROOT = Path("mesa/src/freedreno")
V = ROOT


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V60X source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V60X PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# 1) Scheduler: the FC2 hardware sweep was monotonic 8 -> 6 -> 4. Push the
# already-supported lower bound (2) as the internal default. The pressure ladder
# itself remains unchanged, so this is a clean extrapolation of that measured
# direction rather than a new scheduler algorithm.
# ---------------------------------------------------------------------------
edit(
    "ir3/ir3_compiler.c",
    'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4)',
    'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 2)',
    "promote sy window 2 as internal default",
)

edit(
    "vulkan/tu_device.cc",
    'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4)',
    'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 2)',
    "match shader-cache identity to sy window 2",
)

# ---------------------------------------------------------------------------
# 2) Prefetch: quad + diversity are already default-on. Turn on the existing
# use-count ranking too; with sy=2 this should spend scarce early producer slots
# on fetch results used most by the shader.
# ---------------------------------------------------------------------------
edit(
    "ir3/ir3_compiler.c",
    'debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false)',
    'debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", true)',
    "enable use-score prefetch selection by default",
)

# ---------------------------------------------------------------------------
# 3) GMEM overdrive. Keep every correctness gate around the selector, but widen
# the measured winner frontier and make cold-start bias stronger. Measurement
# cadence is made *faster*, not slower, so a wrong aggressive choice can escape.
# ---------------------------------------------------------------------------
H = "vulkan/frane_mesa_26320_a810_gmem_turbo.h"

edit(
    H,
    """      if (sysmem_probability > 55)
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
    """      /* V60X overdrive: measured winners may challenge much deeper into
       * PROFILED's neutral/SYSMEM territory. Final A810 GMEM safety remains
       * authoritative after this selector.
       */
      if (sysmem_probability > 70)
         return out;

      uint8_t probe_log2 = 0;
      if (state.score >= 8 && eval.structure_score >= 70 &&
          sysmem_probability <= 40) {
         probe_log2 = 10; /* 1/1024 */
      } else if (state.score >= 6 && eval.structure_score >= 60 &&
                 sysmem_probability <= 52) {
         probe_log2 = 9; /* 1/512 */
      } else if (state.score >= 4 && eval.structure_score >= 52) {
         probe_log2 = 8; /* 1/256 */
      } else {
         return out;
      }
""",
    "widen measured GMEM hold frontier",
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

   /* V60X cold-start push. Keep a 1% SYSMEM escape floor and sample 1/2 so
    * bad guesses are discovered quickly even though the initial bias is much
    * more aggressive.
    */
   uint32_t reduction = 30;
   if (eval.structure_score >= 86)
      reduction = 50;
   else if (eval.structure_score >= 74)
      reduction = 40;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;
   effective = std::max(effective, 1u);

   out.override_mode = true;
   out.probe_log2 = 0;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;
   out.force_measure = ((decision_word >> 8) & 1u) == 0u; /* 1/2 */
""",
    "push cold-start GMEM prior with faster escape measurement",
)

# ---------------------------------------------------------------------------
# 4) Re-open V57X's bounded medium tail by default. Hard-tail protection remains
# and V58/V59 LRZ behavior is untouched.
# ---------------------------------------------------------------------------
edit(
    "vulkan/tu_autotune.cc",
    'debug_get_num_option("TU_FRANE_EDGE", 1)',
    'debug_get_num_option("TU_FRANE_EDGE", 2)',
    "restore bounded EDGE=2 reopening for overdrive",
)

edit(
    "vulkan/tu_device.cc",
    "Drnas Turnip V59 / Mesa ",
    "Drnas Turnip A810 V60X OVERDRIVE / Mesa ",
    "V60X display identity",
)

# ---------------------------------------------------------------------------
# Audit the active stack. This build must be risky only in policy aggressiveness,
# not by accidentally undoing known correctness fixes.
# ---------------------------------------------------------------------------
compiler = (V / "ir3/ir3_compiler.c").read_text()
sched = (V / "ir3/ir3_sched.c").read_text()
auto = (V / "vulkan/tu_autotune.cc").read_text()
gmem = (V / "vulkan/frane_mesa_26320_a810_gmem_turbo.h").read_text()
cmd = (V / "vulkan/tu_cmd_buffer.cc").read_text()
lrz = (V / "vulkan/tu_lrz.cc").read_text()
kg = (V / "vulkan/tu_knl_kgsl.cc").read_text()
queue = (V / "vulkan/tu_queue.cc").read_text()
dev = (V / "vulkan/tu_device.cc").read_text()

assert 'TU_A810_26317_TEX_WINDOW_MAX", 2' in compiler
assert 'MIN2(8u, MAX2(2u, frane_tex_window))' in compiler
assert 'TU_A810_26317_TEX_WINDOW_MAX", 2' in dev
assert 'TU_A810_26316_PREFETCH_USE_SCORE", true' in compiler

# The scheduler algorithm remains the hardware-guided V25 ladder.
assert "return MIN2(max_window, 4u);" in sched
assert "return MIN2(max_window, 3u);" in sched
assert sched.count("return MIN2(max_window, 2u);") >= 2

for needle in (
    "sysmem_probability > 70",
    "eval.structure_score >= 70",
    "eval.structure_score >= 60",
    "state.score >= 4",
    "probe_log2 = 10",
    "sysmem_probability > 75",
    "eval.structure_score < 56",
    "std::max(effective, 1u)",
    "& 1u",
):
    assert needle in gmem, needle

assert 'TU_FRANE_EDGE", 2' in auto
assert 'TU_FRANE_TAIL", true' in auto
assert 'TU_FRANE_GMEM_TURBO", true' in auto

# Preserve known-good depth and CB baselines instead of stacking known
# regressions just for the sake of more changes.
assert 'TU_FRANE_DEPTH_DRAWS", 16' in auto
assert 'TU_FRANE_DEPTH_MAX", 23' in auto
assert 'TU_FRANE_CB_MODE", 1' in cmd

# V58/V59 LRZ and all sync/hang fixes must survive.
assert "(CHIP >= A8XX && !z_write_enable)" in lrz
assert "V59 A8XX LRZ-CLEAN" in lrz
assert "if (CHIP < A8XX || z_write_enable)" in lrz
assert "FRANE_2631_POLL_READY" in kg
assert "frane_2631_deadline_ns" in kg
assert "pthread_mutex_unlock(&device->submit_mutex);" in queue
assert "frane_26313_same_lrz_fs_signature" not in cmd

assert "Drnas Turnip A810 V60X OVERDRIVE / Mesa " in dev

print("Drnas Turnip A810 V60X OVERDRIVE applied and audited", flush=True)
