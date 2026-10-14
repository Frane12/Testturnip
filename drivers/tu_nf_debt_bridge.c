/* SPDX-License-Identifier: MIT
 * NeuroFlow Decision Debt bridge for experimental Turnip builds.
 *
 * This provides an exported smoke-test symbol to prove the reference C11
 * controller is linked into libvulkan_freedreno.so. It does NOT modify
 * Mesa's production render-mode selection (PROFILED remains authoritative).
 * No per-frame work is added to Mesa's hot path.
 */
#include <stdint.h>
#include "nf_decision_debt.h"

#if defined(__GNUC__) || defined(__clang__)
#define NF_EXPORT __attribute__((visibility("default")))
#else
#define NF_EXPORT
#endif

/* Explicit prototypes required by Mesa's -Werror=missing-prototypes. */
NF_EXPORT uint32_t tu_neuroflow_reference_abi_version(void);
NF_EXPORT int tu_neuroflow_reference_selftest(void);

NF_EXPORT uint32_t
tu_neuroflow_reference_abi_version(void)
{
   return 0x00010000u; /* reference module v0.1 */
}

NF_EXPORT int
tu_neuroflow_reference_selftest(void)
{
   struct nf_debt_gate gate;
   nf_debt_init(&gate, nf_debt_default_config());

   if (!nf_debt_should_probe(&gate))
      return 0;

   const struct nf_debt_evidence ev = {
      .baseline_ns = 1000,
      .candidate_ns = 500,
      .decision_cpu_ns = 50,
      .transition_cpu_ns = 10,
      .paired_samples = 3,
      .comparable = true,
      .correctness_ok = true,
   };

   return nf_debt_record_window(&gate, &ev) == NF_DEBT_PROFITABLE;
}
