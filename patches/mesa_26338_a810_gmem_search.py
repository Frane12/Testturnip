#!/usr/bin/env python3
"""26.3.38 A810 GMEM-SEARCH.

Layered strictly on the successful V37 GMEM-MASK-LAB.

V37 uses exact subpass occupancy masks but still greedily picks the compatible
track with closest cpp / highest fill. That is locally sensible, yet there are
legal cases where keeping a compatible track free now lets later items collapse
an entire extra track.

V38 keeps V37 as the seed/fallback and adds a bounded branch-and-bound search
for small render passes:
- <= 12 GMEM items (including separate stencil items);
- hard node budget, default 1024 and clamped to 128..8192;
- V37 exact-mask layout is the initial best result;
- partial states are pruned using their exact GMEM pixel capacity as an
  optimistic upper bound (adding future tracks can never increase it);
- symmetric equivalent tracks are skipped;
- search result replaces V37 only on a strict exact gmem_pixels win.

A/B:
  TU_A810_26338_GMEM_SEARCH=1 default
  TU_A810_26338_GMEM_SEARCH=0 exact V37 behavior

Optional search budget:
  TU_A810_26338_GMEM_SEARCH_BUDGET=1024
"""
from pathlib import Path

R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.38 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.38 PASS {label}", flush=True)

anchor = r'''static struct tu_gmem_alloc *
tu_gmem_alloc(struct tu_gmem_alloc *allocs,
'''

