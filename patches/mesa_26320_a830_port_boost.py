#!/usr/bin/env python3
"""Frane Mesa 26.3.20 A830 PORT-BOOST.

Final retarget layer over the already validated 26.3.19 A810 stack.

The earlier patches are intentionally applied and host-tested unchanged first.
This file runs last and retargets only the portable 26.3.x performance layers
to exact known A830 chip IDs.  A810-specific power, sampled-depth and old
workaround code is deliberately left A810-only.

A830 defaults enabled by this layer:
  - PROFILED turbo cadence and profile-aware low-overhead decisions;
  - measured GMEM runtime + 26.3.18 SMART-GMEM structural prior;
  - bounded RAM-only stage-NIR cache + 26.3.19 byte accounting;
  - 26.3.7/8 hot render-pass cache fastpath;
  - 26.3.9 inactive GMEM dimension gating;
  - 26.3.10..16 UBO locality and guarded texture-prefetch selection;
  - 26.3.17 adaptive IR3 pre-RA scheduler (window 12);
  - 26.3.19 allocation/freshness/publication correctness fixes.

No guessed register writes, GMEM offsets, attachment addresses, barriers,
descriptor layouts, WSI override, thermal bypass or undocumented KGSL ioctls.
"""
from pathlib import Path
import re

ROOT = Path("mesa/src/freedreno")
V = ROOT / "vulkan"
IR3 = ROOT / "ir3"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.20 A830 source drift: {label}: expected 1 anchor, saw {n}")
    path.write_text(s.replace(old, new, 1))
    print(f"26.3.20 A830 PASS {label}", flush=True)


def regex_once(path: Path, pattern: str, repl: str, label: str) -> None:
    s = path.read_text()
    ns, n = re.subn(pattern, repl, s, count=1, flags=re.MULTILINE)
    if n != 1:
        raise SystemExit(
            f"26.3.20 A830 source drift: {label}: regex matches={n}")
    path.write_text(ns)
    print(f"26.3.20 A830 PASS {label}", flush=True)


autotune = V / "tu_autotune.cc"

# Exact A830 gate. Keep the old A810 helper because old A810-specific layers
# must remain inert rather than being globally renamed.
replace_once(
    autotune,
    """static bool
frane_a810_gpu(const struct tu_device *device)""",
    """static bool
frane_26320_a830_gpu(const struct tu_device *device)
{
   if (!device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44050000) ||
          id == UINT64_C(0x44050001) ||
          id == UINT64_C(0xffff44050000);
}

static bool
frane_a810_gpu(const struct tu_device *device)""",
    "exact A830 capability gate",
)

# 26.3.2/3 PROFILED cadence: apply the same low-CPU learned-profile policy to
# A830 without touching the A810 helper used by unrelated older experiments.
regex_once(
    autotune,
    r"(frane_2632_profile_base_interval\(\s*frane_a810_sample_interval\(\),\s*)frane_a810_gpu\(at\.device\)",
    r"\1frane_26320_a830_gpu(at.device)",
    "A830 PROFILED turbo base cadence",
)
regex_once(
    autotune,
    r"(frane_2633_profile_interval\(\s*sample_base,\s*)frane_a810_gpu\(at\.device\)",
    r"\1frane_26320_a830_gpu(at.device)",
    "A830 profile-aware adaptive sampling",
)

# 26.3.4 measured GMEM runtime. Give it a 26.3.20-specific variable so it does
# not collide with the older A830 BANDWIDTH-era experiment retained in source.
replace_once(
    autotune,
    """static bool
frane_a810_gmem_runtime_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_GMEM_RUNTIME", true);
   if (!enabled || !device || !device->physical_device)
      return false;
   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}""",
    """static bool
frane_26320_a830_gmem_runtime_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A830_26320_PROFILED_GMEM", true);
   return enabled && frane_26320_a830_gpu(device);
}""",
    "A830 measured GMEM runtime gate",
)
s = autotune.read_text()
n = s.count("frane_a810_gmem_runtime_enabled(")
if n < 1:
    raise SystemExit("26.3.20 A830 source drift: no measured-GMEM call sites")
autotune.write_text(s.replace("frane_a810_gmem_runtime_enabled(",
                              "frane_26320_a830_gmem_runtime_enabled("))
print(f"26.3.20 A830 PASS measured GMEM call sites={n}", flush=True)

