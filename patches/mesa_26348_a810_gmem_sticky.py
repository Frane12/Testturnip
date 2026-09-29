#!/usr/bin/env python3
"""Drnas Turnip V48 GMEM-STICKY.

Layered strictly on V47 CB-PROFILER.

Performance hypothesis:
V47 can still run two independent exploration mechanisms on a render pass that
has already proved to be a strong GMEM winner:

  1) SMART-GMEM's own confidence-aware SYSMEM control probe.
  2) V22 LIVE-AUTOTUNE's generic strong-winner alternate/winner probe pair.

That overlap is useful while a mode is uncertain, but once the measured GMEM
state is armed and both measured timing + structural score agree, it causes
extra mode switches and timestamped control work.

V48 adds a bounded A810-only sticky winner policy:

  TU_A810_26348_GMEM_STICKY_MODE=0
      Exact V47 behavior.

  TU_A810_26348_GMEM_STICKY_MODE=1
      Keep SMART-GMEM's existing probe cadence, but suppress the redundant
      LIVE-AUTOTUNE strong-winner probe pair while an armed SMART-GMEM winner
      is active.

  TU_A810_26348_GMEM_STICKY_MODE=2  (default)
      Mode 1 plus an ultra-sticky case for only the strongest proven winners:
      runtime score == 8, structure >= 75, PROFILED sysmem probability <= 10.
      Those use one measured SYSMEM control probe per 256 decisions instead of
      SMART-GMEM's normal 1/128 ultra-strong cadence.

This does not touch GMEM allocation, attachment offsets, load/store rules, LRZ,
barriers, concurrent-binning correctness, WSI, or shader code. GMEM-TURBO is
left opt-in and V48 deliberately does not alter its policy.
"""

from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V48 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V48 PASS {label}", flush=True)


# Track the chosen experiment mode and whether SMART-GMEM already owns the
# control-probe responsibility for this decision.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         bool runtime_force_measure = false;
         if (!definite && measure && lean_fastpath && gmem_runtime_input) {""",
    """         bool runtime_force_measure = false;

         /* V48: de-duplicate exploration only after SMART-GMEM has a proven
          * armed winner. Mode 0 is byte-for-byte V47 behavior in the decision
          * path below.
          */
         static const int frane_26348_sticky_mode =
            debug_get_num_option("TU_A810_26348_GMEM_STICKY_MODE", 2);
         bool frane_26348_suppress_live_probe = false;

         if (!definite && measure && lean_fastpath && gmem_runtime_input) {""",
    "add bounded sticky-mode state",
)

# After the normal SMART-GMEM decision is computed, preserve it exactly for
# mode 0. Modes 1/2 can only act on already-armed, structurally strong winners.
old = """               runtime_decision.override_mode = smart_decision.override_mode;
               runtime_decision.select_sysmem = smart_decision.select_sysmem;
               runtime_decision.force_measure = smart_decision.force_measure;"""

new = """               runtime_decision.override_mode = smart_decision.override_mode;
               runtime_decision.select_sysmem = smart_decision.select_sysmem;
               runtime_decision.force_measure = smart_decision.force_measure;

               /* Do not interfere with the separately opt-in GMEM-TURBO
                * policy. The sticky experiment is intentionally a refinement
                * of the normal measured SMART-GMEM path only.
                */
               if (!gmem_turbo && frane_26348_sticky_mode > 0 &&
                   runtime_state.armed &&
                   smart_decision.override_mode &&
                   smart_decision.structure_score >= 65 &&
                   l_sysmem_probability <= 20) {
                  frane_26348_suppress_live_probe = true;

                  /* Ultra-sticky mode is deliberately narrow: score 8 means
                   * the measured state machine is fully saturated, structure
                   * >=75 means layout/bandwidth/draw density agree, and <=10
                   * means PROFILED itself strongly favors GMEM.
                   *
                   * Keep one measured SYSMEM control probe per 256 decisions
                   * so scene changes can still be observed and disarm later.
                   */
                  if (frane_26348_sticky_mode >= 2 &&
                      runtime_state.score >= 8 &&
                      smart_decision.structure_score >= 75 &&
                      l_sysmem_probability <= 10) {
                     runtime_decision.override_mode = true;
                     runtime_decision.select_sysmem =
                        (decision_word & UINT64_C(255)) == 0;
                     runtime_decision.force_measure =
                        runtime_decision.select_sysmem;
                  }
               }"""

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    old,
    new,
    "deduplicate strong-GMEM probes and add 1/256 ultra-sticky control probe",
)

# V22's generic strong-winner probe is useful everywhere else. Only skip it
# when the armed SMART-GMEM path above explicitly owns exploration.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         if (live_profiled && (l_sysmem_probability <= 5 ||
                               l_sysmem_probability >= 95)) {""",
    """         if (live_profiled && !frane_26348_suppress_live_probe &&
             (l_sysmem_probability <= 5 ||
              l_sysmem_probability >= 95)) {""",
    "suppress redundant LIVE-AUTOTUNE probing only for sticky GMEM winners",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V47 / Mesa ",
    "Drnas Turnip V48 / Mesa ",
    "V48 display identity",
)

# Surgical audit: V48 must remain a render-mode selection experiment only.
a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
wsi = (V / "tu_wsi.cc").read_text()

for needle in (
    'TU_A810_26348_GMEM_STICKY_MODE", 2',
    "frane_26348_suppress_live_probe",
    "runtime_state.score >= 8",
    "smart_decision.structure_score >= 75",
    "(decision_word & UINT64_C(255)) == 0",
):
    assert needle in a, needle

# Exact V47 fallback remains available.
assert "frane_26348_sticky_mode > 0" in a
assert 'TU_A810_26347_CB_PROFILE_MODE' in cmd
assert 'TU_A810_26347_CB_PROFILE_LOG' in cmd

# Keep the validated GMEM allocator/search stack untouched.
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26337_GMEM_MASK_PACK", true' in passcc

# Aggressive old GMEM-TURBO remains opt-in.
assert 'TU_A810_26320_GMEM_TURBO", false' in a

# No old presentation override returns.
assert "V28-CLEAN: no driver present-mode override" in wsi

# V48 does not weaken the GMEM correctness classifier.
assert 'TU_A810_26326_GMEM_SAFETY", true' in a
assert "frane_a810_gmem_pass_safe" in a

assert "Drnas Turnip V48 / Mesa " in d
print("Drnas Turnip V48 GMEM-STICKY applied", flush=True)
