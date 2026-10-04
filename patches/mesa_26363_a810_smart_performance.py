#!/usr/bin/env python3
"""A810 S1 Smart Performance.

Layered on S1H.  Turns the existing per-render-pass histogram into a default-on
history-first memoized selector.

User-facing master switch:
  TU_FRANE_SMART=1  (default)
  TU_FRANE_SMART=0  (disable Smart Performance and fall back to S1 policy)

The recent histogram remains internal and is populated whenever Smart
Performance is enabled.  Normal operation does not require histogram logging.
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
            f"SMART source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"SMART PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26363_a810_smart_performance.h",
    V / "frane_mesa_26363_a810_smart_performance.h",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26362_a810_histogram.h"',
    '#include "frane_mesa_26362_a810_histogram.h"\n'
    '#include "frane_mesa_26363_a810_smart_performance.h"',
    "include Smart Performance policy",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '''static bool
frane_a810_histogram_smooth_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_HIST_SMOOTH", false);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}''',
    '''static bool
frane_a810_histogram_smooth_enabled(const struct tu_device *device)
{
   /* Single user-facing master switch for the internal Smart Performance
    * experiment. Statistics and memoization are both default-on.
    */
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_SMART", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}''',
    "replace S1H smoothing knob with TU_FRANE_SMART master",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '''   const auto tail_guard_eval = frane_26357_eval_tail_guard(tail);
   if (tail_guard_eval.defer_to_profiled) {
      /* V59 fills only the bounded evidence budget needed by V58. Once both
       * modes reach the target, this becomes a permanent no-op and V58 owns
       * the decision exactly as before.
       */''',
    '''   const auto tail_guard_eval = frane_26357_eval_tail_guard(tail);

   /* Smart Performance fast path.  The Mesa rp_history object is our scene
    * table row. Once its measured histogram is trustworthy, consult it before
    * spending more work on scan/learn. A contradiction simply falls through
    * to the unchanged S1 path below.
    */
   const auto smart_tail_snapshot =
      frane_26358_unpack_tail_snapshot(in.tail_learner_word);
   const auto smart_hist_snapshot =
      frane_26362_unpack_histogram(in.hist_word);
   const auto smart = frane_26363_decide_smart_performance(
      in.hist_smooth,
      tail_guard_eval.defer_to_profiled,
      smart_hist_snapshot,
      smart_tail_snapshot,
      sysmem_probability,
      decision_word);

   if (smart.override_mode) {
      out.override_mode = true;
      out.select_sysmem = smart.select_sysmem;
      out.force_measure = smart.force_measure;
      out.probe_log2 = smart.probe_log2;
      out.effective_sysmem_probability = sysmem_probability;
      return out;
   }

   if (tail_guard_eval.defer_to_profiled) {
      /* V59/V60/V61 are now the cold/relearn path only. Once Smart
       * Performance has a stable history, normal recurrences return above.
       */''',
    "consult history before scan/learn",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '''      const auto tail_snapshot =
         frane_26358_unpack_tail_snapshot(in.tail_learner_word);

      const auto hist_snapshot =
         frane_26362_unpack_histogram(in.hist_word);
      const auto smooth = frane_26362_decide_smoothing(
         in.hist_smooth, hist_snapshot, tail_snapshot,
         sysmem_probability, decision_word);

      if (smooth.override_mode) {
         out.override_mode = true;
         out.select_sysmem = smooth.select_sysmem;
         out.force_measure = smooth.force_measure;
         out.probe_log2 = smooth.probe_log2;
         out.effective_sysmem_probability = sysmem_probability;
         return out;
      }

      const auto learned = frane_26358_decide_tail_learner(''',
    '''      const auto tail_snapshot =
         frane_26358_unpack_tail_snapshot(in.tail_learner_word);

      /* S1H's older smoothing path is intentionally replaced by the
       * history-first Smart Performance table above. This block is reached
       * only when the memoized history declined to own the decision.
       */
      const auto learned = frane_26358_decide_tail_learner(''',
    "remove duplicate S1H smoothing decision",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas-Turnip S1H A810 / Mesa ",
    "A810 S1 Smart Performance / Mesa ",
    "Smart Performance display identity",
)

a = (V / "tu_autotune.cc").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h63 = (V / "frane_mesa_26363_a810_smart_performance.h").read_text()
d = (V / "tu_device.cc").read_text()

assert 'TU_FRANE_SMART", true' in a
assert 'TU_FRANE_HIST_SMOOTH", false' not in a
assert "frane_a810_histogram_active(at.device)" in a
assert "history.frane_hist_word.load" in a

for needle in (
    "frane_mesa_26363_a810_smart_performance.h",
    "frane_26363_decide_smart_performance",
    "smart_hist_snapshot",
    "smart_tail_snapshot",
    "frane_26361_decide_signature_scan",
    "frane_26358_decide_tail_learner",
):
    assert needle in h20, needle

assert h20.count("frane_26362_decide_smoothing") == 0

for needle in (
    "FRANE_26363_POLICY",
    "{ 4, 8, 6, 5, 70, 30 }",
    "{ 6, 12, 7, 6, 78, 22 }",
    "{ 8, 16, 8, 7, 85, 15 }",
    "hist.switches >= 4",
    "structural_tail_risk && hist.confidence < 6",
    "out.force_measure = loser_probe || winner_refresh",
):
    assert needle in h63, needle

for forbidden in (
    "malloc(", "calloc(", "realloc(", "pthread_",
    "std::mutex", "sleep(", "usleep(", "while (", "while("
):
    assert forbidden not in h63, forbidden

assert "A810 S1 Smart Performance / Mesa " in d
print("A810 S1 Smart Performance applied", flush=True)
