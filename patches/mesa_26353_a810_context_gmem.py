#!/usr/bin/env python3
"""Drnas Turnip V53 CONTEXT-GMEM.

Layered on V52 CLEAN-INTERFACE.

Default:
  TU_FRANE_CONTEXT_MODE=1  balanced context policy
  TU_FRANE_CONTEXT_MODE=2  more aggressive GMEM threshold
  TU_FRANE_CONTEXT_MODE=0  exact V52 policy

The policy combines:
- V18 structural score / tile footprint
- attachment and GMEM-attachment count
- depth lifetime across subpasses (depth reuse)
- expected color/depth resolves
- Mesa's per-pixel GMEM/SYSMEM bandwidth estimates
- draw density / estimated tile count
- V4 measured GMEM hysteresis state
- Mesa PROFILED temporal probability

A dead-band preserves the prior decision for ambiguous passes. Rare opposite-
mode control probes (1/128..1/512) keep the model adaptive without re-profiling
every scene transition.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V53 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V53 PASS {label}", flush=True)

shutil.copyfile(
    "patches/frane_mesa_26353_a810_context_gmem.h",
    V / "frane_mesa_26353_a810_context_gmem.h",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_26318_a810_smart_gmem.h"',
    '#include "frane_mesa_26318_a810_smart_gmem.h"\n#include "frane_mesa_26353_a810_context_gmem.h"',
    "include context GMEM policy",
)

# Extend the V18 transport object so pass-level context reaches the measured
# decision point without adding another allocation or hash table.
edit(
    "src/freedreno/vulkan/frane_mesa_26318_a810_smart_gmem.h",
    """   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
};""",
    """   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;

   uint32_t attachment_count = 0;
   uint32_t gmem_attachment_count = 0;
   uint32_t depth_attachment_count = 0;
   uint32_t resolve_count = 0;
   uint32_t depth_reuse_span = 0;
   uint32_t subpass_count = 0;
};""",
    "carry attachment/depth/resolve context",
)

# Populate context using data already computed by Mesa while building the
# render pass. No per-frame heap allocation and no new GPU query is added.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;
      }
""",
    """         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;
         runtime_input.attachment_count = pass->attachment_count;
         runtime_input.subpass_count = pass->subpass_count;

         for (uint32_t i = 0; i < pass->attachment_count; i++) {
            const struct tu_render_pass_attachment &att = pass->attachments[i];
            if (!att.gmem)
               continue;

            runtime_input.gmem_attachment_count++;
            if (vk_format_has_depth(att.format) ||
                vk_format_has_stencil(att.format)) {
               runtime_input.depth_attachment_count++;
               if (att.last_subpass_idx >= att.first_subpass_idx)
                  runtime_input.depth_reuse_span +=
                     att.last_subpass_idx - att.first_subpass_idx + 1;
            }
         }

         for (uint32_t i = 0; i < pass->subpass_count; i++) {
            runtime_input.resolve_count += pass->subpasses[i].resolve_count;
            if (pass->subpasses[i].resolve_depth_stencil)
               runtime_input.resolve_count++;
         }
      }
""",
    "collect pass context without runtime allocation",
)

# Apply the context model after the existing SMART/FRONTIER logic but before
# the selected runtime mode is committed. This lets the new score correct an
# over-eager GMEM hold as well as promote a high-confidence GMEM case.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            if (runtime_decision.override_mode) {
               select_sysmem = runtime_decision.select_sysmem;
               runtime_force_measure = runtime_decision.force_measure;
            }
         }
