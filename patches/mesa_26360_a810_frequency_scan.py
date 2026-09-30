#!/usr/bin/env python3
"""Drnas Turnip V60 A810 FREQUENCY-AWARE SCAN.

Layered strictly on V59 SCAN-LEARNER.

V59 uses one universal scan target (10 samples/mode). V60 keeps the same scan
mechanism but makes the budget grow with per-render-pass recurrence count:

  <16 occurrences   -> 1 sample/mode
  <64               -> 2
  <256              -> 4
  <512              -> 6
  <1024             -> 8
  >=1024            -> 10

Therefore rare passes cannot be repeatedly sacrificed to finish a hot-pass
learning budget. Frequently recurring passes still reach the full V58 learner.

Default:
  TU_FRANE_FREQ=1

Fallbacks:
  TU_FRANE_FREQ=0  -> exact V59 fixed-target scan
  TU_FRANE_SCAN=0  -> exact V58 selector behavior

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
            f"V60 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:220]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V60 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26360_a810_frequency_scan.h",
    V / "frane_mesa_26360_a810_frequency_scan.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26359_a810_scan_learner.h"',
    '#include "frane_mesa_26359_a810_scan_learner.h"\n'
    '#include "frane_mesa_26360_a810_frequency_scan.h"',
    "include V60 frequency-aware policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_scan = false;
   uint32_t tail_scan_word = 0;
};""",
    """   bool tail_scan = false;
   uint32_t tail_scan_word = 0;
   bool tail_frequency = false;
   uint32_t tail_occurrences = 0;
};""",
    "extend smart input with recurrence state",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_scan_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_frequency_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_FREQ", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_scan_enabled(const struct tu_device *device)
{""",
    "add default-on frequency-aware gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   std::atomic<uint32_t> frane_tail_scan_word { 0 };""",
    """   std::atomic<uint32_t> frane_tail_scan_word { 0 };
   std::atomic<uint32_t> frane_tail_occurrences { 0 };""",
    "add per-RP recurrence counter",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_scan_word =
            history.frane_tail_scan_word.load(std::memory_order_relaxed);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    """         runtime_input.tail_scan_word =
            history.frane_tail_scan_word.load(std::memory_order_relaxed);
         runtime_input.tail_frequency =
            frane_a810_tail_frequency_enabled(device);
         runtime_input.tail_occurrences =
            history.frane_tail_occurrences.fetch_add(
               1, std::memory_order_relaxed) + 1;

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    "publish per-RP recurrence to selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """      const auto scan = frane_26359_decide_scan(
         in.tail_scan, true, scan_snapshot,
         sysmem_probability, decision_word);
""",
    """      const auto scan = in.tail_frequency
         ? frane_26360_decide_frequency_scan(
              in.tail_scan, true, scan_snapshot,
              in.tail_occurrences, sysmem_probability, decision_word)
         : frane_26359_decide_scan(
              in.tail_scan, true, scan_snapshot,
              sysmem_probability, decision_word);
""",
    "replace universal scan target with recurrence-aware target",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V59 / Mesa ",
    "Drnas Turnip V60 / Mesa ",
    "V60 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h60 = (V / "frane_mesa_26360_a810_frequency_scan.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_FREQ", true',
    "frane_a810_tail_frequency_enabled",
    "frane_tail_occurrences",
    "history.frane_tail_occurrences.fetch_add",
    "runtime_input.tail_occurrences",
):
    assert needle in a, needle

for needle in (
    "tail_frequency = false",
    "tail_occurrences = 0",
):
    assert needle in h18, needle

for needle in (
    "frane_mesa_26360_a810_frequency_scan.h",
    "frane_26360_decide_frequency_scan",
    "in.tail_occurrences",
    "frane_26359_decide_scan",
):
    assert needle in h20, needle

for needle in (
    "occurrences < 16",
    "occurrences < 64",
    "occurrences < 256",
    "occurrences < 512",
    "occurrences < 1024",
    "target_per_mode = 10",
    "hostile_probe_log2 = 3",
):
    assert needle in h60, needle

# V59 and V58 remain exact in-binary fallbacks.
assert 'TU_FRANE_SCAN", true' in a
assert 'TU_FRANE_LEARN", true' in a
assert "frane_26359_decide_scan" in h20
assert "frane_26358_decide_tail_learner" in h20

# Preserve validated stack and safety fences.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V60 / Mesa " in d

print("Drnas Turnip V60 FREQUENCY-AWARE SCAN applied", flush=True)
