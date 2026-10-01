#!/usr/bin/env python3
"""Drnas Turnip V68 A810 ADAPTIVE-HYSTERESIS.

Layered strictly on V66 WIDE-LAB.

V67 pressure momentum is intentionally absent. V68 instead turns V66's
stateless live-pressure bands into a stateful Schmitt controller with
confirmed reopening. The controller advances once per scheduled IR3
instruction, never once per candidate scan.

Default-on:
  TU_FRANE_HYST=1

Opt-out:
  TU_FRANE_HYST=0  -> exact V66 scheduler behavior.

This is a compiler scheduling experiment only. Vulkan correctness paths,
GMEM policy and V66 simple-color resolve admission remain unchanged.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
F = ROOT / "src/freedreno"
I = F / "ir3"
V = F / "vulkan"


def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V68 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V68 PASS {label}", flush=True)


shutil.copyfile(
    "patches/frane_mesa_26368_a810_adaptive_hysteresis.h",
    I / "frane_mesa_26368_a810_adaptive_hysteresis.h",
)

edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   /* V66 broad-workload scheduler controller. */
   bool frane_26366_shader_balance;
""",
    """   /* V66 broad-workload scheduler controller. */
   bool frane_26366_shader_balance;

   /* V68 stateful pressure-band controller. */
   bool frane_26368_adaptive_hysteresis;
""",
    "add V68 compiler policy bit",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26366_shader_balance =
         debug_get_bool_option("TU_FRANE_SHADER", true);
""",
    """      compiler->frane_26366_shader_balance =
         debug_get_bool_option("TU_FRANE_SHADER", true);

      compiler->frane_26368_adaptive_hysteresis =
         debug_get_bool_option("TU_FRANE_HYST", true);
""",
    "enable V68 adaptive hysteresis by default",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """#include "frane_mesa_26366_a810_wide_lab.h"
""",
    """#include "frane_mesa_26366_a810_wide_lab.h"
