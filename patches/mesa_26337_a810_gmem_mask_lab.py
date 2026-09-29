#!/usr/bin/env python3
"""26.3.37 A810 GMEM-MASK-LAB.

Risky GMEM allocator experiment layered on validated V35.

The existing allocator (including V34 lifetime packing) represents reuse with a
single [first_subpass,last_subpass] envelope.  Once disjoint lifetimes have
been merged, holes inside that envelope are lost and cannot be reused later.
It is also attachment-order dependent because a small-cpp track created first
cannot later host a larger-cpp attachment.

V37 adds a parallel A810-only candidate:
- exact subpass occupancy mask for render passes with <=64 subpasses;
- attachment entries sorted by descending cpp, then lifetime length;
- dense best-fit reuse of tracks with no occupied-subpass overlap;
- exact max-min GMEM block packing independent of the baseline greedy result;
- candidate adopted only on a strict gmem_pixels win;
- if the baseline layout is "impossible", the candidate may rescue it only if
  the exact packer proves a valid non-zero layout.

A/B:
  TU_A810_26337_GMEM_MASK_PACK=1  default
  TU_A810_26337_GMEM_MASK_PACK=0  exact V35 behavior
"""
from pathlib import Path

R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.37 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.37 PASS {label}", flush=True)

anchor = r'''static struct tu_gmem_alloc *
tu_gmem_alloc(struct tu_gmem_alloc *allocs,
'''

