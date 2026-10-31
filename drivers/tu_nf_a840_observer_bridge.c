/* SPDX-License-Identifier: MIT
 * A840 H3.0 staged NeuroFlow CPU observer bridge.
 * Deliberately NOT a Mesa render-path hook. No GPU state, GMEM/SYSMEM
 * selection, TEX or Vulkan synchronization is modified by this module.
 * This source is linked into the Turnip .so to test ABI/toolchain migration.
 */
#include <stdint.h>
#include "nf_a840_temporal.h"
#include "nf_a840_optional_work.h"

#if defined(__clang__) && __has_attribute(retain)
#define NF_KEEP __attribute__((visibility("default"), used, retain))
#else
#define NF_KEEP __attribute__((visibility("default"), used))
#endif

/* Public ABI declarations required by Mesa's -Wmissing-prototypes build. */
uint32_t tu_nf_a840_observer_abi_version(void);
int tu_nf_a840_observer_selftest(void);

NF_KEEP uint32_t tu_nf_a840_observer_abi_version(void)
{
   return UINT32_C(0xA8400301);
}

/* Safe host-side smoke check. Never called automatically from Mesa render. */
NF_KEEP int tu_nf_a840_observer_selftest(void)
{
   struct nf_a840_controller c;
   struct nf_a840_config cfg = nf_a840_default_config();
   nf_a840_init(&c, cfg, UINT64_C(0xA840), 1);
   if (c.safety_blocked || c.mode != NF_A840_OBSERVER ||
       c.current_N != 1 || c.safe_N != 1)
      return 1;
   const struct nf_a840_observation sample = {
      .timestamp_ns = UINT64_C(1000),
      .compatibility_key = UINT64_C(0xA840),
      .pattern_key = 1,
      .observed_cost_ns = UINT64_C(100),
      .cost_valid = true,
      .correctness_ok = true,
   };
   if (!nf_a840_observe(&c, &sample))
      return 2;
   struct nf_a840_optional_gate gate;
   nf_a840_optional_init(&gate, UINT64_C(1000000));
   if (gate.pending || gate.disabled)
      return 3;
   return 0;
}
