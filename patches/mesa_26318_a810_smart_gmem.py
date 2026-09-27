#!/usr/bin/env python3
"""Frane Mesa 26.3.18 A810 SMART-GMEM EXP.

Layered strictly on green 26.3.17 ADAPTIVE-IR3-SCHED.

Adds an A810-only structural GMEM prior to the existing measured PROFILED
runtime. The prior consumes Mesa's own per-render-pass bandwidth metadata,
GMEM tiling geometry and draw density. Measured GPU timings remain authoritative.

Default-on experiment:
  TU_A810_26318_SMART_GMEM=1

Opt-out:
  TU_A810_26318_SMART_GMEM=0

Opt-out restores the 26.3.17 / 26.3.4 measured GMEM runtime policy exactly.
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
            f"26.3.18 SMART-GMEM source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.18 SMART-GMEM PASS {label}", flush=True)


shutil.copyfile("patches/frane_mesa_26318_a810_smart_gmem.h",
                V / "frane_mesa_26318_a810_smart_gmem.h")

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_2634_a810_gmem_runtime.h"',
    '#include "frane_mesa_2634_a810_gmem_runtime.h"\n#include "frane_mesa_26318_a810_smart_gmem.h"',
    "include smart GMEM pure policy",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_lean_profiled()
{""",
    """static bool
frane_a810_smart_gmem_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26318_SMART_GMEM", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_lean_profiled()
{""",
    "add default-on A810 smart GMEM gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         const frane_2634_gmem_layout_input *gmem_runtime_input = nullptr)
      {""",
    """         const frane_26318_smart_gmem_input *gmem_runtime_input = nullptr,
         bool smart_gmem = false)
      {""",
    "extend profiled decision with smart GMEM metadata and gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         bool runtime_force_measure = false;
         if (!definite && measure && lean_fastpath && gmem_runtime_input) {
            const auto layout = frane_2634_eval_layout(*gmem_runtime_input);
            const auto runtime_state = frane_2634_unpack_gmem_state(
               history.frane_gmem_runtime_word.load(std::memory_order_relaxed));
            const auto runtime_decision = frane_2634_decide_gmem_runtime(
               gmem_runtime_input->physical_gmem != 0,
               layout.eligible, runtime_state,
               l_sysmem_probability, decision_word);
            if (runtime_decision.override_mode) {
               select_sysmem = runtime_decision.select_sysmem;
               runtime_force_measure = runtime_decision.force_measure;
            }
         }
""",
    """         bool runtime_force_measure = false;
         if (!definite && measure && lean_fastpath && gmem_runtime_input) {
            const auto layout =
               frane_2634_eval_layout(gmem_runtime_input->layout);
            const auto runtime_state = frane_2634_unpack_gmem_state(
               history.frane_gmem_runtime_word.load(std::memory_order_relaxed));

            frane_2634_gmem_decision runtime_decision {};
            if (smart_gmem) {
               const auto smart_decision = frane_26318_decide_smart_gmem(
                  true, *gmem_runtime_input, runtime_state,
                  l_sysmem_probability, decision_word);
               runtime_decision.override_mode = smart_decision.override_mode;
               runtime_decision.select_sysmem = smart_decision.select_sysmem;
               runtime_decision.force_measure = smart_decision.force_measure;
            } else {
               runtime_decision = frane_2634_decide_gmem_runtime(
                  gmem_runtime_input->layout.physical_gmem != 0,
                  layout.eligible, runtime_state,
                  l_sysmem_probability, decision_word);
            }

            if (runtime_decision.override_mode) {
               select_sysmem = runtime_decision.select_sysmem;
               runtime_force_measure = runtime_decision.force_measure;
            }
         }
""",
    "blend structural cost model with measured GMEM runtime",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      frane_2634_gmem_layout_input runtime_input {};
      if (frane_a810_gmem_runtime_enabled(device)) {
         uint64_t pass_pixels = 0;""",
    """      frane_26318_smart_gmem_input runtime_input {};
      if (frane_a810_gmem_runtime_enabled(device)) {
         uint64_t pass_pixels = 0;""",
    "upgrade runtime metadata container",
)

for label, old, new in [
    ("physical GMEM", "runtime_input.physical_gmem =", "runtime_input.layout.physical_gmem ="),
    ("usable GMEM", "runtime_input.usable_gmem =", "runtime_input.layout.usable_gmem ="),
    ("pixels per tile", "runtime_input.pixels_per_tile =", "runtime_input.layout.pixels_per_tile ="),
    ("pass pixels", "runtime_input.pass_pixels = pass_pixels;", "runtime_input.layout.pass_pixels = pass_pixels;"),
    ("drawcalls", "runtime_input.drawcalls = rp_state->drawcall_count;", "runtime_input.layout.drawcalls = rp_state->drawcall_count;"),
]:
    edit("src/freedreno/vulkan/tu_autotune.cc", old, new, "wrap " + label + " in smart input")

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.layout.drawcalls = rp_state->drawcall_count;
      }

      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.physical_gmem ? &runtime_input : nullptr);
""",
    """         runtime_input.layout.drawcalls = rp_state->drawcall_count;
         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;
      }

      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device));
""",
    "feed Mesa bandwidth metadata into smart GMEM decision",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.17 A810 ADAPTIVE-IR3-SCHED EXP / Mesa ",
    "Frane Mesa 26.3.18 A810 SMART-GMEM EXP / Mesa ",
    "experimental driver identity",
)

# Hard guards.
autotune = (V / "tu_autotune.cc").read_text()
device = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
pipeline = (V / "tu_pipeline.cc").read_text()
sched = (ROOT / "src/freedreno/ir3/ir3_sched.c").read_text()

for needle in (
    "TU_A810_26318_SMART_GMEM",
    "frane_26318_decide_smart_gmem",
    "sysmem_bandwidth_per_pixel",
    "gmem_bandwidth_per_pixel",
    "runtime_input.layout.physical_gmem",
):
    assert needle in autotune, needle

# Opt-out still has the exact old measured-only runtime.
assert "frane_2634_decide_gmem_runtime(" in autotune
assert "gmem_runtime_input->layout.physical_gmem != 0" in autotune

# Preserve previous correctness/performance layers.
assert "TU_A810_26317_ADAPTIVE_SCHED" in (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert "frane_26317_sy_window" in sched
assert "TU_A810_2639_GMEM_DIM_GATING" in cmd
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd
assert "TU_A810_26313_LRZ_FASTPATH" in pipeline

assert "Frane Mesa 26.3.18 A810 SMART-GMEM EXP" in device

print("Frane Mesa 26.3.18 A810 SMART-GMEM EXP applied", flush=True)
