#!/usr/bin/env python3
"""Drnas Turnip V58 A810 TAIL-LEARNER.

Layered strictly on V57 PROFILED-TAIL-GUARD.

V57 identifies structurally expensive tail-risk render passes and lets Mesa
PROFILED decide them. V58 keeps that behavior during learning, then allows a
small per-render-pass learner to stabilize only those same V57-risk passes once
both GMEM and SYSMEM have enough measured duration samples.

The learner keeps:
- a slow EMA for normal cost;
- a fast-rise / slow-decay high-latency envelope;
- a tail-aware cost = mean + 0.5 * tail penalty;
- paired-sample scoring so a more frequently sampled mode cannot win by volume;
- hysteresis (-8..8) and sparse measured loser probes.

Default:
  TU_FRANE_LEARN=1

Fallback:
  TU_FRANE_LEARN=0
  -> exact V57 selector behavior.

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
            f"V58 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:220]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V58 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26358_a810_tail_learner.h",
    V / "frane_mesa_26358_a810_tail_learner.h",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_2634_a810_gmem_runtime.h"',
    '#include "frane_mesa_2634_a810_gmem_runtime.h"\n'
    '#include "frane_mesa_26358_a810_tail_learner.h"',
    "include V58 tail learner",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_learner_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_LEARN", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{""",
    "add default-on A810 learner gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   frane_2634_gmem_state frane_gmem_runtime_state {};
   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };""",
    """   frane_2634_gmem_state frane_gmem_runtime_state {};
   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };

   /* V58 state is submit-thread owned. Recording threads only read the packed
    * atomic snapshot, matching the existing A810 GMEM runtime ownership model.
    */
   frane_26358_tail_state frane_tail_state {};
   std::atomic<uint32_t> frane_tail_word { 0 };""",
    "add per-RP submit-owned tail learner state",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      if (entry_config.test(metric_flag::TS)) {
         if (entry.sysmem) {
            uint64_t rp_duration = entry.get_rp_duration();

            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(entry.get_rp_duration());

            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
""",
    """      if (entry_config.test(metric_flag::TS)) {
         const uint64_t rp_duration = entry.get_rp_duration();

         if (entry.sysmem) {
            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(rp_duration);

            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (frane_a810_tail_learner_enabled(at.device)) {
            frane_tail_state = frane_26358_update_tail_state(
               frane_tail_state, entry.sysmem, rp_duration);
            frane_tail_word.store(
               frane_26358_pack_tail_snapshot(frane_tail_state),
               std::memory_order_relaxed);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
""",
    "learn tail cost from existing measured RP durations",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_guard = false;
   bool zs_load_store = false;
};""",
    """   bool tail_guard = false;
   bool zs_load_store = false;
   bool tail_learner = false;
   uint32_t tail_learner_word = 0;
};""",
    "extend smart input with V58 learner snapshot",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);
         runtime_input.tail_learner =
            frane_a810_tail_learner_enabled(device);
         runtime_input.tail_learner_word =
            history.frane_tail_word.load(std::memory_order_relaxed);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    "feed per-RP learner snapshot into selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26357_a810_tail_guard.h"',
    '#include "frane_mesa_26357_a810_tail_guard.h"\n'
    '#include "frane_mesa_26358_a810_tail_learner.h"',
    "include V58 pure learner policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """   if (frane_26357_eval_tail_guard(tail).defer_to_profiled)
      return frane_26318_smart_gmem_decision {};
""",
    """   const auto tail_guard_eval = frane_26357_eval_tail_guard(tail);
   if (tail_guard_eval.defer_to_profiled) {
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

      /* Not enough evidence yet, or evidence conflicts with a strong live
       * profiler: retain V57 exactly and let Mesa PROFILED decide.
       */
      return frane_26318_smart_gmem_decision {};
   }
""",
    "replace V57 blind defer with measured tail-aware stabilization",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V57 / Mesa ",
    "Drnas Turnip V58 / Mesa ",
    "V58 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h58 = (V / "frane_mesa_26358_a810_tail_learner.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_LEARN", true',
    "frane_a810_tail_learner_enabled",
    "frane_tail_state",
    "frane_tail_word",
    "frane_26358_update_tail_state",
    "history.frane_tail_word.load",
):
    assert needle in a, needle

for needle in (
    "tail_learner = false",
    "tail_learner_word = 0",
):
    assert needle in h18, needle

for needle in (
    "frane_mesa_26358_a810_tail_learner.h",
    "frane_26358_unpack_tail_snapshot",
    "frane_26358_decide_tail_learner",
    "tail_guard_eval.defer_to_profiled",
):
    assert needle in h20, needle

for needle in (
    "paired_samples",
    "mean + add",
    "score = int8_t",
    "confidence < 4",
    "probe_log2 = 7",
):
    assert needle in h58, needle

# V57 remains the structural gate; V58 changes only what happens after it fires.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a

# Preserve all validated safety/performance layers.
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "sysmem_probability > 55" in h20
assert "probe_log2 = 9" in h20
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V58 / Mesa " in d

print("Drnas Turnip V58 TAIL-LEARNER applied", flush=True)
