#!/usr/bin/env python3
"""Drnas Turnip A830 V1 — first-pass A830 retarget over the V41 golden stack.

Goals:
  * keep the mature V39/V41 logic and portable 26.3.x fast paths;
  * retarget only portable logic to exact known A830 chip IDs;
  * make the newer PROFILED path the default on A830 instead of the old
    V15-era BANDWIDTH policy;
  * port the V33/V34/V37/V38/V39 GMEM allocator/search work to A830;
  * keep A810-only risky power/sampled-depth/GMEM safety work A810-only.

No guessed register writes, GMEM addresses, UBWC bits, KGSL ioctls or WSI hacks.
"""

from pathlib import Path
import re

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"
IR3 = ROOT / "src/freedreno/ir3"


def replace_once(path: Path, old: str, new: str, label: str):
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"A830 V1 drift {label}: expected 1 anchor, found {n}")
    path.write_text(s.replace(old, new, 1))
    print(f"A830 V1 PASS {label}", flush=True)


def regex_once(path: Path, pattern: str, repl: str, label: str, flags=0):
    s = path.read_text()
    ns, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f"A830 V1 drift {label}: regex matches={n}")
    path.write_text(ns)
    print(f"A830 V1 PASS {label}", flush=True)


def function_block(path: Path, name: str):
    s = path.read_text()
    start = s.find("static bool\n" + name)
    if start < 0:
        raise SystemExit(f"A830 V1: function not found: {name} in {path}")
    end = s.find("\n}\n", start)
    if end < 0:
        raise SystemExit(f"A830 V1: function end not found: {name} in {path}")
    return s, start, end + 3


def retarget_simple_gate(path: Path, old_name: str, new_name: str,
                         old_env: str | None, new_env: str | None):
    s, start, end = function_block(path, old_name)
    block = s[start:end]
    if old_env is not None:
        if old_env not in block:
            raise SystemExit(f"A830 V1: env {old_env} missing in {old_name}")
        block = block.replace(old_env, new_env)

    pat = re.compile(
        r"return\s+([A-Za-z_][A-Za-z0-9_]*)\s*==\s*UINT64_C\(0x44010000\)\s*\|\|\s*"
        r"\1\s*==\s*UINT64_C\(0xffff44010000\)\s*;"
    )
    block, n = pat.subn(
        r"return \1 == UINT64_C(0x44050000) ||\n"
        r"          \1 == UINT64_C(0x44050001) ||\n"
        r"          \1 == UINT64_C(0xffff44050000);",
        block, count=1
    )
    if n != 1:
        raise SystemExit(f"A830 V1: expected A810 chip gate in {old_name}, got {n}")

    block = block.replace(old_name, new_name, 1)
    s = s[:start] + block + s[end:]
    # Retarget all call sites after changing the definition.
    s = s.replace(old_name + "(", new_name + "(")
    path.write_text(s)
    print(f"A830 V1 PASS retarget {old_name} -> {new_name}", flush=True)


autotune = V / "tu_autotune.cc"
cmd = V / "tu_cmd_buffer.cc"
dev = V / "tu_device.cc"
passcc = V / "tu_pass.cc"
pipeline = V / "tu_pipeline.cc"
stage_h = V / "frane_mesa_2635_shader_pipeline.h"
compiler = IR3 / "ir3_compiler.c"

# ---------------------------------------------------------------------------
# Exact A830 helper used only by portable hot paths. Keep frane_a810_gpu()
# intact so A810-only legacy experiments do not accidentally become A830 code.
# ---------------------------------------------------------------------------
replace_once(
    autotune,
    """static bool
frane_a810_gpu(const struct tu_device *device)
""",
    """static bool
drnas_a830_gpu(const struct tu_device *device)
{
   if (!device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44050000) ||
          id == UINT64_C(0x44050001) ||
          id == UINT64_C(0xffff44050000);
}

static bool
frane_a810_gpu(const struct tu_device *device)
""",
    "add exact A830 capability gate",
)

