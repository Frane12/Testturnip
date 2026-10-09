#!/usr/bin/env python3
"""A830 S2-BW2: adaptive tile-cost + measured-history rollback over BW1.

Runs after:
  patches/a830-smart2-complete.patch
  patches/a830_upstream_rebase.py
  patches/a830_s2_d2.py
  patches/a830_s2_bw1.py

BW2 is policy only. Mesa remains authoritative for allocation, selected layout,
attachment offsets, synchronization, resolves, LRZ and register programming.

A/B:
  TU_FRANE_A830_BW2=1 default
  TU_FRANE_A830_BW2=0 disables only BW2
"""

from pathlib import Path
import hashlib
import shutil

ROOT = Path("mesa/src/freedreno")
V = ROOT / "vulkan"

before = {
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ROOT.rglob("*") if p.is_file()
}

def edit(path: Path, old: str, new: str, label: str) -> None:
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"BW2 source drift {label}: expected one anchor, saw {n}: {old[:180]!r}"
        )
    path.write_text(s.replace(old, new, 1))
    print(f"BW2 PASS {label}", flush=True)

shutil.copyfile("patches/frane_a830_s2_bw2.h", V / "frane_a830_s2_bw2.h")

smart = V / "frane_mesa_26318_a810_smart_gmem.h"
edit(
    smart,
    '#include "frane_a830_s2_bw1.h"',
    '#include "frane_a830_s2_bw1.h"\n'
    '#include "frane_a830_s2_bw2.h"',
    "include BW2 policy",
)

edit(
    smart,
    """   bool a830_bw1 = false;
};""",
    """   bool a830_bw1 = false;
   bool a830_bw2 = false;

   /* Existing per-render-pass timing history, snapshotted by tu_autotune. */
   int8_t a830_history_score = 0;
   uint8_t a830_history_pairs = 0;
   bool a830_history_ready = false;
   uint8_t a830_measured_score = 0;
   bool a830_measured_armed = false;
};""",
    "extend SMART input with existing history",
)

edit(
    smart,
    """   if (in.a830_bw1) {
      const auto bw1 = frane_a830_s2bw1_evaluate(
         in.layout.pass_pixels,
         in.selected_tile_pixels,
         in.allocator_capacity_pixels,
         in.layout.drawcalls,
         in.sysmem_bandwidth_per_pixel,
         in.gmem_bandwidth_per_pixel,
         in.peak_live_cpp,
         uint32_t(std::min<uint64_t>(in.layout.usable_gmem, UINT32_MAX)),
         in.peak_live_planes);
      if (bw1.valid)
         score += bw1.score_delta;
   }

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    """   if (in.a830_bw1) {
      const auto bw1 = frane_a830_s2bw1_evaluate(
         in.layout.pass_pixels,
         in.selected_tile_pixels,
         in.allocator_capacity_pixels,
         in.layout.drawcalls,
         in.sysmem_bandwidth_per_pixel,
         in.gmem_bandwidth_per_pixel,
         in.peak_live_cpp,
         uint32_t(std::min<uint64_t>(in.layout.usable_gmem, UINT32_MAX)),
         in.peak_live_planes);
      if (bw1.valid)
         score += bw1.score_delta;
   }

   if (in.a830_bw2) {
      const auto bw2 = frane_a830_s2bw2_evaluate(
         in.layout.pass_pixels,
         in.selected_tile_pixels,
         in.allocator_capacity_pixels,
         in.layout.drawcalls,
         in.sysmem_bandwidth_per_pixel,
         in.gmem_bandwidth_per_pixel,
         in.peak_live_cpp,
         uint32_t(std::min<uint64_t>(in.layout.usable_gmem, UINT32_MAX)),
         in.peak_live_planes,
         in.a830_history_score,
         in.a830_history_pairs,
         in.a830_history_ready,
         in.a830_measured_score,
         in.a830_measured_armed);
      if (bw2.valid)
         score += bw2.score_delta;
   }

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    "blend adaptive tile cost",
)

auto = V / "tu_autotune.cc"
edit(
    auto,
    """static bool
frane_a830_s2bw1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW1", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
    """static bool
frane_a830_s2bw1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW1", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_s2bw2_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW2", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
    "add BW2 runtime gate",
)

