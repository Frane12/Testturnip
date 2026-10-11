/* SPDX-License-Identifier: MIT
 * A810 S Ultimate v1.3: bounded coordination between S1 measured runtime
 * state and the AT4 GPU-timestamp champion. No new queries or locks.
 */
#ifndef FRANE_A810_S1AT4_COORD_H
#define FRANE_A810_S1AT4_COORD_H
#include <cstdint>

enum frane_s1at4_reason : uint8_t {
   FRANE_S1AT4_OFF = 0,
   FRANE_S1AT4_NO_S1,
   FRANE_S1AT4_MEASURE,
   FRANE_S1AT4_AGREE,
   FRANE_S1AT4_AT4_PRIORITY,
   FRANE_S1AT4_S1_WEAK,
   FRANE_S1AT4_GPU_STRONG,
   FRANE_S1AT4_S1_TIE_BREAK
};
struct frane_s1at4_result {
   bool prefer_s1 = false;
   frane_s1at4_reason reason = FRANE_S1AT4_OFF;
};

/* A true return only adjusts AT4's chosen mode. The caller MUST retain
 * AT4's override_mode and sampling/measurement state, so the render-pass
 * remains under AT4 and the existing downstream GMEM correctness gate.
 * GPU samples are paired per category; bandwidth byte estimates NEVER count
 * as a substitute for real GPU timestamps.
 */
static inline frane_s1at4_result
frane_s1at4_coordinate(bool enabled, bool context_safe,
                       bool s1_override, bool s1_sysmem, bool s1_measure,
                       bool s1_armed, unsigned s1_score,
                       bool at4_override, bool at4_sysmem, bool at4_measure,
                       bool gpu_signature_match, unsigned gpu_pairs,
                       unsigned gpu_score_abs, unsigned gpu_volatility,
                       bool gpu_stale)
{
   frane_s1at4_result r{};
   if (!enabled) return r;
   if (!context_safe || !s1_override || !s1_armed) {
      r.reason = FRANE_S1AT4_NO_S1;
      return r;
   }
   if (s1_measure || at4_measure) {
      r.reason = FRANE_S1AT4_MEASURE;
      return r;
   }
   if (!at4_override || !gpu_signature_match || gpu_stale ||
       gpu_pairs < 8 || gpu_volatility > 3 || gpu_score_abs < 6) {
      r.reason = FRANE_S1AT4_AT4_PRIORITY;
      return r;
   }
   if (s1_sysmem == at4_sysmem) {
      r.reason = FRANE_S1AT4_AGREE;
      return r;
   }
   if (s1_score < 7) {
      r.reason = FRANE_S1AT4_S1_WEAK;
      return r;
   }
   /* AT4 is authoritative once its opposing champion is sufficiently
    * established. Only adjudicate narrow confidence margins. */
   if (gpu_pairs >= 12 || gpu_score_abs >= 10) {
      r.reason = FRANE_S1AT4_GPU_STRONG;
      return r;
   }
   r.prefer_s1 = true;
   r.reason = FRANE_S1AT4_S1_TIE_BREAK;
   return r;
}
#endif
