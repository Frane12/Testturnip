#!/usr/bin/env python3
"""26.3.24 A810 QCOM-EFFICIENCY-AUDIT.

This is a conservative efficiency audit layered strictly on 26.3.23.

It does not copy proprietary Qualcomm code or register programming.  It only
uses independently observable policy signals as constraints on our own
downstream experiments:

* keep measured PROFILED timing authoritative before SMART-GMEM may override;
* make aggressive GMEM-TURBO opt-in instead of default;
* never let the custom A810 scheduler exceed upstream's fixed sy=8 window;
* allow 4/6/8 A/B windows and reduce the window as estimated pressure rises.

LRZ correctness, selected tile geometry, UBO locality, legal texture-prefetch
filters, cache budgets, synchronization and WSI are intentionally unchanged.
"""
from pathlib import Path

R = Path("mesa/src/freedreno")


def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.24 QCOM-EFFICIENCY source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.24 QCOM-EFFICIENCY PASS {label}", flush=True)


# 1. The custom scheduler used to expand beyond upstream's fixed sy=8 cap.
# Keep the pressure-aware ordering experiment, but stop inventing extra
# outstanding memory/texture work on A810.  4 and 6 remain available for
# hardware A/B, while the default becomes upstream-safe 8.
edit(
    "ir3/ir3_compiler.c",
    '''      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 12);
      compiler->frane_26317_tex_window_max =
         MIN2(16u, MAX2(8u, frane_tex_window));''',
    '''      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 8);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(4u, frane_tex_window));''',
    "bound A810 sy window to 4..8 with default 8",
)

edit(
    "ir3/ir3_sched.c",
    '''static unsigned
frane_26317_sy_window(struct ir3_sched_ctx *ctx)
{
   if (!ctx->compiler->frane_26317_adaptive_sched)
      return 8;

   const unsigned p = frane_26317_pressure_pct(ctx);
   const unsigned max_window = ctx->compiler->frane_26317_tex_window_max;

   if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 10u);
   if (p < 50)
      return 8;
   if (p < 65)
      return 6;
   return 4;
}''',
    '''static unsigned
frane_26317_sy_window(struct ir3_sched_ctx *ctx)
{
   if (!ctx->compiler->frane_26317_adaptive_sched)
      return 8;

   const unsigned p = frane_26317_pressure_pct(ctx);
   const unsigned max_window = ctx->compiler->frane_26317_tex_window_max;

   /* 26.3.24: never exceed upstream's sy=8 window.  Under pressure, trade
    * some latency hiding for shorter live ranges.  max=6 gives the exact
    * 6/6/4/4/2 Qualcomm-model A/B ladder discussed for A810; max=4 gives a
    * deliberately conservative 4/4/4/4/2 variant.
    */
   if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 6u);
   if (p < 50)
      return MIN2(max_window, 4u);
   if (p < 65)
      return MIN2(max_window, 4u);
   return MIN2(max_window, 2u);
}''',
    "replace 12/10/8/6/4 ladder with bounded pressure ladder",
)

# 2. The 26.3.18 structural score is useful after measurement, but was too
# aggressive as a cold-start authority.  Before the paired timing state arms,
# leave mode selection to PROFILED instead of forcing up to ~92% GMEM.
smart_old = '''   /* Before enough timing samples exist, use layout/bandwidth only as a
    * bounded prior.  Never override a profiler that already leans strongly
    * toward SYSMEM.
    */
   if (sysmem_probability > 60)
      return out;

   uint32_t reduction = 0;
   if (eval.structure_score >= 80)
      reduction = 25;
   else if (eval.structure_score >= 68)
      reduction = 18;
   else if (eval.structure_score >= 58)
      reduction = 10;
   else
      return out;

   uint32_t effective =
      sysmem_probability > reduction ? sysmem_probability - reduction : 0u;

   /* A purely structural prior is never allowed to lock SYSMEM exploration
    * out completely. */
   effective = std::max(effective, 8u);

   out.override_mode = true;
   out.effective_sysmem_probability = effective;
   out.select_sysmem = (decision_word % 100u) < effective;

   /* Accelerate learning while still unarmed.  This only requests timestamp
    * measurement; it does not alter Vulkan synchronization or render state.
    */
   out.force_measure = ((decision_word >> 8) & 15u) == 0u; /* 1/16 */
   return out;'''
