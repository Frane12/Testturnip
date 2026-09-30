#!/usr/bin/env python3
"""Drnas Turnip V61 A810 SIGNATURE-GATED SCAN.

Layered strictly on V60 FREQUENCY-AWARE-SCAN.

V60 correctly limits scan budget by recurrence, but a cold/rare render pass
still pays for a forced 1+1 scan even though V58 cannot act before six paired
samples. V61 removes that dead-cost path.

The V61 scan is a rescue/completion mechanism:
- rare histories stay on Mesa PROFILED and gather natural timing evidence;
- render-pass structure (replay work, tiles, draw count, target size) selects
  the recurrence threshold required before forcing measurements;
- natural V58 paired evidence lowers the threshold;
- confidence >=4 stops forced scanning completely;
- only unresolved very-hot histories can extend beyond the six-pair readiness
  threshold.

Default:
  TU_FRANE_SIG=1

Fallbacks:
  TU_FRANE_SIG=0  -> exact V60 recurrence-aware scan
  TU_FRANE_FREQ=0 -> exact V59 fixed-target scan
  TU_FRANE_SCAN=0 -> exact V58 selector behavior

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
            f"V61 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:240]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V61 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26361_a810_signature_scan.h",
    V / "frane_mesa_26361_a810_signature_scan.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26360_a810_frequency_scan.h"',
    '#include "frane_mesa_26360_a810_frequency_scan.h"\n'
    '#include "frane_mesa_26361_a810_signature_scan.h"',
    "include V61 signature-gated policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_frequency = false;
   uint32_t tail_occurrences = 0;
};""",
    """   bool tail_frequency = false;
   uint32_t tail_occurrences = 0;
   bool tail_signature = false;
};""",
    "extend smart input with V61 signature gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_frequency_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_SIG", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_frequency_enabled(const struct tu_device *device)
{""",
    "add default-on V61 signature gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_frequency =
            frane_a810_tail_frequency_enabled(device);
         runtime_input.tail_occurrences =
""",
    """         runtime_input.tail_frequency =
            frane_a810_tail_frequency_enabled(device);
         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_occurrences =
""",
    "feed V61 gate into selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """      const auto scan = in.tail_frequency
         ? frane_26360_decide_frequency_scan(
              in.tail_scan, true, scan_snapshot,
              in.tail_occurrences, sysmem_probability, decision_word)
         : frane_26359_decide_scan(
              in.tail_scan, true, scan_snapshot,
              sysmem_probability, decision_word);
""",
    """      const auto scan = in.tail_signature
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
""",
    "replace V60 cold scan with V61 signature-gated rescue",
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
h61 = (V / "frane_mesa_26361_a810_signature_scan.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_SIG", true',
    "frane_a810_tail_signature_enabled",
    "runtime_input.tail_signature",
):
    assert needle in a, needle

assert "tail_signature = false" in h18

for needle in (
    "frane_mesa_26361_a810_signature_scan.h",
    "frane_26361_decide_signature_scan",
    "tail_guard_eval.replay_work",
    "in.tail_learner_word",
    "frane_26360_decide_frequency_scan",
    "frane_26359_decide_scan",
):
    assert needle in h20, needle

for needle in (
    "learned.paired_samples >= 4",
    "learned.paired_samples >= 2",
    "target = 6",
    "confidence >= 4",
    "frane_26361_sat_mul",
    "start_occurrences = 128",
    "start_occurrences = 192",
    "start_occurrences = 256",
):
    assert needle in h61, needle

# Exact V60/V59/V58 fallback layers remain in the binary.
assert 'TU_FRANE_FREQ", true' in a
assert 'TU_FRANE_SCAN", true' in a
assert 'TU_FRANE_LEARN", true' in a
assert "frane_26360_decide_frequency_scan" in h20
assert "frane_26359_decide_scan" in h20
assert "frane_26358_decide_tail_learner" in h20

# Preserve the validated safety/performance stack.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V61 / Mesa " in d

print("Drnas Turnip V61 SIGNATURE-GATED-SCAN applied", flush=True)
