#!/usr/bin/env python3
"""26.3.39 A810 GMEM-PRESSURE.

Layered strictly on V38 GMEM-SEARCH.

V38's branch-and-bound uses only the tracks already created by a partial
assignment as its optimistic upper bound. That bound is safe, but weak: it
assumes every remaining item might reuse existing tracks for free.

V39 adds a future-aware subpass pressure bound. For each remaining subpass it
computes an optimistic minimum set of additional tracks that must exist at that
subpass after matching active items against currently-free compatible tracks.
The tightest subpass bound is still optimistic, so pruning is safe.

The stronger bound cuts search work enough to expand the searched item limit
from 12 to 16 and raise the default node budget from 1024 to 4096.

A/B:
  TU_A810_26339_GMEM_PRESSURE_BOUND=1 default
  TU_A810_26339_GMEM_PRESSURE_BOUND=0 exact V38 search behavior

Optional V39 budget:
  TU_A810_26339_GMEM_SEARCH_BUDGET=4096
"""
from pathlib import Path

R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.39 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.39 PASS {label}", flush=True)

edit(
    "tu_pass.cc",
    "#define FRANE_26338_GMEM_SEARCH_MAX_ITEMS 12\n",
    "#define FRANE_26338_GMEM_SEARCH_MAX_ITEMS 16\n",
    "expand bounded search scratch to 16 items",
)

edit(
    "tu_pass.cc",
    r'''   uint32_t node_budget;
   uint32_t nodes;

   uint32_t best_pixels;
''',
    r'''   uint32_t node_budget;
   uint32_t nodes;
   bool future_pressure;

   uint32_t best_pixels;
''',
    "track future-pressure mode in search context",
)

gate_anchor = r'''static uint32_t
frane_gmem_mask_item_count(const struct tu_render_pass *pass)
'''

gate_new = r'''static bool
frane_a810_gmem_pressure_bound_enabled(void)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26339_GMEM_PRESSURE_BOUND", true);
   return enabled;
}

static uint32_t
frane_gmem_mask_item_count(const struct tu_render_pass *pass)
'''

edit(
    "tu_pass.cc",
    gate_anchor,
    gate_new,
    "add V39 future-pressure A/B gate",
)

helper_anchor = r'''struct frane_gmem_search_option {
   uint8_t track;
   uint32_t slack;
   unsigned fill;
};
'''

helper_new = r'''static uint32_t
frane_gmem_search_future_upper(const struct frane_gmem_search_ctx *ctx,
                               uint32_t pos,
                               const struct frane_gmem_search_track *tracks,
                               uint32_t num_tracks)
{
   if (pos >= ctx->item_count)
      return frane_gmem_search_pixels(tracks, num_tracks,
                                      ctx->gmem_size,
                                      ctx->gmem_align,
                                      ctx->block_align_shift);

   uint32_t upper = UINT32_MAX;
   if (num_tracks > 0) {
      upper = frane_gmem_search_pixels(tracks, num_tracks,
                                       ctx->gmem_size,
                                       ctx->gmem_align,
                                       ctx->block_align_shift);
   }

   uint64_t remaining_subpasses = 0;
   for (uint32_t i = pos; i < ctx->item_count; i++) {
      uint64_t item_mask = 0;
      if (!frane_subpass_range_mask(ctx->items[i].first_subpass,
                                    ctx->items[i].last_subpass,
                                    &item_mask))
         return upper;
      remaining_subpasses |= item_mask;
   }

   while (remaining_subpasses) {
      const uint32_t subpass = (uint32_t) __builtin_ctzll(remaining_subpasses);
      const uint64_t bit = UINT64_C(1) << subpass;
      remaining_subpasses &= remaining_subpasses - 1;

      uint32_t active_cpp[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
      uint32_t active_count = 0;

      for (uint32_t i = pos; i < ctx->item_count; i++) {
         uint64_t item_mask = 0;
         if (!frane_subpass_range_mask(ctx->items[i].first_subpass,
                                       ctx->items[i].last_subpass,
                                       &item_mask))
            continue;
         if (item_mask & bit)
            active_cpp[active_count++] = ctx->items[i].cpp;
      }

      /* Largest active cpp first. This makes the greedy matching below an
       * optimistic maximum reuse of existing free tracks at this subpass.
       */
      for (uint32_t i = 1; i < active_count; i++) {
         const uint32_t key = active_cpp[i];
         uint32_t j = i;
         while (j > 0 && key > active_cpp[j - 1]) {
            active_cpp[j] = active_cpp[j - 1];
            j--;
         }
         active_cpp[j] = key;
      }

      uint32_t free_cpp[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
      uint32_t free_count = 0;

      struct frane_gmem_search_track
         pressure[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};
      uint32_t pressure_count = num_tracks;

      for (uint32_t i = 0; i < num_tracks; i++) {
         pressure[i] = tracks[i];
         if (!(tracks[i].busy & bit))
            free_cpp[free_count++] = tracks[i].cpp;
      }

      for (uint32_t i = 1; i < free_count; i++) {
         const uint32_t key = free_cpp[i];
         uint32_t j = i;
         while (j > 0 && key < free_cpp[j - 1]) {
            free_cpp[j] = free_cpp[j - 1];
            j--;
         }
         free_cpp[j] = key;
      }

      for (uint32_t i = 0; i < active_count; i++) {
         const uint32_t cpp = active_cpp[i];
         uint32_t match = UINT32_MAX;

         for (uint32_t j = 0; j < free_count; j++) {
            if (free_cpp[j] >= cpp) {
               match = j;
               break;
            }
         }

         if (match != UINT32_MAX) {
            for (uint32_t j = match + 1; j < free_count; j++)
               free_cpp[j - 1] = free_cpp[j];
            free_count--;
            continue;
         }

         assert(pressure_count < FRANE_26338_GMEM_SEARCH_MAX_ITEMS);
         pressure[pressure_count++] = {
            .cpp = cpp,
            .busy = 0,
         };
      }

      const uint32_t subpass_upper =
         frane_gmem_search_pixels(pressure, pressure_count,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);
      upper = MIN2(upper, subpass_upper);

      if (upper <= ctx->best_pixels)
         return upper;
   }

   return upper;
}

struct frane_gmem_search_option {
   uint8_t track;
   uint32_t slack;
   unsigned fill;
};
'''

