#!/usr/bin/env python3
"""Frane Mesa 26.3.20 A810 GMEM-TURBO EXP.

Layered strictly on green 26.3.19 MEMORY-AUDIT.

This is intentionally an aggressive A810-only render-mode experiment.  It does
not change GMEM layout, attachment offsets, LRZ state, synchronization, shader
code or the proven adaptive IR3 window.  It only changes the SMART-GMEM mode
selection policy.

Default-on:
  TU_A810_26320_GMEM_TURBO=1

Opt-out:
  TU_A810_26320_GMEM_TURBO=0
  -> exact 26.3.19 / 26.3.18 SMART-GMEM policy.
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
            f"26.3.20 GMEM-TURBO source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.20 GMEM-TURBO PASS {label}", flush=True)


shutil.copyfile("patches/frane_mesa_26320_a810_gmem_turbo.h",
                V / "frane_mesa_26320_a810_gmem_turbo.h")

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_26318_a810_smart_gmem.h"',
    '#include "frane_mesa_26318_a810_smart_gmem.h"\n#include "frane_mesa_26320_a810_gmem_turbo.h"',
    "include aggressive A810 GMEM policy",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_lean_profiled()
{""",
    """static bool
frane_a810_gmem_turbo_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26320_GMEM_TURBO", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_lean_profiled()
{""",
    "add default-on A810 GMEM-TURBO gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         const frane_26318_smart_gmem_input *gmem_runtime_input = nullptr,
         bool smart_gmem = false)
      {""",
    """         const frane_26318_smart_gmem_input *gmem_runtime_input = nullptr,
         bool smart_gmem = false,
         bool gmem_turbo = false)
      {""",
    "extend profiled decision with turbo gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """               const auto smart_decision = frane_26318_decide_smart_gmem(
                  true, *gmem_runtime_input, runtime_state,
                  l_sysmem_probability, decision_word);""",
    """               const auto smart_decision =
                  gmem_turbo ?
                  frane_26320_decide_gmem_turbo(
                     true, *gmem_runtime_input, runtime_state,
                     l_sysmem_probability, decision_word) :
                  frane_26318_decide_smart_gmem(
                     true, *gmem_runtime_input, runtime_state,
                     l_sysmem_probability, decision_word);""",
    "select aggressive policy only behind A810 turbo gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device));""",
    """         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device),
         frane_a810_gmem_turbo_enabled(device));""",
    "wire turbo gate into render-mode decision",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.19 A810 MEMORY-AUDIT / Mesa ",
    "Frane Mesa 26.3.20 A810 GMEM-TURBO EXP / Mesa ",
    "experimental driver identity",
)

autotune = (V / "tu_autotune.cc").read_text()
device = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
sched = (ROOT / "src/freedreno/ir3/ir3_sched.c").read_text()

for needle in (
    "TU_A810_26320_GMEM_TURBO",
    "frane_26320_decide_gmem_turbo",
    "frane_a810_gmem_turbo_enabled",
    "bool gmem_turbo = false",
):
    assert needle in autotune, needle

# Exact fallback remains reachable.
assert "frane_26318_decide_smart_gmem(" in autotune
assert "TU_A810_26318_SMART_GMEM" in autotune

# Keep today's proven/safety-sensitive pieces untouched.
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'frane_26313_same_lrz_fs_signature' not in cmd
assert 'TU_A810_26317_TEX_WINDOW_MAX", 12' in (
    ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert 'frane_26317_sy_window' in sched
assert 'Frane Mesa 26.3.20 A810 GMEM-TURBO EXP' in device

print("Frane Mesa 26.3.20 A810 GMEM-TURBO EXP applied", flush=True)
