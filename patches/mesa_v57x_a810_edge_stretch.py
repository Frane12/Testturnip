#!/usr/bin/env python3
"""Drnas Turnip V57X A810 EDGE-STRETCH.

Base: exact V57 PROFILED-TAIL-GUARD.

The stable stack is deliberately preserved:
- V47/V45 CB keep baseline;
- V53 bounded depth window;
- V56 measured GMEM hard-push;
- V57 tail guard.

V57X changes only the boundary decision around V57's tail guard.

TU_FRANE_EDGE=0 -> exact V57
TU_FRANE_EDGE=1 -> hard-tail floor protection only
TU_FRANE_EDGE=2 -> floor protection + bounded medium-tail GMEM reopening
                    (default)

No allocator/GMEM offsets, attachment programming, LRZ, barriers, shaders,
concurrent-binning correctness, resolve/MSAA safety, WSI or synchronization
are changed.
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
            f"V57X source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:220]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V57X PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_v57x_a810_edge_stretch.h",
    V / "frane_v57x_a810_edge_stretch.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26357_a810_tail_guard.h"',
    '#include "frane_mesa_26357_a810_tail_guard.h"\n'
    '#include "frane_v57x_a810_edge_stretch.h"',
    "include V57X edge policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_guard = false;
   bool zs_load_store = false;
};""",
    """   bool tail_guard = false;
   bool zs_load_store = false;
   uint8_t tail_edge_mode = 0;
};""",
    "extend smart input with V57X mode",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{""",
    """static uint8_t
frane_a810_tail_edge_mode(const struct tu_device *device)
{
   if (!device || !device->physical_device)
      return 0;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   if (id != UINT64_C(0x44010000) &&
       id != UINT64_C(0xffff44010000))
      return 0;

   const int64_t mode =
      debug_get_num_option("TU_FRANE_EDGE", 2);
   return (uint8_t) std::clamp<int64_t>(mode, 0, 2);
}

static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{""",
    "add A810 V57X edge mode",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);
         runtime_input.tail_edge_mode =
            frane_a810_tail_edge_mode(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    "feed V57X mode into selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """   if (frane_26357_eval_tail_guard(tail).defer_to_profiled)
      return frane_26318_smart_gmem_decision {};

   if (sysmem_probability > 100)
""",
    """   const auto edge =
      frane_v57x_eval_edge(in.tail_edge_mode, tail);
   if (edge.defer_to_profiled)
      return frane_26318_smart_gmem_decision {};

   if (sysmem_probability > 100)
""",
    "route V57 tail boundary through V57X",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V57 / Mesa ",
    "Drnas Turnip V57X / Mesa ",
    "V57X display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
hx = (V / "frane_v57x_a810_edge_stretch.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'debug_get_num_option("TU_FRANE_EDGE", 2)',
    "frane_a810_tail_edge_mode",
    "runtime_input.tail_edge_mode",
):
    assert needle in a, needle

assert "tail_edge_mode = 0" in h18
assert "frane_v57x_eval_edge" in h20
assert "frane_v57x_a810_edge_stretch.h" in h20

for needle in (
    "out.replay_work >= 320",
    "out.replay_work <= 224",
    "frane_26357_ratio_le(gm, sys, 1, 2)",
    "frane_26357_ratio_le(gm, sys, 4, 5)",
    "in.measured_score >= 8",
    "in.measured_score >= 6",
):
    assert needle in hx, needle

# Proven V57 stack must remain present.
assert 'TU_FRANE_TAIL", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert 'TU_FRANE_DEPTH_DRAWS", 16' in a
assert 'TU_FRANE_DEPTH_MAX", 23' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V57X / Mesa " in d

print("Drnas Turnip V57X EDGE-STRETCH applied", flush=True)
