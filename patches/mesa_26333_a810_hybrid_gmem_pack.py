#!/usr/bin/env python3
"""26.3.33 A810 hybrid GMEM packing.

Builds on the validated 26.3.32 performance baseline and changes only GMEM
block distribution. Mesa's current allocator contains a TODO noting that its
proportional greedy split is not always optimal for mixed cpp attachments.

This experiment keeps both policies:
- upstream greedy allocator is computed first as the known-good baseline;
- a balanced max-min allocator computes the largest common pixel capacity
  that fits all GMEM allocations after each allocation's block alignment;
- balanced packing is used only when it strictly increases pass->gmem_pixels.
  Otherwise the exact upstream greedy layout is retained.

A/B:
  TU_A810_26333_GMEM_HYBRID_PACK=1  default
  TU_A810_26333_GMEM_HYBRID_PACK=0  exact upstream packing

A810-only. No render-pass safety classes are opened here.
"""
from pathlib import Path
R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.33 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.33 PASS {label}", flush=True)

edit(
    "tu_pass.cc",
    '#include "util/xxhash.h"\n',
    '#include "util/xxhash.h"\n#include "util/u_debug.h"\n',
    "include debug option helper",
)

edit(
    "tu_pass.cc",
    r'''struct tu_gmem_alloc {
   uint32_t gmem_offset;
   uint32_t cpp;
   uint32_t first_subpass;
   uint32_t last_subpass;
};
''',
    r'''struct tu_gmem_alloc {
   uint32_t gmem_offset;
   uint32_t cpp;
   uint32_t first_subpass;
   uint32_t last_subpass;
};

static bool
frane_a810_hybrid_gmem_pack_enabled(const struct tu_physical_device *phys_dev)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26333_GMEM_HYBRID_PACK", true);

   if (!enabled || !phys_dev)
      return false;

   const uint64_t id = phys_dev->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static uint32_t
frane_gmem_blocks_for_pixels(uint32_t pixels, uint32_t cpp,
                             uint32_t gmem_align,
                             uint32_t block_align_shift)
{
   const uint32_t align = MAX2(1u, cpp >> block_align_shift);
   uint64_t nblocks =
      DIV_ROUND_UP((uint64_t) pixels * cpp, (uint64_t) gmem_align);

   nblocks = MAX2(nblocks, (uint64_t) align);
   nblocks = (nblocks + align - 1) & ~((uint64_t) align - 1);

   return nblocks > UINT32_MAX ? UINT32_MAX : (uint32_t) nblocks;
}
''',
    "add A810 hybrid packing helpers",
)

old=r'''      /* TODO: this algorithm isn't optimal
       * for example, two attachments with cpp = {1, 4}
       * result:  nblocks = {12, 52}, pixels = 196608
       * optimal: nblocks = {13, 51}, pixels = 208896
       */
      uint32_t gmem_size = phys_dev->usable_gmem_size_gmem;
      if (layout == TU_GMEM_LAYOUT_AVOID_CCU) {
         gmem_size = MIN2(gmem_size, phys_dev->config_gmem.color_ccu_offset);
         if (custom_resolve_depth_stencil)
            gmem_size = MIN2(gmem_size, phys_dev->config_gmem.depth_ccu_offset);
      }
      uint32_t gmem_blocks = gmem_size / gmem_align;
      uint32_t offset = 0, pixels = ~0u, i;
      bool layout_impossible = false;
      for (i = 0; i < num_gmem_alloc; i++) {
         struct tu_gmem_alloc *alloc = &gmem_alloc[i];

         uint32_t align = MAX2(1, alloc->cpp >> block_align_shift);
         uint32_t nblocks = MAX2((gmem_blocks * alloc->cpp / cpp_total) & ~(align - 1), align);

         if (nblocks > gmem_blocks) {
            /* gmem layout impossible */
            layout_impossible = true;
            break;
         }

         gmem_blocks -= nblocks;
         cpp_total -= alloc->cpp;
         alloc->gmem_offset = offset;
         offset += nblocks * gmem_align;
         pixels = MIN2(pixels, nblocks * gmem_align / alloc->cpp);
      }

      /* Impossible layouts have no valid GMEM offsets. */
      if (layout_impossible) {
         pass->gmem_pixels[layout] = 0;
         continue;
      }

      pass->gmem_pixels[layout] = pixels;
'''