helpers = r'''#define FRANE_26338_GMEM_SEARCH_MAX_ITEMS 12

struct frane_gmem_search_track {
   uint32_t cpp;
   uint64_t busy;
};

struct frane_gmem_search_ctx {
   const struct frane_gmem_mask_item *items;
   uint32_t item_count;
   uint32_t gmem_size;
   uint32_t gmem_align;
   uint32_t block_align_shift;
   uint32_t node_budget;
   uint32_t nodes;

   uint32_t best_pixels;
   uint32_t best_num_tracks;
   struct frane_gmem_search_track
      best_tracks[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
   uint8_t current_assignment[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
   uint8_t best_assignment[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
};

static bool
frane_a810_gmem_search_enabled(const struct tu_physical_device *phys_dev)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26338_GMEM_SEARCH", true);

   if (!enabled || !phys_dev)
      return false;

   const uint64_t id = phys_dev->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static uint32_t
frane_gmem_mask_item_count(const struct tu_render_pass *pass)
{
   uint32_t count = 0;

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment *att = &pass->attachments[i];
      if (!att->gmem)
         continue;

      count++;
      if (att->format == VK_FORMAT_D32_SFLOAT_S8_UINT)
         count++;
   }

   return count;
}

static uint32_t
frane_gmem_search_pixels(const struct frane_gmem_search_track *tracks,
                         uint32_t num_tracks,
                         uint32_t gmem_size,
                         uint32_t gmem_align,
                         uint32_t block_align_shift)
{
   if (!num_tracks || !gmem_align)
      return 0;

   const uint32_t total_blocks = gmem_size / gmem_align;
   if (!total_blocks)
      return 0;

   uint32_t min_cpp = UINT32_MAX;
   uint64_t min_needed = 0;

   for (uint32_t i = 0; i < num_tracks; i++) {
      min_cpp = MIN2(min_cpp, tracks[i].cpp);
      min_needed += frane_gmem_blocks_for_pixels(
         1, tracks[i].cpp, gmem_align, block_align_shift);
   }

   if (min_needed > total_blocks)
      return 0;

   uint32_t low = 1;
   uint32_t high = gmem_size / min_cpp;

   while (low < high) {
      const uint32_t mid = low + (high - low + 1) / 2;
      uint64_t needed = 0;

      for (uint32_t i = 0; i < num_tracks; i++) {
         needed += frane_gmem_blocks_for_pixels(
            mid, tracks[i].cpp, gmem_align, block_align_shift);
         if (needed > total_blocks)
            break;
      }

      if (needed <= total_blocks)
         low = mid;
      else
         high = mid - 1;
   }

   return low;
}

struct frane_gmem_search_option {
   uint8_t track;
   uint32_t slack;
   unsigned fill;
};

static bool
frane_gmem_search_option_before(const struct frane_gmem_search_option *a,
                                const struct frane_gmem_search_option *b)
{
   if (a->slack != b->slack)
      return a->slack < b->slack;
   if (a->fill != b->fill)
      return a->fill > b->fill;
   return a->track < b->track;
}

static void
frane_gmem_search_recurse(struct frane_gmem_search_ctx *ctx,
                          uint32_t pos,
                          struct frane_gmem_search_track *tracks,
                          uint32_t num_tracks)
{
   if (++ctx->nodes > ctx->node_budget)
      return;

   /* Existing tracks only form an optimistic upper bound: every remaining
    * item can at best reuse them for free. If a future item needs a new track,
    * exact capacity can only stay equal or decrease.
    */
   if (num_tracks > 0) {
      const uint32_t upper =
         frane_gmem_search_pixels(tracks, num_tracks,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);
      if (upper <= ctx->best_pixels)
         return;
   }

   if (pos == ctx->item_count) {
      const uint32_t pixels =
         frane_gmem_search_pixels(tracks, num_tracks,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);

      if (pixels > ctx->best_pixels) {
         ctx->best_pixels = pixels;
         ctx->best_num_tracks = num_tracks;

         for (uint32_t i = 0; i < num_tracks; i++)
            ctx->best_tracks[i] = tracks[i];

         for (uint32_t i = 0; i < ctx->item_count; i++)
            ctx->best_assignment[i] = ctx->current_assignment[i];
      }
      return;
   }

   const struct frane_gmem_mask_item *item = &ctx->items[pos];
   uint64_t item_mask = 0;
   if (!frane_subpass_range_mask(item->first_subpass,
                                 item->last_subpass,
                                 &item_mask))
      return;

   struct frane_gmem_search_option
      options[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
   uint32_t option_count = 0;

   /* Equivalent tracks lead to equivalent child states. */
   for (uint32_t i = 0; i < num_tracks; i++) {
      if (tracks[i].busy & item_mask || tracks[i].cpp < item->cpp)
         continue;

      bool duplicate = false;
      for (uint32_t j = 0; j < i; j++) {
         if (tracks[j].cpp == tracks[i].cpp &&
             tracks[j].busy == tracks[i].busy &&
             !(tracks[j].busy & item_mask) &&
             tracks[j].cpp >= item->cpp) {
            duplicate = true;
            break;
         }
      }
      if (duplicate)
         continue;

      options[option_count++] = {
         .track = (uint8_t) i,
         .slack = tracks[i].cpp - item->cpp,
         .fill = (unsigned) __builtin_popcountll(tracks[i].busy),
      };
   }

   /* Preserve V37's useful branch ordering: closest cpp, then densest track.
    * Search explores alternatives too, but promising states establish a
    * stronger best bound earlier and prune more work.
    */
   for (uint32_t i = 1; i < option_count; i++) {
      const struct frane_gmem_search_option key = options[i];
      uint32_t j = i;
      while (j > 0 &&
             frane_gmem_search_option_before(&key, &options[j - 1])) {
         options[j] = options[j - 1];
         j--;
      }
      options[j] = key;
   }

   for (uint32_t i = 0; i < option_count; i++) {
      const uint32_t track = options[i].track;
      const uint64_t old_busy = tracks[track].busy;

      tracks[track].busy |= item_mask;
      ctx->current_assignment[pos] = (uint8_t) track;

      frane_gmem_search_recurse(ctx, pos + 1, tracks, num_tracks);

      tracks[track].busy = old_busy;
      if (ctx->nodes >= ctx->node_budget)
         return;
   }

   /* Deliberately explore a new track even if reuse was possible. Sometimes
    * spending one track now preserves a scarce hole and lets several later
    * items collapse into fewer / cheaper tracks overall.
    */
   if (num_tracks < FRANE_26338_GMEM_SEARCH_MAX_ITEMS) {
      tracks[num_tracks] = {
         .cpp = item->cpp,
         .busy = item_mask,
      };
      ctx->current_assignment[pos] = (uint8_t) num_tracks;

      frane_gmem_search_recurse(ctx, pos + 1, tracks, num_tracks + 1);
   }
}

static bool
frane_refine_gmem_mask_candidate(
   const struct tu_render_pass *pass,
   struct tu_gmem_alloc *allocs,
   struct tu_gmem_alloc **att_allocs,
   uint64_t *busy_masks,
   const struct frane_gmem_mask_item *items,
   uint32_t *num_allocs,
   uint32_t gmem_size,
   uint32_t gmem_align,
   uint32_t block_align_shift)
{
   const uint32_t item_count = frane_gmem_mask_item_count(pass);

   if (item_count < 3 ||
       item_count > FRANE_26338_GMEM_SEARCH_MAX_ITEMS ||
       *num_allocs == 0 ||
       *num_allocs > FRANE_26338_GMEM_SEARCH_MAX_ITEMS)
      return false;

   struct frane_gmem_search_track
      seed[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};

   for (uint32_t i = 0; i < *num_allocs; i++) {
      seed[i].cpp = allocs[i].cpp;
      seed[i].busy = busy_masks[i];
   }

   const uint32_t seed_pixels =
      frane_gmem_search_pixels(seed, *num_allocs,
                               gmem_size, gmem_align, block_align_shift);

   int budget_opt =
      debug_get_num_option("TU_A810_26338_GMEM_SEARCH_BUDGET", 1024);
   uint32_t budget = budget_opt < 128 ? 128u : (uint32_t) budget_opt;
   budget = MIN2(budget, 8192u);

   struct frane_gmem_search_ctx ctx = {
      .items = items,
      .item_count = item_count,
      .gmem_size = gmem_size,
      .gmem_align = gmem_align,
      .block_align_shift = block_align_shift,
      .node_budget = budget,
      .nodes = 0,
      .best_pixels = seed_pixels,
      .best_num_tracks = 0,
   };

   struct frane_gmem_search_track
      tracks[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};

   frane_gmem_search_recurse(&ctx, 0, tracks, 0);

   /* No strict win: preserve the V37 candidate byte-for-byte. */
   if (ctx.best_num_tracks == 0 || ctx.best_pixels <= seed_pixels)
      return false;

   for (uint32_t i = 0; i < 2 * pass->attachment_count; i++)
      att_allocs[i] = NULL;

   for (uint32_t i = 0; i < ctx.best_num_tracks; i++) {
      allocs[i].gmem_offset = 0;
      allocs[i].cpp = ctx.best_tracks[i].cpp;
      allocs[i].first_subpass = UINT32_MAX;
      allocs[i].last_subpass = 0;
      busy_masks[i] = ctx.best_tracks[i].busy;
   }

   for (uint32_t i = 0; i < item_count; i++) {
      const struct frane_gmem_mask_item *item = &items[i];
      const uint32_t track = ctx.best_assignment[i];

      assert(track < ctx.best_num_tracks);
      att_allocs[item->slot] = &allocs[track];
      allocs[track].first_subpass =
         MIN2(allocs[track].first_subpass, item->first_subpass);
      allocs[track].last_subpass =
         MAX2(allocs[track].last_subpass, item->last_subpass);
   }

   *num_allocs = ctx.best_num_tracks;
   return true;
}

''' + anchor

