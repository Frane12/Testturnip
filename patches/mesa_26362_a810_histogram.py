#!/usr/bin/env python3
"""Drnas-Turnip S1H A810 user histogram + optional frametime stabilizer.

Layered strictly on the frozen S1/V61 selector.

TU_FRANE_HIST=1
  Enables low-rate user-readable per-render-pass histogram logging.
  Logging occurs on preference changes and every 16 completed measurement pairs.

TU_FRANE_HIST_SMOOTH=1
  Enables the optional histogram dead-band stabilizer. The histogram is
  recent-weighted and may hold a repeatedly proven GMEM/SYSMEM winner through
  low-confidence selector noise. Strong contradictory V58 learner or live
  PROFILED evidence vetoes the hold. Sparse measured loser probes remain.

Both options default OFF, so this experimental branch is selector-identical to
S1 unless explicitly enabled.
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
            f"S1H source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"S1H PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26362_a810_histogram.h",
    V / "frane_mesa_26362_a810_histogram.h",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_26358_a810_tail_learner.h"',
    '#include "frane_mesa_26358_a810_tail_learner.h"\n'
    '#include "frane_mesa_26362_a810_histogram.h"',
    "include S1H histogram helper",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_histogram_log_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_HIST", false);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_histogram_smooth_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_HIST_SMOOTH", false);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_histogram_active(const struct tu_device *device)
{
   return frane_a810_histogram_log_enabled(device) ||
          frane_a810_histogram_smooth_enabled(device);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    "add S1H user/log and smoothing gates",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   frane_26358_tail_state frane_tail_state {};
   std::atomic<uint32_t> frane_tail_word { 0 };
   std::atomic<uint32_t> frane_tail_scan_word { 0 };
   std::atomic<uint32_t> frane_tail_occurrences { 0 };""",
    """   frane_26358_tail_state frane_tail_state {};
   std::atomic<uint32_t> frane_tail_word { 0 };
   std::atomic<uint32_t> frane_tail_scan_word { 0 };
   std::atomic<uint32_t> frane_tail_occurrences { 0 };

   /* S1H histogram state is submit-thread owned. Recording threads see only
    * the compact relaxed-atomic snapshot used by the optional stabilizer.
    */
   frane_26362_hist_state frane_hist_state {};
   std::atomic<uint32_t> frane_hist_word { 0 };""",
    "add compact per-RP histogram state",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         if (frane_a810_tail_learner_enabled(at.device)) {
            frane_tail_state = frane_26358_update_tail_state(
               frane_tail_state, entry.sysmem, rp_duration);
            frane_tail_word.store(
               frane_26358_pack_tail_snapshot(frane_tail_state),
               std::memory_order_relaxed);
            frane_tail_scan_word.store(
               frane_26359_pack_scan(
                  frane_tail_state.sysmem.samples,
                  frane_tail_state.gmem.samples),
               std::memory_order_relaxed);
         }
""",
    """         if (frane_a810_tail_learner_enabled(at.device)) {
            const uint16_t old_pairs = frane_tail_state.paired_samples;
            frane_tail_state = frane_26358_update_tail_state(
               frane_tail_state, entry.sysmem, rp_duration);
            frane_tail_word.store(
               frane_26358_pack_tail_snapshot(frane_tail_state),
               std::memory_order_relaxed);
            frane_tail_scan_word.store(
               frane_26359_pack_scan(
                  frane_tail_state.sysmem.samples,
                  frane_tail_state.gmem.samples),
               std::memory_order_relaxed);

            if (frane_a810_histogram_active(at.device) &&
                frane_tail_state.paired_samples > old_pairs) {
               const int8_t old_pref = frane_hist_state.preference;
               const uint64_t sys_cost =
                  frane_26358_tail_cost(frane_tail_state.sysmem);
               const uint64_t gm_cost =
                  frane_26358_tail_cost(frane_tail_state.gmem);

               frane_hist_state = frane_26362_update_histogram(
                  frane_hist_state, sys_cost, gm_cost);
               frane_hist_word.store(
                  frane_26362_pack_histogram(frane_hist_state),
                  std::memory_order_relaxed);

               const bool changed = old_pref != frane_hist_state.preference;
               if (frane_a810_histogram_log_enabled(at.device) &&
                   (changed || (frane_hist_state.observations & 15u) == 0u)) {
                  const char pref =
                     frane_hist_state.preference == FRANE_HIST_PREF_GMEM ? 'G' :
                     frane_hist_state.preference == FRANE_HIST_PREF_SYSMEM ? 'S' : '-';
                  mesa_logi(
                     "DRNAS_HIST rp=%016" PRIx64
                     " occ=%u obs=%u bins[G25=%u G12=%u G6=%u T=%u S6=%u S12=%u S25=%u]"
                     " G{n=%u mean=%" PRIu64 "us tail=%" PRIu64 "us}"
                     " S{n=%u mean=%" PRIu64 "us tail=%" PRIu64 "us}"
                     " score=%d pref=%c conf=%u switches=%u",
                     hash,
                     frane_tail_occurrences.load(std::memory_order_relaxed),
                     frane_hist_state.observations,
                     frane_hist_state.bins[FRANE_HIST_GMEM_25],
                     frane_hist_state.bins[FRANE_HIST_GMEM_12],
                     frane_hist_state.bins[FRANE_HIST_GMEM_6],
                     frane_hist_state.bins[FRANE_HIST_TIE],
                     frane_hist_state.bins[FRANE_HIST_SYSMEM_6],
                     frane_hist_state.bins[FRANE_HIST_SYSMEM_12],
                     frane_hist_state.bins[FRANE_HIST_SYSMEM_25],
                     frane_tail_state.gmem.samples,
                     ticks_to_us(frane_tail_state.gmem.mean),
                     ticks_to_us(frane_tail_state.gmem.tail),
                     frane_tail_state.sysmem.samples,
                     ticks_to_us(frane_tail_state.sysmem.mean),
                     ticks_to_us(frane_tail_state.sysmem.tail),
                     int(frane_tail_state.score),
                     pref,
                     frane_hist_state.confidence,
                     frane_hist_state.switches);
               }
            }
         }
