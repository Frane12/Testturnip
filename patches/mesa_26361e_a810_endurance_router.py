#!/usr/bin/env python3
"""Drnas Turnip V61E A810 ENDURANCE-ROUTER.

Layered strictly on V61 SIGNATURE-GATED-SCAN.

The endurance policy keeps V57's structural tail guard unchanged and composes
both useful V61 ideas:
- cold/rare render passes keep V61 signature-gated rescue behavior;
- once V58 has >=8 paired samples and its decision is actionable under live
  Mesa PROFILED probability, that mature learner decision gets authority before
  any additional forced scan.

Default:
  TU_FRANE_ENDURANCE=1

Fallback:
  TU_FRANE_ENDURANCE=0 -> exact V61 signature-gated ordering.

No GMEM allocation/offsets, attachment programming, LRZ, barriers, shaders,
concurrent binning, WSI, MSAA/resolve safety or Vulkan synchronization change.
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
            f"V61E source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V61E PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26361e_a810_endurance_router.h",
    V / "frane_mesa_26361e_a810_endurance_router.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26361_a810_signature_scan.h"',
    '#include "frane_mesa_26361_a810_signature_scan.h"\n'
    '#include "frane_mesa_26361e_a810_endurance_router.h"',
    "include V61E endurance router",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_signature = false;
};""",
    """   bool tail_signature = false;
   bool tail_endurance = false;
};""",
    "extend smart input with endurance gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_endurance_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_ENDURANCE", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    "add default-on V61E endurance gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_occurrences =""",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_endurance =
            frane_a810_tail_endurance_enabled(device);
         runtime_input.tail_occurrences =""",
    "feed endurance gate into selector",
)

old_selector = """      const auto scan = (in.tail_signature && in.tail_frequency)
         ? frane_26361_decide_signature_scan(
              in.tail_scan, true, scan_snapshot,
              in.tail_learner_word,
              in.tail_occurrences,
              tail_guard_eval.replay_work,
              tail.pass_pixels,
              tail.estimated_tiles,
              tail.drawcalls,
              tail.zs_load_store,
              sysmem_probability,
              decision_word)
         : in.tail_frequency
            ? frane_26360_decide_frequency_scan(
                 in.tail_scan, true, scan_snapshot,
                 in.tail_occurrences, sysmem_probability, decision_word)
            : frane_26359_decide_scan(
                 in.tail_scan, true, scan_snapshot,
                 sysmem_probability, decision_word);

      if (scan.override_mode) {
         out.override_mode = true;
         out.select_sysmem = scan.select_sysmem;
         out.force_measure = true;
         out.probe_log2 = 0;
         out.effective_sysmem_probability = sysmem_probability;
         return out;
      }

      const auto tail_snapshot =
         frane_26358_unpack_tail_snapshot(in.tail_learner_word);
      const auto learned = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);

      if (learned.override_mode) {
         out.override_mode = true;
         out.select_sysmem = learned.select_sysmem;
         out.force_measure = learned.force_measure;
         out.probe_log2 = learned.probe_log2;
         out.effective_sysmem_probability = sysmem_probability;
         return out;
      }
"""

new_selector = """      const auto route = frane_26361e_route_endurance(
         in.tail_endurance,
         in.tail_learner,
         in.tail_scan,
         in.tail_signature,
         in.tail_frequency,
         true,
         in.tail_learner_word,
         scan_snapshot,
         in.tail_occurrences,
         tail_guard_eval.replay_work,
         tail.pass_pixels,
         tail.estimated_tiles,
         tail.drawcalls,
         tail.zs_load_store,
         sysmem_probability,
         decision_word);

      if (route.override_mode) {
         out.override_mode = true;
         out.select_sysmem = route.select_sysmem;
         out.force_measure = route.force_measure;
         out.probe_log2 = route.probe_log2;
         out.effective_sysmem_probability = sysmem_probability;
         return out;
      }
"""

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    old_selector,
    new_selector,
    "compose signature scan and mature learner ordering",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V61 / Mesa ",
    "Drnas Turnip V61E / Mesa ",
    "V61E display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
he = (V / "frane_mesa_26361e_a810_endurance_router.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_ENDURANCE", true',
    "frane_a810_tail_endurance_enabled",
    "runtime_input.tail_endurance",
):
    assert needle in a, needle

assert "tail_endurance = false" in h18

for needle in (
    "frane_mesa_26361e_a810_endurance_router.h",
    "frane_26361e_route_endurance",
    "in.tail_endurance",
    "route.override_mode",
):
    assert needle in h20, needle

for needle in (
    "tail.paired_samples >= 8",
    "learned.override_mode",
    "scan_enabled && learner_enabled",
    "frane_26361_decide_signature_scan",
    "frane_26360_decide_frequency_scan",
    "frane_26359_decide_scan",
):
    assert needle in he, needle

# Preserve the complete V57 -> V61 safety/performance stack.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_SIG", true' in a
assert 'TU_FRANE_FREQ", true' in a
assert 'TU_FRANE_SCAN", true' in a
assert 'TU_FRANE_LEARN", true' in a
assert 'TU_FRANE_TAIL", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V61E / Mesa " in d

print("Drnas Turnip V61E ENDURANCE-ROUTER applied", flush=True)
