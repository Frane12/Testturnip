#!/usr/bin/env python3
"""A810 V38R PROOF-SEARCH research layer.

Layered strictly on Turnip A810 V38 GMEM-SEARCH.

V38 already has the right safety contract: V37 exact-mask packing is the seed
and any searched layout is accepted only on a strict exact gmem_pixels win.
V38R keeps that contract and attacks search overhead instead of simply growing
the search window.

Research ideas:
- prove V37 is already optimal when a global per-subpass overlap upper bound
  equals the seed capacity, skipping search completely;
- use V39's future-aware pressure upper bound without expanding beyond V38's
  <=12-item search domain;
- exact canonical-state memoization with collision-safe structural equality;
- adaptive node budget based on the remaining proven capacity gap;
- explicit opt-out restores exact V38 search behavior.

A/B:
  TU_FRANE_V38R_PROOF=1 default
  TU_FRANE_V38R_PROOF=0 exact V38 behavior
  TU_FRANE_V38R_MEMO=1 default
  TU_FRANE_V38R_BUDGET=0 default adaptive, or explicit 128..4096
"""
from pathlib import Path

R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V38R source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"V38R PASS {label}", flush=True)

edit(
    "tu_pass.cc",
    r'''struct frane_gmem_search_track {
   uint32_t cpp;
   uint64_t busy;
};

struct frane_gmem_search_ctx {
''',
    r'''struct frane_gmem_search_track {
   uint32_t cpp;
   uint64_t busy;
};

#define FRANE_V38R_MEMO_SLOTS 64
#define FRANE_V38R_MEMO_PROBES 4

struct frane_v38r_memo_entry {
   bool valid;
   uint8_t pos;
   uint8_t num_tracks;
   struct frane_gmem_search_track
      tracks[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
};

struct frane_gmem_search_ctx {
''',
    "add exact canonical memo storage",
)

edit(
    "tu_pass.cc",
    r'''   uint32_t node_budget;
   uint32_t nodes;

   uint32_t best_pixels;
''',
    r'''   uint32_t node_budget;
   uint32_t nodes;
   bool v38r;
   bool memo_enabled;
   uint32_t memo_hits;

   struct frane_v38r_memo_entry memo[FRANE_V38R_MEMO_SLOTS];

   uint32_t best_pixels;
''',
    "extend search context for V38R proof mode",
)

gate_anchor = r'''static uint32_t
frane_gmem_mask_item_count(const struct tu_render_pass *pass)
'''

gate_new = r'''static bool
frane_v38r_proof_enabled(void)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_V38R_PROOF", true);
   return enabled;
}

static bool
frane_v38r_memo_enabled(void)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_V38R_MEMO", true);
   return enabled;
}

static uint32_t
frane_gmem_mask_item_count(const struct tu_render_pass *pass)
'''

edit(
    "tu_pass.cc",
    gate_anchor,
    gate_new,
    "add V38R A/B gates",
)

helper_anchor = r'''struct frane_gmem_search_option {
   uint8_t track;
   uint32_t slack;
   unsigned fill;
};
'''