edit(
    "tu_pass.cc",
    helper_anchor,
    helper_new,
    "add future subpass pressure upper bound",
)

old_bound = r'''   if (num_tracks > 0) {
      const uint32_t upper =
         frane_gmem_search_pixels(tracks, num_tracks,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);
      if (upper <= ctx->best_pixels)
         return;
   }
'''

new_bound = r'''   if (num_tracks > 0 || ctx->future_pressure) {
      const uint32_t upper =
         ctx->future_pressure
            ? frane_gmem_search_future_upper(ctx, pos, tracks, num_tracks)
            : frane_gmem_search_pixels(tracks, num_tracks,
                                       ctx->gmem_size,
                                       ctx->gmem_align,
                                       ctx->block_align_shift);
      if (upper <= ctx->best_pixels)
         return;
   }
'''

edit(
    "tu_pass.cc",
    old_bound,
    new_bound,
    "use future-pressure bound during branch-and-bound",
)

old_refine_head = r'''   const uint32_t item_count = frane_gmem_mask_item_count(pass);

   if (item_count < 3 ||
       item_count > FRANE_26338_GMEM_SEARCH_MAX_ITEMS ||
       *num_allocs == 0 ||
       *num_allocs > FRANE_26338_GMEM_SEARCH_MAX_ITEMS)
      return false;
'''

new_refine_head = r'''   const uint32_t item_count = frane_gmem_mask_item_count(pass);
   const bool future_pressure = frane_a810_gmem_pressure_bound_enabled();
   const uint32_t max_items =
      future_pressure ? FRANE_26338_GMEM_SEARCH_MAX_ITEMS : 12u;

   if (item_count < 3 ||
       item_count > max_items ||
       *num_allocs == 0 ||
       *num_allocs > max_items)
      return false;
'''

edit(
    "tu_pass.cc",
    old_refine_head,
    new_refine_head,
    "preserve exact V38 item limit when V39 is disabled",
)

old_budget = r'''   int budget_opt =
      debug_get_num_option("TU_A810_26338_GMEM_SEARCH_BUDGET", 1024);
   uint32_t budget = budget_opt < 128 ? 128u : (uint32_t) budget_opt;
   budget = MIN2(budget, 8192u);

   struct frane_gmem_search_ctx ctx = {
'''

new_budget = r'''   int budget_opt =
      future_pressure
         ? debug_get_num_option("TU_A810_26339_GMEM_SEARCH_BUDGET", 4096)
         : debug_get_num_option("TU_A810_26338_GMEM_SEARCH_BUDGET", 1024);
   uint32_t budget = budget_opt < 128 ? 128u : (uint32_t) budget_opt;
   budget = MIN2(budget, future_pressure ? 16384u : 8192u);

   struct frane_gmem_search_ctx ctx = {
'''

edit(
    "tu_pass.cc",
    old_budget,
    new_budget,
    "use V39 budget only while pressure bound is enabled",
)

edit(
    "tu_pass.cc",
    r'''      .node_budget = budget,
      .nodes = 0,
      .best_pixels = seed_pixels,
''',
    r'''      .node_budget = budget,
      .nodes = 0,
      .future_pressure = future_pressure,
      .best_pixels = seed_pixels,
''',
    "wire future-pressure mode into context",
)

edit(
    "tu_device.cc",
    "Turnip A810 V38 / Mesa ",
    "Turnip A810 V39 / Mesa ",
    "short driver identity",
)

p = (R / "tu_pass.cc").read_text()
d = (R / "tu_device.cc").read_text()

for needle in (
    'TU_A810_26339_GMEM_PRESSURE_BOUND", true',
    'TU_A810_26339_GMEM_SEARCH_BUDGET", 4096',
    "FRANE_26338_GMEM_SEARCH_MAX_ITEMS 16",
    "frane_gmem_search_future_upper",
    "remaining_subpasses &= remaining_subpasses - 1",
    "future_pressure ? FRANE_26338_GMEM_SEARCH_MAX_ITEMS : 12u",
    "ctx->future_pressure",
    "TU_A810_26338_GMEM_SEARCH",
    "TU_A810_26337_GMEM_MASK_PACK",
):
    assert needle in p, needle

assert "Turnip A810 V39 / Mesa " in d
print("26.3.39 A810 GMEM-PRESSURE applied", flush=True)
