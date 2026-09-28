#!/usr/bin/env python3
"""26.3.25 A810 SCHED-TUNE.

Hardware feedback from A810/FC2 showed a monotonic gain when reducing
TU_A810_26317_TEX_WINDOW_MAX from 8 -> 6 -> 4, while GMEM-TURBO made little
difference.  This pass isolates that signal:

* default scheduler max window becomes 4;
* env A/B range expands to 2..8 so 2/3/4/6/8 can be tested;
* default pressure ladder becomes 4/4/3/2/2;
* GMEM policy, LRZ, prefetch, cache budgets, sync and WSI stay unchanged.

This is an A810-specific downstream experiment, not an upstream Qualcomm
algorithm claim.
"""
from pathlib import Path

R = Path("mesa/src/freedreno")


def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.25 SCHED-TUNE source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.25 SCHED-TUNE PASS {label}", flush=True)


# 1. Promote the best hardware-tested value so no env var is needed.
# Keep 2..8 available for controlled A/B work.
edit(
    "ir3/ir3_compiler.c",
    '''      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 8);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(4u, frane_tex_window));''',
    '''      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(2u, frane_tex_window));''',
    "promote A810 sy window default 4 and allow 2..8 A/B",
)

# 2. Make the default max=4 path exactly 4/4/3/2/2 as pressure rises.
# Overrides above 4 remain useful experiments: e.g. max=6 => 6/4/3/2/2,
# max=8 => 8/4/3/2/2.  Adaptive opt-out still restores upstream fixed 8.
edit(
    "ir3/ir3_sched.c",
    '''   /* 26.3.24: never exceed upstream's sy=8 window.  Under pressure, trade
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
   return MIN2(max_window, 2u);''',
    '''   /* 26.3.25 A810 hardware-guided ladder.
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
   return MIN2(max_window, 2u);''',
    "promote 4/4/3/2/2 pressure ladder",
)

# 3. Keep Vulkan and IR3 cache identity normalized to the exact compiler policy.
edit(
    "vulkan/tu_device.cc",
    '''   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 8);''',
    '''   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);''',
    "match physical-device cache default 4",
)
edit(
    "vulkan/tu_device.cc",
    '''   options[8] = MIN2(8u, MAX2(4u, window));''',
    '''   options[8] = MIN2(8u, MAX2(2u, window));''',
    "match physical-device cache clamp 2..8",
)

edit(
    "vulkan/tu_device.cc",
    "Frane Mesa 26.3.24 A810 QCOM-EFFICIENCY-AUDIT EXP / Mesa ",
    "Frane Mesa 26.3.25 A810 SCHED-TUNE EXP / Mesa ",
    "driver identity",
)

# Guards: this pass is intentionally scheduler/cache-identity only.
compiler = (R / "ir3/ir3_compiler.c").read_text()
sched = (R / "ir3/ir3_sched.c").read_text()
autotune = (R / "vulkan/tu_autotune.cc").read_text()
smart = (R / "vulkan/frane_mesa_26318_a810_smart_gmem.h").read_text()
device = (R / "vulkan/tu_device.cc").read_text()
cmd = (R / "vulkan/tu_cmd_buffer.cc").read_text()

assert 'TU_A810_26317_TEX_WINDOW_MAX", 4' in compiler
assert 'MIN2(8u, MAX2(2u, frane_tex_window))' in compiler
assert 'return MIN2(max_window, 4u);' in sched
assert 'return MIN2(max_window, 3u);' in sched
assert sched.count('return MIN2(max_window, 2u);') == 2
assert 'TU_A810_26317_TEX_WINDOW_MAX", 4' in device
assert 'MIN2(8u, MAX2(2u, window))' in device
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert 'structural GMEM evidence is advisory until paired GPU timings arm' in smart
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'frane_26313_same_lrz_fs_signature' not in cmd

print("26.3.25 A810 SCHED-TUNE applied", flush=True)
