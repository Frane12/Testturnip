#!/usr/bin/env python3
"""Drnas Turnip V57 PROFILED-TAIL-GUARD.

Layered strictly on V56 GMEM-HARD-PUSH.

V56 materially improves the warm average, but the same deterministic minimum
survives across all three Crysis passes. V57 therefore does not back off the
successful aggressive GMEM policy globally. Instead it adds one A810-only
escape hatch for expensive tail passes.

The design combines three pieces:
- Mesa PROFILED remains the final fallback when the guard fires;
- the existing Drnas measured GMEM state remains authoritative when strongly
  armed;
- an A810 community Gallium heuristic (depth/stencil load-store + multiple
  tiles is costly in GMEM) is translated to Turnip and bounded by replay work
  plus Mesa's render-pass bandwidth estimate.

Default:
  TU_FRANE_TAIL=1

A/B fallback:
  TU_FRANE_TAIL=0
  -> exact V56 selector policy.

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
            f"V57 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V57 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26357_a810_tail_guard.h",
    V / "frane_mesa_26357_a810_tail_guard.h",
)


edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_live_profiled(const struct tu_device *device)
{""",
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

static bool
frane_a810_live_profiled(const struct tu_device *device)
{""",
    "add A810 V57 tail guard gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;
      }
""",
    """         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;
         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {
            const struct tu_render_pass_attachment &att = pass->attachments[i];
            if (!att.gmem ||
                !(vk_format_has_depth(att.format) ||
                  vk_format_has_stencil(att.format)))
               continue;

            if (att.load || att.store || att.load_stencil || att.store_stencil) {
               runtime_input.zs_load_store = true;
               break;
            }
         }
      }
""",
    "feed depth/stencil load-store pressure into V57",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V56 / Mesa ",
    "Drnas Turnip V57 / Mesa ",
    "V57 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h57 = (V / "frane_mesa_26357_a810_tail_guard.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_TAIL", true',
    "frane_a810_tail_guard_enabled",
    "runtime_input.zs_load_store",
    "att.load || att.store || att.load_stencil || att.store_stencil",
):
    assert needle in a, needle

for needle in ("tail_guard = false", "zs_load_store = false"):
    assert needle in h18, needle

for needle in (
    "frane_mesa_26357_a810_tail_guard.h",
    "frane_26357_eval_tail_guard(tail).defer_to_profiled",
    "tail.measured_score = state.score",
    "tail.sysmem_probability = sysmem_probability",
):
    assert needle in h20, needle

for needle in (
    "out.replay_work >= 128",
    "in.estimated_tiles >= 4",
    "frane_26357_ratio_le(gm, sys, 2, 3)",
    "in.measured_score >= 7",
    "in.sysmem_probability <= 30",
    "FULL_HD_PIXELS",
):
    assert needle in h57, needle

assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "sysmem_probability > 55" in h20
assert "probe_log2 = 9" in h20
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V57 / Mesa " in d

print("Drnas Turnip V57 PROFILED-TAIL-GUARD applied", flush=True)