#include "frane_mesa_26368_a810_adaptive_hysteresis.h"
""",
    "include V68 hysteresis helper",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   int frane_live_gpr_elems;
};""",
    """   int frane_live_gpr_elems;

   /* V68: one state machine per shader block. */
   struct frane_26368_hyst_state frane_26368_hyst;
};""",
    "add V68 block-local controller state",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """static int live_effect(struct ir3_instruction *instr);

static bool
is_scheduled""",
    """static int live_effect(struct ir3_instruction *instr);
static unsigned frane_26317_pressure_pct(struct ir3_sched_ctx *ctx);

static bool
is_scheduled""",
    "forward-declare pressure estimator for V68 state update",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   if (ctx->compiler->frane_26317_adaptive_sched) {
      ctx->frane_live_gpr_elems =
         MAX2(0, ctx->frane_live_gpr_elems + frane_live_delta);
   }

   di(instr, "schedule");""",
    """   if (ctx->compiler->frane_26317_adaptive_sched) {
      ctx->frane_live_gpr_elems =
         MAX2(0, ctx->frane_live_gpr_elems + frane_live_delta);

      /* Advance adaptation exactly once per real scheduling decision. */
      if (ctx->compiler->frane_26366_shader_balance &&
          ctx->compiler->frane_26368_adaptive_hysteresis) {
         const unsigned pressure = frane_26317_pressure_pct(ctx);
         frane_26368_hyst_step(&ctx->frane_26368_hyst, pressure);
      }
   }

   di(instr, "schedule");""",
    "advance V68 controller once per scheduled instruction",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   return frane_26366_shader_window(
      ctx->compiler->frane_26366_shader_balance,
      p, legacy_window);""",
    """   const unsigned v66_window = frane_26366_shader_window(
      ctx->compiler->frane_26366_shader_balance,
      p, legacy_window);

   if (!ctx->compiler->frane_26366_shader_balance ||
       !ctx->compiler->frane_26368_adaptive_hysteresis ||
       !ctx->frane_26368_hyst.valid)
      return v66_window;

   return ctx->frane_26368_hyst.window;""",
    "serve stable V68 state instead of reclassifying every candidate",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   ctx->frane_live_gpr_elems = 0;

   /* The terminator has to stay at the end.""",
    """   ctx->frane_live_gpr_elems = 0;
   ctx->frane_26368_hyst.window = 0;
   ctx->frane_26368_hyst.recover_streak = 0;
   ctx->frane_26368_hyst.valid = false;

   /* The terminator has to stay at the end.""",
    "reset V68 controller per shader block",
)

# Vulkan cache identity: append the V68 compiler-policy bit.
edit(
    "src/freedreno/vulkan/tu_device.cc",
    "frane_26323_a810_cache_options(uint32_t options[11])",
    "frane_26323_a810_cache_options(uint32_t options[12])",
    "extend Vulkan compiler-option cache vector",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    """   options[10] = debug_get_bool_option("TU_FRANE_SHADER", true);
}""",
    """   options[10] = debug_get_bool_option("TU_FRANE_SHADER", true);
   options[11] = debug_get_bool_option("TU_FRANE_HYST", true);
}""",
    "hash V68 hysteresis policy in Vulkan cache identity",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "      uint32_t options[11];",
    "      uint32_t options[12];",
    "resize Vulkan compiler-option cache vector",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    'static const char schema[] = "frane-a810-compile-options-v2";',
    'static const char schema[] = "frane-a810-compile-options-v3";',
    "bump Vulkan A810 compiler cache schema",
)

edit(
    "src/freedreno/ir3/ir3_disk_cache.c",
    """         compiler->frane_26366_shader_balance,
      };
      static const char schema[] = "frane-a810-compile-options-v2";""",
    """         compiler->frane_26366_shader_balance,
         compiler->frane_26368_adaptive_hysteresis,
      };
      static const char schema[] = "frane-a810-compile-options-v3";""",
    "hash V68 hysteresis policy in IR3 disk-cache identity",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V66 / Mesa ",
    "Drnas Turnip V68 / Mesa ",
    "V68 display identity",
)

# Audit guards.
compiler_c = (I / "ir3_compiler.c").read_text()
compiler_h = (I / "ir3_compiler.h").read_text()
sched = (I / "ir3_sched.c").read_text()
disk = (I / "ir3_disk_cache.c").read_text()
device = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

assert 'TU_FRANE_HYST", true' in compiler_c
assert "frane_26368_adaptive_hysteresis" in compiler_h
assert "frane_26368_hyst_step(&ctx->frane_26368_hyst, pressure)" in sched
assert "return ctx->frane_26368_hyst.window;" in sched
assert "frane_26368_hyst.valid = false" in sched

assert "frane-a810-compile-options-v3" in device
assert "frane-a810-compile-options-v3" in disk
assert 'options[11] = debug_get_bool_option("TU_FRANE_HYST", true);' in device
assert "compiler->frane_26368_adaptive_hysteresis" in disk

# Preserve exact V66 fallback and the proven V61/V66 correctness stack.
assert 'TU_FRANE_SHADER", true' in compiler_c
assert "frane_26366_shader_window" in sched
assert 'TU_FRANE_RESOLVE", true' in autotune
assert "frane_26366_simple_color_resolve" in autotune
assert 'TU_FRANE_SIG", true' in autotune
assert 'TU_FRANE_FREQ", true' in autotune
assert 'TU_FRANE_SCAN", true' in autotune
assert 'TU_FRANE_LEARN", true' in autotune
assert 'TU_FRANE_TAIL", true' in autotune
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "Drnas Turnip V68 / Mesa " in device

# V67 momentum experiment must not leak into this clean branch.
assert "TU_FRANE_MOMENTUM" not in compiler_c
assert "frane_26367_momentum" not in sched

print("Drnas Turnip V68 ADAPTIVE-HYSTERESIS applied", flush=True)