helper_new = r'''static uint32_t
frane_v38r_global_upper(const struct frane_gmem_mask_item *items,
                        uint32_t item_count,
                        uint32_t gmem_size,
                        uint32_t gmem_align,
                        uint32_t block_align_shift)
{
   uint64_t subpasses = 0;
   for (uint32_t i = 0; i < item_count; i++) {
      uint64_t item_mask = 0;
      if (!frane_subpass_range_mask(items[i].first_subpass,
                                    items[i].last_subpass,
                                    &item_mask))
         return UINT32_MAX;
      subpasses |= item_mask;
   }

   uint32_t upper = UINT32_MAX;

   while (subpasses) {
      const uint32_t subpass = (uint32_t)__builtin_ctzll(subpasses);
      const uint64_t bit = UINT64_C(1) << subpass;
      subpasses &= subpasses - 1;

      struct frane_gmem_search_track
         active[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};
      uint32_t active_count = 0;

      for (uint32_t i = 0; i < item_count; i++) {
         uint64_t item_mask = 0;
         if (!frane_subpass_range_mask(items[i].first_subpass,
                                       items[i].last_subpass,
                                       &item_mask))
            continue;
         if (item_mask & bit) {
            assert(active_count < FRANE_26338_GMEM_SEARCH_MAX_ITEMS);
            active[active_count++] = {
               .cpp = items[i].cpp,
               .busy = 0,
            };
         }
      }

      if (!active_count)
         continue;

      const uint32_t subpass_upper =
         frane_gmem_search_pixels(active, active_count,
                                  gmem_size, gmem_align,
                                  block_align_shift);
      upper = MIN2(upper, subpass_upper);
   }

   return upper;
}

static uint32_t
frane_v38r_future_upper(const struct frane_gmem_search_ctx *ctx,
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
      const uint32_t subpass =
         (uint32_t)__builtin_ctzll(remaining_subpasses);
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

static bool
frane_v38r_track_before(const struct frane_gmem_search_track *a,
                        const struct frane_gmem_search_track *b)
{
   if (a->cpp != b->cpp)
      return a->cpp < b->cpp;
   return a->busy < b->busy;
}

static uint64_t
frane_v38r_state_hash(uint32_t pos,
                      const struct frane_gmem_search_track *tracks,
                      uint32_t num_tracks)
{
   uint64_t h = UINT64_C(1469598103934665603);
#define FRANE_V38R_HASH_MIX(v) \
   do { h ^= (uint64_t)(v); h *= UINT64_C(1099511628211); } while (0)
   FRANE_V38R_HASH_MIX(pos);
   FRANE_V38R_HASH_MIX(num_tracks);
   for (uint32_t i = 0; i < num_tracks; i++) {
      FRANE_V38R_HASH_MIX(tracks[i].cpp);
      FRANE_V38R_HASH_MIX(tracks[i].busy);
   }
#undef FRANE_V38R_HASH_MIX
   return h;
}

static bool
frane_v38r_memo_seen(struct frane_gmem_search_ctx *ctx,
                     uint32_t pos,
                     const struct frane_gmem_search_track *tracks,
                     uint32_t num_tracks)
{
   if (!ctx->memo_enabled || !num_tracks)
      return false;

   struct frane_gmem_search_track
      canonical[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};

   for (uint32_t i = 0; i < num_tracks; i++)
      canonical[i] = tracks[i];

   for (uint32_t i = 1; i < num_tracks; i++) {
      const struct frane_gmem_search_track key = canonical[i];
      uint32_t j = i;
      while (j > 0 &&
             frane_v38r_track_before(&key, &canonical[j - 1])) {
         canonical[j] = canonical[j - 1];
         j--;
      }
      canonical[j] = key;
   }

   const uint64_t hash =
      frane_v38r_state_hash(pos, canonical, num_tracks);
   const uint32_t base = (uint32_t)hash & (FRANE_V38R_MEMO_SLOTS - 1);
   uint32_t replace = base;

   for (uint32_t probe = 0; probe < FRANE_V38R_MEMO_PROBES; probe++) {
      const uint32_t slot =
         (base + probe) & (FRANE_V38R_MEMO_SLOTS - 1);
      struct frane_v38r_memo_entry *entry = &ctx->memo[slot];

      if (!entry->valid) {
         entry->valid = true;
         entry->pos = (uint8_t)pos;
         entry->num_tracks = (uint8_t)num_tracks;
         for (uint32_t i = 0; i < num_tracks; i++)
            entry->tracks[i] = canonical[i];
         return false;
      }

      if (entry->pos != pos || entry->num_tracks != num_tracks)
         continue;

      bool same = true;
      for (uint32_t i = 0; i < num_tracks; i++) {
         if (entry->tracks[i].cpp != canonical[i].cpp ||
             entry->tracks[i].busy != canonical[i].busy) {
            same = false;
            break;
         }
      }

      if (same) {
         ctx->memo_hits++;
         return true;
      }
   }

   /* Bounded memo is only a performance cache. Replacing an entry can create
    * false misses later, never a false hit, so search correctness is unchanged.
    */
   struct frane_v38r_memo_entry *entry = &ctx->memo[replace];
   entry->valid = true;
   entry->pos = (uint8_t)pos;
   entry->num_tracks = (uint8_t)num_tracks;
   for (uint32_t i = 0; i < num_tracks; i++)
      entry->tracks[i] = canonical[i];

   return false;
}

static uint32_t
frane_v38r_budget(uint32_t seed_pixels, uint32_t proof_upper)
{
   int explicit_budget =
      debug_get_num_option("TU_FRANE_V38R_BUDGET", 0);

   if (explicit_budget > 0) {
      uint32_t budget =
         MAX2(128u, (uint32_t)explicit_budget);
      return MIN2(budget, 4096u);
   }

   if (proof_upper <= seed_pixels)
      return 0;

   if (!seed_pixels)
      return 2048;

   const uint64_t delta = (uint64_t)proof_upper - seed_pixels;
   const uint64_t base = seed_pixels;

   if (delta * 100 <= base)
      return 128;
   if (delta * 100 <= base * 3)
      return 256;
   if (delta * 100 <= base * 6)
      return 512;
   if (delta * 100 <= base * 12)
      return 1024;

   return 2048;
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
    "add proof bounds, exact memo and adaptive budget",
)

old_recurse_head = r'''   if (++ctx->nodes > ctx->node_budget)
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
'''

new_recurse_head = r'''   if (++ctx->nodes > ctx->node_budget)
      return;

   if (ctx->v38r &&
       frane_v38r_memo_seen(ctx, pos, tracks, num_tracks))
      return;

   /* V38R uses the stronger future-aware optimistic upper bound while keeping
    * V38's exact branch ordering and strict-win admission. Opt-out restores
    * the original V38 existing-track bound byte-for-byte.
    */
   if (ctx->v38r) {
      const uint32_t upper =
         frane_v38r_future_upper(ctx, pos, tracks, num_tracks);
      if (upper <= ctx->best_pixels)
         return;
   } else if (num_tracks > 0) {
      const uint32_t upper =
         frane_gmem_search_pixels(tracks, num_tracks,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);
      if (upper <= ctx->best_pixels)
         return;
   }
