#include "../patches/frane_s1at1_contextual_autotune.h"

#include <cassert>
#include <cstdint>
#include <iostream>

static frane_s1at1_context_input base_context()
{
   frane_s1at1_context_input in {};
   in.pass_pixels = 1280ull * 720ull;
   in.estimated_tiles = 4;
   in.drawcalls = 64;
   in.sysmem_bandwidth_per_pixel = 24;
   in.gmem_bandwidth_per_pixel = 14;
   in.occurrences = 512;
   in.sysmem_probability = 50;
   return in;
}

int main()
{
   {
      auto in = base_context();
      const auto c = frane_s1at1_catalog_for(in);
      assert(c.bandwidth_adequate);
      assert(c.id == FRANE_S1AT1_BW_GMEM);
      assert(c.prior_sysmem_bias < 0);
   }
   {
      auto in = base_context();
      in.pass_pixels = 320ull * 180ull;
      in.drawcalls = 4;
      const auto c = frane_s1at1_catalog_for(in);
      assert(!c.bandwidth_adequate);
      assert(c.id == FRANE_S1AT1_TRANSIENT);
   }
   {
      auto in = base_context();
      in.zs_load_store = true;
      in.estimated_tiles = 8;
      in.drawcalls = 64;
      const auto c = frane_s1at1_catalog_for(in);
      assert(c.id == FRANE_S1AT1_DEPTH_REPLAY);
      assert(c.prior_sysmem_bias > 0);
   }

   /* Regression: a fresh history, or an old zero sentinel, must not look
    * like strong measured evidence for SYSMEM. The structural bandwidth prior
    * remains effective, but there is no fabricated learned bias.
    */
   {
      frane_s1at1_state initial {};
      const uint32_t neutral_word = frane_s1at1_pack_snapshot(initial);
      assert(neutral_word == 16u);
      const auto neutral = frane_s1at1_unpack_snapshot(neutral_word);
      const auto zero_sentinel = frane_s1at1_unpack_snapshot(0u);
      assert(neutral.score == 0 && zero_sentinel.score == 0);
      assert(neutral.sysmem_samples == 0 && neutral.gmem_samples == 0);
      assert(zero_sentinel.sysmem_samples == 0 && zero_sentinel.gmem_samples == 0);
      const auto in = base_context();
      const auto a = frane_s1at1_decide(true, in, neutral, 0x123456789abcdef0ULL);
      const auto b = frane_s1at1_decide(true, in, zero_sentinel, 0x123456789abcdef0ULL);
      assert(a.override_mode && b.override_mode);
      assert(a.confidence == 0 && b.confidence == 0);
      assert(a.effective_sysmem_probability == 38u); /* Mesa 50 - BW prior 12 */
      assert(b.effective_sysmem_probability == a.effective_sysmem_probability);
   }

   frane_s1at1_state state {};
   const auto ctx = base_context();
   const uint16_t sig = frane_s1at1_catalog_for(ctx).signature;

   /* Stable GMEM advantage should build positive evidence. */
   for (unsigned i = 0; i < 40; i++) {
      state = frane_s1at1_update_state(state, true, 1200 + (i % 3) * 8, sig);
      state = frane_s1at1_update_state(state, false, 900 + (i % 3) * 8, sig);
   }
   assert(state.score > 0);
   auto snap = frane_s1at1_unpack_snapshot(frane_s1at1_pack_snapshot(state));
   assert(frane_s1at1_confidence(snap) >= 6);

   {
      auto in = ctx;
      in.sysmem_probability = 50;
      auto d = frane_s1at1_decide(true, in, snap, 0x123456789abcdef0ULL);
      assert(d.override_mode);
      assert(d.effective_sysmem_probability >= 4);
      assert(d.effective_sysmem_probability <= 96);
      assert(d.effective_sysmem_probability < 50);
      assert(d.probe_log2 >= 3 && d.probe_log2 <= 10);
   }

   /* Same history, materially different render signature: confidence is cut
    * immediately instead of locking the old winner forever.
    */
   {
      auto changed = ctx;
      changed.zs_load_store = true;
      changed.estimated_tiles = 12;
      const uint16_t sig2 = frane_s1at1_catalog_for(changed).signature;
      const int old_score = state.score;
      state = frane_s1at1_update_state(state, true, 700, sig2);
      assert(sig2 != sig);
      assert(state.score <= old_score / 2 + 1);
      assert(state.volatility > 0);

      /* Then make SYSMEM the persistent winner. The model must reverse. */
      for (unsigned i = 0; i < 80; i++) {
         state = frane_s1at1_update_state(state, true, 700 + (i % 4) * 4, sig2);
         state = frane_s1at1_update_state(state, false, 1200 + (i % 4) * 4, sig2);
      }
      assert(state.score < 0);
   }

   /* Finite probe floor: high confidence still never becomes an infinite lock. */
   {
      auto s = frane_s1at1_unpack_snapshot(frane_s1at1_pack_snapshot(state));
      auto in = base_context();
      in.occurrences = 10000;
      auto d = frane_s1at1_decide(true, in, s, 0x0ULL);
      assert(d.override_mode);
      assert(d.probe_log2 >= 3 && d.probe_log2 <= 7);
      assert(d.effective_sysmem_probability >= 4);
      assert(d.effective_sysmem_probability <= 96);
   }

   /* Fuzz structural and statistical bounds. */
   uint64_t x = 0x9e3779b97f4a7c15ULL;
   frane_s1at1_state fuzz {};
   for (unsigned i = 0; i < 200000; i++) {
      x ^= x << 7;
      x ^= x >> 9;
      x ^= x << 8;

      frane_s1at1_context_input in {};
      in.pass_pixels = 1 + (x & ((1u << 22) - 1));
      in.estimated_tiles = 1 + ((x >> 22) & 31u);
      in.drawcalls = 1 + uint32_t((x >> 27) & 255u);
      in.sysmem_bandwidth_per_pixel = 1 + uint32_t((x >> 35) & 127u);
      in.gmem_bandwidth_per_pixel = 1 + uint32_t((x >> 42) & 127u);
      in.occurrences = 1 + uint32_t((x >> 49) & 8191u);
      in.sysmem_probability = uint32_t((x >> 17) % 101u);
      in.zs_load_store = (x >> 63) != 0;

      const auto c = frane_s1at1_catalog_for(in);
      const bool sys = ((x >> 5) & 1u) != 0;
      const uint64_t sample = 1 + ((x >> 11) & 0xfffffu);
      fuzz = frane_s1at1_update_state(fuzz, sys, sample, c.signature);
      assert(fuzz.score >= -16 && fuzz.score <= 16);
      assert(fuzz.volatility <= 15);

      const auto ss = frane_s1at1_unpack_snapshot(frane_s1at1_pack_snapshot(fuzz));
      const auto d = frane_s1at1_decide(true, in, ss, x);
      assert(d.effective_sysmem_probability <= 100);
      if (d.override_mode) {
         assert(d.effective_sysmem_probability >= 4);
         assert(d.effective_sysmem_probability <= 96);
         assert(d.probe_log2 >= 3 && d.probe_log2 <= 10);
      }
   }

   std::cout << "S1 AT1 contextual autotune tests passed\n";
   return 0;
}