# 26.3.18 structural SMART-GMEM prior, still subordinate to measured timings.
replace_once(
    autotune,
    """static bool
frane_a810_smart_gmem_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26318_SMART_GMEM", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}""",
    """static bool
frane_26320_a830_smart_gmem_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A830_26320_SMART_GMEM", true);
   return enabled && frane_26320_a830_gpu(device);
}""",
    "A830 SMART-GMEM gate",
)
s = autotune.read_text()
n = s.count("frane_a810_smart_gmem_enabled(")
if n < 1:
    raise SystemExit("26.3.20 A830 source drift: no SMART-GMEM call sites")
autotune.write_text(s.replace("frane_a810_smart_gmem_enabled(",
                              "frane_26320_a830_smart_gmem_enabled("))
print(f"26.3.20 A830 PASS SMART-GMEM call sites={n}", flush=True)

# 26.3.7 core fastpath: preserve the exact hot-cache implementation and only
# change the device gate + opt-out variable.
s = autotune.read_text()
old = """frane_2637_core_fastpath()
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_2637_CORE_FASTPATH", true);"""
new = """frane_2637_core_fastpath()
{
   static const bool enabled =
      debug_get_bool_option("TU_A830_26320_CORE_FASTPATH", true);"""
if s.count(old) != 1:
    raise SystemExit("26.3.20 A830 source drift: core-fastpath switch")
s = s.replace(old, new, 1)
autotune.write_text(s)
regex_once(
    autotune,
    r"(const bool frane_hot\s*=\s*frane_2637_core_fastpath\(\)\s*&&\s*)frane_a810_gpu\(device\)",
    r"\1frane_26320_a830_gpu(device)",
    "26.3.7/8 hot-RP A830 device gate",
)
print("26.3.20 A830 PASS 26.3.7/8 hot-RP fastpath", flush=True)

# Bounded stage NIR cache. 26.3.19's 32 MiB charged-byte cap and 2 MiB
# per-object payload limit remain unchanged.
stage_h = V / "frane_mesa_2635_shader_pipeline.h"
replace_once(
    stage_h,
    """static inline bool
frane_2635_is_a810_chip(uint64_t chip_id)
{
   return chip_id == UINT64_C(0x44010000) ||
          chip_id == UINT64_C(0xffff44010000);
}""",
    """static inline bool
frane_26320_is_a830_chip(uint64_t chip_id)
{
   return chip_id == UINT64_C(0x44050000) ||
          chip_id == UINT64_C(0x44050001) ||
          chip_id == UINT64_C(0xffff44050000);
}""",
    "A830 stage-cache helper",
)
dev = V / "tu_device.cc"
s = dev.read_text()
if s.count("frane_2635_is_a810_chip(") != 1:
    raise SystemExit("26.3.20 A830 source drift: stage-cache chip helper call")
s = s.replace("frane_2635_is_a810_chip(", "frane_26320_is_a830_chip(", 1)
if s.count('debug_get_bool_option("TU_A810_STAGE_NIR_CACHE", true)') != 1:
    raise SystemExit("26.3.20 A830 source drift: stage-cache env")
s = s.replace('debug_get_bool_option("TU_A810_STAGE_NIR_CACHE", true)',
              'debug_get_bool_option("TU_A830_26320_STAGE_NIR_CACHE", true)', 1)
dev.write_text(s)
print("26.3.20 A830 PASS bounded stage-NIR cache", flush=True)

# IR3 A810 feature block -> exact A830. The generated policy fields are already
# GPU-neutral; only this constructor gate and the A/B variable names were A810.
compiler = IR3 / "ir3_compiler.c"
replace_once(
    compiler,
    """   const bool frane_is_a810 =
       frane_chip_id == UINT64_C(0x44010000) ||
       frane_chip_id == UINT64_C(0xffff44010000);
   if (frane_is_a810) {""",
    """   const bool frane_is_a830 =
       frane_chip_id == UINT64_C(0x44050000) ||
       frane_chip_id == UINT64_C(0x44050001) ||
       frane_chip_id == UINT64_C(0xffff44050000);
   if (frane_is_a830) {""",
    "IR3 experimental feature block -> A830",
)
s = compiler.read_text()
count = s.count("TU_A810_263")
if count < 6:
    raise SystemExit(
        f"26.3.20 A830 source drift: expected several IR3 A810 envs, saw {count}")
compiler.write_text(s.replace("TU_A810_263", "TU_A830_263"))
print(f"26.3.20 A830 PASS IR3 A/B variables retargeted={count}", flush=True)

