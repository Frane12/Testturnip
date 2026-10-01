#!/usr/bin/env python3
"""Drnas Turnip V64 A810 STABLE-SENTINEL.

Layered directly on V61 SIGNATURE-GATED-SCAN. V62/V63 are intentionally not
part of this branch.

V64 keeps V61's winner logic intact and only sparsifies already-confident V58
loser-control probes after 256 occurrences. It uses existing V61 state only:
no new per-RP atomics, counters, locks or structural baselines.

Default:
  TU_FRANE_SENT=1

Fallback:
  TU_FRANE_SENT=0 -> exact V61 behavior.

No GMEM layout/offset, attachments, LRZ, barriers, shaders, CB, WSI,
MSAA/resolve safety or Vulkan synchronization changes.
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
            f"V64 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V64 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26364_a810_stable_sentinel.h",
    V / "frane_mesa_26364_a810_stable_sentinel.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26361_a810_signature_scan.h"',
    '#include "frane_mesa_26361_a810_signature_scan.h"\n'
    '#include "frane_mesa_26364_a810_stable_sentinel.h"',
    "include V64 stable sentinel policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_signature = false;
};""",
    """   bool tail_signature = false;
   bool tail_sentinel = false;
};""",
    "extend smart input with V64 sentinel gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_sentinel_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_SENT", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    "add default-on V64 A810 sentinel gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_occurrences =
""",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_sentinel =
            frane_a810_tail_sentinel_enabled(device);
         runtime_input.tail_occurrences =
""",
    "feed V64 gate without new per-RP state",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """      const auto learned = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);

      if (learned.override_mode) {
""",
    """      auto learned = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);
      learned = frane_26364_apply_stable_sentinel(
         in.tail_sentinel, in.tail_occurrences,
         tail_snapshot, decision_word, learned);

      if (learned.override_mode) {
""",
    "sparsify only V58 loser-control probes",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V61 / Mesa ",
    "Drnas Turnip V64 / Mesa ",
    "V64 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h64 = (V / "frane_mesa_26364_a810_stable_sentinel.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_SENT", true',
    "frane_a810_tail_sentinel_enabled",
    "runtime_input.tail_sentinel",
):
    assert needle in a, needle

assert "tail_sentinel = false" in h18

for needle in (
    "frane_mesa_26364_a810_stable_sentinel.h",
    "frane_26364_apply_stable_sentinel",
    "in.tail_occurrences",
    "tail_snapshot, decision_word, learned",
):
    assert needle in h20, needle

for needle in (
    "occurrences < 256",
    "sentinel_log2 = 8",
    "sentinel_log2 = 9",
    "sentinel_log2 = 10",
    "selected_is_loser",
    "learned.force_measure = false",
):
    assert needle in h64, needle

# The V64 experiment must not recreate V63's hot-path state cost.
for forbidden in (
    "frane_tail_draw_sum",
    "frane_tail_draw_samples",
    "tail_rp_draw_sum",
    "tail_rp_draw_samples",
):
    assert forbidden not in a, forbidden

# Exactly the pre-existing V61 recurrence counter remains.
assert a.count("frane_tail_occurrences.fetch_add") == 1

# Exact V61 behavior remains reachable by disabling only the new gate.
assert 'TU_FRANE_SIG", true' in a
assert 'TU_FRANE_FREQ", true' in a
assert 'TU_FRANE_SCAN", true' in a
assert 'TU_FRANE_LEARN", true' in a
assert "frane_26361_decide_signature_scan" in h20
assert "frane_26360_decide_frequency_scan" in h20
assert "frane_26359_decide_scan" in h20
assert "frane_26358_decide_tail_learner" in h20

# Preserve validated safety/performance layers.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V64 / Mesa " in d

print("Drnas Turnip V64 STABLE-SENTINEL applied", flush=True)
