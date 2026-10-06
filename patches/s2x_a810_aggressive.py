#!/usr/bin/env python3
"""Turnip-Drnas A810 S2-X aggressive GMEM/scheduler experiment.

Layered strictly after the published S2 policy (V38 SH1 + GF1).  It keeps
attachment layout legality, LRZ correctness, synchronization, barriers and the
bounded V38 GMEM search unchanged.  It deliberately makes three policy layers
more aggressive while keeping each one reversible:

  TU_FRANE_S2X_GMEM=1      default; enables GMEM-TURBO again
  TU_FRANE_S2X_STICKY=1    default; extends measured GMEM hold/probe spacing
  TU_FRANE_S2X_SCHED=1     default; 6/5/4/3/2 low->high-pressure sy ladder

A/B restore:
  TU_FRANE_S2X_GMEM=0
  TU_FRANE_S2X_STICKY=0
  TU_FRANE_S2X_SCHED=0

The S2-X scheduler switch restores S2 defaults (window 4, pressure threshold 35)
when disabled.  No HOT2/render-pass cache changes from S2.1 are included.
"""

from pathlib import Path

ROOT = Path("mesa/src/freedreno")
V = ROOT / "vulkan"
IR3 = ROOT / "ir3"


def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"S2-X source drift: {label}: expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"S2-X PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# 1) Aggressive GMEM mode.
#
# Re-enable the already-bounded 26.3.20 GMEM-TURBO path behind a new S2-X
# switch.  The old QCOM-audit default stays represented by S2X_GMEM=0.
# ---------------------------------------------------------------------------
edit(
    "vulkan/tu_autotune.cc",
    """static bool
frane_a810_gmem_turbo_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26320_GMEM_TURBO", false);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_lean_profiled()
{""",
    """static bool
frane_a810_gmem_turbo_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_S2X_GMEM", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_s2x_sticky_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_S2X_STICKY", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_lean_profiled()
{""",
    "add S2-X GMEM and sticky gates",
)

# Extend the pure turbo helper with one explicit sticky-policy input.
edit(
    "vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """frane_26320_decide_gmem_turbo(bool enabled,
                              const frane_26318_smart_gmem_input &in,""",
    """frane_26320_decide_gmem_turbo(bool enabled,
                              bool sticky,
                              const frane_26318_smart_gmem_input &in,""",
    "add sticky argument to GMEM-TURBO helper",
)

edit(
    "vulkan/tu_autotune.cc",
    """         const frane_26318_smart_gmem_input *gmem_runtime_input = nullptr,
         bool smart_gmem = false,
         bool gmem_turbo = false,
         bool live_profiled = false)
      {""",
    """         const frane_26318_smart_gmem_input *gmem_runtime_input = nullptr,
         bool smart_gmem = false,
         bool gmem_turbo = false,
         bool live_profiled = false,
         bool s2x_sticky = false)
      {""",
    "carry S2-X sticky gate into profiled decision scope",
)

edit(
    "vulkan/tu_autotune.cc",
    """frane_26320_decide_gmem_turbo(
                     true, *gmem_runtime_input, runtime_state,
                     l_sysmem_probability, decision_word)""",
    """frane_26320_decide_gmem_turbo(
                     true, s2x_sticky,
                     *gmem_runtime_input, runtime_state,
                     l_sysmem_probability, decision_word)""",
    "wire local sticky policy into GMEM-TURBO decision",
)

edit(
    "vulkan/tu_autotune.cc",
    """         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device),
         frane_a810_gmem_turbo_enabled(device),
         frane_a810_live_profiled(device));""",
    """         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device),
         frane_a810_gmem_turbo_enabled(device),
         frane_a810_live_profiled(device),
         frane_s2x_sticky_enabled(device));""",
    "pass sticky gate from tu_autotune into profiled decision",
)

# Broaden the armed window and make very strong measured winners much stickier.
edit(
    "vulkan/frane_mesa_26320_a810_gmem_turbo.h",
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
      if (sysmem_probability > 45)
         return out;

      uint8_t probe_log2 = 0;
      if (state.score >= 8 && eval.structure_score >= 78 &&
          sysmem_probability <= 25) {
         probe_log2 = sticky ? 10 : 8; /* 1/1024 or 1/256 */
      } else if (state.score >= 7 && eval.structure_score >= 68 &&
                 sysmem_probability <= 35) {
         probe_log2 = sticky ? 9 : 7;  /* 1/512 or 1/128 */
      } else if (state.score >= 6 && eval.structure_score >= 60) {
         probe_log2 = sticky ? 7 : 6;  /* 1/128 or 1/64 */
      } else {
         return out;
      }
""",
    "extend measured GMEM hold and sparse control probes",
)