new=r'''      uint32_t gmem_size = phys_dev->usable_gmem_size_gmem;
      if (layout == TU_GMEM_LAYOUT_AVOID_CCU) {
         gmem_size = MIN2(gmem_size, phys_dev->config_gmem.color_ccu_offset);
         if (custom_resolve_depth_stencil)
            gmem_size = MIN2(gmem_size, phys_dev->config_gmem.depth_ccu_offset);
      }

      const uint32_t total_gmem_blocks = gmem_size / gmem_align;

      /* First calculate the exact upstream greedy result. This remains our
       * fallback and also gives us a hard floor: the hybrid policy is never
       * allowed to reduce the available pixels.
       */
      uint32_t greedy_blocks = total_gmem_blocks;
      uint32_t greedy_cpp_total = cpp_total;
      uint32_t greedy_pixels = ~0u;
      bool layout_impossible = false;

      for (uint32_t i = 0; i < num_gmem_alloc; i++) {
         const struct tu_gmem_alloc *alloc = &gmem_alloc[i];
         const uint32_t align =
            MAX2(1u, alloc->cpp >> block_align_shift);
         const uint32_t nblocks =
            MAX2((greedy_blocks * alloc->cpp / greedy_cpp_total) &
                    ~(align - 1),
                 align);

         if (nblocks > greedy_blocks) {
            layout_impossible = true;
            break;
         }

         greedy_blocks -= nblocks;
         greedy_cpp_total -= alloc->cpp;
         greedy_pixels =
            MIN2(greedy_pixels, nblocks * gmem_align / alloc->cpp);
      }

      if (layout_impossible) {
         pass->gmem_pixels[layout] = 0;
         continue;
      }

      bool use_balanced =
         frane_a810_hybrid_gmem_pack_enabled(phys_dev) &&
         num_gmem_alloc > 1;
      uint32_t balanced_pixels = greedy_pixels;

      if (use_balanced) {
         /* Exact max-min search. For a target pixel capacity P, each
          * allocation needs ceil(P * cpp / gmem_align) blocks, rounded up to
          * that allocation's block granularity. Feasibility is monotonic, so
          * binary search finds the best common pixel capacity.
          */
         uint32_t low = 0;
         uint32_t high = gmem_size / min_cpp;

         while (low < high) {
            const uint32_t mid = low + (high - low + 1) / 2;
            uint64_t needed = 0;

            for (uint32_t i = 0; i < num_gmem_alloc; i++) {
               needed += frane_gmem_blocks_for_pixels(
                  mid, gmem_alloc[i].cpp, gmem_align, block_align_shift);
               if (needed > total_gmem_blocks)
                  break;
            }

            if (needed <= total_gmem_blocks)
               low = mid;
            else
               high = mid - 1;
         }

         balanced_pixels = low;

         /* Hybrid policy: preserve the upstream layout unless the balanced
          * packing produces a strict capacity win. Equal-result cases keep
          * the known-good offset layout byte-for-byte.
          */
         use_balanced = balanced_pixels > greedy_pixels;
      }

      uint32_t gmem_blocks = total_gmem_blocks;
      uint32_t offset = 0;
      uint32_t pixels = ~0u;
      uint32_t i;

      if (use_balanced) {
         for (uint32_t i = 0; i < num_gmem_alloc; i++) {
            struct tu_gmem_alloc *alloc = &gmem_alloc[i];
            const uint32_t nblocks = frane_gmem_blocks_for_pixels(
               balanced_pixels, alloc->cpp, gmem_align, block_align_shift);

            assert(nblocks <= gmem_blocks);
            gmem_blocks -= nblocks;
            alloc->gmem_offset = offset;
            offset += nblocks * gmem_align;
            pixels = MIN2(pixels, nblocks * gmem_align / alloc->cpp);
         }

         assert(pixels >= greedy_pixels);
      } else {
         uint32_t remaining_cpp = cpp_total;

         for (uint32_t i = 0; i < num_gmem_alloc; i++) {
            struct tu_gmem_alloc *alloc = &gmem_alloc[i];
            const uint32_t align =
               MAX2(1u, alloc->cpp >> block_align_shift);
            const uint32_t nblocks =
               MAX2((gmem_blocks * alloc->cpp / remaining_cpp) &
                       ~(align - 1),
                    align);

            assert(nblocks <= gmem_blocks);
            gmem_blocks -= nblocks;
            remaining_cpp -= alloc->cpp;
            alloc->gmem_offset = offset;
            offset += nblocks * gmem_align;
            pixels = MIN2(pixels, nblocks * gmem_align / alloc->cpp);
         }
      }

      pass->gmem_pixels[layout] = pixels;
'''

edit("tu_pass.cc",old,new,"replace greedy-only allocation with hybrid max-min packing")

edit(
    "tu_device.cc",
    "Frane Mesa 26.3.32 A810 GMEM-PERF-BASE EXP / Mesa ",
    "Frane Mesa 26.3.33 A810 HYBRID-GMEM-PACK EXP / Mesa ",
    "driver identity",
)

p=(R/"tu_pass.cc").read_text()
d=(R/"tu_device.cc").read_text()
for x in [
    'TU_A810_26333_GMEM_HYBRID_PACK", true',
    'frane_gmem_blocks_for_pixels',
    'balanced_pixels > greedy_pixels',
    'assert(pixels >= greedy_pixels)',
    'const uint64_t id = phys_dev->dev_id.chip_id',
]:
    assert x in p, x

assert "Frane Mesa 26.3.33 A810 HYBRID-GMEM-PACK EXP" in d
print("26.3.33 A810 hybrid GMEM packing applied", flush=True)
