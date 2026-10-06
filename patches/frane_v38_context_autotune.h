/* SPDX-License-Identifier: MIT
 * V38 A810 context-aware autotuner helpers.
 * Experimental downstream policy; no GPU legality/layout changes.
 */
#ifndef FRANE_V38_CONTEXT_AUTOTUNE_H
#define FRANE_V38_CONTEXT_AUTOTUNE_H

#include <cstdint>

struct frane_v38_context_input {
   uint32_t drawcalls = 0;
   uint64_t pass_pixels = 0;
   uint64_t gmem_pixels = 0;
   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
   uint32_t draw_bandwidth_per_sample = 0;
   bool has_depth = false;
   bool has_stencil = false;
};

static inline uint8_t
frane_v38_draw_bucket(uint32_t draws)
{
   if (draws < 12)
      return 0;
   if (draws < 32)
      return 1;
   return 2;
}

static inline uint8_t
frane_v38_tile_bucket(uint64_t pass_pixels, uint64_t gmem_pixels)
{
   if (!pass_pixels || !gmem_pixels)
      return 2;

   const uint64_t tiles = (pass_pixels + gmem_pixels - 1) / gmem_pixels;
   if (tiles <= 8)
      return 0;
   if (tiles <= 20)
      return 1;
   return 2;
}

static inline uint8_t
frane_v38_ds_bucket(bool has_depth, bool has_stencil)
{
   if (has_stencil)
      return 2;
   if (has_depth)
      return 1;
   return 0;
}

static inline uint8_t
frane_v38_pass_bw_bucket(uint32_t sysmem, uint32_t gmem)
{
   if (!sysmem || !gmem)
      return 1;

   if (gmem >= sysmem)
      return 0;

   /* <= 75% of SYSMEM's attachment traffic is a strong GMEM prior. */
   if (gmem <= sysmem - sysmem / 4)
      return 2;

   return 1;
}

static inline uint8_t
frane_v38_draw_traffic_bucket(uint32_t bytes_per_sample)
{
   if (bytes_per_sample <= 4)
      return 0;
   if (bytes_per_sample <= 10)
      return 1;
   return 2;
}

/* Coarse on purpose: at most 3^5 structural classes per base RP, while real
 * workloads normally occupy only a few. The original RP hash remains the
 * dominant identity; this word merely splits materially different contexts.
 */
static inline uint32_t
frane_v38_context_word(const frane_v38_context_input &in)
{
   const uint32_t draw = frane_v38_draw_bucket(in.drawcalls);
   const uint32_t tile = frane_v38_tile_bucket(in.pass_pixels, in.gmem_pixels);
   const uint32_t ds = frane_v38_ds_bucket(in.has_depth, in.has_stencil);
   const uint32_t bw =
      frane_v38_pass_bw_bucket(in.sysmem_bandwidth_per_pixel,
                               in.gmem_bandwidth_per_pixel);
   const uint32_t traffic =
      frane_v38_draw_traffic_bucket(in.draw_bandwidth_per_sample);

   return 0xA8103800u |
          draw |
          (tile << 2) |
          (ds << 4) |
          (bw << 6) |
          (traffic << 8);
}

enum class frane_v38_reversal_observation : uint8_t {
   NONE = 0,
   SYSMEM = 1,
   GMEM = 2,
   IGNORE = 3,
};

/* Strong-winner change detector. Only an observation of the alternative mode
 * can vote for reopening. Preferred-mode samples are ignored so sparse control
 * probes can accumulate evidence across normal winner measurements.
 *
 * A vote requires the alternative to be at least ~20% faster than the current
 * winner's smoothed duration. Two matching votes are required by the caller.
 */
static inline frane_v38_reversal_observation
frane_v38_reversal_vote(uint32_t sysmem_probability,
                        bool sample_is_sysmem,
                        uint64_t sample_duration,
                        uint64_t incumbent_average)
{
   if (!sample_duration || !incumbent_average)
      return frane_v38_reversal_observation::IGNORE;

   if (sysmem_probability <= 5) {
      if (!sample_is_sysmem)
         return frane_v38_reversal_observation::IGNORE;

      const uint64_t threshold =
         incumbent_average - incumbent_average / 5;
      return sample_duration <= threshold
         ? frane_v38_reversal_observation::SYSMEM
         : frane_v38_reversal_observation::NONE;
   }

   if (sysmem_probability >= 95) {
      if (sample_is_sysmem)
         return frane_v38_reversal_observation::IGNORE;

      const uint64_t threshold =
         incumbent_average - incumbent_average / 5;
      return sample_duration <= threshold
         ? frane_v38_reversal_observation::GMEM
         : frane_v38_reversal_observation::NONE;
   }

   return frane_v38_reversal_observation::IGNORE;
}

#endif