edit(
    auto,
    """         runtime_input.a830_bw1 =
            frane_a830_s2bw1_enabled(device);

         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;""",
    """         runtime_input.a830_bw1 =
            frane_a830_s2bw1_enabled(device);
         runtime_input.a830_bw2 =
            frane_a830_s2bw2_enabled(device);

         if (runtime_input.a830_bw2) {
            const auto bw2_tail = frane_a830_v2_unpack_tail(
               history.frane_a830_v2_tail_word.load(std::memory_order_relaxed));
            const auto bw2_measured = frane_2634_unpack_gmem_state(
               history.frane_gmem_runtime_word.load(std::memory_order_relaxed));

            runtime_input.a830_history_score = bw2_tail.score;
            runtime_input.a830_history_pairs = bw2_tail.paired_samples;
            runtime_input.a830_history_ready = bw2_tail.ready;
            runtime_input.a830_measured_score = bw2_measured.score;
            runtime_input.a830_measured_armed = bw2_measured.armed;
         }

         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;""",
    "feed existing RP history into BW2",
)

adaptive = V / "frane_a830_v2_adaptive_gmem.h"
edit(
    adaptive,
    """   const auto layout = frane_26318_eval_smart_gmem(in);
   if (!layout.eligible)
      return out;

   sysmem_probability = std::min(sysmem_probability, 100u);""",
    """   const auto layout = frane_26318_eval_smart_gmem(in);
   if (!layout.eligible)
      return out;

   /* BW2 fast rollback: repeated measured SYSMEM wins are allowed to veto a
    * stale structural GMEM prior immediately. Keep sparse GMEM audits so a
    * later scene regime can recover without a permanent lock.
    */
   if (in.a830_bw2) {
      const auto bw2 = frane_a830_s2bw2_evaluate(
         in.layout.pass_pixels,
         in.selected_tile_pixels,
         in.allocator_capacity_pixels,
         in.layout.drawcalls,
         in.sysmem_bandwidth_per_pixel,
         in.gmem_bandwidth_per_pixel,
         in.peak_live_cpp,
         uint32_t(std::min<uint64_t>(in.layout.usable_gmem, UINT32_MAX)),
         in.peak_live_planes,
         in.a830_history_score,
         in.a830_history_pairs,
         in.a830_history_ready,
         in.a830_measured_score,
         in.a830_measured_armed);

      if (bw2.valid && bw2.rollback_sysmem) {
         const uint8_t audit_log2 = bw2.audit_log2 ? bw2.audit_log2 : 6u;
         const uint64_t mask = (UINT64_C(1) << audit_log2) - 1u;
         const bool gmem_audit = (decision_word & mask) == 0u;

         out.override_mode = true;
         out.select_sysmem = !gmem_audit;
         out.force_measure =
            gmem_audit || (((decision_word >> 16) & 63u) == 0u);
         out.learned = true;
         out.confidence = uint8_t(std::min(8, -int(in.a830_history_score)));
         out.probe_log2 = audit_log2;
         return out;
      }
   }

   sysmem_probability = std::min(sysmem_probability, 100u);""",
    "add measured-history fast rollback",
)

edit(
    V / "tu_device.cc",
    "Turnip-Drnas A830 S2-BW1 / Mesa ",
    "Turnip-Drnas A830 S2-BW2 Adaptive Tile Cost / Mesa ",
    "BW2 driver identity",
)

# Integration checks.
smart_text = smart.read_text()
auto_text = auto.read_text()
adaptive_text = adaptive.read_text()
device_text = (V / "tu_device.cc").read_text()

for needle in (
    '#include "frane_a830_s2_bw2.h"',
    "bool a830_bw2 = false",
    "a830_history_score",
    "frane_a830_s2bw2_evaluate",
):
    assert needle in smart_text, needle

for needle in (
    'TU_FRANE_A830_BW2", true',
    "runtime_input.a830_bw2",
    "frane_a830_v2_unpack_tail",
    "frane_2634_unpack_gmem_state",
):
    assert needle in auto_text, needle

for needle in (
    "BW2 fast rollback",
    "bw2.rollback_sysmem",
    "gmem_audit",
):
    assert needle in adaptive_text, needle

assert "Turnip-Drnas A830 S2-BW2 Adaptive Tile Cost / Mesa " in device_text

after = {
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ROOT.rglob("*") if p.is_file()
}
changed = {k for k in before.keys() | after.keys()
           if before.get(k) != after.get(k)}
expected = {
    "vulkan/frane_a830_s2_bw2.h",
    "vulkan/frane_mesa_26318_a810_smart_gmem.h",
    "vulkan/frane_a830_v2_adaptive_gmem.h",
    "vulkan/tu_autotune.cc",
    "vulkan/tu_device.cc",
}
if changed != expected:
    raise SystemExit(f"BW2 unexpected source scope: {sorted(changed ^ expected)}")

print("A830 S2-BW2 adaptive tile cost applied; source scope verified", flush=True)