helpers = r'''struct frane_gmem_mask_item {
   uint32_t slot;
   uint32_t cpp;
   uint32_t first_subpass;
   uint32_t last_subpass;
};

static bool
frane_a810_gmem_mask_pack_enabled(const struct tu_physical_device *phys_dev)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26337_GMEM_MASK_PACK", true);

   if (!enabled || !phys_dev)
      return false;

   const uint64_t id = phys_dev->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_subpass_range_mask(uint32_t first, uint32_t last, uint64_t *mask)
{
   if (first > last || last >= 64)
      return false;

   const uint32_t len = last - first + 1;
   if (len == 64) {
      *mask = UINT64_MAX;
   } else {
      *mask = ((UINT64_C(1) << len) - 1) << first;
   }
   return true;
}

static bool
frane_mask_item_before(const struct frane_gmem_mask_item *a,
                       const struct frane_gmem_mask_item *b)
{
   if (a->cpp != b->cpp)
      return a->cpp > b->cpp;

   const uint32_t a_span = a->last_subpass - a->first_subpass + 1;
   const uint32_t b_span = b->last_subpass - b->first_subpass + 1;
   if (a_span != b_span)
      return a_span > b_span;

   if (a->first_subpass != b->first_subpass)
      return a->first_subpass < b->first_subpass;

   return a->slot < b->slot;
}

static bool
frane_build_gmem_mask_candidate(
   const struct tu_render_pass *pass,
   struct tu_gmem_alloc *allocs,
   struct tu_gmem_alloc **att_allocs,
   uint64_t *busy_masks,
   struct frane_gmem_mask_item *items,
   uint32_t *num_allocs_out)
{
   if (!pass || pass->subpass_count <= 1 || pass->subpass_count > 64)
      return false;

   const uint32_t slots = 2 * pass->attachment_count;
   for (uint32_t i = 0; i < slots; i++)
      att_allocs[i] = NULL;

   uint32_t item_count = 0;
   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment *att = &pass->attachments[i];
      if (!att->gmem)
         continue;

      items[item_count++] = {
         .slot = 2 * i,
         .cpp = att->cpp,
         .first_subpass = att->first_subpass_idx,
         .last_subpass = att->last_subpass_idx,
      };

      if (att->format == VK_FORMAT_D32_SFLOAT_S8_UINT) {
         items[item_count++] = {
            .slot = 2 * i + 1,
            .cpp = att->samples,
            .first_subpass = att->first_subpass_idx,
            .last_subpass = att->last_subpass_idx,
         };
      }
   }

   if (item_count <= 1)
      return false;

   /* Small fixed-size insertion sort. Render-pass attachment counts are tiny,
    * and doing this at pass creation keeps runtime draw/submit paths untouched.
    * Processing larger cpp first removes the old order dependency where a
    * small track created early cannot later be upgraded for a larger cpp.
    */
   for (uint32_t i = 1; i < item_count; i++) {
      const struct frane_gmem_mask_item key = items[i];
      uint32_t j = i;
      while (j > 0 && frane_mask_item_before(&key, &items[j - 1])) {
         items[j] = items[j - 1];
         j--;
      }
      items[j] = key;
   }

   uint32_t num_allocs = 0;

   for (uint32_t n = 0; n < item_count; n++) {
      const struct frane_gmem_mask_item *item = &items[n];
      uint64_t mask = 0;
      if (!frane_subpass_range_mask(item->first_subpass,
                                    item->last_subpass,
                                    &mask))
         return false;

      uint32_t best = UINT32_MAX;
      uint32_t best_slack = UINT32_MAX;
      unsigned best_fill = 0;

      for (uint32_t i = 0; i < num_allocs; i++) {
         if (busy_masks[i] & mask)
            continue;
         if (allocs[i].cpp < item->cpp)
            continue;

         const uint32_t slack = allocs[i].cpp - item->cpp;
         const unsigned fill = __builtin_popcountll(busy_masks[i]);

         /* First use the closest cpp, then pack into the already-busiest
          * compatible track. Exact masks preserve holes, so denser tracks
          * leave more completely free alternatives for later items.
          */
         if (best == UINT32_MAX ||
             slack < best_slack ||
             (slack == best_slack && fill > best_fill)) {
            best = i;
            best_slack = slack;
            best_fill = fill;
         }
      }

      if (best == UINT32_MAX) {
         best = num_allocs++;
         allocs[best].gmem_offset = 0;
         allocs[best].cpp = item->cpp;
         allocs[best].first_subpass = item->first_subpass;
         allocs[best].last_subpass = item->last_subpass;
         busy_masks[best] = mask;
      } else {
         allocs[best].first_subpass =
            MIN2(allocs[best].first_subpass, item->first_subpass);
         allocs[best].last_subpass =
            MAX2(allocs[best].last_subpass, item->last_subpass);
         busy_masks[best] |= mask;
      }

      att_allocs[item->slot] = &allocs[best];
   }

   *num_allocs_out = num_allocs;
   return num_allocs > 0;
}

static uint32_t
frane_pack_gmem_exact(struct tu_gmem_alloc *allocs,
                      uint32_t num_allocs,
                      uint32_t gmem_size,
                      uint32_t gmem_align,
                      uint32_t block_align_shift)
{
   if (!num_allocs || !gmem_align)
      return 0;

   const uint32_t total_blocks = gmem_size / gmem_align;
   if (!total_blocks)
      return 0;

   uint32_t min_cpp = UINT32_MAX;
   uint64_t min_needed = 0;
   for (uint32_t i = 0; i < num_allocs; i++) {
      min_cpp = MIN2(min_cpp, allocs[i].cpp);
      min_needed += frane_gmem_blocks_for_pixels(
         1, allocs[i].cpp, gmem_align, block_align_shift);
   }

   if (min_needed > total_blocks)
      return 0;

   uint32_t low = 1;
   uint32_t high = gmem_size / min_cpp;

   while (low < high) {
      const uint32_t mid = low + (high - low + 1) / 2;
      uint64_t needed = 0;

      for (uint32_t i = 0; i < num_allocs; i++) {
         needed += frane_gmem_blocks_for_pixels(
            mid, allocs[i].cpp, gmem_align, block_align_shift);
         if (needed > total_blocks)
            break;
      }

      if (needed <= total_blocks)
         low = mid;
      else
         high = mid - 1;
   }

   uint32_t remaining = total_blocks;
   uint32_t offset = 0;
   uint32_t actual_pixels = UINT32_MAX;

   for (uint32_t i = 0; i < num_allocs; i++) {
      const uint32_t nblocks = frane_gmem_blocks_for_pixels(
         low, allocs[i].cpp, gmem_align, block_align_shift);

      if (nblocks > remaining)
         return 0;

      remaining -= nblocks;
      allocs[i].gmem_offset = offset;
      offset += nblocks * gmem_align;
      actual_pixels =
         MIN2(actual_pixels, nblocks * gmem_align / allocs[i].cpp);
   }

   return actual_pixels;
}

''' + anchor

edit("tu_pass.cc", anchor, helpers, "add exact-mask allocator and exact packer")

edit(
    "tu_pass.cc",
    r'''   STACK_ARRAY(struct tu_gmem_alloc, lifetime_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, lifetime_att_gmem_alloc, 2 * pass->attachment_count);

   const bool frane_lifetime_pack =
      frane_a810_lifetime_tile_pack_enabled(phys_dev);
''',
    r'''   STACK_ARRAY(struct tu_gmem_alloc, lifetime_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, lifetime_att_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc, mask_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, mask_att_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(uint64_t, mask_busy, 2 * pass->attachment_count);
   STACK_ARRAY(struct frane_gmem_mask_item, mask_items, 2 * pass->attachment_count);

   const bool frane_lifetime_pack =
      frane_a810_lifetime_tile_pack_enabled(phys_dev);
   const bool frane_mask_pack =
      frane_a810_gmem_mask_pack_enabled(phys_dev);
''',
    "allocate mask candidate scratch and cache gate",
)

build_anchor = r'''      uint32_t cpp_total = 0;
      uint32_t min_cpp = UINT32_MAX;
'''