# The old V15 A830 policy forced BANDWIDTH ahead of the later generic PROFILED
# default. Keep it available only as an explicit A/B switch.
s, start, end = function_block(autotune, "frane_a830_smart_gmem")
block = s[start:end]
block, n = re.subn(
    r'return\s+!env\s*\|\|\s*strcmp\(env,\s*"0"\)\s*!=\s*0;',
    'return env && strcmp(env, "1") == 0;',
    block, count=1
)
if n != 1:
    raise SystemExit("A830 V1: old A830 BANDWIDTH default anchor not found")
autotune.write_text(s[:start] + block + s[end:])
print("A830 V1 PASS legacy A830 BANDWIDTH becomes explicit-only", flush=True)

# ---------------------------------------------------------------------------
# Retarget the mature portable PROFILED / SMART-GMEM path.
# ---------------------------------------------------------------------------
retarget_simple_gate(
    autotune, "frane_a810_gmem_runtime_enabled",
    "drnas_a830_gmem_runtime_enabled",
    "TU_A810_GMEM_RUNTIME", "TU_A830_V1_GMEM_RUNTIME"
)
retarget_simple_gate(
    autotune, "frane_a810_smart_gmem_enabled",
    "drnas_a830_smart_gmem_enabled",
    "TU_A810_26318_SMART_GMEM", "TU_A830_V1_SMART_GMEM"
)
retarget_simple_gate(
    autotune, "frane_a810_live_profiled",
    "drnas_a830_live_profiled",
    "TU_A810_26322_LIVE_AUTOTUNE", "TU_A830_V1_LIVE_AUTOTUNE"
)

regex_once(
    autotune,
    r"(frane_2632_profile_base_interval\(\s*frane_a810_sample_interval\(\),\s*)frane_a810_gpu\(at\.device\)",
    r"\1drnas_a830_gpu(at.device)",
    "A830 PROFILED base cadence",
)
regex_once(
    autotune,
    r"(frane_2633_profile_interval\(\s*sample_base,\s*)frane_a810_gpu\(at\.device\)",
    r"\1drnas_a830_gpu(at.device)",
    "A830 profile-aware sample cadence",
)
regex_once(
    autotune,
    r"(const bool frane_hot\s*=\s*frane_2637_core_fastpath\(\)\s*&&\s*)frane_a810_gpu\(device\)",
    r"\1drnas_a830_gpu(device)",
    "A830 hot render-pass cache gate",
)
# Give the switch an A830 name while keeping implementation unchanged.
s = autotune.read_text()
if 'TU_A810_2637_CORE_FASTPATH' not in s:
    raise SystemExit("A830 V1: core-fastpath switch missing")
autotune.write_text(s.replace("TU_A810_2637_CORE_FASTPATH",
                              "TU_A830_V1_CORE_FASTPATH"))

# ---------------------------------------------------------------------------
# Bounded stage-NIR cache: portable, RAM-capped and already audited.
# ---------------------------------------------------------------------------
retarget_simple_gate(
    stage_h, "frane_2635_is_a810_chip", "drnas_2635_is_a830_chip",
    None, None
)
s = dev.read_text()
if s.count("frane_2635_is_a810_chip(") != 1:
    raise SystemExit("A830 V1: stage-NIR helper call drift")
s = s.replace("frane_2635_is_a810_chip(", "drnas_2635_is_a830_chip(", 1)
if 'TU_A810_STAGE_NIR_CACHE' not in s:
    raise SystemExit("A830 V1: stage-NIR switch missing")
s = s.replace("TU_A810_STAGE_NIR_CACHE", "TU_A830_V1_STAGE_NIR_CACHE")
dev.write_text(s)
print("A830 V1 PASS bounded stage-NIR cache", flush=True)

# ---------------------------------------------------------------------------
# Portable IR3 locality/prefetch/scheduler stack.
# ---------------------------------------------------------------------------
s = compiler.read_text()
b0 = s.find("const bool frane_is_a810")
b1 = s.find("if (frane_is_a810)", b0)
if b0 < 0 or b1 < 0:
    raise SystemExit("A830 V1: IR3 A810 feature gate not found")
b1 += len("if (frane_is_a810) {")
gate = s[b0:b1]
if "0x44010000" not in gate or "0xffff44010000" not in gate:
    raise SystemExit("A830 V1: IR3 gate IDs drifted")
