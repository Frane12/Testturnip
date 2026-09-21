#!/usr/bin/env python3
"""V15-K SMART GMEM STATISTICS: add cheap confidence, tile-aware cost and
memory-pressure tiers to successful V15-J; NEVER import V15-H/I tuning.

One atomic uint32_t per EXISTING renderpass history, no secondary hash map,
GPU allocation, descriptor edits or thread-blocking locks. Keep V15-J
MemAvailable probes at most once / 350 ms, stop below 1280 MiB and resume
above 1792 MiB. Introduce caution tier below 2560 MiB. Preserve V15-G RAM.

A830-specific behavior when TU_A830_SMART_GMEM is enabled:
 * >=2 profitable observations of the same renderpass before opting in;
 * expected GMEM saving >=12.5% + 0.8%/tile beyond 4 + 5% in caution tier;
 * 3%-point hold hysteresis when already opted in; memory danger resets
   permission immediately (this cannot preempt submitted GPU work).
 * Diagnostic counters and once-per-5s log only if
   TU_A830_SMART_GMEM_LOG=1. Default logging imposes no counter work.

Use TU_A830_SMART_GMEM=0 for V15-G control or revert ZIP to V15-J.
This is a selection optimizer, NOT a page-fault fix or physical GMEM cache.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def replace_once(before: str, after: str) -> None:
    global s
    n = s.count(before)
    if n != 1:
        raise SystemExit(f"V15-K patch drift (matches={n}): {before[:100]!r}")
    s = s.replace(before, after, 1)

replace_once(
    """static bool
frane_a830_gmem_pressure_ok(void)""",
    """static uint32_t
