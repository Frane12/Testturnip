/* SPDX-License-Identifier: MIT
 * Frane Mesa 26.3.4 A810 GMEM-RUNTIME EXP.
 * Pure policy/state helpers. Experimental downstream code, not official Mesa.
 */
#ifndef FRANE_MESA_2634_A810_GMEM_RUNTIME_H
#define FRANE_MESA_2634_A810_GMEM_RUNTIME_H

#include <cstdint>
#include <limits>

struct frane_2634_gmem_state {
   uint8_t score = 0;   /* 0..8 */
   bool armed = false;  /* hysteretic promotion gate */
};

struct frane_2634_gmem_layout_input {
   uint64_t physical_gmem = 0;
   uint64_t usable_gmem = 0;
   uint64_t pixels_per_tile = 0;
   uint64_t pass_pixels = 0;
   uint32_t drawcalls = 0;
};

struct frane_2634_gmem_layout_eval {
   bool eligible = false;
   uint64_t estimated_tiles = 0;
};

struct frane_2634_gmem_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
};

/* lhs <= rhs * num / den, for num <= den, without overflowing uint64_t. */
static inline bool
frane_2634_ratio_le(uint64_t lhs, uint64_t rhs,
                    uint32_t num, uint32_t den)
{
   if (!den || num > den)
      return false;
   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   const uint64_t threshold = q * num + (r * num) / den;
   return lhs <= threshold;
}

static inline frane_2634_gmem_layout_eval
frane_2634_eval_layout(const frane_2634_gmem_layout_input &in)
{
   frane_2634_gmem_layout_eval out{};

   constexpr uint64_t KiB = 1024ull;
   constexpr uint64_t MAX_PASS_PIXELS = 1920ull * 1080ull;
   constexpr uint64_t MAX_ESTIMATED_TILES = 24ull;

   /* These are sanity bounds only. Mesa's real GMEM allocator remains the
    * hardware authority. If metadata looks strange, the runtime simply does
    * nothing and the 26.3.3 baseline decision survives unchanged.
    */
   const bool geometry_ok =
      in.physical_gmem >= 256ull * KiB &&
      in.physical_gmem <= 2048ull * KiB &&
      in.usable_gmem >= 64ull * KiB &&
      in.usable_gmem <= in.physical_gmem &&
      in.pixels_per_tile >= 16 &&
      in.pass_pixels > 0 &&
      in.pass_pixels <= MAX_PASS_PIXELS &&
      in.drawcalls >= 5;

   if (!geometry_ok)
      return out;

   /* Predict with 1/16 tile headroom. This never alters actual attachment
    * offsets, tile dimensions or GMEM bytes.
    */
   const uint64_t effective_pixels =
      in.pixels_per_tile - in.pixels_per_tile / 16ull;
   if (!effective_pixels)
      return out;

   out.estimated_tiles =
      in.pass_pixels / effective_pixels +
      (in.pass_pixels % effective_pixels ? 1ull : 0ull);
   out.eligible = out.estimated_tiles > 0 &&
                  out.estimated_tiles <= MAX_ESTIMATED_TILES;
   return out;
}

/* Submit-thread state machine fed by measured GPU render-pass durations.
 * It deliberately needs multiple observations before it can arm and several
 * weak/bad observations before it disarms, preventing threshold chatter.
 */
static inline frane_2634_gmem_state
frane_2634_update_gmem_state(frane_2634_gmem_state state,
                             uint64_t sysmem_ticks,
                             uint64_t gmem_ticks,
                             uint64_t sysmem_samples,
                             uint64_t gmem_samples)
{
   if (state.score > 8)
      state.score = 8;

   if (sysmem_samples < 8 || gmem_samples < 8 ||
       !sysmem_ticks || !gmem_ticks)
      return state;

   const bool strong =
      frane_2634_ratio_le(gmem_ticks, sysmem_ticks, 7, 8);   /* >=12.5% win */
   const bool profitable =
      frane_2634_ratio_le(gmem_ticks, sysmem_ticks, 15, 16); /* >=6.25% win */
   const bool hold =
      frane_2634_ratio_le(gmem_ticks, sysmem_ticks, 31, 32); /* >=3.125% win */

   if (strong) {
      state.score = state.score >= 6 ? 8 : uint8_t(state.score + 2);
   } else if (profitable) {
      if (state.score < 8)
         state.score++;
   } else if (!hold) {
      if (state.score > 0)
         state.score--;
   }

   if (!state.armed && state.score >= 6)
      state.armed = true;
   else if (state.armed && state.score <= 2)
      state.armed = false;

   return state;
}

static inline uint32_t
frane_2634_pack_gmem_state(frane_2634_gmem_state state)
{
   const uint32_t score = state.score > 8 ? 8u : state.score;
   return score | (state.armed ? (1u << 8) : 0u);
}

static inline frane_2634_gmem_state
frane_2634_unpack_gmem_state(uint32_t word)
{
   frane_2634_gmem_state state{};
   state.score = uint8_t(word & 0xffu);
   if (state.score > 8)
      state.score = 8;
   state.armed = (word & (1u << 8)) != 0;
   if (state.armed && state.score <= 2)
      state.armed = false;
   return state;
}

/* When armed, promote a proven-safe A810 pass to GMEM for 63/64 decisions.
 * The 1/64 SYSMEM control probe is always measured so scene changes can
 * eventually disarm the runtime. probability > 40 keeps the baseline
 * PROFILED behavior untouched: we never promote GMEM against a doubtful
 * profiler.
 */
static inline frane_2634_gmem_decision
frane_2634_decide_gmem_runtime(bool enabled,
                               bool layout_eligible,
                               frane_2634_gmem_state state,
                               uint32_t sysmem_probability,
                               uint64_t decision_word)
{
   frane_2634_gmem_decision out{};
   if (!enabled || !layout_eligible || !state.armed ||
       sysmem_probability > 40)
      return out;

   out.override_mode = true;
   if ((decision_word & 63ull) == 0ull) {
      out.select_sysmem = true;
      out.force_measure = true;
   } else {
      out.select_sysmem = false;
   }
   return out;
}

#endif
