#!/usr/bin/env python3
"""Drnas Turnip V63 A810 PER-RP SPIKE FREEZE.

Layered directly on V61 SIGNATURE-GATED-SCAN, intentionally skipping the
regressive V62 absolute heavy/very-heavy policy.

V63 learns a tiny structural baseline independently for each Mesa rp_history.
It never changes the learned winner. It only freezes exploration when the
current invocation is a large draw/replay spike relative to that same RP:

- baseline accumulates for the first ~128 RP occurrences;
- detection becomes active after 64 prior samples;
- spike requires >=1.5x baseline draws, >=+16 draws and replay_work >=192;
- V61 forced rescue scan is skipped during a spike;
- a V58 loser-control probe is converted back to the learned winner;
- normal winner path and winner timing refresh remain unchanged.

Default:
  TU_FRANE_RP=1

Fallback:
  TU_FRANE_RP=0 -> exact V61 behavior.

No GMEM layout/offset, attachments, LRZ, barriers, shaders, CB, WSI, MSAA/
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
            f"V63 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V63 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26363_a810_rp_spike_freeze.h",
    V / "frane_mesa_26363_a810_rp_spike_freeze.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26361_a810_signature_scan.h"',
    '#include "frane_mesa_26361_a810_signature_scan.h"\n'
    '#include "frane_mesa_26363_a810_rp_spike_freeze.h"',
    "include V63 per-RP spike policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_signature = false;
};""",
    """   bool tail_signature = false;
   bool tail_rp = false;
   uint64_t tail_rp_draw_sum = 0;
   uint32_t tail_rp_draw_samples = 0;
};""",
    "extend smart input with per-RP baseline snapshot",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_rp_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_RP", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    "add default-on V63 A810 per-RP gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   std::atomic<uint32_t> frane_tail_occurrences { 0 };""",
    """   std::atomic<uint32_t> frane_tail_occurrences { 0 };

   /* V63 structural baseline is recording-thread updated and lock-free.
    * Only the first ~128 observations are accumulated; small overshoot from
    * concurrent recorders is harmless and keeps this off any mutex path.
    */
   std::atomic<uint64_t> frane_tail_draw_sum { 0 };
   std::atomic<uint32_t> frane_tail_draw_samples { 0 };""",
    "add bounded per-RP structural baseline state",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_occurrences =
            history.frane_tail_occurrences.fetch_add(
               1, std::memory_order_relaxed) + 1;
""",
    """         runtime_input.tail_signature =
            frane_a810_tail_signature_enabled(device);
         runtime_input.tail_rp =
            frane_a810_tail_rp_enabled(device);
         runtime_input.tail_rp_draw_samples =
            history.frane_tail_draw_samples.load(std::memory_order_relaxed);
         runtime_input.tail_rp_draw_sum =
            history.frane_tail_draw_sum.load(std::memory_order_relaxed);

         /* Snapshot first so the current draw count cannot dilute its own
          * spike test. Training stops after roughly 128 observations.
          */
         if (runtime_input.tail_rp &&
             runtime_input.tail_rp_draw_samples < 128) {
            history.frane_tail_draw_sum.fetch_add(
               runtime_input.layout.drawcalls, std::memory_order_relaxed);
            history.frane_tail_draw_samples.fetch_add(
               1, std::memory_order_relaxed);
         }

         runtime_input.tail_occurrences =
            history.frane_tail_occurrences.fetch_add(
               1, std::memory_order_relaxed) + 1;
""",
    "publish and train per-RP draw baseline",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """      const auto scan_snapshot =
         frane_26359_unpack_scan(in.tail_scan_word);
      const auto scan = (in.tail_signature && in.tail_frequency)
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
""",
    """      const auto rp_phase = frane_26363_eval_rp_phase(
         in.tail_rp,
         in.tail_rp_draw_sum,
         in.tail_rp_draw_samples,
         tail.drawcalls,
         tail_guard_eval.replay_work);

      const auto scan_snapshot =
         frane_26359_unpack_scan(in.tail_scan_word);
      frane_26359_scan_decision scan {};
      if (!rp_phase.spike) {
         scan = (in.tail_signature && in.tail_frequency)
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
      }

      if (scan.override_mode) {
""",
    "freeze V61 forced scan during per-RP structural spikes",
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
      learned = frane_26363_freeze_loser_probe(
         rp_phase.spike, tail_snapshot, learned);

      if (learned.override_mode) {
""",
    "freeze only loser-control probes during per-RP spikes",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V61 / Mesa ",
    "Drnas Turnip V63 / Mesa ",
    "V63 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h63 = (V / "frane_mesa_26363_a810_rp_spike_freeze.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_RP", true',
    "frane_a810_tail_rp_enabled",
    "frane_tail_draw_sum",
    "frane_tail_draw_samples",
    "runtime_input.tail_rp_draw_sum",
    "runtime_input.tail_rp_draw_samples",
):
    assert needle in a, needle

for needle in (
    "tail_rp = false",
    "tail_rp_draw_sum = 0",
    "tail_rp_draw_samples = 0",
):
    assert needle in h18, needle

for needle in (
    "frane_mesa_26363_a810_rp_spike_freeze.h",
    "frane_26363_eval_rp_phase",
    "if (!rp_phase.spike)",
    "frane_26363_freeze_loser_probe",
):
    assert needle in h20, needle

for needle in (
    "draw_samples < 64",
    "baseline + 16u",
    "current_replay_work >= 192",
    "selected_is_loser",
    "learned.force_measure = false",
):
    assert needle in h63, needle

# Exact V61 behavior is reachable by disabling only the new gate.
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
assert "Drnas Turnip V63 / Mesa " in d

print("Drnas Turnip V63 PER-RP SPIKE FREEZE applied", flush=True)
