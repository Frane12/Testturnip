#!/usr/bin/env python3
"""Drnas Turnip V59 A810 SCAN-LEARNER.

Layered strictly on V58 TAIL-LEARNER.

V58 can learn a stable tail-aware preference once it has enough measured
GMEM/SYSMEM pairs. V59 adds a bounded early scan only on the same V57-classified
tail-risk passes so hot render passes reach that evidence threshold quickly
inside a normal benchmark.

Default:
  TU_FRANE_SCAN=1

Fallback:
  TU_FRANE_SCAN=0
  -> exact V58 selector behavior.

The scan target is 10 measured samples per mode. If the under-sampled mode
contradicts an extreme live PROFILED opinion (<=5% or >=95% SYSMEM), exploration
is throttled to 1/4 cadence rather than hammered every occurrence.

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
            f"V59 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:220]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V59 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26359_a810_scan_learner.h",
    V / "frane_mesa_26359_a810_scan_learner.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26358_a810_tail_learner.h"',
    '#include "frane_mesa_26358_a810_tail_learner.h"\n'
    '#include "frane_mesa_26359_a810_scan_learner.h"',
    "include V59 scan policy",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_learner = false;
   uint32_t tail_learner_word = 0;
};""",
    """   bool tail_learner = false;
   uint32_t tail_learner_word = 0;
   bool tail_scan = false;
   uint32_t tail_scan_word = 0;
};""",
    "extend smart input with scan snapshot",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_learner_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_tail_scan_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_SCAN", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_learner_enabled(const struct tu_device *device)
{""",
    "add default-on bounded scan gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   frane_26358_tail_state frane_tail_state {};
   std::atomic<uint32_t> frane_tail_word { 0 };""",
    """   frane_26358_tail_state frane_tail_state {};
   std::atomic<uint32_t> frane_tail_word { 0 };
   std::atomic<uint32_t> frane_tail_scan_word { 0 };""",
    "add compact per-RP scan sample snapshot",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            frane_tail_word.store(
               frane_26358_pack_tail_snapshot(frane_tail_state),
               std::memory_order_relaxed);
         }
""",
    """            frane_tail_word.store(
               frane_26358_pack_tail_snapshot(frane_tail_state),
               std::memory_order_relaxed);
            frane_tail_scan_word.store(
               frane_26359_pack_scan(
                  frane_tail_state.sysmem.samples,
                  frane_tail_state.gmem.samples),
               std::memory_order_relaxed);
         }
""",
    "publish measured mode counts for bounded scan",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_learner_word =
            history.frane_tail_word.load(std::memory_order_relaxed);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    """         runtime_input.tail_learner_word =
            history.frane_tail_word.load(std::memory_order_relaxed);
         runtime_input.tail_scan =
            frane_a810_tail_scan_enabled(device);
         runtime_input.tail_scan_word =
            history.frane_tail_scan_word.load(std::memory_order_relaxed);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {""",
    "feed scan state into tail-risk selector",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """   const auto tail_guard_eval = frane_26357_eval_tail_guard(tail);
   if (tail_guard_eval.defer_to_profiled) {
      const auto tail_snapshot =
         frane_26358_unpack_tail_snapshot(in.tail_learner_word);
      const auto learned = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);

      if (learned.override_mode) {
""",
    """   const auto tail_guard_eval = frane_26357_eval_tail_guard(tail);
   if (tail_guard_eval.defer_to_profiled) {
      /* V59 fills only the bounded evidence budget needed by V58. Once both
       * modes reach the target, this becomes a permanent no-op and V58 owns
       * the decision exactly as before.
       */
      const auto scan_snapshot =
         frane_26359_unpack_scan(in.tail_scan_word);
      const auto scan = frane_26359_decide_scan(
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
""",
    "scan before V58 stabilization on V57 tail-risk passes",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V58 / Mesa ",
    "Drnas Turnip V59 / Mesa ",
    "V59 display identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h59 = (V / "frane_mesa_26359_a810_scan_learner.h").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_SCAN", true',
    "frane_a810_tail_scan_enabled",
    "frane_tail_scan_word",
    "frane_26359_pack_scan",
    "history.frane_tail_scan_word.load",
):
    assert needle in a, needle

for needle in (
    "tail_scan = false",
    "tail_scan_word = 0",
):
    assert needle in h18, needle

for needle in (
    "frane_mesa_26359_a810_scan_learner.h",
    "frane_26359_unpack_scan",
    "frane_26359_decide_scan",
    "scan.override_mode",
    "frane_26358_decide_tail_learner",
):
    assert needle in h20, needle

for needle in (
    "TARGET = 10",
    "sysmem_probability <= 5",
    "sysmem_probability >= 95",
    "force_measure = true",
):
    assert needle in h59, needle

# Exact V58 fallback remains available by disabling only V59 scan.
assert 'TU_FRANE_LEARN", true' in a
assert "frane_26358_update_tail_state" in a
assert "frane_26357_eval_tail_guard" in h20
assert 'TU_FRANE_TAIL", true' in a

# Preserve validated stack.
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert "probe_log2 = 9" in h20
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas Turnip V59 / Mesa " in d

print("Drnas Turnip V59 SCAN-LEARNER applied", flush=True)
