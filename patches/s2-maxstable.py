#!/usr/bin/env python3
"""A810 S2 MaxStable synthesis layer.

Applied after:
  1) s1-smart2-complete.patch
  2) s1-smart-cb1.py

S2 is intentionally a synthesis/pruning pass, not another pile of heuristics.

Default policy:
- keep proven A810 compiler, hotpath, GMEM allocator/search, Smart v2 and CB1 work;
- preserve the pre-S2 A810 CCU/cache override for an isolated render bisect;
- make GMEM-TURBO measured-first: no structural cold-start forcing before the
  measured A810 runtime has armed;
- disable the Crysis-derived fixed depth draw bands by default and let measured
  history + the final GMEM safety classifier decide;
- keep scheduler max window = 4, guarded texture prefetch, UBO locality,
  LRZ-safe behavior, PWR_MAX request and Smart CB1 unchanged.

This is meant to maximize repeatable whole-workload performance rather than
optimize one benchmark frame range.
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
            f"S2 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"S2 PASS {label}", flush=True)


# 1) Preserve the pre-S2 A810 CCU/cache override. The S2 inherited-topology
# change is the first bisect target after an on-device corruption report.
# Keep this isolated from performance policy so the next device test can
# attribute recovery (or lack of recovery) to this rollback alone.

# 2) Remove the benchmark-shaped depth draw window from normal defaults.
# The code remains available for A/B through TU_FRANE_DEPTH_MODE=1.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'debug_get_num_option("TU_FRANE_DEPTH_MODE", 1);',
    'debug_get_num_option("TU_FRANE_DEPTH_MODE", 0);',
    "disable fixed depth-band force by default",
)

# 3) Keep the aggressive measured GMEM hold, but delete the V56 cold-start
# structural force. Before the runtime is armed, the already-measured-first
# SMART-GMEM result / Mesa PROFILED path owns the decision.
edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '''   /* Aggressive cold-start prior.  This path still refuses to fight a strong
    * live SYSMEM preference.  Strong structural evidence may reduce the
    * exploratory SYSMEM share below 26.3.18's 8% floor, but never below 4%.
    * It also doubles the measurement cadence to converge faster.
    */
   if (sysmem_probability > 65 || eval.structure_score < 62)
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
   return out;
''',
    '''   /* S2 measured-first cold path.
    *
    * Do not spend cold frames forcing a structural GMEM prior.  Mesa PROFILED
    * already measures whole render-pass cost including HW binning, while
    * Smart v2 collects fresh paired evidence. Once the A810 runtime is armed,
    * the aggressive measured hold above is still available.
    */
   return out;
''',
    "remove unmeasured GMEM cold-start force",
)

# 4) Identity.
edit(
    "src/freedreno/vulkan/tu_device.cc",
    "A810 S1 Smart CB1 / Mesa ",
    "A810 S2.1 Render Recovery / Mesa ",
    "S2 display identity",
)

# Static synthesis invariants.
devinfo = (ROOT / "src/freedreno/common/freedreno_devices.py").read_text()
autotune = (V / "tu_autotune.cc").read_text()
gmem = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
device = (V / "tu_device.cc").read_text()
compiler = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()

assert "A810 S2.1 Render Recovery / Mesa " in device
assert 'debug_get_num_option("TU_FRANE_DEPTH_MODE", 0)' in autotune
assert "Aggressive cold-start prior" not in gmem
assert "S2 measured-first cold path" in gmem

# The rollback must preserve the complete pre-S2 A810 CCU/cache block.
a810 = devinfo[devinfo.index('GPUId(chip_id=0xffff44010000, name="Adreno (TM) 810")'):]
a810 = a810[:a810.index("add_gpus([", 200)]
for required in (
    "sysmem_per_ccu_color_cache_size = 64 * 1024",
    "sysmem_per_ccu_depth_cache_size = 64 * 1024",
    "gmem_per_ccu_color_cache_size = 32 * 1024",
    "gmem_per_ccu_depth_cache_size = 48 * 1024",
):
    assert required in a810, required

# Keep the proven compiler/runtime stack.
for needle in (
    'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4)',
    'debug_get_bool_option("TU_A810_26311_SAFE_TEX_PREFETCH", true)',
    'debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", true)',
    'debug_get_bool_option("TU_A810_26315_PREFETCH_DIVERSITY", true)',
):
    assert needle in compiler, needle

for needle in (
    'TU_FRANE_SMART_CB", true',
    'TU_FRANE_SMART_CB_MODE", 1',
    "PIPE_BV_WAIT_FOR_BR",
    "PIPE_BR_WAIT_FOR_BV",
    "partial LRZ fast clear",
):
    assert needle in cmd, needle

# Keep the max-clock request available/default-on in this performance build.
queue = (V / "tu_knl_kgsl.cc").read_text()
assert 'debug_get_bool_option("TU_A810_PWR_MAX", true)' in queue

print("A810 S2.1 render rollback applied", flush=True)
# CI trigger: S2 synthesis candidate
