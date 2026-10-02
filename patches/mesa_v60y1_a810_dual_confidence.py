#!/usr/bin/env python3
"""Drnas Turnip A810 V60Y.1 DUAL-CONFIDENCE.

Layered strictly on V60Y PREDICTIVE-SELECTOR.

Purpose:
  Make the predictor cheaper and more statistically stable by learning GMEM and
  SYSMEM evidence separately instead of maintaining one mode + one confidence.

Packed predictor state:
  bits 0..3  GMEM score   (0..15)
  bits 4..7  SYSMEM score (0..15)

Training happens only on full-selector audit decisions:
  - chosen mode gains +2 (saturating);
  - opposite mode decays by -1;
  - no additional map, hash, clock, allocation or scan is introduced.

Prediction requires:
  - winner score >= 6;
  - winner/loser margin >= 3.

Audit cadence is driven by *both* score and margin:
  weak stable state      -> 1/8 full audit
  medium stable state    -> 1/16
  strong stable state    -> 1/32
  very strong SYSMEM     -> 1/64
  very strong GMEM       -> capped at 1/32 because GMEM still benefits from
                            more frequent correctness/performance revalidation.

If the two scores become close, prediction automatically stops and the complete
V59 selector runs until the evidence separates again.

A/B:
  TU_FRANE_PREDICT=0 -> exact V59 selector path.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V60Y.1 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V60Y.1 PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# Reinterpret the packed predictor word as two independent statistical scores.
# The storage size and atomic count stay exactly the same as V60Y.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   /* V60Y: tiny final-decision predictor.  This lives in the existing
    * rp_history so there is no additional map/hash lookup on the hot path.
    */
   std::atomic<uint32_t> frane_predict_word { 0 };
   std::atomic<uint32_t> frane_predict_ticket { 0 };""",
    """   /* V60Y.1: two 4-bit evidence counters packed in one relaxed atomic:
    * bits 0..3 GMEM score, bits 4..7 SYSMEM score.
    * Keeping one word avoids growing the hot history footprint.
    */
   std::atomic<uint32_t> frane_predict_word { 0 };
   std::atomic<uint32_t> frane_predict_ticket { 0 };""",
    "reinterpret predictor state as dual evidence counters",
)

# ---------------------------------------------------------------------------
# Replace V60Y's one-sided confidence fast path with score+margin prediction.
# This is intentionally just a few integer ops and one relaxed atomic ticket.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      if (frane_predict_enabled && frane_a810_tail_device(device)) {
         const uint32_t predict_word =
            history.frane_predict_word.load(std::memory_order_relaxed);
         const bool valid = predict_word & 1u;
         const bool predict_sysmem = predict_word & 2u;
         const uint32_t confidence = (predict_word >> 2) & 7u;

         if (valid && confidence >= 4u) {
            const uint32_t ticket =
               history.frane_predict_ticket.fetch_add(
                  1u, std::memory_order_relaxed);

            /* Confidence controls how long we trust the cheap prediction.
             * Even at saturation, 1/32 decisions still run the complete
             * selector so scene/regime changes cannot remain invisible.
             */
            const uint32_t audit_mask =
               confidence >= 7u ? 31u :
               confidence >= 6u ? 15u : 7u;

            if ((ticket & audit_mask) != 0u) {
               if (predict_sysmem)
                  return render_mode::SYSMEM;

               /* Never let a statistical shortcut bypass correctness. */
               if (frane_a810_gmem_pass_safe(
                      device, cmd_state, pass, framebuffer))
                  return render_mode::GMEM;

               return render_mode::SYSMEM;
            }
         }
      }
""",
    """      if (frane_predict_enabled && frane_a810_tail_device(device)) {
         const uint32_t predict_word =
            history.frane_predict_word.load(std::memory_order_relaxed);
         const uint32_t gmem_score = predict_word & 15u;
         const uint32_t sysmem_score = (predict_word >> 4) & 15u;
         const bool predict_sysmem = sysmem_score > gmem_score;
         const uint32_t winner_score =
            predict_sysmem ? sysmem_score : gmem_score;
         const uint32_t loser_score =
            predict_sysmem ? gmem_score : sysmem_score;
         const uint32_t margin = winner_score - loser_score;

         /* Close/volatile histories deliberately fall back to the complete
          * selector.  No extra volatility state is required: the score margin
          * itself is the cheap statistical stability signal.
          */
         if (winner_score >= 6u && margin >= 3u) {
            const uint32_t ticket =
               history.frane_predict_ticket.fetch_add(
                  1u, std::memory_order_relaxed);

            uint32_t audit_mask = 7u; /* 1/8 */
            if (winner_score >= 14u && margin >= 10u)
               audit_mask = predict_sysmem ? 63u : 31u; /* 1/64 vs 1/32 */
            else if (winner_score >= 12u && margin >= 8u)
               audit_mask = 31u; /* 1/32 */
            else if (winner_score >= 9u && margin >= 5u)
               audit_mask = 15u; /* 1/16 */

            if ((ticket & audit_mask) != 0u) {
               if (predict_sysmem)
                  return render_mode::SYSMEM;

               /* Predicted GMEM always keeps the proven A810 correctness gate.
                * Stable GMEM is also capped at 1/32 auditing by design.
                */
               if (frane_a810_gmem_pass_safe(
                      device, cmd_state, pass, framebuffer))
                  return render_mode::GMEM;

               return render_mode::SYSMEM;
            }
         }
      }