""",
    "update and expose user histogram only on new measured pairs",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   bool tail_frequency = false;
   uint32_t tail_occurrences = 0;
   bool tail_signature = false;
};""",
    """   bool tail_frequency = false;
   uint32_t tail_occurrences = 0;
   bool tail_signature = false;
   bool hist_smooth = false;
   uint32_t hist_word = 0;
};""",
    "extend selector input with S1H histogram snapshot",
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
         runtime_input.tail_occurrences =
            history.frane_tail_occurrences.fetch_add(
               1, std::memory_order_relaxed) + 1;
         runtime_input.hist_smooth =
            frane_a810_histogram_smooth_enabled(device);
         if (runtime_input.hist_smooth) {
            runtime_input.hist_word =
               history.frane_hist_word.load(std::memory_order_relaxed);
         }
""",
    "feed histogram snapshot only when smoothing is enabled",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    '#include "frane_mesa_26361_a810_signature_scan.h"',
    '#include "frane_mesa_26361_a810_signature_scan.h"\n'
    '#include "frane_mesa_26362_a810_histogram.h"',
    "include S1H histogram stabilizer",
)

edit(
    "src/freedreno/vulkan/frane_mesa_26320_a810_gmem_turbo.h",
    """      const auto tail_snapshot =
         frane_26358_unpack_tail_snapshot(in.tail_learner_word);
      const auto learned = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);
""",
    """      const auto tail_snapshot =
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

      const auto learned = frane_26358_decide_tail_learner(
         in.tail_learner, true, tail_snapshot,
         sysmem_probability, decision_word);
""",
    "insert optional histogram dead-band before V58 stabilization",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas-Turnip S1 A810 / Mesa ",
    "Drnas-Turnip S1H A810 / Mesa ",
    "S1H experimental identity",
)

a = (V / "tu_autotune.cc").read_text()
h18 = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
h20 = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
h62 = (V / "frane_mesa_26362_a810_histogram.h").read_text()
d = (V / "tu_device.cc").read_text()

for needle in (
    'TU_FRANE_HIST", false',
    'TU_FRANE_HIST_SMOOTH", false',
    "DRNAS_HIST rp=%016",
    "frane_hist_state",
    "frane_hist_word",
    "frane_26362_update_histogram",
):
    assert needle in a, needle

for needle in ("hist_smooth = false", "hist_word = 0"):
    assert needle in h18, needle

for needle in (
    "frane_mesa_26362_a810_histogram.h",
    "frane_26362_decide_smoothing",
    "frane_26358_decide_tail_learner",
    "frane_26361_decide_signature_scan",
):
    assert needle in h20, needle

for forbidden in (
    "malloc(", "calloc(", "realloc(", "pthread_",
    "std::mutex", "sleep(", "usleep(", "while (", "while("
):
    assert forbidden not in h62, forbidden

assert "Drnas-Turnip S1H A810 / Mesa " in d
print("Drnas-Turnip S1H histogram/stabilizer applied", flush=True)