smart_new = '''   /* 26.3.24 measured-first policy:
    * structural GMEM evidence is advisory until paired GPU timings arm the
    * runtime.  PROFILED remains solely responsible for cold-start sampling.
    * This avoids turning an unverified layout estimate into a near-forced
    * GMEM choice on a low-tier/single-slice A810.
    */
   return out;'''
edit(
    "vulkan/frane_mesa_26318_a810_smart_gmem.h",
    smart_old,
    smart_new,
    "make SMART-GMEM measured-first before armed state",
)

# 3. Keep the old aggressive policy available for deliberate A/B, but do not
# enable it silently.  The normal default is SMART-GMEM + live PROFILED.
edit(
    "vulkan/tu_autotune.cc",
    'debug_get_bool_option("TU_A810_26320_GMEM_TURBO", true);',
    'debug_get_bool_option("TU_A810_26320_GMEM_TURBO", false);',
    "make GMEM-TURBO opt-in",
)

# 4. Cache identity must normalize the scheduler setting exactly like the
# compiler or an A/B run could reuse stale shaders.
edit(
    "vulkan/tu_device.cc",
    '''   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 12);''',
    '''   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 8);''',
    "match physical-device cache default",
)
edit(
    "vulkan/tu_device.cc",
    '''   options[8] = MIN2(16u, MAX2(8u, window));''',
    '''   options[8] = MIN2(8u, MAX2(4u, window));''',
    "match physical-device cache clamp",
)

edit(
    "vulkan/tu_device.cc",
    "Frane Mesa 26.3.23 A810 UPSTREAM-AUDIT EXP / Mesa ",
    "Frane Mesa 26.3.24 A810 QCOM-EFFICIENCY-AUDIT EXP / Mesa ",
    "driver identity",
)

# Guards: prove the audit touched only the intended policy surfaces.
compiler = (R / "ir3/ir3_compiler.c").read_text()
sched = (R / "ir3/ir3_sched.c").read_text()
smart = (R / "vulkan/frane_mesa_26318_a810_smart_gmem.h").read_text()
autotune = (R / "vulkan/tu_autotune.cc").read_text()
device = (R / "vulkan/tu_device.cc").read_text()
cmd = (R / "vulkan/tu_cmd_buffer.cc").read_text()
pipeline = (R / "vulkan/tu_pipeline.cc").read_text()

assert 'TU_A810_26317_TEX_WINDOW_MAX", 8' in compiler
assert 'MIN2(8u, MAX2(4u, frane_tex_window))' in compiler
assert 'return MIN2(max_window, 6u);' in sched
assert sched.count('return MIN2(max_window, 4u);') == 2
assert 'return MIN2(max_window, 2u);' in sched
assert 'effective = std::max(effective, 8u);' not in smart
assert 'structural GMEM evidence is advisory until paired GPU timings arm' in smart
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert 'TU_A810_26317_TEX_WINDOW_MAX", 8' in device
assert 'MIN2(8u, MAX2(4u, window))' in device

# Preserve correctness-sensitive pieces.
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'frane_26313_same_lrz_fs_signature' not in cmd
assert 'TU_A810_26313_LRZ_FASTPATH' in pipeline
assert 'frane_26321_selected_tile_count' in autotune
assert 'TU_A810_26322_LIVE_AUTOTUNE' in autotune

print("26.3.24 A810 QCOM-EFFICIENCY-AUDIT applied", flush=True)
