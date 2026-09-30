#!/usr/bin/env python3
"""Drnas Turnip V56 GMEM-HARD-PUSH.

Layered strictly on preserved V55.

V55 showed the extra 32..39 depth band was effectively neutral in Crysis.
V56 stops widening draw-count windows and attacks the live GMEM/SYSMEM
decision itself.

Default-on V56:
  TU_FRANE_GMEM_TURBO=1

Opt-out:
  TU_FRANE_GMEM_TURBO=0
  -> V55 SMART-GMEM/frontier behavior remains available for exact fallback.

The V20 turbo policy already sits behind the A810 gate and the final V26+
GMEM safety classifier. V56 deliberately makes that path materially more
aggressive:
- enable turbo by default;
- admit armed measured winners up to 55% live SYSMEM probability;
- lower structural/score thresholds for GMEM hold;
- stretch control-probe cadence for strong winners;
- make cold-start GMEM prior stronger while retaining measured escape probes.

No GMEM offsets/packing, attachment load/store programming, LRZ, barriers,
MSAA/resolve correctness gates, shaders, WSI or CB policy are changed.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V56 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V56 PASS {label}", flush=True)

# Re-enter the aggressive measured GMEM policy by default. V49's frontier
# logic already explicitly stands aside while gmem_turbo is enabled, so this
# remains one coherent selection policy rather than two stacked overrides.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'debug_get_bool_option("TU_FRANE_GMEM_TURBO", false)',
    'debug_get_bool_option("TU_FRANE_GMEM_TURBO", true)',
    "enable GMEM turbo by default",
)

H = "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h"

edit(
    H,
    """   if (state.armed) {
      if (sysmem_probability > 35)
         return out;

      uint8_t probe_log2 = 0;
      if (state.score >= 8 && eval.structure_score >= 82 &&
          sysmem_probability <= 20) {
         probe_log2 = 8; /* 1/256 */
      } else if (state.score >= 7 && eval.structure_score >= 72 &&
                 sysmem_probability <= 30) {
         probe_log2 = 7; /* 1/128 */
      } else if (state.score >= 6 && eval.structure_score >= 65) {
         probe_log2 = 6; /* 1/64 */
      } else {
         return out;
      }
""",
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
    "widen armed GMEM hold frontier",
)

edit(
    H,
    """   if (sysmem_probability > 55 || eval.structure_score < 72)
      return out;

   uint32_t reduction = 18;
   if (eval.structure_score >= 88)
      reduction = 36;
   else if (eval.structure_score >= 80)
      reduction = 28;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;
   effective = std::max(effective, 4u);

   out.override_mode = true;
   out.probe_log2 = 0;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;
   out.force_measure = ((decision_word >> 8) & 7u) == 0u; /* 1/8 */
""",
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
    "strengthen cold-start GMEM prior with faster measurement",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V55 / Mesa ",
    "Drnas Turnip V56 / Mesa ",
    "V56 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_GMEM_TURBO", true',
    "frane_26320_decide_gmem_turbo",
    "frane_a810_gmem_pass_safe",
    "TU_FRANE_DEPTH_DRAWS",
    "TU_FRANE_DEPTH_MAX",
    "TU_FRANE_DEPTH_BAND2_MIN",
):
    assert needle in a, needle

for needle in (
    "sysmem_probability > 55",
    "eval.structure_score >= 76",
    "eval.structure_score >= 66",
    "state.score >= 5",
    "probe_log2 = 9",
    "sysmem_probability > 65",
    "eval.structure_score < 62",
    "std::max(effective, 2u)",
    "& 3u",
):
    assert needle in h, needle

# Preserve the validated allocator/search and all correctness-sensitive gates.
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "frane_gmem_search_future_upper" in p
assert "TU_FRANE_GMEM_MASK" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V56 / Mesa " in d

print("Drnas Turnip V56 GMEM-HARD-PUSH applied", flush=True)
