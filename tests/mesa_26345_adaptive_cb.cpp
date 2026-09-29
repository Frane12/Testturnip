#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>

static unsigned min_draws(int base, uint32_t tiles, uint32_t avg_bw, bool gmem)
{
   int threshold = std::max(1, base);

   if (!gmem) {
      threshold += 8;
   } else {
      if (tiles >= 16) threshold -= 4;
      else if (tiles >= 8) threshold -= 3;
      else if (tiles >= 4) threshold -= 1;
      else threshold += 2;

      if (avg_bw >= 24) threshold -= 2;
      else if (avg_bw && avg_bw <= 8) threshold += 1;
   }

   return (unsigned)std::clamp(threshold, 2, 24);
}

static bool keep_heavy(uint32_t draws, uint32_t tiles, uint32_t avg_bw,
                       unsigned keep_draws=24, unsigned keep_tiles=8)
{
   return (draws >= keep_draws && tiles >= keep_tiles) ||
          (draws >= std::max(12u, keep_draws / 2) &&
           tiles >= std::max(16u, keep_tiles * 2) &&
           avg_bw >= 16);
}

int main()
{
   // Wide/heavy GMEM passes are admitted earlier.
   assert(min_draws(8, 16, 24, true) == 2);
   assert(min_draws(8, 8, 16, true) == 5);
   assert(min_draws(8, 4, 16, true) == 7);

   // Tiny/light passes must amortize CB setup.
   assert(min_draws(8, 1, 4, true) == 11);

   // Sysmem stays conservative.
   assert(min_draws(8, 0, 0, false) == 16);

   // Heavy-pass keep policy only trips on clearly substantial work.
   assert(keep_heavy(24, 8, 0));
   assert(keep_heavy(16, 16, 16));
   assert(!keep_heavy(12, 8, 16));
   assert(!keep_heavy(24, 4, 32));

   std::puts("V45 adaptive CB policy model PASS");
   return 0;
}