# More aggressive cold start, but keep a nonzero SYSMEM sample share and
# increase measurement cadence so a bad prior can arm/correct faster.
edit(
    "vulkan/frane_mesa_26320_a810_gmem_turbo.h",
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

   uint32_t reduction = 24;
   if (eval.structure_score >= 90)
      reduction = 44;
   else if (eval.structure_score >= 82)
      reduction = 36;
   else if (eval.structure_score >= 72)
      reduction = 30;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;
   effective = std::max(effective, 2u);

   out.override_mode = true;
   out.probe_log2 = 0;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;
   out.force_measure = ((decision_word >> 8) & 3u) == 0u; /* 1/4 */
""",
    "make cold-start structural prior more aggressive but faster-learning",
)


# ---------------------------------------------------------------------------
# 2) Aggressive scheduler.
#
# S2 hardware tuning settled on window=4 and SH1 pressure threshold=35.
# S2-X uses window=6 and threshold=42 by default, but one boolean switch
# restores the exact S2 defaults.  The normalized values are already part of
# both shader cache identities, so A/B runs cannot silently reuse stale code.
# ---------------------------------------------------------------------------
edit(
    "ir3/ir3_compiler.c",
    """      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(2u, frane_tex_window));
      compiler->frane_sh1_mode = frane_sh1_mode(
         debug_get_num_option("TU_FRANE_SHADER_MODE", 1));
      compiler->frane_sh1_threshold = frane_sh1_threshold(
         debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));""",
    """      const bool frane_s2x_sched =
         debug_get_bool_option("TU_FRANE_S2X_SCHED", true);
      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX",
                              frane_s2x_sched ? 6 : 4);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(2u, frane_tex_window));
      compiler->frane_sh1_mode = frane_sh1_mode(
         debug_get_num_option("TU_FRANE_SHADER_MODE", 1));
      compiler->frane_sh1_threshold = frane_sh1_threshold(
         debug_get_num_option("TU_FRANE_SHADER_PRESSURE",
                              frane_s2x_sched ? 42 : 35));""",
    "raise low-pressure issue window and SH1 pressure threshold",
)

edit(
    "ir3/ir3_sched.c",
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
    """   /* S2-X: preserve the exact S2 4/4/3/2/2 ladder when max<=4.
    * Aggressive default max=6 opens more low-pressure memory/texture latency
    * hiding, then contracts progressively as live-register pressure rises.
    */
   if (max_window <= 4) {
      if (p < 20)
         return max_window;
      if (p < 35)
         return MIN2(max_window, 4u);
      if (p < 50)
         return MIN2(max_window, 3u);
      if (p < 65)
         return MIN2(max_window, 2u);
      return MIN2(max_window, 2u);
   }

   if (p < 20)
      return max_window;            /* default 6 */
   if (p < 35)
      return MIN2(max_window, 5u);
   if (p < 50)
      return MIN2(max_window, 4u);
   if (p < 65)
      return MIN2(max_window, 3u);
   return MIN2(max_window, 2u);""",
    "add 6/5/4/3/2 aggressive pressure ladder with exact S2 fallback",
)

edit(
    "vulkan/tu_device.cc",
    """   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);""",
    """   const bool s2x_sched =
      debug_get_bool_option("TU_FRANE_S2X_SCHED", true);
   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX",
                                          s2x_sched ? 6 : 4);""",
    "match physical-device cache default to S2-X scheduler switch",
)

edit(
    "vulkan/tu_device.cc",
    """   options[11] = frane_sh1_threshold(debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));""",
    """   options[11] = frane_sh1_threshold(
      debug_get_num_option("TU_FRANE_SHADER_PRESSURE",
                           s2x_sched ? 42 : 35));""",
    "match cache identity to S2-X SH1 threshold",
)

edit(
    "vulkan/tu_device.cc",
    "Turnip-Drnas A810 V38 SH1 GF1 / Mesa ",
    "Turnip-Drnas A810 S2-X / Mesa ",
    "S2-X driver identity",
)


# Scope/correctness guards.
autotune = (V / "tu_autotune.cc").read_text()
turbo = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
compiler = (IR3 / "ir3_compiler.c").read_text()
sched = (IR3 / "ir3_sched.c").read_text()
device = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_S2X_GMEM", true',
    'TU_FRANE_S2X_STICKY", true',
    "frane_s2x_sticky_enabled",
    "bool s2x_sticky = false",
    "frane_s2x_sticky_enabled(device));",
):
    assert needle in autotune, needle

for needle in (
    "bool sticky",
    "probe_log2 = sticky ? 10 : 8",
    "probe_log2 = sticky ? 9 : 7",
    "sysmem_probability > 65",
    "std::max(effective, 2u)",
):
    assert needle in turbo, needle

for needle in (
    'TU_FRANE_S2X_SCHED", true',
    "frane_s2x_sched ? 6 : 4",
    "frane_s2x_sched ? 42 : 35",
):
    assert needle in compiler, needle

assert "if (max_window <= 4)" in sched
assert "return MIN2(max_window, 5u);" in sched
assert "return MIN2(max_window, 3u);" in sched
assert 'TU_FRANE_S2X_SCHED", true' in device
assert "s2x_sched ? 42 : 35" in device
assert "Turnip-Drnas A810 S2-X / Mesa " in device

# Keep correctness-sensitive render state untouched.
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'frane_26313_same_lrz_fs_signature' not in cmd
assert 'TU_FRANE_GMEM_FOOTPRINT", true' in autotune
assert 'TU_FRANE_SHADER_MODE", 1' in compiler

print("Turnip-Drnas A810 S2-X aggressive GMEM/scheduler policy applied", flush=True)
