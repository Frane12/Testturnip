#!/usr/bin/env python3
"""Drnas Turnip V51 DEPTH-HEAVY.

Layered strictly on V50 DEPTH-FRONTIER.

Field result:
- V50 MODE=1 (safe depth-only GMEM) materially improved Crysis minimum and
  average versus combined depth/stencil MODE=2.
- The next question is whether forcing *every* safe depth-only pass into GMEM
  leaves performance on the table for small/light render passes.

V51 keeps the proven V50 depth-only path and adds one live workload threshold:

  TU_A810_26351_DEPTH_MIN_DRAWS=0 (default)
      Exact V50 MODE=1 behavior when
      TU_A810_26350_DEPTH_FRONTIER_MODE=1.

  =8 / 16 / 32 / 64 ...
      A safe depth-only pass is forced from PROFILED SYSMEM to GMEM only when
      rp_state->drawcall_count is at least this value.

This is deliberately broad rather than frame-specific: it classifies every
safe depth-only render pass by actual draw density.  Heavy passes retain the
GMEM bandwidth/locality win while tiny passes can stay under PROFILED control.

No GMEM offsets/packing, LRZ state, load/store programming, barriers, shaders,
CB policy, stencil policy, MSAA/resolve rules, or safety gates are changed.
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
            f"V51 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V51 PASS {label}", flush=True)

# Make the field-proven depth-only policy the V51 default while preserving the
# old selector for exact A/B fallback.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'debug_get_num_option("TU_A810_26350_DEPTH_FRONTIER_MODE", 0)',
    'debug_get_num_option("TU_A810_26350_DEPTH_FRONTIER_MODE", 1)',
    "promote proven V50 depth-only mode to default",
)

# Feed render-pass draw density into the live depth selector.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """                           tu_autotune::render_mode current,
                           bool *measure)
{""",
    """                           tu_autotune::render_mode current,
                           uint32_t drawcall_count,
                           bool *measure)
{""",
    "add render-pass draw count to depth selector",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   if (!has_gmem_depth)
      return current;

   /* Mode 1 is the clean depth-only probe. Mode 2 may also force a combined
    * DS pass, but only after the existing V26-V32 safety classifier has
    * already accepted it.
    */
   if (mode == 1 && has_gmem_stencil)
      return current;

   if (measure)
      *measure = false;
""",
    """   if (!has_gmem_depth)
      return current;

   /* Mode 1 is the field-proven depth-only path. Mode 2 remains available
    * only as the prior combined-DS A/B probe.
    */
   if (mode == 1 && has_gmem_stencil)
      return current;

   /* V51: broad workload-density filter.  A threshold of zero is bit-for-bit
    * V50 MODE=1 selection policy.  Non-zero values let PROFILED retain small
    * depth passes in SYSMEM while keeping dense passes in GMEM.
    */
   static const uint32_t min_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_A810_26351_DEPTH_MIN_DRAWS", 0),
         INT64_C(0), INT64_C(4096)));

   if (mode == 1 && drawcall_count < min_draws)
      return current;

   if (measure)
      *measure = false;
""",
    "add live depth draw-density threshold",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      mode = frane_26350_depth_frontier(
         device, cmd_state, pass, framebuffer, mode, &measure);""",
    """      mode = frane_26350_depth_frontier(
         device, cmd_state, pass, framebuffer, mode,
         rp_state->drawcall_count, &measure);""",
    "wire draw density into fast PROFILED path",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      mode = frane_26350_depth_frontier(
         device, cmd_state, pass, framebuffer, mode, nullptr);""",
    """      mode = frane_26350_depth_frontier(
         device, cmd_state, pass, framebuffer, mode,
         rp_state->drawcall_count, nullptr);""",
    "wire draw density into non-fast PROFILED path",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V50 / Mesa ",
    "Drnas Turnip V51 / Mesa ",
    "V51 display identity",
)

a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_A810_26350_DEPTH_FRONTIER_MODE", 1',
    'TU_A810_26351_DEPTH_MIN_DRAWS", 0',
    "drawcall_count < min_draws",
    "INT64_C(4096)",
    "rp_state->drawcall_count, &measure",
    "rp_state->drawcall_count, nullptr",
):
    assert needle in a, needle

# Keep the V50 field-proven split: depth-only is testable independently from
# combined depth/stencil, and the full V26-V32 correctness gate is final.
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
assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 4
assert a.count("frane_26350_depth_frontier(") == 3

# Preserve the validated allocator/search, LRZ-safe and CB stack.
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26337_GMEM_MASK_PACK", true' in passcc
assert 'TU_A810_26347_CB_PROFILE_MODE' in cmd
assert "Drnas Turnip V51 / Mesa " in d

print("Drnas Turnip V51 DEPTH-HEAVY applied", flush=True)
