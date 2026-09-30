#!/usr/bin/env python3
"""Drnas Turnip V49 GMEM-FRONTIER.

Layered strictly on V48 GMEM-STICKY.

Goal:
Find the A810 performance/correctness frontier by progressively allowing a
proven measured GMEM winner to stay in GMEM longer before PROFILED/SYSMEM
control pressure can take it back.

This is deliberately a render-mode policy experiment only. The A810 GMEM
safety classifier remains authoritative after mode selection, so unsafe passes
still fall back to SYSMEM. V49 does not alter the attachment-class policy
established by V27-V32: simple depth, simple combined depth/stencil and packed
depth/stencil retain their existing defaults, while stencil load/store remains
conservative.

Modes:
  TU_A810_26349_GMEM_FRONTIER_MODE=0
      Exact V48 policy.

  =1
      V48 ultra-strong thresholds, but stretch the measured SYSMEM control
      probe from 1/256 to 1/512.

  =2 (default)
      Strong measured winner: score >=7, structure >=70, PROFILED SYSMEM
      probability <=20. Hold GMEM with one measured SYSMEM probe per 512
      decisions. Other cases retain V48 behavior.

  =3
      Aggressive frontier: armed score >=6, structure >=60, SYSMEM probability
      <=50. This may deliberately hold GMEM even across V48's normal >40
      PROFILED fallback boundary. One measured control probe per 1024 decisions.

  =4
      Limit-search mode: armed score >=6, structure >=50, SYSMEM probability
      <=60. One measured control probe per 2048 decisions.

The safety gate, GMEM allocator/layout, attachment offsets, load/store rules,
LRZ, barriers, WSI, shaders and CB policy remain untouched.
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
            f"V49 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V49 PASS {label}", flush=True)


# Add a single sweep knob. Mode 0 preserves V48 exactly.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         static const int frane_26348_sticky_mode =
            debug_get_num_option("TU_A810_26348_GMEM_STICKY_MODE", 2);
         bool frane_26348_suppress_live_probe = false;""",
    """         static const int frane_26348_sticky_mode =
            debug_get_num_option("TU_A810_26348_GMEM_STICKY_MODE", 2);
         static const int frane_26349_frontier_mode =
            static_cast<int>(std::clamp<int64_t>(
               debug_get_num_option("TU_A810_26349_GMEM_FRONTIER_MODE", 2),
               INT64_C(0), INT64_C(4)));
         bool frane_26348_suppress_live_probe = false;""",
    "add bounded frontier mode selector",
)

old = """               /* Do not interfere with the separately opt-in GMEM-TURBO
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

new = """               /* V49 frontier sweep. Mode 0 preserves the exact V48 block
                * below. Modes 1..4 only operate on an already-armed measured
                * GMEM state and never bypass the later V26 correctness gate.
                */
               if (!gmem_turbo && runtime_state.armed) {
                  if (frane_26349_frontier_mode == 0) {
                     if (frane_26348_sticky_mode > 0 &&
                         smart_decision.override_mode &&
                         smart_decision.structure_score >= 65 &&
                         l_sysmem_probability <= 20) {
                        frane_26348_suppress_live_probe = true;

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
                     }
                  } else {
                     bool frontier_hold = false;
                     uint64_t probe_mask = UINT64_C(511); /* 1/512 */

                     if (frane_26349_frontier_mode == 1) {
                        frontier_hold =
                           smart_decision.override_mode &&
                           runtime_state.score >= 8 &&
                           smart_decision.structure_score >= 75 &&
                           l_sysmem_probability <= 10;
                     } else if (frane_26349_frontier_mode == 2) {
                        frontier_hold =
                           runtime_state.score >= 7 &&
                           smart_decision.structure_score >= 70 &&
                           l_sysmem_probability <= 20;
                     } else if (frane_26349_frontier_mode == 3) {
                        frontier_hold =
                           runtime_state.score >= 6 &&
                           smart_decision.structure_score >= 60 &&
                           l_sysmem_probability <= 50;
                        probe_mask = UINT64_C(1023); /* 1/1024 */
                     } else {
                        frontier_hold =
                           runtime_state.score >= 6 &&
                           smart_decision.structure_score >= 50 &&
                           l_sysmem_probability <= 60;
                        probe_mask = UINT64_C(2047); /* 1/2048 */
                     }

                     if (frontier_hold) {
                        /* V49 intentionally makes GMEM authoritative inside
                         * the selected frontier window. The rare SYSMEM probe
                         * remains timestamped so a changed workload still has
                         * an escape path through the measured state machine.
                         */
                        frane_26348_suppress_live_probe = true;
                        runtime_decision.override_mode = true;
                        runtime_decision.select_sysmem =
                           (decision_word & probe_mask) == 0;
                        runtime_decision.force_measure =
                           runtime_decision.select_sysmem;
                     }
                  }
               }"""

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    old,
    new,
    "replace fixed sticky window with four-step GMEM frontier sweep",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V48 / Mesa ",
    "Drnas Turnip V49 / Mesa ",
    "V49 display identity",
)

# Hard guards: this build may change mode-selection pressure, not correctness.
a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
wsi = (V / "tu_wsi.cc").read_text()

for needle in (
    'TU_A810_26349_GMEM_FRONTIER_MODE", 2',
    "frane_26349_frontier_mode == 0",
    "runtime_state.score >= 7",
    "smart_decision.structure_score >= 70",
    "l_sysmem_probability <= 50",
    "l_sysmem_probability <= 60",
    "UINT64_C(1023)",
    "UINT64_C(2047)",
):
    assert needle in a, needle

# The evolved V26->V32 safety policy remains the final authority after selection.
# V27 replaced the old TU_A810_26326_GMEM_ALLOW_DEPTH knob, so guard the
# current known-good attachment policy instead of asserting a stale option.
for needle in (
    'TU_A810_26326_GMEM_SAFETY", true',
    'TU_A810_26327_GMEM_SIMPLE_DEPTH", true',
    'TU_A810_26328_GMEM_SIMPLE_DS", true',
    'TU_A810_26330_GMEM_PACKED_DS", true',
    'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false',
    "subpass.resolve_depth_stencil",
    "subpass.feedback_loop_ds",
    "subpass.samples != VK_SAMPLE_COUNT_1_BIT",
):
    assert needle in a, needle
assert "frane_a810_gmem_pass_safe" in a
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3

# Preserve the validated allocator/search and CB stack.
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26337_GMEM_MASK_PACK", true' in passcc
assert 'TU_A810_26347_CB_PROFILE_MODE' in cmd

# Aggressive legacy GMEM-TURBO stays opt-in and WSI remains clean.
assert 'TU_A810_26320_GMEM_TURBO", false' in a
assert "V28-CLEAN: no driver present-mode override" in wsi

assert "Drnas Turnip V49 / Mesa " in d
print("Drnas Turnip V49 GMEM-FRONTIER applied", flush=True)
