#!/usr/bin/env python3
"""26.3.36 A810 TURBO-HUNT.

High-risk, fully bisectable performance experiment on validated V35.

Three independent defaults are changed:
  1. A810 adaptive SY scheduler max window: 4 -> 3.
  2. A810 legal texture-prefetch use-score: off -> on.
  3. A810 GMEM-TURBO policy: off -> on.

No legality gates are widened. Packed depth/stencil, LRZ correctness, V34
lifetime packing, V35 deep-audit cleanup, synchronization, WSI, and memory
ownership remain unchanged.

Exact V35 A/B restore:
  TU_A810_26317_TEX_WINDOW_MAX=4
  TU_A810_26316_PREFETCH_USE_SCORE=0
  TU_A810_26320_GMEM_TURBO=0
"""
from pathlib import Path

R = Path("mesa/src/freedreno")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.36 TURBO-HUNT source drift {label}: expected 1, got {n}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.36 PASS {label}", flush=True)

# 1) Follow the hardware trend 8 -> 6 -> 4 by taking the next conservative
# step to 3.  Keep the entire V35 pressure ladder unchanged so env=4 is an
# exact scheduler A/B back to V35.
edit(
    "ir3/ir3_compiler.c",
    '''      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);''',
    '''      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 3);''',
    "scheduler default 4 -> 3",
)

# 2) The use-score only changes WHICH already-legal candidates occupy the
# existing prefetch slots. It adds no runtime GPU work and preserves the
# current legality filters.
edit(
    "ir3/ir3_compiler.c",
    '''      compiler->frane_26316_prefetch_use_score =
         debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false);''',
    '''      compiler->frane_26316_prefetch_use_score =
         debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", true);''',
    "enable legal prefetch use-score by default",
)

# 3) Re-test aggressive GMEM selection now that V33/V34 packing and lifetime
# reuse have materially changed the GMEM quality compared with the old test.
edit(
    "vulkan/tu_autotune.cc",
    'debug_get_bool_option("TU_A810_26320_GMEM_TURBO", false);',
    'debug_get_bool_option("TU_A810_26320_GMEM_TURBO", true);',
    "re-enable GMEM-TURBO by default",
)

# Physical-device cache UUID must resolve to the same compile defaults as IR3.
edit(
    "vulkan/tu_device.cc",
    '''   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);''',
    '''   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 3);''',
    "cache scheduler default 4 -> 3",
)

edit(
    "vulkan/tu_device.cc",
    '''   options[6] = debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false);''',
    '''   options[6] = debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", true);''',
    "cache prefetch-score default on",
)

edit(
    "vulkan/tu_device.cc",
    "Turnip A810 V35 / Mesa ",
    "Turnip A810 V36 / Mesa ",
    "short driver identity",
)

compiler = (R / "ir3/ir3_compiler.c").read_text()
sched = (R / "ir3/ir3_sched.c").read_text()
autotune = (R / "vulkan/tu_autotune.cc").read_text()
device = (R / "vulkan/tu_device.cc").read_text()
lower = (R / "ir3/ir3_nir_lower_tex_prefetch.c").read_text()
cmd = (R / "vulkan/tu_cmd_buffer.cc").read_text()
tu_pass = (R / "vulkan/tu_pass.cc").read_text()

assert 'TU_A810_26317_TEX_WINDOW_MAX", 3' in compiler
assert 'MIN2(8u, MAX2(2u, frane_tex_window))' in compiler
assert 'TU_A810_26316_PREFETCH_USE_SCORE", true' in compiler
assert 'TU_A810_26320_GMEM_TURBO", true' in autotune

# V35 scheduler semantics stay intact; env=4 is therefore an exact scheduler
# rollback rather than a different ladder.
assert 'return MIN2(max_window, 4u);' in sched
assert 'return MIN2(max_window, 3u);' in sched
assert sched.count('return MIN2(max_window, 2u);') == 2

# Compiler cache identity must match the new defaults.
assert 'TU_A810_26317_TEX_WINDOW_MAX", 3' in device
assert 'TU_A810_26316_PREFETCH_USE_SCORE", true' in device
assert 'MIN2(8u, MAX2(2u, window))' in device

# Prefetch legality remains exactly the guarded A810 path.
assert 'ok_tex_samp(tex, allow_bindless)' in lower
assert 'if (!allow_bindless)' in lower
assert 'uses > best_uses' in lower

# Preserve correctness-critical validated paths.
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'candidate_pixels > pixels' in tu_pass
assert 'frane_lifetime_candidate_can_beat' in tu_pass
assert 'Turnip A810 V36 / Mesa ' in device

print("26.3.36 A810 TURBO-HUNT applied", flush=True)
