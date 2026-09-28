#!/usr/bin/env python3
"""26.3.34 A810 lifetime-aware + tile-effective GMEM packing.

Builds on validated 26.3.33 HYBRID-GMEM-PACK.

The upstream allocator already allows non-overlapping attachment lifetimes to
share one GMEM allocation, but its first-fit/exact-cpp preference can widen an
allocation lifetime across large subpass gaps. That can block later reuse.

This experiment computes a second lifetime-aware assignment in parallel:
- only non-overlapping lifetimes may alias;
- allocation cpp must still be >= requested cpp;
- candidates are scored by incremental lifetime*cpp waste;
- the candidate is packed with the exact same V33 hybrid packer policy;
- it is adopted only when it produces strictly more pass->gmem_pixels.
Equal or worse results keep the exact V33 allocation and offsets.

A/B:
  TU_A810_26334_GMEM_LIFETIME_TILE_PACK=1  default
  TU_A810_26334_GMEM_LIFETIME_TILE_PACK=0  exact V33 behavior

A810-only. No additional render-pass safety class is opened.
"""
from pathlib import Path

R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.34 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.34 PASS {label}", flush=True)

helper_anchor = r'''static uint32_t
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
'''

helper_new = helper_anchor + r'''
static bool
frane_a810_lifetime_tile_pack_enabled(const struct tu_physical_device *phys_dev)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26334_GMEM_LIFETIME_TILE_PACK", true);

   if (!enabled || !phys_dev)
      return false;

   const uint64_t id = phys_dev->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static struct tu_gmem_alloc *
frane_gmem_alloc_lifetime_bestfit(struct tu_gmem_alloc *allocs,
                                  uint32_t *num_allocs,
                                  uint32_t cpp,
                                  uint32_t first_subpass,
                                  uint32_t last_subpass)
{
   struct tu_gmem_alloc *best = NULL;
   uint64_t best_cost = UINT64_MAX;
   uint32_t best_cpp_slack = UINT32_MAX;
   uint32_t best_gap = UINT32_MAX;
   const uint32_t new_span = last_subpass - first_subpass + 1;

   for (uint32_t i = 0; i < *num_allocs; i++) {
      struct tu_gmem_alloc *alloc = &allocs[i];

      if (!(alloc->first_subpass > last_subpass ||
            alloc->last_subpass < first_subpass))
         continue;

      if (alloc->cpp < cpp)
         continue;

      const uint32_t gap =
         alloc->last_subpass < first_subpass ?
            first_subpass - alloc->last_subpass - 1 :
            alloc->first_subpass - last_subpass - 1;
      const uint32_t cpp_slack = alloc->cpp - cpp;

      /* Incremental occupied lifetime*cpp area:
       * - gap * alloc cpp models the false lifetime introduced by merging;
       * - cpp_slack * new span models bytes reserved but unused by this att.
       */
      const uint64_t cost =
         (uint64_t) gap * alloc->cpp +
         (uint64_t) cpp_slack * new_span;

      if (!best ||
          cost < best_cost ||
          (cost == best_cost && cpp_slack < best_cpp_slack) ||
          (cost == best_cost && cpp_slack == best_cpp_slack &&
           gap < best_gap)) {
         best = alloc;
         best_cost = cost;
         best_cpp_slack = cpp_slack;
         best_gap = gap;
      }
   }

   if (best) {
      best->first_subpass = MIN2(best->first_subpass, first_subpass);
      best->last_subpass = MAX2(best->last_subpass, last_subpass);
      return best;
   }

   best = &allocs[(*num_allocs)++];
   best->cpp = cpp;
   best->first_subpass = first_subpass;
   best->last_subpass = last_subpass;
   return best;
}

static uint32_t
frane_pack_gmem_candidate(struct tu_gmem_alloc *allocs,
                          uint32_t num_allocs,
                          uint32_t gmem_size,
                          uint32_t gmem_align,
                          uint32_t block_align_shift,
                          const struct tu_physical_device *phys_dev)
{
   if (!num_allocs)
      return 0;

   uint32_t cpp_total = 0;
   uint32_t min_cpp = UINT32_MAX;
   for (uint32_t i = 0; i < num_allocs; i++) {
      cpp_total += allocs[i].cpp;
      min_cpp = MIN2(min_cpp, allocs[i].cpp);
   }

   const uint32_t total_gmem_blocks = gmem_size / gmem_align;
   uint32_t greedy_blocks = total_gmem_blocks;
   uint32_t greedy_cpp_total = cpp_total;
   uint32_t greedy_pixels = ~0u;

   for (uint32_t i = 0; i < num_allocs; i++) {
      const struct tu_gmem_alloc *alloc = &allocs[i];
      const uint32_t align =
         MAX2(1u, alloc->cpp >> block_align_shift);
      const uint32_t nblocks =
         MAX2((greedy_blocks * alloc->cpp / greedy_cpp_total) &
                 ~(align - 1),
              align);

      if (nblocks > greedy_blocks)
         return 0;

      greedy_blocks -= nblocks;
      greedy_cpp_total -= alloc->cpp;
      greedy_pixels =
         MIN2(greedy_pixels, nblocks * gmem_align / alloc->cpp);
   }

   bool use_balanced =
      frane_a810_hybrid_gmem_pack_enabled(phys_dev) && num_allocs > 1;
   uint32_t balanced_pixels = greedy_pixels;

   if (use_balanced) {
      uint32_t low = 0;
      uint32_t high = gmem_size / min_cpp;

      while (low < high) {
         const uint32_t mid = low + (high - low + 1) / 2;
         uint64_t needed = 0;

         for (uint32_t i = 0; i < num_allocs; i++) {
            needed += frane_gmem_blocks_for_pixels(
               mid, allocs[i].cpp, gmem_align, block_align_shift);
            if (needed > total_gmem_blocks)
               break;
         }

         if (needed <= total_gmem_blocks)
            low = mid;
         else
            high = mid - 1;
      }

      balanced_pixels = low;
      use_balanced = balanced_pixels > greedy_pixels;
   }

   uint32_t gmem_blocks = total_gmem_blocks;
   uint32_t offset = 0;
   uint32_t pixels = ~0u;

   if (use_balanced) {
      for (uint32_t i = 0; i < num_allocs; i++) {
         struct tu_gmem_alloc *alloc = &allocs[i];
         const uint32_t nblocks = frane_gmem_blocks_for_pixels(
            balanced_pixels, alloc->cpp, gmem_align, block_align_shift);

         if (nblocks > gmem_blocks)
            return 0;

         gmem_blocks -= nblocks;
         alloc->gmem_offset = offset;
         offset += nblocks * gmem_align;
         pixels = MIN2(pixels, nblocks * gmem_align / alloc->cpp);
      }

      assert(pixels >= greedy_pixels);
   } else {
      uint32_t remaining_cpp = cpp_total;

      for (uint32_t i = 0; i < num_allocs; i++) {
         struct tu_gmem_alloc *alloc = &allocs[i];
         const uint32_t align =
            MAX2(1u, alloc->cpp >> block_align_shift);
         const uint32_t nblocks =
            MAX2((gmem_blocks * alloc->cpp / remaining_cpp) &
                    ~(align - 1),
                 align);

         if (nblocks > gmem_blocks)
            return 0;

         gmem_blocks -= nblocks;
         remaining_cpp -= alloc->cpp;
         alloc->gmem_offset = offset;
         offset += nblocks * gmem_align;
         pixels = MIN2(pixels, nblocks * gmem_align / alloc->cpp);
      }
   }

   return pixels;
}
'''