gate = gate.replace("const bool frane_is_a810", "const bool drnas_is_a830", 1)
gate = gate.replace(
    "frane_chip_id == UINT64_C(0x44010000) ||",
    "frane_chip_id == UINT64_C(0x44050000) ||\n"
    "       frane_chip_id == UINT64_C(0x44050001) ||",
    1,
)
gate = gate.replace("0xffff44010000", "0xffff44050000", 1)
gate = gate.replace("if (frane_is_a810)", "if (drnas_is_a830)", 1)
s = s[:b0] + gate + s[b1:]
count = s.count("TU_A810_263")
if count < 6:
    raise SystemExit(f"A830 V1: expected IR3 A810 switches, found {count}")
s = s.replace("TU_A810_263", "TU_A830_263")
compiler.write_text(s)
print(f"A830 V1 PASS IR3 portable stack switches retargeted={count}", flush=True)

# LRZ fastpath is correctness-fenced by the existing V13/V14 work.
s = pipeline.read_text()
if s.count("TU_A810_26313_LRZ_FASTPATH") != 1:
    raise SystemExit("A830 V1: LRZ fastpath switch drift")
pipeline.write_text(
    s.replace("TU_A810_26313_LRZ_FASTPATH",
              "TU_A830_V1_26313_LRZ_FASTPATH", 1)
)
print("A830 V1 PASS LRZ fastpath switch", flush=True)

# Gen8 GMEM-dimension gating: same metadata logic, exact A830 device IDs.
s = cmd.read_text()
if s.count("TU_A810_2639_GMEM_DIM_GATING") != 1:
    raise SystemExit("A830 V1: GMEM-dimension switch drift")
s = s.replace("TU_A810_2639_GMEM_DIM_GATING",
              "TU_A830_V1_2639_GMEM_DIM_GATING", 1)
old_guard = """   if (chip_id != UINT64_C(0x44010000) &&
       chip_id != UINT64_C(0xffff44010000))
      return usage;"""
new_guard = """   if (chip_id != UINT64_C(0x44050000) &&
       chip_id != UINT64_C(0x44050001) &&
       chip_id != UINT64_C(0xffff44050000))
      return usage;"""
if s.count(old_guard) != 1:
    raise SystemExit("A830 V1: GMEM-dimension chip gate drift")
cmd.write_text(s.replace(old_guard, new_guard, 1))
print("A830 V1 PASS GMEM-dimension gate", flush=True)

# ---------------------------------------------------------------------------
# Port the successful allocator/search side of the V33..V39 GMEM work.
# These algorithms consume the device-reported GMEM size/alignment; no A810
# register/layout constants are carried over.
# ---------------------------------------------------------------------------
retarget_simple_gate(
    passcc, "frane_a810_hybrid_gmem_pack_enabled",
    "drnas_a830_hybrid_gmem_pack_enabled",
    "TU_A810_26333_GMEM_HYBRID_PACK", "TU_A830_V1_26333_GMEM_HYBRID_PACK"
)
retarget_simple_gate(
    passcc, "frane_a810_lifetime_tile_pack_enabled",
    "drnas_a830_lifetime_tile_pack_enabled",
    "TU_A810_26334_GMEM_LIFETIME_TILE_PACK", "TU_A830_V1_26334_GMEM_LIFETIME_TILE_PACK"
)
retarget_simple_gate(
    passcc, "frane_a810_gmem_mask_pack_enabled",
    "drnas_a830_gmem_mask_pack_enabled",
    "TU_A810_26337_GMEM_MASK_PACK", "TU_A830_V1_26337_GMEM_MASK_PACK"
)
retarget_simple_gate(
    passcc, "frane_a810_gmem_search_enabled",
    "drnas_a830_gmem_search_enabled",
    "TU_A810_26338_GMEM_SEARCH", "TU_A830_V1_26338_GMEM_SEARCH"
)

s = passcc.read_text()
if s.count("frane_a810_gmem_pressure_bound_enabled") != 2:
    raise SystemExit("A830 V1: pressure-bound helper/call count drift")
s = s.replace("frane_a810_gmem_pressure_bound_enabled",
              "drnas_a830_gmem_pressure_bound_enabled")
s = s.replace("TU_A810_26339_GMEM_PRESSURE_BOUND",
              "TU_A830_V1_26339_GMEM_PRESSURE_BOUND")
