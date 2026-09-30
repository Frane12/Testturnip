#!/usr/bin/env python3
"""Drnas Turnip V58 TAIL-REGIME.

Layered strictly on V57 PROFILED-TAIL-GUARD.

Why this test exists:
- V57 gives a stable warm average, but the Crysis GPU TimeDemo still produces
  a deterministic minimum near the same late frame on repeated passes.
- V57 treats a strong measured GMEM winner as authoritative even when the same
  render-pass identity later enters a much heavier tile-replay workload.
- V58 tests one narrow hypothesis: some of that historical confidence may be
  stale across a scene-regime change.

TU_FRANE_TAIL modes:
  0 = exact V56 selector behavior (tail guard off)
  1 = exact V57 tail-guard policy
  2 = V58 tail-regime policy (default)

V58 does not force SYSMEM. When its bounded regime-change guard fires it
returns the decision to Mesa PROFILED, exactly like V57.

No GMEM allocation/offsets, LRZ, barriers, shaders, CB, MSAA/resolve safety,
attachment programming or Vulkan synchronization are changed.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V58 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V58 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26358_a810_tail_regime.h",
    V / "frane_mesa_26358_a810_tail_regime.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26357_a810_tail_guard.h"',
    '#include "frane_mesa_26357_a810_tail_guard.h"\n'
    '#include "frane_mesa_26358_a810_tail_regime.h"',
    "include V58 tail-regime policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_guard = false;
   bool zs_load_store = false;
};""",
    """   bool tail_guard = false;
   uint8_t tail_mode = 0;
   bool zs_load_store = false;
};""",
    "extend smart input with tail mode",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """   if (frane_26357_eval_tail_guard(tail).defer_to_profiled)
      return frane_26318_smart_gmem_decision {};
""",
    """   if (in.tail_mode == 1) {
      if (frane_26357_eval_tail_guard(tail).defer_to_profiled)
         return frane_26318_smart_gmem_decision {};
   } else if (in.tail_mode >= 2) {
      if (frane_26358_eval_tail_regime(tail).defer_to_profiled)
         return frane_26318_smart_gmem_decision {};
   }
""",
    "select V57 or V58 tail policy",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_TAIL", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}
""",
    """static uint8_t
frane_a810_tail_mode(const struct tu_device *device)
{
   static const uint8_t mode =
      static_cast<uint8_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_TAIL", 2),
         INT64_C(0), INT64_C(2)));
   if (!mode || !device || !device->physical_device)
      return 0;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   if (id == UINT64_C(0x44010000) ||
       id == UINT64_C(0xffff44010000))
      return mode;
   return 0;
}
""",
    "turn tail switch into 0/1/2 policy mode",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {
""",
    """         runtime_input.tail_mode =
            frane_a810_tail_mode(device);
         runtime_input.tail_guard = runtime_input.tail_mode != 0;

         for (uint32_t i = 0; i < pass->attachment_count; i++) {
""",
    "feed V58 tail mode into selector",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V57 / Mesa ",
    "Drnas Turnip V58 / Mesa ",
    "V58 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h58 = (V / "frane_mesa_26358_a810_tail_regime.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_TAIL", 2',
    "frane_a810_tail_mode",
    "runtime_input.tail_mode",
):
    assert needle in a, needle

for needle in ("tail_guard = false", "tail_mode = 0", "zs_load_store = false"):
    assert needle in h18, needle

for needle in (
    "frane_mesa_26358_a810_tail_regime.h",
    "in.tail_mode == 1",
    "in.tail_mode >= 2",
    "frane_26358_eval_tail_regime(tail).defer_to_profiled",
):
    assert needle in h20, needle

for needle in (
    "out.replay_work >= 256",
    "in.estimated_tiles >= 8",
    "in.sysmem_probability >= 35",
    "in.measured_score >= 8",
    "frane_26357_ratio_le(gm, sys, 1, 2)",
):
    assert needle in h58, needle

assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V58 / Mesa " in d

print("Drnas Turnip V58 TAIL-REGIME applied", flush=True)
