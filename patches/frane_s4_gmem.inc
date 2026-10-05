static unsigned
frane_s4_span(uint64_t mask)
{
   return mask ? 64u - __builtin_clzll(mask) - __builtin_ctzll(mask) : 0;
}

static uint32_t
frane_s4_peak_upper(const struct frane_gmem_search_ctx *ctx)
{
   uint32_t upper = UINT32_MAX;
   uint64_t starts = 0;
   for (unsigned i = 0; i < ctx->item_count; i++)
      starts |= UINT64_C(1) << ctx->items[i].first_subpass;
   while (starts) {
      const unsigned s = __builtin_ctzll(starts);
      starts &= starts - 1;
      struct frane_gmem_search_track active[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};
      unsigned count = 0;
      for (unsigned i = 0; i < ctx->item_count; i++) {
         const struct frane_gmem_mask_item *it = &ctx->items[i];
         if (it->first_subpass <= s && s <= it->last_subpass)
            active[count++].cpp = it->cpp;
      }
      if (count)
         upper = MIN2(upper, frane_gmem_search_pixels(active, count,
            ctx->gmem_size, ctx->gmem_align, ctx->block_align_shift));
   }
   return upper;
}

static void
frane_s4_multiseed(struct frane_gmem_search_ctx *ctx, unsigned seeds, bool gaps)
{
   if (ctx->best_pixels >= ctx->peak_upper)
      return;
   uint64_t masks[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};
   unsigned degree[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};
   for (unsigned i = 0; i < ctx->item_count; i++) {
      if (!frane_subpass_range_mask(ctx->items[i].first_subpass,
                                    ctx->items[i].last_subpass, &masks[i]))
         return;
   }
   for (unsigned i = 0; i < ctx->item_count; i++)
      for (unsigned j = 0; j < ctx->item_count; j++)
         degree[i] += i != j && (masks[i] & masks[j]) != 0;
   for (unsigned mode = 0; mode < seeds; mode++) {
      unsigned order[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
      int64_t priority[FRANE_26338_GMEM_SEARCH_MAX_ITEMS];
      for (unsigned i = 0; i < ctx->item_count; i++) {
         order[i] = i;
         const struct frane_gmem_mask_item *it = &ctx->items[i];
         priority[i] = mode == 0 ? (int64_t)it->cpp * 128 + degree[i] :
            mode == 1 ? (int64_t)degree[i] * 256 + it->cpp :
            mode == 2 ? -(int64_t)it->first_subpass * 256 + it->cpp :
            (int64_t)it->cpp * (degree[i] + 1) * 64 + frane_s4_span(masks[i]);
      }
      for (unsigned i = 1; i < ctx->item_count; i++) {
         unsigned key = order[i], j = i;
         while (j && priority[key] > priority[order[j - 1]]) {
            order[j] = order[j - 1];
            j--;
         }
         order[j] = key;
      }
      struct frane_gmem_search_track tracks[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};
      uint8_t assignment[FRANE_26338_GMEM_SEARCH_MAX_ITEMS] = {};
      unsigned count = 0;
      for (unsigned n = 0; n < ctx->item_count; n++) {
         const unsigned i = order[n];
         const uint32_t cpp = ctx->items[i].cpp;
         unsigned best = count;
         uint64_t best_cost = UINT64_MAX;
         for (unsigned t = 0; t < count; t++) {
            if (tracks[t].busy & masks[i])
               continue;
            const uint32_t new_cpp = MAX2(cpp, tracks[t].cpp);
            const uint64_t grow = new_cpp - tracks[t].cpp;
            const uint64_t slack = new_cpp - cpp;
            const uint64_t holes = frane_s4_span(tracks[t].busy | masks[i]) -
               __builtin_popcountll(tracks[t].busy | masks[i]);
            const uint64_t cost = grow * 65536 + slack * 256 +
               (gaps ? holes : 64u - __builtin_popcountll(tracks[t].busy));
            if (cost < best_cost) {
               best = t;
               best_cost = cost;
            }
         }
         if (best == count)
            count++;
         tracks[best].cpp = MAX2(tracks[best].cpp, cpp);
         tracks[best].busy |= masks[i];
         assignment[i] = best;
      }
      const uint32_t pixels = frane_gmem_search_pixels(tracks, count,
         ctx->gmem_size, ctx->gmem_align, ctx->block_align_shift);
      if (pixels > ctx->best_pixels) {
         ctx->best_pixels = pixels;
         ctx->best_num_tracks = count;
         for (unsigned i = 0; i < count; i++)
            ctx->best_tracks[i] = tracks[i];
         for (unsigned i = 0; i < ctx->item_count; i++)
            ctx->best_assignment[i] = assignment[i];
      }
      if (ctx->best_pixels >= ctx->peak_upper)
         return;
   }
}