# 26.3.9 GMEM-dimension gating: same layout metadata, now exact A830 only.
cmd = V / "tu_cmd_buffer.cc"
s = cmd.read_text()
if s.count('debug_get_bool_option("TU_A810_2639_GMEM_DIM_GATING", true)') != 1:
    raise SystemExit("26.3.20 A830 source drift: GMEM-dim env")
s = s.replace('debug_get_bool_option("TU_A810_2639_GMEM_DIM_GATING", true)',
              'debug_get_bool_option("TU_A830_2639_GMEM_DIM_GATING", true)', 1)
old = """   if (chip_id != UINT64_C(0x44010000) &&
       chip_id != UINT64_C(0xffff44010000))
      return usage;"""
new = """   if (chip_id != UINT64_C(0x44050000) &&
       chip_id != UINT64_C(0x44050001) &&
       chip_id != UINT64_C(0xffff44050000))
      return usage;"""
if s.count(old) != 1:
    raise SystemExit("26.3.20 A830 source drift: GMEM-dim chip gate")
cmd.write_text(s.replace(old, new, 1))
print("26.3.20 A830 PASS inactive GMEM-dimension gating", flush=True)

# LRZ-safe pipeline optimization is already correctness-fenced; only its opt-out
# name was A810-specific in the final source.
pipeline = V / "tu_pipeline.cc"
s = pipeline.read_text()
count = s.count("TU_A810_26313_LRZ_FASTPATH")
if count != 1:
    raise SystemExit(
        f"26.3.20 A830 source drift: LRZ env occurrences={count}")
pipeline.write_text(s.replace("TU_A810_26313_LRZ_FASTPATH",
                              "TU_A830_26313_LRZ_FASTPATH"))
print("26.3.20 A830 PASS LRZ-safe pipeline fastpath", flush=True)

# Experimental identity.
replace_once(
    dev,
    "Frane Mesa 26.3.19 A810 MEMORY-AUDIT / Mesa ",
    "Frane Mesa 26.3.20 A830 PORT-BOOST / Mesa ",
    "driver identity",
)

# Final surgical audit.  Old A810-specific PWR_MAX / sampled-depth switches are
# intentionally still present and still A810-gated; do not turn them into A830
# behavior by accident.
a = autotune.read_text()
c = compiler.read_text()
d = dev.read_text()
cmd_s = cmd.read_text()
pipe_s = pipeline.read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
img = (V / "tu_image.cc").read_text()

for needle in (
    "frane_26320_a830_gpu",
    "TU_A830_26320_PROFILED_GMEM",
    "TU_A830_26320_SMART_GMEM",
    "TU_A830_26320_CORE_FASTPATH",
    "frane_26318_decide_smart_gmem",
    "frane_26319_update_gmem",
):
    assert needle in a, needle

for needle in (
    "TU_A830_26310_UBO_GAP",
    "TU_A830_26311_SAFE_TEX_PREFETCH",
    "TU_A830_26312_DUAL_TEX_PREFETCH",
    "TU_A830_26314_TRIPLE_TEX_PREFETCH",
    "TU_A830_26315_PREFETCH_DIVERSITY",
    "TU_A830_26315_QUAD_TEX_PREFETCH",
    "TU_A830_26316_PREFETCH_USE_SCORE",
    "TU_A830_26317_ADAPTIVE_SCHED",
    "TU_A830_26317_TEX_WINDOW_MAX",
):
    assert needle in c, needle

assert "TU_A830_2639_GMEM_DIM_GATING" in cmd_s
assert "TU_A830_26313_LRZ_FASTPATH" in pipe_s
assert "TU_A830_26320_STAGE_NIR_CACHE" in d
assert "Frane Mesa 26.3.20 A830 PORT-BOOST / Mesa " in d

# A810-only risky legacy layers remain A810-only.
assert "TU_A810_PWR_MAX" in kg
assert "TU_A810_SAMPLED_DEPTH_DIAG" in img
assert "KGSL_CONSTRAINT_PWR_MAX" in kg

# Known A830 IDs must be represented in every new exact-device gate.
for chip in ("0x44050000", "0x44050001", "0xffff44050000"):
    assert chip in a
    assert chip in stage_h.read_text()
    assert chip in c
    assert chip in cmd_s

print("Frane Mesa 26.3.20 A830 PORT-BOOST applied and audited", flush=True)
