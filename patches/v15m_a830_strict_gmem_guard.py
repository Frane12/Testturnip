#!/usr/bin/env python3
"""V15-M: optional *slightly stricter* A830 GMEM memory-pressure guard.

Layer this AFTER V15-D / V15-G / V15-J / V15-K / V15-L. V15-L remains
unmodified as the user-tested reference. Do NOT alter GPU resource lifetimes,
BO allocations/refcounts, fences, tiling, UBWC, or mandatory load/store.
Qualcomm blobs are NOT linked.

Default guard (TU_A830_GMEM_STRICT_GUARD=1):
  MemAvailable < 1792 MiB: block OPTIONAL GMEM on subsequent eligible passes
  resume optional GMEM at >= 2304 MiB (512 MiB hysteresis)
  caution below 3072 MiB: require >=12 draws and <=10 estimated tiles,
    and a further 1 percentage point cost saving.
Guard opt-out TU_A830_GMEM_STRICT_GUARD=0 restores the V15-L thresholds,
selection/margins and logging behavior. TU_A830_SMART_GMEM=0 still
reverts to V15-G. The guard cannot cancel already-submitted GPU work
and can increase SYSMEM RAM cost: compare memory and frame times A/B.
"""
from pathlib import Path
p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def replace_once(old: str, new: str):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V15-M patch drift: anchor matches={n}: {old[:105]!r}")
    s = s.replace(old, new, 1)

replace_once(
    """static uint32_t
frane_a830_gmem_pressure_tier(void)""",
    """/* Opt-out restores tested V15-L. No extra polling or heap allocations. */
static bool
frane_a830_gmem_strict_guard_enabled(void)
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A830_GMEM_STRICT_GUARD");
      return !env || strcmp(env, "0") != 0;
   }();
   return enabled;
}

static uint32_t
frane_a830_gmem_pressure_tier(void)""",
)

replace_once(
    """   constexpr uint64_t MiB = 1024ull * 1024ull;
   const uint64_t now = os_time_get_nano();""",
    """   constexpr uint64_t MiB = 1024ull * 1024ull;
   const bool strict = frane_a830_gmem_strict_guard_enabled();
   /* MemAvailable includes reclaimable cache, unlike HUD's used-RAM %.
    * Protect proactively, never try to reclaim live GPU allocations.
    */
   const uint64_t suspend_at = (strict ? 1792ull : 1280ull) * MiB;
   const uint64_t resume_at = (strict ? 2304ull : 1792ull) * MiB;
   const uint64_t caution_at = (strict ? 3072ull : 2560ull) * MiB;
   const uint64_t now = os_time_get_nano();""",
)

replace_once(
    """         if (available < 1280ull * MiB)
            allow_gmem.store(false, std::memory_order_relaxed);
         else if (available >= 1792ull * MiB)
            allow_gmem.store(true, std::memory_order_relaxed);

         const bool permitted = allow_gmem.load(std::memory_order_relaxed);
         const uint32_t tier =
            !permitted ? 0u : (available < 2560ull * MiB ? 1u : 2u);""",
    """         if (available < suspend_at)
            allow_gmem.store(false, std::memory_order_relaxed);
         else if (available >= resume_at)
            allow_gmem.store(true, std::memory_order_relaxed);

         const bool permitted = allow_gmem.load(std::memory_order_relaxed);
         const uint32_t tier =
            !permitted ? 0u : (available < caution_at ? 1u : 2u);""",
)

replace_once(
    """            const bool measured_candidate =
               a830_memory_tier != 0 &&
               rp_state->drawcall_count >= 10 &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= 12 &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""",
    """            const bool strict_caution =
               a830_memory_tier == 1 &&
               frane_a830_gmem_strict_guard_enabled();
            const bool measured_candidate =
               a830_memory_tier != 0 &&
               rp_state->drawcall_count >= (strict_caution ? 12u : 10u) &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= (strict_caution ? 10u : 12u) &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""",
)

replace_once(
    """            const uint32_t entry_margin = 125 + tile_penalty +
               low_draw_penalty + (a830_memory_tier == 1 ? 50 : 0);""",
    """            /* One extra cost percentage-point ONLY in strict caution.
             * Confidence hysteresis and V15-K safety gates remain intact.
             */
            const uint32_t entry_margin = 125 + tile_penalty +
               low_draw_penalty +
               (a830_memory_tier == 1 ? (strict_caution ? 60 : 50) : 0);""",
)

replace_once(
    """                            " saving_threshold=%u.%u%% q8428=%u dense=%u"
                            " gmem_bw=%" PRIu64 " sysmem_bw=%" PRIu64,""",
    """                            " saving_threshold=%u.%u%% q8428=%u dense=%u"
                            " guard=%u gmem_bw=%" PRIu64 " sysmem_bw=%" PRIu64,""",
)

replace_once(
    """                            q8428_policy ? 1u : 0u, dense_confirmed ? 1u : 0u,
                            gmem_bandwidth, sysmem_bandwidth);""",
    """                            q8428_policy ? 1u : 0u, dense_confirmed ? 1u : 0u,
                            frane_a830_gmem_strict_guard_enabled() ? 1u : 0u,
                            gmem_bandwidth, sysmem_bandwidth);""",
)

p.write_text(s)
print("V15-M strict guard: 1792/2304 MiB hysteresis; caution below 3072; disable with TU_A830_GMEM_STRICT_GUARD=0")
