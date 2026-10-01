#!/usr/bin/env python3
"""Drnas Turnip V65 A810 LIVE-DISAGREE-ESCAPE.

Layered directly on V61 SIGNATURE-GATED-SCAN. V62/V63/V64 are intentionally
not in this branch.

The experiment keeps every V61 learner/scan/probe cadence intact. It only
cancels a high-confidence V58 learned-winner override when the current pass is
an extreme depth/stencil replay phase and Mesa PROFILED strongly prefers the
opposite mode.

Default:
  TU_FRANE_ESCAPE=1

Fallback:
  TU_FRANE_ESCAPE=0 -> exact V61 behavior.

No new per-RP state, atomics, locks, allocations, timers, divisions or loops.
No GMEM layout/offset, attachment, LRZ, barrier, shader, CB, WSI, MSAA/resolve
or Vulkan synchronization changes.
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
            f"V65 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V65 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26365_a810_live_disagree_escape.h",
    V / "frane_mesa_26365_a810_live_disagree_escape.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26361_a810_signature_scan.h"',
    '#include "frane_mesa_26361_a810_signature_scan.h"\n'
    '#include "frane_mesa_26365_a810_live_disagree_escape.h"',
    "include V65 live-disagree escape",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_signature = false;
};""",
    """   bool tail_signature = false;
   bool tail_escape = false;
};""",
    "extend smart input with V65 escape gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_escape_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_ESCAPE", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    "add default-on V65 A810 escape gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_occurrences =
""",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_escape =
            frane_a810_tail_escape_enabled(device);
         runtime_input.tail_occurrences =
""",
    "feed V65 gate without new RP state",
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
      learned = frane_26365_apply_live_escape(
         in.tail_escape,
         tail.zs_load_store,
         tail_guard_eval.replay_work,
         tail.estimated_tiles,
         tail.drawcalls,
         tail_snapshot,
         sysmem_probability,
         learned);

      if (learned.override_mode) {
""",
    "escape only stale learned-winner overrides on extreme live disagreement",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V61 / Mesa ",
    "Drnas Turnip V65 / Mesa ",
    "V65 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h65 = (V / "frane_mesa_26365_a810_live_disagree_escape.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_ESCAPE", true',
    "frane_a810_tail_escape_enabled",
    "runtime_input.tail_escape",
):
    assert needle in a, needle

assert "tail_escape = false" in h18

for needle in (
    "frane_mesa_26365_a810_live_disagree_escape.h",
    "frane_26365_apply_live_escape",
    "tail_guard_eval.replay_work",
    "tail.estimated_tiles",
    "tail.drawcalls",
):
    assert needle in h20, needle

for needle in (
    "replay_work >= 640",
    "drawcalls >= 80",
    "estimated_tiles >= 8",
    "confidence < 7",
    "sysmem_probability <= 25",
    "sysmem_probability >= 75",
    "selected_is_winner",
):
    assert needle in h65, needle

# No V63 structural baseline and no V64 probe-thinning state is introduced.
for forbidden in (
    "frane_tail_draw_sum",
    "frane_tail_draw_samples",
    "tail_rp_draw_sum",
    "tail_rp_draw_samples",
):
    assert forbidden not in a, forbidden

# V61 recurrence learner remains exactly one counter.
assert a.count("frane_tail_occurrences.fetch_add") == 1

# Exact V61 remains reachable with TU_FRANE_ESCAPE=0.
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
assert "Drnas Turnip V65 / Mesa " in d

print("Drnas Turnip V65 LIVE-DISAGREE-ESCAPE applied", flush=True)