'''

edit(
    "tu_pass.cc",
    old_recurse_head,
    new_recurse_head,
    "use proof-aware pruning and canonical dedup",
)

old_budget = r'''   int budget_opt =
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
'''

new_budget = r'''   const bool v38r = frane_v38r_proof_enabled();

   uint32_t proof_upper = UINT32_MAX;
   uint32_t budget = 0;

   if (v38r) {
      proof_upper =
         frane_v38r_global_upper(items, item_count,
                                 gmem_size, gmem_align,
                                 block_align_shift);

      /* Equality is a proof, not a heuristic: the V37 seed has reached the
       * optimistic overlap limit, so no legal global track layout can win.
       */
      if (proof_upper <= seed_pixels)
         return false;

      budget = frane_v38r_budget(seed_pixels, proof_upper);
      if (!budget)
         return false;
   } else {
      int budget_opt =
         debug_get_num_option("TU_A810_26338_GMEM_SEARCH_BUDGET", 1024);
      budget = budget_opt < 128 ? 128u : (uint32_t)budget_opt;
      budget = MIN2(budget, 8192u);
   }

   struct frane_gmem_search_ctx ctx = {
      .items = items,
      .item_count = item_count,
      .gmem_size = gmem_size,
      .gmem_align = gmem_align,
      .block_align_shift = block_align_shift,
      .node_budget = budget,
      .nodes = 0,
      .v38r = v38r,
      .memo_enabled = v38r && frane_v38r_memo_enabled(),
      .memo_hits = 0,
      .best_pixels = seed_pixels,
      .best_num_tracks = 0,
   };
'''

edit(
    "tu_pass.cc",
    old_budget,
    new_budget,
    "prove easy cases and choose adaptive search budget",
)

edit(
    "tu_device.cc",
    "Turnip A810 V38 / Mesa ",
    "Turnip A810 V38R / Mesa ",
    "research driver identity",
)

p = (R / "tu_pass.cc").read_text()
d = (R / "tu_device.cc").read_text()

for needle in (
    'TU_FRANE_V38R_PROOF", true',
    'TU_FRANE_V38R_MEMO", true',
    'TU_FRANE_V38R_BUDGET", 0',
    "frane_v38r_global_upper",
    "frane_v38r_future_upper",
    "frane_v38r_memo_seen",
    "FRANE_V38R_MEMO_SLOTS 64",
    "proof_upper <= seed_pixels",
    "delta * 100 <= base * 12",
    "TU_A810_26338_GMEM_SEARCH",
    "TU_A810_26337_GMEM_MASK_PACK",
):
    assert needle in p, needle

assert "FRANE_26338_GMEM_SEARCH_MAX_ITEMS 12" in p
assert "Turnip A810 V38R / Mesa " in d
print("A810 V38R PROOF-SEARCH research layer applied", flush=True)
