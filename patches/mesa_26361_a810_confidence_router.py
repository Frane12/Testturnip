#!/usr/bin/env python3
"""Drnas Turnip V61 A810 CONFIDENCE-ROUTER.

Layered strictly on V60 FREQUENCY-AWARE-SCAN.

V60 fixed the rare-pass failure of V59, but scan still has first authority when
its frequency tier grows. That can force extra measurements even after V58 has
already formed a mature, actionable tail-aware decision.

V61 composes the two policies instead of using a blind score threshold:
- ask V58 whether the learner decision is actually actionable under the current
  live PROFILED probability;
- require at least 8 completed GMEM/SYSMEM pairs before that decision may cancel
  additional scan work;
- if actionable+mature, learner wins immediately;
- otherwise V60 scan may continue gathering bounded evidence;
- if scan is finished/throttled, preserve V58 exactly;
- automatically suppress scan if the learner is disabled, avoiding a hidden
  V59/V60 A/B trap where forced samples had no consumer.

Default:
  TU_FRANE_EARLY=1

Fallback:
  TU_FRANE_EARLY=0 -> V60 scan-first ordering.

No GMEM layout/offsets, attachment programming, LRZ, barriers, shaders,
concurrent binning, MSAA/resolve safety or Vulkan synchronization are changed.
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
            f"V61 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:220]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V61 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26361_a810_confidence_router.h",
    V / "frane_mesa_26361_a810_confidence_router.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26360_a810_frequency_scan.h"',
    '#include "frane_mesa_26360_a810_frequency_scan.h"\n'
    '#include "frane_mesa_26361_a810_confidence_router.h"',
    "include V61 confidence router",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_frequency = false;
   uint32_t tail_occurrences = 0;
};""",
    """   bool tail_frequency = false;
   uint32_t tail_occurrences = 0;
   bool tail_early = false;
};""",
    "extend smart input with V61 early-stop gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_frequency_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_early_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_EARLY", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_frequency_enabled(const struct tu_device *device)
{""",
    "add default-on confidence-router gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_occurrences =
            history.frane_tail_occurrences.fetch_add(
               1, std::memory_order_relaxed) + 1;

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    """         runtime_input.tail_occurrences =
            history.frane_tail_occurrences.fetch_add(
               1, std::memory_order_relaxed) + 1;
         runtime_input.tail_early =
            frane_a810_tail_early_enabled(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    "feed V61 gate into selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """      const auto scan_snapshot =
         frane_26359_unpack_scan(in.tail_scan_word);
      const auto scan = in.tail_frequency
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
""",
    """      const auto scan_snapshot =
         frane_26359_unpack_scan(in.tail_scan_word);
      const auto tail_snapshot =
         frane_26358_unpack_tail_snapshot(in.tail_learner_word);

      const auto route = frane_26361_route_tail_pass(
         in.tail_early,
         in.tail_learner,
         in.tail_scan,
         in.tail_frequency,
         tail_snapshot,
         scan_snapshot,
         in.tail_occurrences,
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
""",
    "route mature learner before unnecessary scan",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V60 / Mesa ",
    "Drnas Turnip V61 / Mesa ",
    "V61 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h61 = (V / "frane_mesa_26361_a810_confidence_router.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_EARLY", true',
    "frane_a810_tail_early_enabled",
    "runtime_input.tail_early",
):
    assert needle in a, needle

assert "tail_early = false" in h18

for needle in (
    "frane_mesa_26361_a810_confidence_router.h",
    "frane_26361_route_tail_pass",
    "in.tail_early",
    "route.override_mode",
):
    assert needle in h20, needle

for needle in (
    "tail.paired_samples >= 8",
    "learned.override_mode",
    "scan_enabled && learner_enabled",
    "frequency_enabled",
    "frane_26361_route_source::LEARNER",
    "frane_26361_route_source::SCAN",
):
    assert needle in h61, needle

# In-binary A/B chain remains intact.
assert 'TU_FRANE_FREQ", true' in a
assert 'TU_FRANE_SCAN", true' in a
assert 'TU_FRANE_LEARN", true' in a
assert "frane_26360_decide_frequency_scan" in h61
assert "frane_26359_decide_scan" in h61
assert "frane_26358_decide_tail_learner" in h61

# Preserve validated safety/performance stack.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V61 / Mesa " in d

print("Drnas Turnip V61 CONFIDENCE-ROUTER applied", flush=True)
