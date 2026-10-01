#!/usr/bin/env python3
"""Drnas Turnip V62 A810 REGIME-HOLD.

Layered strictly on V61 SIGNATURE-GATED-SCAN.

V61 fixed cold/rare scan cost. V62 targets the remaining deterministic heavy
hotspot by recognizing that one Mesa rp_history may span multiple structural
render regimes over time.

V62 does not alter learning or scan acquisition. It only stabilizes a learned
V58 decision when the current invocation is structurally heavy:

- cost class 0: exact V61 behavior;
- cost class 1: confidence >=5 and bounded live-PROFILED disagreement;
- cost class 2: confidence >=6 and live agreement unless confidence saturates;
- accepted heavy winners use 1/256 or 1/512 loser probes;
- winner timing refresh remains 1/64.

Default:
  TU_FRANE_REGIME=1

Fallback:
  TU_FRANE_REGIME=0 -> exact V61 behavior.

No GMEM layout, attachment offsets, LRZ, barriers, shaders, CB, WSI, MSAA/
resolve safety or Vulkan synchronization changes.
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
            f"V62 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:240]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V62 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26362_a810_regime_hold.h",
    V / "frane_mesa_26362_a810_regime_hold.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26361_a810_signature_scan.h"',
    '#include "frane_mesa_26361_a810_signature_scan.h"\n'
    '#include "frane_mesa_26362_a810_regime_hold.h"',
    "include V62 regime hold",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_signature = false;
};""",
    """   bool tail_signature = false;
   bool tail_regime = false;
};""",
    "extend smart input with V62 regime gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_regime_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_REGIME", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    "add default-on V62 A810 regime gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_occurrences =
""",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_regime =
            frane_a810_tail_regime_enabled(device);
         runtime_input.tail_occurrences =
""",
    "feed V62 regime gate into selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """      const auto learned = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);

      if (learned.override_mode) {
         out.override_mode = true;
         out.select_sysmem = learned.select_sysmem;
         out.force_measure = learned.force_measure;
         out.probe_log2 = learned.probe_log2;
""",
    """      const auto learned_raw = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);
      const auto learned = frane_26362_stabilize_tail_decision(
         in.tail_regime,
         tail_snapshot,
         learned_raw,
         tail_guard_eval.replay_work,
         tail.pass_pixels,
         tail.estimated_tiles,
         tail.drawcalls,
         tail.zs_load_store,
         sysmem_probability,
         decision_word);

      if (learned.override_mode) {
         out.override_mode = true;
         out.select_sysmem = learned.select_sysmem;
         out.force_measure = learned.force_measure;
         out.probe_log2 = learned.probe_log2;
""",
    "stabilize V58 learned hold by current render regime",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V61 / Mesa ",
    "Drnas Turnip V62 / Mesa ",
    "V62 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h62 = (V / "frane_mesa_26362_a810_regime_hold.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_REGIME", true',
    "frane_a810_tail_regime_enabled",
    "runtime_input.tail_regime",
):
    assert needle in a, needle

assert "tail_regime = false" in h18

for needle in (
    "frane_mesa_26362_a810_regime_hold.h",
    "frane_26362_stabilize_tail_decision",
    "const auto learned_raw",
    "tail_guard_eval.replay_work",
):
    assert needle in h20, needle

for needle in (
    "sig.cost_class == 0",
    "required_confidence",
    "probe_log2 = sig.cost_class == 1 ? 8u : 9u",
    "confidence >= 8",
    "Winner refresh",
):
    assert needle in h62, needle

# Preserve exact V61 and all lower fallbacks in-binary.
assert 'TU_FRANE_SIG", true' in a
assert 'TU_FRANE_FREQ", true' in a
assert 'TU_FRANE_SCAN", true' in a
assert 'TU_FRANE_LEARN", true' in a
assert "frane_26361_decide_signature_scan" in h20
assert "frane_26360_decide_frequency_scan" in h20
assert "frane_26359_decide_scan" in h20
assert "frane_26358_decide_tail_learner" in h20

# Preserve safety/performance fences.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V62 / Mesa " in d

print("Drnas Turnip V62 REGIME-HOLD applied", flush=True)
