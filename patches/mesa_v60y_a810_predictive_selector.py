#!/usr/bin/env python3
"""Drnas Turnip A810 V60Y PREDICTIVE-SELECTOR.

Base: V59 LRZ-CLEAN.

Goal:
  Spend less CPU time repeatedly deciding GMEM vs SYSMEM for the same hot
  render-pass history.  Learn the *final* mode that the full selector actually
  chose, build confidence from repeated agreement, then predict that mode on
  most subsequent hits.

The predictor is deliberately statistical and bounded:
  - keyed naturally by Mesa's existing rp_history (no new hash/map lookup);
  - first four agreeing full decisions are learning/warmup;
  - confidence 4-5: full audit every 8 hits;
  - confidence 6:   full audit every 16 hits;
  - confidence 7:   full audit every 32 hits;
  - disagreement decays confidence before the predicted side flips;
  - predicted GMEM still passes the existing A810 GMEM correctness classifier;
  - periodic full decisions keep PROFILED/SMART/TURBO/tail timing feedback alive.

Fast predicted hits skip:
  - render-area pixel accumulation;
  - SMART-GMEM layout construction;
  - tail/edge selector work;
  - PROFILED random/probability decision work;
  - measurement bookkeeping for that hit.

They do not skip:
  - the A810 GMEM safety classifier when the prediction is GMEM;
  - Mesa/Turnip correctness rules outside the autotune selector.

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
            f"V60Y source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V60Y PASS {label}", flush=True)


# One packed predictor word per existing render-pass history:
# bit 0      valid
# bit 1      predicted mode (1=SYSMEM, 0=GMEM)
# bits 2..4  confidence 0..7
# Ticket only selects periodic full-audit decisions.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   frane_2634_gmem_state frane_gmem_runtime_state {};
   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };""",
    """   frane_2634_gmem_state frane_gmem_runtime_state {};
   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };

   /* V60Y: tiny final-decision predictor.  This lives in the existing
    * rp_history so there is no additional map/hash lookup on the hot path.
    */
   std::atomic<uint32_t> frane_predict_word { 0 };
   std::atomic<uint32_t> frane_predict_ticket { 0 };""",
    "add per-history packed predictor state",
)

# Fast-predict before constructing runtime_input.  This is where the CPU work is
# actually avoided, rather than merely replacing one branch later in SMART-GMEM.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      frane_26318_smart_gmem_input runtime_input {};
      if (frane_a810_gmem_runtime_enabled(device)) {""",
    """      /* V60Y PREDICTIVE-SELECTOR:
       * Once the final selector has agreed often enough for this exact
       * rp_history, predict the same final mode and bypass the expensive
       * decision construction.  Periodic audit slots fall through to the
       * complete V59 path and refresh confidence.
       */
      static const bool frane_predict_enabled =
         debug_get_bool_option("TU_FRANE_PREDICT", true);

      if (frane_predict_enabled && frane_a810_tail_device(device)) {
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

      frane_26318_smart_gmem_input runtime_input {};
      if (frane_a810_gmem_runtime_enabled(device)) {""",
    "predict hot RP mode before runtime metadata and full selector work",
)

# Feed the *final* post-safety decision back into the predictor.  We use a
# 3-bit saturating confidence counter. A disagreement lowers confidence; only
# after confidence is exhausted does the predicted side flip. This keeps one
# exploratory/probe decision from destroying a useful hot prediction.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)) {
         mode = render_mode::SYSMEM;
         measure = false;
      }

      if (measure)
""",
    """      if (mode == render_mode::GMEM &&
          !frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)) {
         mode = render_mode::SYSMEM;
         measure = false;
      }

      if (frane_predict_enabled && frane_a810_tail_device(device)) {
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

      if (measure)
""",
    "train predictor from final post-safety selector outcome",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V59 / Mesa ",
    "Drnas Turnip A810 V60Y PREDICTIVE / Mesa ",
    "V60Y display identity",
)

# Active-stack audit.
a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
lrz = (V / "tu_lrz.cc").read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
q = (V / "tu_queue.cc").read_text()

for needle in (
    'TU_FRANE_PREDICT", true',
    "frane_predict_word",
    "frane_predict_ticket",
    "confidence >= 4u",
    "confidence >= 7u ? 31u",
    "confidence >= 6u ? 15u : 7u",
    "compare_exchange_weak",
    "frane_a810_gmem_pass_safe",
):
    assert needle in a, needle

# Predictor must execute before runtime metadata construction.
assert a.index("V60Y PREDICTIVE-SELECTOR") < a.index(
    "frane_26318_smart_gmem_input runtime_input {}")

# Full V59 path remains available and periodic audit decisions still reach it.
assert "frane_26320_decide_gmem_turbo" in a
assert "runtime_input.zs_load_store = pass->frane_zs_load_store;" in a
assert 'TU_FRANE_GMEM_TURBO", true' in a
assert 'TU_FRANE_EDGE", 1' in a
assert 'TU_FRANE_DEPTH_DRAWS", 16' in a
assert 'TU_FRANE_DEPTH_MAX", 23' in a

# Never compromise known correctness/hang fixes.
assert "(CHIP >= A8XX && !z_write_enable)" in lrz
assert "if (CHIP < A8XX || z_write_enable)" in lrz
assert "FRANE_2631_POLL_READY" in kg
assert "frane_2631_deadline_ns" in kg
assert "pthread_mutex_unlock(&device->submit_mutex);" in q
assert "frane_26313_same_lrz_fs_signature" not in cmd

assert "Drnas Turnip A810 V60Y PREDICTIVE / Mesa " in d
print("Drnas Turnip A810 V60Y PREDICTIVE-SELECTOR applied and audited", flush=True)