frane_a830_gmem_pressure_tier(void)""",
)
replace_once(
    """   static std::atomic<uint64_t> free_bytes { 0 };
   static std::atomic<bool> allow_gmem { true };""",
    """   static std::atomic<bool> allow_gmem { true };
   /* Tier 0: pause optional GMEM; 1: caution; 2: healthy memory.
    * Start at caution until the first real Android memory observation.
    */
   static std::atomic<uint32_t> memory_tier { 1 };""",
)
replace_once(
    """         free_bytes.store(available, std::memory_order_relaxed);
         if (available < 1280ull * MiB)
            allow_gmem.store(false, std::memory_order_relaxed);
         else if (available >= 1792ull * MiB)
            allow_gmem.store(true, std::memory_order_relaxed);""",
    """         if (available < 1280ull * MiB)
            allow_gmem.store(false, std::memory_order_relaxed);
         else if (available >= 1792ull * MiB)
            allow_gmem.store(true, std::memory_order_relaxed);

         const bool permitted = allow_gmem.load(std::memory_order_relaxed);
         const uint32_t tier =
            !permitted ? 0u : (available < 2560ull * MiB ? 1u : 2u);
         memory_tier.store(tier, std::memory_order_relaxed);""",
)
replace_once(
    """         allow_gmem.store(false, std::memory_order_relaxed);
      }
   }
   return allow_gmem.load(std::memory_order_relaxed);
}""",
    """         allow_gmem.store(false, std::memory_order_relaxed);
         memory_tier.store(0, std::memory_order_relaxed);
      }
   }
   return memory_tier.load(std::memory_order_relaxed);
}""",
)
replace_once(
    """      exponential_average<uint32_t> mean_samples_passed;

     public:""",
    """      exponential_average<uint32_t> mean_samples_passed;
      /* 0=SYSMEM/idle, 1=first profitable observation,
       * 2=GMEM confirmed. In the existing RP history; no extra map.
       */
      std::atomic<uint32_t> a830_gmem_confidence { 0 };

     public:""",
)
replace_once(
    """                                   bool a830_smart_gmem,
                                   bool a830_mem_ok)""",
    """                                   bool a830_smart_gmem,
                                   uint32_t a830_memory_tier)""",
)

# Anchor is V15-J's decision core, intentionally leave every original
# eligibility condition and hardware safety check in place.
replace_once(
    """            const bool measured_candidate =
               a830_mem_ok &&
               rp_state->drawcall_count >= 10 &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= 12 &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;

            /* GMEM must estimate at least 12.5% lower memory traffic.
             * Unlike V15-I, don't discount actual GMEM load/store costs.
             */
            select_sysmem = !measured_candidate ||
               (gmem_bandwidth * 8 > sysmem_bandwidth * 7);""",
    """            const bool measured_candidate =
               a830_memory_tier != 0 &&
               rp_state->drawcall_count >= 10 &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= 12 &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;

            /* A830 cost heuristic: V15-J 12.5% minimum saving, plus
             * up to 6.4 points for 5..12 GMEM tiles, plus 5 points when
             * Android reports memory caution. Do NOT discount actual
             * required GMEM attachment load/store/resolves.
             */
            const uint32_t tile_penalty =
               approx_tiles > 4 && approx_tiles <= 12
                  ? (uint32_t) (approx_tiles - 4) * 8 : 0;
            const uint32_t entry_margin =
               125 + tile_penalty + (a830_memory_tier == 1 ? 50 : 0);
            const uint32_t old_confidence =
               a830_gmem_confidence.load(std::memory_order_relaxed);
            const uint32_t margin =
               old_confidence >= 2 ? entry_margin - 30 : entry_margin;
            const uint64_t retained_per_mille = 1000 - margin;
            /* Avoid multiplying full bandwidth by 1000 (possible overflow).
             * Fixed-point threshold with safe division before scaling.
             */
            const uint64_t max_acceptable_gmem =
               (sysmem_bandwidth / 1000) * retained_per_mille +
               ((sysmem_bandwidth % 1000) * retained_per_mille) / 1000;
            const bool profitable =
               measured_candidate && gmem_bandwidth <= max_acceptable_gmem;

            /* Same-RP confidence: one observation warms the tuner up;
             * second profitable observation enables GMEM. Retain it
             * across up to 3 percentage-point cost-model noise; release
             * immediately if memory pressure makes GMEM ineligible.
             * Relaxed atomics avoid locks and data races across CB threads.
             */
            const uint32_t new_confidence =
               profitable ? MIN2(old_confidence + 1, 2u) : 0u;
            a830_gmem_confidence.store(new_confidence,
                                       std::memory_order_relaxed);
            select_sysmem = new_confidence < 2;""",
)

replace_once(
    """            if (frane_a830_gmem_diag_enabled()) {
               static std::atomic<uint64_t> last_log_ns { 0 };
               const uint64_t now = os_time_get_nano();
               uint64_t old = last_log_ns.load(std::memory_order_relaxed);
               if (now > old && now - old > 5'000'000'000ull &&
                   last_log_ns.compare_exchange_strong(old, now)) {
                  mesa_logi("Frane V15-J: mode=%s mem_ok=%d draws=%u pixels=%u tiles=%" PRIu64
                            " gmem_bw=%" PRIu64 " sysmem_bw=%" PRIu64,
                            select_sysmem ? "SYSMEM" : "GMEM", a830_mem_ok,
                            rp_state->drawcall_count, pass_pixel_count,
                            approx_tiles, gmem_bandwidth, sysmem_bandwidth);
               }
            }""",
    """            if (frane_a830_gmem_diag_enabled()) {
               /* Statistics enabled only when requested, and use static
                * counters, not per-pass heap allocations or log spam.
                */
               static std::atomic<uint32_t> gmem_count { 0 };
               static std::atomic<uint32_t> sysmem_count { 0 };
               static std::atomic<uint32_t> pressure_count { 0 };
               static std::atomic<uint32_t> warmup_count { 0 };
               static std::atomic<uint32_t> last_log_ns_dummy { 0 };
               static std::atomic<uint64_t> last_log_ns { 0 };
               (void) last_log_ns_dummy;
               if (select_sysmem)
                  sysmem_count.fetch_add(1, std::memory_order_relaxed);
               else
                  gmem_count.fetch_add(1, std::memory_order_relaxed);
               if (a830_memory_tier == 0)
                  pressure_count.fetch_add(1, std::memory_order_relaxed);
               if (profitable && select_sysmem)
                  warmup_count.fetch_add(1, std::memory_order_relaxed);

               const uint64_t now = os_time_get_nano();
               uint64_t old = last_log_ns.load(std::memory_order_relaxed);
               if (now > old && now - old > 5'000'000'000ull &&
                   last_log_ns.compare_exchange_strong(
                      old, now, std::memory_order_relaxed)) {
                  const uint32_t g = gmem_count.exchange(0, std::memory_order_relaxed);
                  const uint32_t s = sysmem_count.exchange(0, std::memory_order_relaxed);
                  const uint32_t p = pressure_count.exchange(0, std::memory_order_relaxed);
                  const uint32_t w = warmup_count.exchange(0, std::memory_order_relaxed);
                  mesa_logi("Frane V15-K: GMEM=%u SYSMEM=%u pressure_skip=%u warmup=%u"
                            " tier=%u selected=%s conf=%u draws=%u tiles=%" PRIu64
                            " saving_threshold=%u.%u%%",
                            g, s, p, w, a830_memory_tier,
                            select_sysmem ? "SYSMEM" : "GMEM",
                            new_confidence, rp_state->drawcall_count,
                            approx_tiles, entry_margin / 10, entry_margin % 10);
               }
            }""",
)
replace_once(
    """         smart, !smart || frane_a830_gmem_pressure_ok());""",
    """         smart, smart ? frane_a830_gmem_pressure_tier() : 2u);""",
)

p.write_text(s)
print("V15-K: pressure tiers + per-RP confidence + tile-aware margin + optional diagnostics")