""",
    "use dual-score margin and asymmetric adaptive audit cadence",
)

# ---------------------------------------------------------------------------
# Train both scores from the final *post-safety* full-selector outcome.
# +2 winner / -1 loser converges quickly for a repeated pass while allowing a
# real regime change to erase stale confidence over several audit decisions.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      if (frane_predict_enabled && frane_a810_tail_device(device)) {
         const bool final_sysmem = mode == render_mode::SYSMEM;
         uint32_t old_word =
            history.frane_predict_word.load(std::memory_order_relaxed);

         for (;;) {
            const bool old_valid = old_word & 1u;
            const bool old_sysmem = old_word & 2u;
            uint32_t confidence = (old_word >> 2) & 7u;
            bool next_sysmem = final_sysmem;

            if (!old_valid) {
               confidence = 1u;
            } else if (old_sysmem == final_sysmem) {
               next_sysmem = old_sysmem;
               confidence = MIN2(confidence + 1u, 7u);
            } else if (confidence > 1u) {
               /* Hysteresis: disagreement weakens trust first. */
               next_sysmem = old_sysmem;
               confidence--;
            } else {
               /* Repeated disagreement: change prediction. */
               confidence = 1u;
            }

            const uint32_t next_word =
               1u | (next_sysmem ? 2u : 0u) | (confidence << 2);

            if (history.frane_predict_word.compare_exchange_weak(
                   old_word, next_word,
                   std::memory_order_relaxed,
                   std::memory_order_relaxed))
               break;
         }
      }
""",
    """      if (frane_predict_enabled && frane_a810_tail_device(device)) {
         const bool final_sysmem = mode == render_mode::SYSMEM;
         uint32_t old_word =
            history.frane_predict_word.load(std::memory_order_relaxed);

         for (;;) {
            uint32_t gmem_score = old_word & 15u;
            uint32_t sysmem_score = (old_word >> 4) & 15u;

            if (final_sysmem) {
               sysmem_score = MIN2(sysmem_score + 2u, 15u);
               if (gmem_score)
                  gmem_score--;
            } else {
               gmem_score = MIN2(gmem_score + 2u, 15u);
               if (sysmem_score)
                  sysmem_score--;
            }

            const uint32_t next_word =
               gmem_score | (sysmem_score << 4);

            if (history.frane_predict_word.compare_exchange_weak(
                   old_word, next_word,
                   std::memory_order_relaxed,
                   std::memory_order_relaxed))
               break;
         }
      }
""",
    "train independent GMEM and SYSMEM evidence counters",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip A810 V60Y PREDICTIVE / Mesa ",
    "Drnas Turnip A810 V60Y.1 DUAL-CONFIDENCE / Mesa ",
    "V60Y.1 display identity",
)

# ---------------------------------------------------------------------------
# Audit: V60Y.1 may alter only predictor statistics/cadence, never safety or
# underlying selection/rendering semantics.
# ---------------------------------------------------------------------------
a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
lrz = (V / "tu_lrz.cc").read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
q = (V / "tu_queue.cc").read_text()

for needle in (
    "gmem_score = predict_word & 15u",
    "sysmem_score = (predict_word >> 4) & 15u",
    "winner_score >= 6u",
    "margin >= 3u",
    "predict_sysmem ? 63u : 31u",
    "winner_score >= 12u && margin >= 8u",
    "winner_score >= 9u && margin >= 5u",
    "sysmem_score = MIN2(sysmem_score + 2u, 15u)",
    "gmem_score = MIN2(gmem_score + 2u, 15u)",
):
    assert needle in a, needle

# One packed state word + one ticket only.
assert a.count("std::atomic<uint32_t> frane_predict_word") == 1
assert a.count("std::atomic<uint32_t> frane_predict_ticket") == 1

# Prediction still precedes expensive runtime metadata construction.
assert a.index("const uint32_t gmem_score = predict_word & 15u") < a.index(
    "frane_26318_smart_gmem_input runtime_input {}")

# Correctness and V59 selection path remain intact.
assert "frane_a810_gmem_pass_safe(" in a
assert "frane_26320_decide_gmem_turbo" in a
assert "runtime_input.zs_load_store = pass->frane_zs_load_store;" in a
assert 'TU_FRANE_PREDICT", true' in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert 'TU_FRANE_EDGE", 1' in a
assert 'TU_FRANE_DEPTH_DRAWS", 16' in a
assert 'TU_FRANE_DEPTH_MAX", 23' in a

assert "(CHIP >= A8XX && !z_write_enable)" in lrz
assert "if (CHIP < A8XX || z_write_enable)" in lrz
assert "FRANE_2631_POLL_READY" in kg
assert "frane_2631_deadline_ns" in kg
assert "pthread_mutex_unlock(&device->submit_mutex);" in q
assert "frane_26313_same_lrz_fs_signature" not in cmd

assert "Drnas Turnip A810 V60Y.1 DUAL-CONFIDENCE / Mesa " in d
print("Drnas Turnip A810 V60Y.1 DUAL-CONFIDENCE applied and audited", flush=True)
