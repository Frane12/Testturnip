#!/usr/bin/env python3
"""Drnas Turnip A810 1.0 RC1 PASS-HISTORY-HYSTERESIS.

Layered strictly on public V57 PROFILED-TAIL-GUARD.

Release-candidate design:
- reuse Mesa's existing exact rp_history as the history table;
- learn only from GPU-duration samples PROFILED already measured;
- no predictive early return and no skip of V57/full selector construction;
- paired GMEM/SYSMEM evidence prevents sampling imbalance from creating trust;
- arm a mode only after hysteretic confidence reaches +/-3;
- keep the hold through small confidence decay, release at zero, and require the
  opposite side to reach its own threshold before switching;
- periodic full PROFILED audit slots and strong contradictory live probability
  can break a stale hold;
- no new hash map, allocation, mutex, clock read, render-pass rescan or active
  loser probing.

Default:
  TU_FRANE_HISTORY=1

Fallback:
  TU_FRANE_HISTORY=0 -> exact V57 selector behavior.

This patch changes selector policy only. GMEM layout/offsets, attachment
programming, LRZ, barriers, shaders, concurrent binning, WSI, MSAA/resolve
safety and Vulkan synchronization are untouched.
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
            f"RC1 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"RC1 PASS {label}", flush=True)


shutil.copyfile(
    "patches/frane_a810_rc1_pass_history.h",
    V / "frane_a810_rc1_pass_history.h",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_2634_a810_gmem_runtime.h"',
    '#include "frane_mesa_2634_a810_gmem_runtime.h"\n'
    '#include "frane_a810_rc1_pass_history.h"',
    "include RC1 pass-history learner",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_history_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_HISTORY", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{""",
    "add default-on A810 history gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };""",
    """   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };

   /* RC1: submit thread owns the full measured state; recording threads read
    * only the compact relaxed snapshot. Mesa's exact rp_history is the table,
    * so there is no second lookup or allocation in the decision path.
    */
   frane_rc1_history_state frane_rc1_history {};
   std::atomic<uint32_t> frane_rc1_history_word { 0 };""",
    "add per-RP measured history state",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
""",
    """            if (entry_config.test(metric_flag::TS_TILE) && at_config.test(mod_flag::PREEMPT_OPTIMIZE))
               preempt_optimize.update_gmem(*this, entry.get_max_tile_duration());
         }

         if (frane_a810_history_enabled(at.device)) {
            frane_rc1_history = frane_rc1_update_history(
               frane_rc1_history, entry.sysmem, rp_duration);
            frane_rc1_history_word.store(
               frane_rc1_pack_history(frane_rc1_history),
               std::memory_order_relaxed);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
""",
    "learn from existing measured RP durations",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_guard = false;
   bool zs_load_store = false;
};""",
    """   bool tail_guard = false;
   bool zs_load_store = false;
   bool pass_history = false;
   uint32_t pass_history_word = 0;
};""",
    "extend SMART input with compact history snapshot",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);
         runtime_input.pass_history =
            frane_a810_history_enabled(device);
         runtime_input.pass_history_word =
            history.frane_rc1_history_word.load(std::memory_order_relaxed);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    "feed exact-RP history snapshot into final selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26357_a810_tail_guard.h"',
    '#include "frane_mesa_26357_a810_tail_guard.h"\n'
    '#include "frane_a810_rc1_pass_history.h"',
    "include RC1 pure history policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """   if (frane_26357_eval_tail_guard(tail).defer_to_profiled)
      return frane_26318_smart_gmem_decision {};
""",
    """   const auto tail_guard_eval = frane_26357_eval_tail_guard(tail);
   if (tail_guard_eval.defer_to_profiled) {
      const auto history_snapshot =
         frane_rc1_unpack_history(in.pass_history_word);
      const auto learned = frane_rc1_decide_history(
         in.pass_history, true, history_snapshot,
         sysmem_probability, decision_word);

      if (learned.override_mode) {
         out.override_mode = true;
         out.select_sysmem = learned.select_sysmem;
         out.force_measure = false;
         out.probe_log2 = 0;
         out.effective_sysmem_probability = sysmem_probability;
         return out;
      }

      /* Cold/weak/contradictory/audit histories retain V57 exactly: defer to
       * Mesa PROFILED. RC1 never bypasses the full selector before this point.
       */
      return frane_26318_smart_gmem_decision {};
   }
""",
    "stabilize only V57 tail-risk passes after full selector work",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V57 / Mesa ",
    "Drnas Turnip A810 1.0 RC1 HISTORY / Mesa ",
    "RC1 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
hrc = (V / "frane_a810_rc1_pass_history.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_HISTORY", true',
    "frane_a810_history_enabled",
    "frane_rc1_history",
    "frane_rc1_history_word",
    "frane_rc1_update_history",
    "history.frane_rc1_history_word.load",
):
    assert needle in a, needle

for needle in (
    "pass_history = false",
    "pass_history_word = 0",
):
    assert needle in h18, needle

for needle in (
    "frane_a810_rc1_pass_history.h",
    "frane_rc1_unpack_history",
    "frane_rc1_decide_history",
    "tail_guard_eval.defer_to_profiled",
    "out.force_measure = false",
):
    assert needle in h20, needle

for needle in (
    "paired < 4",
    "score >= 3",
    "score <= -3",
    "score <= 0",
    "score >= 0",
    "confidence >= 5 ? 31u : 15u",
    "sysmem_probability > 75",
    "sysmem_probability < 25",
):
    assert needle in hrc, needle

# Deliberately based on V57: no V60Y predictive early-return path.
assert "TU_FRANE_PREDICT" not in a
assert "frane_predict_word" not in a
assert "frane_predict_ticket" not in a

# History is only a final stabilizer inside the existing V57 structural gate.
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a
assert a.index("frane_26318_smart_gmem_input runtime_input {}") < a.index(
    "history.frane_rc1_history_word.load")

# Preserve validated V57 safety/performance stack.
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "sysmem_probability > 55" in h20
assert "probe_log2 = 9" in h20
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip A810 1.0 RC1 HISTORY / Mesa " in d

print("Drnas Turnip A810 1.0 RC1 PASS-HISTORY-HYSTERESIS applied and audited", flush=True)