edit("tu_pass.cc", anchor, helpers, "add bounded GMEM track search")

search_anchor = r'''      if (layout_impossible) {
         pass->gmem_pixels[layout] = 0;
'''

search_new = r'''      if (num_mask_alloc > 0 &&
          frane_a810_gmem_search_enabled(phys_dev)) {
         frane_refine_gmem_mask_candidate(
            pass,
            mask_gmem_alloc,
            mask_att_gmem_alloc,
            mask_busy,
            mask_items,
            &num_mask_alloc,
            gmem_size,
            gmem_align,
            block_align_shift);
      }

      if (layout_impossible) {
         pass->gmem_pixels[layout] = 0;
'''

edit("tu_pass.cc", search_anchor, search_new, "refine V37 candidate before admission/rescue")

edit(
    "tu_device.cc",
    "Turnip A810 V37 / Mesa ",
    "Turnip A810 V38 / Mesa ",
    "short driver identity",
)

p = (R / "tu_pass.cc").read_text()
d = (R / "tu_device.cc").read_text()

for needle in (
    'TU_A810_26338_GMEM_SEARCH", true',
    'TU_A810_26338_GMEM_SEARCH_BUDGET", 1024',
    "FRANE_26338_GMEM_SEARCH_MAX_ITEMS 12",
    "frane_gmem_search_recurse",
    "frane_refine_gmem_mask_candidate",
    "upper <= ctx->best_pixels",
    "ctx.best_pixels <= seed_pixels",
    "mask_pixels > pass->gmem_pixels[layout]",
    "TU_A810_26337_GMEM_MASK_PACK",
):
    assert needle in p, needle

assert "Turnip A810 V38 / Mesa " in d
print("26.3.38 A810 GMEM-SEARCH applied", flush=True)