edit("tu_pass.cc", helper_anchor, helper_new, "add lifetime/tile candidate helpers")

edit(
    "tu_pass.cc",
    r'''   STACK_ARRAY(struct tu_gmem_alloc, gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, att_gmem_alloc, 2 * pass->attachment_count);
''',
    r'''   STACK_ARRAY(struct tu_gmem_alloc, gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, att_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc, lifetime_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, lifetime_att_gmem_alloc, 2 * pass->attachment_count);
''',
    "allocate parallel lifetime candidate arrays",
)

candidate_insert = r'''      uint32_t cpp_total = 0;
      uint32_t min_cpp = UINT32_MAX;
'''

candidate_new = r'''      uint32_t num_lifetime_alloc = 0;
      for (int i = 0; i < 2 * pass->attachment_count; i++)
         lifetime_att_gmem_alloc[i] = NULL;

      if (frane_a810_lifetime_tile_pack_enabled(phys_dev)) {
         for (uint32_t i = 0; i < pass->attachment_count; i++) {
            struct tu_render_pass_attachment *att = &pass->attachments[i];
            if (!att->gmem)
               continue;

            lifetime_att_gmem_alloc[i * 2] =
               frane_gmem_alloc_lifetime_bestfit(
                  lifetime_gmem_alloc, &num_lifetime_alloc, att->cpp,
                  att->first_subpass_idx, att->last_subpass_idx);

            if (att->format == VK_FORMAT_D32_SFLOAT_S8_UINT) {
               lifetime_att_gmem_alloc[i * 2 + 1] =
                  frane_gmem_alloc_lifetime_bestfit(
                     lifetime_gmem_alloc, &num_lifetime_alloc, att->samples,
                     att->first_subpass_idx, att->last_subpass_idx);
            }
         }
      }

      uint32_t cpp_total = 0;
      uint32_t min_cpp = UINT32_MAX;
'''