s = s.replace("TU_A810_26339_GMEM_SEARCH_BUDGET",
              "TU_A830_V1_26339_GMEM_SEARCH_BUDGET")
s = s.replace("TU_A810_26338_GMEM_SEARCH_BUDGET",
              "TU_A830_V1_26338_GMEM_SEARCH_BUDGET")
passcc.write_text(s)
print("A830 V1 PASS V39 pressure bound + budgets", flush=True)

# ---------------------------------------------------------------------------
# V41 clean-draw caches are pure CPU-side derived-state caches. Retarget the
# exact device gate and keep the broad invalidation policy unchanged.
# ---------------------------------------------------------------------------
retarget_simple_gate(
    cmd, "frane_26341_a810", "drnas_26341_a830",
    None, None
)
s = cmd.read_text()
for old, new in (
    ("TU_A810_26341_INITIATOR_CACHE", "TU_A830_V1_26341_INITIATOR_CACHE"),
    ("TU_A810_26341_BANDWIDTH_CACHE", "TU_A830_V1_26341_BANDWIDTH_CACHE"),
):
    if old not in s:
        raise SystemExit(f"A830 V1: V41 switch missing: {old}")
    s = s.replace(old, new)
cmd.write_text(s)
print("A830 V1 PASS V41 clean-draw caches", flush=True)

# Short AdrenoTools/Winlator display identity.
replace_once(
    dev,
    "Turnip A810 V41 / Mesa ",
    "Drnas Turnip A830 V1 / Mesa ",
    "driver identity",
)

# ---------------------------------------------------------------------------
# Surgical audit: portable work must be A830-targeted, while risky A810-only
# power/sampled-depth and A810 GMEM-safety experiments stay isolated.
# ---------------------------------------------------------------------------
a = autotune.read_text()
p = passcc.read_text()
c = compiler.read_text()
cb = cmd.read_text()
d = dev.read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
img = (V / "tu_image.cc").read_text()

for needle in (
    "drnas_a830_gpu",
    "TU_A830_V1_GMEM_RUNTIME",
    "TU_A830_V1_SMART_GMEM",
    "TU_A830_V1_LIVE_AUTOTUNE",
    "TU_A830_V1_CORE_FASTPATH",
):
    assert needle in a, needle

for needle in (
    "TU_A830_V1_26333_GMEM_HYBRID_PACK",
    "TU_A830_V1_26334_GMEM_LIFETIME_TILE_PACK",
    "TU_A830_V1_26337_GMEM_MASK_PACK",
    "TU_A830_V1_26338_GMEM_SEARCH",
    "TU_A830_V1_26339_GMEM_PRESSURE_BOUND",
    "TU_A830_V1_26339_GMEM_SEARCH_BUDGET",
    "frane_gmem_search_future_upper",
):
    assert needle in p, needle

for needle in (
    "TU_A830_V1_26341_INITIATOR_CACHE",
    "TU_A830_V1_26341_BANDWIDTH_CACHE",
    "drnas_26341_a830",
    "TU_A830_V1_2639_GMEM_DIM_GATING",
):
    assert needle in cb, needle

assert "TU_A830_26317_ADAPTIVE_SCHED" in c
assert "TU_A830_26317_TEX_WINDOW_MAX" in c
assert "TU_A830_V1_26313_LRZ_FASTPATH" in pipeline.read_text()
assert "TU_A830_V1_STAGE_NIR_CACHE" in d
assert "Drnas Turnip A830 V1 / Mesa " in d

# A810-only hardware/risky workaround layers must remain A810-only.
assert "TU_A810_PWR_MAX" in kg and "TU_A830_PWR_MAX" not in kg
assert "TU_A810_SAMPLED_DEPTH_DIAG" in img and "TU_A830_SAMPLED_DEPTH_DIAG" not in img
assert "TU_A810_26326_GMEM_SAFETY" in a
assert "TU_A830_26326_GMEM_SAFETY" not in a

for chip in ("0x44050000", "0x44050001", "0xffff44050000"):
    assert chip in a
    assert chip in p
    assert chip in cb
    assert chip in c

print("Drnas Turnip A830 V1 retarget + GMEM first pass applied and audited", flush=True)