build_new = r'''      uint32_t num_mask_alloc = 0;
      const bool try_mask_pack =
         frane_mask_pack &&
         pass->subpass_count > 1 &&
         pass->subpass_count <= 64 &&
         num_gmem_alloc > 1;

      if (try_mask_pack) {
         if (!frane_build_gmem_mask_candidate(
                pass, mask_gmem_alloc, mask_att_gmem_alloc,
                mask_busy, mask_items, &num_mask_alloc)) {
            num_mask_alloc = 0;
         }
      }

      uint32_t cpp_total = 0;
      uint32_t min_cpp = UINT32_MAX;
'''

edit("tu_pass.cc", build_anchor, build_new, "build exact-mask candidate per layout")

impossible_old = r'''      if (layout_impossible) {
         pass->gmem_pixels[layout] = 0;
         continue;
      }
'''

impossible_new = r'''      if (layout_impossible) {
         pass->gmem_pixels[layout] = 0;

         /* V33-V35 stopped here. V37 gives the exact-mask candidate one
          * chance to rescue the layout. A non-zero exact pack proves that
          * every track fits with aligned offsets; otherwise preserve V35.
          */
         if (num_mask_alloc > 0) {
            const uint32_t rescued_pixels =
               frane_pack_gmem_exact(mask_gmem_alloc,
                                     num_mask_alloc,
                                     gmem_size,
                                     gmem_align,
                                     block_align_shift);

            if (rescued_pixels > 0) {
               pass->gmem_pixels[layout] = rescued_pixels;
               for (uint32_t a = 0; a < pass->attachment_count; a++) {
                  struct tu_render_pass_attachment *att =
                     &pass->attachments[a];
                  if (!att->gmem)
                     continue;

                  att->gmem_offset[layout] =
                     mask_att_gmem_alloc[2 * a]->gmem_offset;
                  if (att->format == VK_FORMAT_D32_SFLOAT_S8_UINT) {
                     att->gmem_offset_stencil[layout] =
                        mask_att_gmem_alloc[2 * a + 1]->gmem_offset;
                  }
               }
            }
         }

         continue;
      }
'''

edit("tu_pass.cc", impossible_old, impossible_new, "allow exact-mask rescue of impossible baseline")

final_anchor = r'''      for (i = 0; i < pass->attachment_count; i++) {
         struct tu_render_pass_attachment *att = &pass->attachments[i];
         if (!att->gmem)
            continue;

         att->gmem_offset[layout] = chosen_att_gmem_alloc[2 * i]->gmem_offset;
         if (att->format == VK_FORMAT_D32_SFLOAT_S8_UINT)
            att->gmem_offset_stencil[layout] =
               chosen_att_gmem_alloc[2 * i + 1]->gmem_offset;
      }
'''

final_new = r'''      if (num_mask_alloc > 0 &&
          frane_lifetime_candidate_can_beat(mask_gmem_alloc,
                                            num_mask_alloc,
                                            gmem_size,
                                            pass->gmem_pixels[layout])) {
         const uint32_t mask_pixels =
            frane_pack_gmem_exact(mask_gmem_alloc,
                                  num_mask_alloc,
                                  gmem_size,
                                  gmem_align,
                                  block_align_shift);

         if (mask_pixels > pass->gmem_pixels[layout]) {
            pass->gmem_pixels[layout] = mask_pixels;
            chosen_att_gmem_alloc = mask_att_gmem_alloc;
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

edit("tu_pass.cc", final_anchor, final_new, "admit mask layout only on strict capacity win")

edit(
    "tu_pass.cc",
    r'''   STACK_ARRAY_FINISH(lifetime_gmem_alloc);
   STACK_ARRAY_FINISH(lifetime_att_gmem_alloc);
}
''',
    r'''   STACK_ARRAY_FINISH(lifetime_gmem_alloc);
   STACK_ARRAY_FINISH(lifetime_att_gmem_alloc);
   STACK_ARRAY_FINISH(mask_gmem_alloc);
   STACK_ARRAY_FINISH(mask_att_gmem_alloc);
   STACK_ARRAY_FINISH(mask_busy);
   STACK_ARRAY_FINISH(mask_items);
}
''',
    "finish mask candidate scratch arrays",
)

edit(
    "tu_device.cc",
    "Turnip A810 V35 / Mesa ",
    "Turnip A810 V37 / Mesa ",
    "short driver identity",
)

p = (R / "tu_pass.cc").read_text()
d = (R / "tu_device.cc").read_text()

for needle in (
    'TU_A810_26337_GMEM_MASK_PACK", true',
    "frane_build_gmem_mask_candidate",
    "frane_pack_gmem_exact",
    "pass->subpass_count <= 64",
    "rescued_pixels > 0",
    "mask_pixels > pass->gmem_pixels[layout]",
    "candidate_pixels > pixels",
    "frane_lifetime_candidate_can_beat",
):
    assert needle in p, needle

assert "Turnip A810 V37 / Mesa " in d
print("26.3.37 A810 GMEM-MASK-LAB applied", flush=True)
