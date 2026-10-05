#!/usr/bin/env python3
"""V15-I TURBO DEV: riskier A830 GMEM cost-model experiment AFTER V15-H.

Only reweights the GMEM/SYSMEM *selection* when original Mesa's safety
checks have passed, for moderate or large renderpasses with measured samples.

Default A830: 6+ draws, 320x180 .. 2560x1440 total pass pixels and
GMEM attachment cost <= SYSMEM attachment cost:
   estimated GMEM cost = 0.95 * attachment bytes + 0.05 * sampled draw bytes
versus V15-H's 1.05 * attachment bytes + 0.10 * sampled draw bytes.
This is aggressive and can be slower than V15-G/H when tile reloads dominate.

Runtime AB: TU_A830_GMEM_TURBO=0 reverts solely V15-I heuristic to V15-H.
Runtime AB: TU_A830_GMEM_DEV=0 reverts BOTH changes to V15-G autotune.
User TU_AUTOTUNE_ALGO and TU_DEBUG override as in V15-H. No GPU registers,
GMEM tile layout, UBWC, BO lifetime, barriers, load/store semantics touched.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def replace_once(before: str, after: str) -> None:
    global s
    n = s.count(before)
    if n != 1:
        raise SystemExit(f"V15-I: upstream/patch drift: expected one anchor, found {n}: {before[:120]!r}")
    s = s.replace(before, after, 1)

replace_once(
    """/** Configuration **/""",
    """/* V15-I opt-out: set TU_A830_GMEM_TURBO=0 to retain V15-H only.
 * TU_A830_GMEM_DEV=0 additionally switches off the complete H experiment.
 */
static bool
frane_a830_gmem_turbo_enabled(const struct tu_device *device)
{
   static const bool turbo_enabled = []() {
      const char *env = os_get_option("TU_A830_GMEM_TURBO");
      return !env || strcmp(env, "0") != 0;
   }();
   return turbo_enabled && frane_a830_gmem_dev_enabled(device);
}

/** Configuration **/""",
)

replace_once(
    """                                    bool frane_a830_gmem_dev)
      {""",
    """                                    bool frane_a830_gmem_dev,
                                    bool frane_a830_gmem_turbo)
      {""",
)

replace_once(
    """          if (a830_candidate)
             gmem_bandwidth = (gmem_bandwidth * 21 + total_draw_call_bandwidth * 2) / 20;
          else
            gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;""",
    """          /* V15-I: aggressive, A830-only, opt-out cost model. Keep the
           * actual RP layout, attachment stores, loadOps and hardware
           * compatibility checks exactly as upstream Mesa/V15-H.
           */
          const bool turbo_candidate =
             frane_a830_gmem_turbo &&
             rp_state->drawcall_count >= 6 &&
             mean_samples > 0 &&
             pass_pixel_count >= 320u * 180u &&
             pass_pixel_count <= 2560u * 1440u &&
             pass->gmem_bandwidth_per_pixel <= pass->sysmem_bandwidth_per_pixel;

          if (turbo_candidate)
             gmem_bandwidth = (gmem_bandwidth * 19 + total_draw_call_bandwidth) / 20;
          else if (a830_candidate)
             gmem_bandwidth = (gmem_bandwidth * 21 + total_draw_call_bandwidth * 2) / 20;
          else
            gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;""",
)

replace_once(
    """          frane_a830_gmem_dev_enabled(device));""",
    """          frane_a830_gmem_dev_enabled(device),
          frane_a830_gmem_turbo_enabled(device));""",
)

p.write_text(s)
print("V15-I TURBO: A830-only cost model; two-stage kill switch; V15-G budget/UBWC unchanged")
