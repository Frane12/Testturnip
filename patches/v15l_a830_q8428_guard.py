#!/usr/bin/env python3
"""V15-L Q8428 POLICY: conservative Qualcomm-842.8-inspired refinement.

This is independently written Turnip policy; NO proprietary Qualcomm code,
binary linking, borrowed memory-free algorithm or unsafe GMEM BO lifetime edits.
Qualcomm 842.8 exports timing-based frees and advertises 'Low Draws, Gmem Load'.
Neither proves a specific Vulkan driver algorithm. Mesa's synchronization and
resource ownership remain entirely in charge.

Keep field-tested V15-K default and only adjust its cost model:
 - eliminate the overflow-prone 8x bandwidth compare in V15-J A/B mode;
 - for many GMEM tiles with low draws/tile, ask for another 1%-point saving;
 - for sustained high draw density and already CONFIRMED GMEM passes, refund at
   most 1.6%-points of V15-K's tile penalty (only in healthy memory tier);
 - avoid allocating BOs, extra per-RP maps, extra threads or changing frees;
 - log cost inputs only when TU_A830_SMART_GMEM_LOG=1 (existing 5s limit).
 TU_A830_Q8428_POLICY=0 turns off *all* new tuning but keeps overflow fix.
 TU_A830_SMART_GMEM_STATS=0 and TU_A830_SMART_GMEM=0 still work as before.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def replace_once(before: str, after: str) -> None:
    global s
    n = s.count(before)
    if n != 1:
        raise SystemExit(f"V15-L patch drift: matches={n} for {before[:90]!r}")
    s = s.replace(before, after, 1)

replace_once(
    """static bool
frane_a830_gmem_diag_enabled(void)""",
    """/* Q8428 is a selectable cost heuristic, not a stock-driver code port. */
static bool
frane_a830_q8428_policy_enabled(void)
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A830_Q8428_POLICY");
      return !env || strcmp(env, "0") != 0;
   }();
   return enabled;
}

static bool
frane_a830_gmem_diag_enabled(void)""",
)

replace_once(
    """            const uint32_t tile_penalty =
               approx_tiles > 4 && approx_tiles <= 12
                  ? (uint32_t) (approx_tiles - 4) * 8 : 0;
            const uint32_t entry_margin =
               125 + tile_penalty + (a830_memory_tier == 1 ? 50 : 0);
            const uint32_t old_confidence =
               a830_gmem_confidence.load(std::memory_order_relaxed);
            const bool use_stats = frane_a830_gmem_stats_enabled();""",
    """            const uint32_t old_confidence =
               a830_gmem_confidence.load(std::memory_order_relaxed);
            const bool use_stats = frane_a830_gmem_stats_enabled();
            const bool q8428_policy =
               use_stats && frane_a830_q8428_policy_enabled();

            /* Existing V15-K threshold and tile approximation are retained.
             * The official 842.8 binary contains a 'Low Draws, Gmem Load'
             * diagnostic: use that as a hypothesis, NOT inferred source.
             * Apply a small additional penalty when a tiled RP contains few
             * draws, since attachment load/store overhead may dominate.
             *
             * Only relax V15-K's penalty for an already-confirmed,
             * repeatedly profitable pass with high draw density. A fresh
             * pass still needs ALL original V15-K savings. No relaxation
             * during memory caution (tier 1) or stop (tier 0).
             */
            const uint32_t base_tile_penalty =
               approx_tiles > 4 && approx_tiles <= 12
                  ? (uint32_t) (approx_tiles - 4) * 8 : 0;
            const bool dense_confirmed =
               q8428_policy && a830_memory_tier == 2 &&
               old_confidence >= 2 && approx_tiles > 4 &&
               approx_tiles <= 12 &&
               (uint64_t) rp_state->drawcall_count >= 3 * approx_tiles;
            const uint32_t tile_penalty =
               base_tile_penalty -
               (dense_confirmed ? MIN2(base_tile_penalty, 16u) : 0u);
            const uint32_t low_draw_penalty =
               q8428_policy && approx_tiles >= 7 && approx_tiles <= 12 &&
               (uint64_t) rp_state->drawcall_count < 2 * approx_tiles
                  ? 10u : 0u; /* 1.0 percentage point; never bypass gates */
            const uint32_t entry_margin = 125 + tile_penalty +
               low_draw_penalty + (a830_memory_tier == 1 ? 50 : 0);""",
)

replace_once(
    """               (use_stats ? gmem_bandwidth <= max_acceptable_gmem
                          : (gmem_bandwidth * 8 <= sysmem_bandwidth * 7));""",
    """               (use_stats ? gmem_bandwidth <= max_acceptable_gmem
                          : (gmem_bandwidth <=
                             (sysmem_bandwidth / 8) * 7 +
                             ((sysmem_bandwidth % 8) * 7) / 8));""",
)

replace_once(
    """                            " saving_threshold=%u.%u%%",
                            g, s, p, w, a830_memory_tier,
                            select_sysmem ? "SYSMEM" : "GMEM",
                            new_confidence, rp_state->drawcall_count,
                            approx_tiles, entry_margin / 10, entry_margin % 10);""",
    """                            " saving_threshold=%u.%u%% q8428=%u dense=%u"
                            " gmem_bw=%" PRIu64 " sysmem_bw=%" PRIu64,
                            g, s, p, w, a830_memory_tier,
                            select_sysmem ? "SYSMEM" : "GMEM",
                            new_confidence, rp_state->drawcall_count,
                            approx_tiles, entry_margin / 10, entry_margin % 10,
                            q8428_policy ? 1u : 0u, dense_confirmed ? 1u : 0u,
                            gmem_bandwidth, sysmem_bandwidth);""",
)

p.write_text(s)
print("V15-L: Q8428 cost policy, safe legacy bandwidth compare, unchanged GPU frees")