edit("tu_pass.cc", candidate_insert, candidate_new, "build lifetime-aware allocation candidate")

final_old = r'''      pass->gmem_pixels[layout] = pixels;

      for (i = 0; i < pass->attachment_count; i++) {
         struct tu_render_pass_attachment *att = &pass->attachments[i];
         if (!att->gmem)
            continue;

         att->gmem_offset[layout] = att_gmem_alloc[2 * i]->gmem_offset;
         if (att->format == VK_FORMAT_D32_SFLOAT_S8_UINT)
            att->gmem_offset_stencil[layout] = att_gmem_alloc[2 * i + 1]->gmem_offset;
      }
'''

final_new = r'''      pass->gmem_pixels[layout] = pixels;

      struct tu_gmem_alloc **chosen_att_gmem_alloc = att_gmem_alloc;

      if (num_lifetime_alloc > 0 &&
          frane_a810_lifetime_tile_pack_enabled(phys_dev)) {
         const uint32_t candidate_pixels =
            frane_pack_gmem_candidate(lifetime_gmem_alloc,
                                      num_lifetime_alloc,
                                      gmem_size,
                                      gmem_align,
                                      block_align_shift,
                                      phys_dev);

         /* Tile-effective admission: only alter V33's offsets when the
          * lifetime-aware plan increases the actual GMEM pixel capacity.
          * Equal results are intentionally byte-for-byte V33.
          */
         if (candidate_pixels > pixels) {
            pass->gmem_pixels[layout] = candidate_pixels;
            chosen_att_gmem_alloc = lifetime_att_gmem_alloc;
         }
      }

      for (i = 0; i < pass->attachment_count; i++) {
         struct tu_render_pass_attachment *att = &pass->attachments[i];
         if (!att->gmem)
            continue;

         att->gmem_offset[layout] = chosen_att_gmem_alloc[2 * i]->gmem_offset;
         if (att->format == VK_FORMAT_D32_SFLOAT_S8_UINT)
            att->gmem_offset_stencil[layout] =
               chosen_att_gmem_alloc[2 * i + 1]->gmem_offset;
      }
'''

edit("tu_pass.cc", final_old, final_new, "admit lifetime layout only on strict tile-capacity win")

edit(
    "tu_pass.cc",
    r'''out:
   STACK_ARRAY_FINISH(gmem_alloc);
   STACK_ARRAY_FINISH(att_gmem_alloc);
}
''',
    r'''out:
   STACK_ARRAY_FINISH(gmem_alloc);
   STACK_ARRAY_FINISH(att_gmem_alloc);
   STACK_ARRAY_FINISH(lifetime_gmem_alloc);
   STACK_ARRAY_FINISH(lifetime_att_gmem_alloc);
}
''',
    "finish lifetime candidate arrays",
)

edit(
    "tu_device.cc",
    "Frane Mesa 26.3.33 A810 HYBRID-GMEM-PACK EXP / Mesa ",
    "Frane Mesa 26.3.34 A810 LIFETIME-TILE-PACK EXP / Mesa ",
    "driver identity",
)

p = (R / "tu_pass.cc").read_text()
d = (R / "tu_device.cc").read_text()
for x in [
    'TU_A810_26334_GMEM_LIFETIME_TILE_PACK", true',
    'frane_gmem_alloc_lifetime_bestfit',
    'frane_pack_gmem_candidate',
    'candidate_pixels > pixels',
    'chosen_att_gmem_alloc = lifetime_att_gmem_alloc',
    'frane_a810_hybrid_gmem_pack_enabled(phys_dev)',
]:
    assert x in p, x

assert "Frane Mesa 26.3.34 A810 LIFETIME-TILE-PACK EXP" in d
print("26.3.34 A810 lifetime/tile GMEM packing applied", flush=True)