""",
    """            static const int frane_26353_context_mode =
               static_cast<int>(std::clamp<int64_t>(
                  debug_get_num_option("TU_FRANE_CONTEXT_MODE", 1),
                  INT64_C(0), INT64_C(2)));

            if (frane_26353_context_mode > 0) {
               frane_26353_context_input context {};
               const auto structural =
                  frane_26318_eval_smart_gmem(*gmem_runtime_input);
               context.eligible = structural.eligible;
               context.structure_score = structural.structure_score;
               context.measured_score = runtime_state.score;
               context.measured_armed = runtime_state.armed;
               context.sysmem_probability = l_sysmem_probability;
               context.attachment_count = gmem_runtime_input->attachment_count;
               context.gmem_attachment_count =
                  gmem_runtime_input->gmem_attachment_count;
               context.depth_attachment_count =
                  gmem_runtime_input->depth_attachment_count;
               context.resolve_count = gmem_runtime_input->resolve_count;
               context.depth_reuse_span =
                  gmem_runtime_input->depth_reuse_span;
               context.subpass_count = gmem_runtime_input->subpass_count;
               context.drawcalls = gmem_runtime_input->layout.drawcalls;
               context.estimated_tiles = structural.estimated_tiles;
               context.sysmem_bandwidth_per_pixel =
                  gmem_runtime_input->sysmem_bandwidth_per_pixel;
               context.gmem_bandwidth_per_pixel =
                  gmem_runtime_input->gmem_bandwidth_per_pixel;

               const auto context_decision =
                  frane_26353_decide_context(
                     frane_26353_context_mode, context, decision_word);

               if (context_decision.override_mode) {
                  runtime_decision.override_mode = true;
                  runtime_decision.select_sysmem =
                     context_decision.select_sysmem;
                  runtime_decision.force_measure =
                     context_decision.force_measure;
                  frane_26348_suppress_live_probe = true;
               }
            }

            if (runtime_decision.override_mode) {
               select_sysmem = runtime_decision.select_sysmem;
               runtime_force_measure = runtime_decision.force_measure;
            }
         }
""",
    "blend context score into measured render-mode decision",
)

# When V53 is active, the old unconditional depth-only post-selector would
# override a context decision back to GMEM. Bypass that legacy selector only
# while CONTEXT_MODE is enabled. Mode 0 therefore restores exact V52 behavior.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   static const int mode =
      debug_get_num_option("TU_FRANE_DEPTH_MODE", 1);

   if (mode <= 0 || current != tu_autotune::render_mode::SYSMEM ||""",
    """   static const int mode =
      debug_get_num_option("TU_FRANE_DEPTH_MODE", 1);
   static const int context_mode =
      debug_get_num_option("TU_FRANE_CONTEXT_MODE", 1);

   if (context_mode > 0)
      return current;

   if (mode <= 0 || current != tu_autotune::render_mode::SYSMEM ||""",
    "make V52 depth selector legacy-only under context mode",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V52 / Mesa ",
    "Drnas Turnip V53 / Mesa ",
    "V53 display identity",
)

# Audit the intended scope.
a = (V / "tu_autotune.cc").read_text()
h = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
d = (V / "tu_device.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_CONTEXT_MODE", 1',
    "frane_26353_context_input",
    "frane_26353_decide_context",
    "runtime_input.gmem_attachment_count",
    "runtime_input.depth_reuse_span",
    "runtime_input.resolve_count",
    "context.measured_score = runtime_state.score",
    "context.sysmem_probability = l_sysmem_probability",
):
    assert needle in a, needle

for needle in (
    "gmem_attachment_count",
    "depth_attachment_count",
    "resolve_count",
    "depth_reuse_span",
):
    assert needle in h, needle

# Existing safety/allocator and CB layers remain authoritative.
for needle in (
    'TU_FRANE_GMEM_SAFE", true',
    'TU_FRANE_SIMPLE_DEPTH", true',
    'TU_FRANE_SIMPLE_DS", true',
    'TU_FRANE_PACKED_DS", true',
    'TU_FRANE_STENCIL_LS", false',
):
    assert needle in a, needle
assert "frane_a810_gmem_pass_safe" in a
assert 'TU_FRANE_GMEM_PRESSURE", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_FRANE_CB_MODE' in cmd
assert "Drnas Turnip V53 / Mesa " in d

print("Drnas Turnip V53 CONTEXT-GMEM applied", flush=True)
