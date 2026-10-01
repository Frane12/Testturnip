#!/usr/bin/env python3
"""Drnas Turnip V67 A810 MOMENTUM-SCHED.

Layered strictly on V66 WIDE-LAB.

V67 keeps the V66 shader-pressure controller as the neutral path, then adds a
small per-block pressure-direction EMA.  Rising pressure brakes the SY/texture
producer window earlier; draining pressure can reopen one bounded step of MLP.

Default-on:
  TU_FRANE_MOMENTUM=1

Opt-out:
  TU_FRANE_MOMENTUM=0

This is a compiler scheduling experiment only.  Vulkan correctness paths and
the V66 simple-color resolve admission are unchanged.
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
            f"V67 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V67 PASS {label}", flush=True)


# Pure helper is copied into IR3 where the scheduler consumes it.
shutil.copyfile(
    "patches/frane_mesa_26367_a810_momentum_sched.h",
    I / "frane_mesa_26367_a810_momentum_sched.h",
)

edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   /* V66 broad-workload scheduler controller. */
   bool frane_26366_shader_balance;
""",
    """   /* V66 broad-workload scheduler controller. */
   bool frane_26366_shader_balance;

   /* V67 pressure-direction scheduler controller. */
   bool frane_26367_momentum_sched;
""",
    "add V67 compiler policy bit",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26366_shader_balance =
         debug_get_bool_option("TU_FRANE_SHADER", true);
""",
    """      compiler->frane_26366_shader_balance =
         debug_get_bool_option("TU_FRANE_SHADER", true);

      compiler->frane_26367_momentum_sched =
         debug_get_bool_option("TU_FRANE_MOMENTUM", true);
""",
    "enable V67 momentum scheduler by default",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """#include "frane_mesa_26366_a810_wide_lab.h"
""",
    """#include "frane_mesa_26366_a810_wide_lab.h"
#include "frane_mesa_26367_a810_momentum_sched.h"
""",
    "include V67 momentum helper",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   int frane_live_gpr_elems;
};""",
    """   int frane_live_gpr_elems;

   /* V67: short per-block EMA of pressure direction, x4 fixed point. */
   uint8_t frane_26367_prev_pressure_pct;
   int frane_26367_momentum_x4;
   bool frane_26367_pressure_valid;
};""",
    "add V67 per-block pressure momentum state",
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
    "forward-declare pressure estimator for schedule update",
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

      if (ctx->compiler->frane_26367_momentum_sched) {
         const unsigned pressure = frane_26317_pressure_pct(ctx);

         if (!ctx->frane_26367_pressure_valid) {
            ctx->frane_26367_prev_pressure_pct = pressure;
            ctx->frane_26367_momentum_x4 = 0;
            ctx->frane_26367_pressure_valid = true;
         } else {
            const int delta =
               (int)pressure - (int)ctx->frane_26367_prev_pressure_pct;

            /* 3/4 previous + 1/4 newest delta, stored as x4 fixed point.
             * Integer-only and bounded by the scheduler's 0..100% signal.
             */
            ctx->frane_26367_momentum_x4 =
               (ctx->frane_26367_momentum_x4 * 3 + delta * 4) / 4;
            ctx->frane_26367_prev_pressure_pct = pressure;
         }
      }
   }

   di(instr, "schedule");""",
    "update pressure-direction EMA once per scheduled instruction",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   return frane_26366_shader_window(
      ctx->compiler->frane_26366_shader_balance,
      p, legacy_window);""",
    """   const unsigned v66_window = frane_26366_shader_window(
      ctx->compiler->frane_26366_shader_balance,
      p, legacy_window);

   return frane_26367_momentum_window(
      ctx->compiler->frane_26367_momentum_sched,
      p, ctx->frane_26367_momentum_x4, v66_window);""",
    "layer pressure momentum on top of V66 shader window",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   ctx->frane_live_gpr_elems = 0;

   /* The terminator has to stay at the end.""",
    """   ctx->frane_live_gpr_elems = 0;
   ctx->frane_26367_prev_pressure_pct = 0;
   ctx->frane_26367_momentum_x4 = 0;
   ctx->frane_26367_pressure_valid = false;

   /* The terminator has to stay at the end.""",
    "reset V67 momentum state per block",
)

# Vulkan cache identity: one additional compiler-policy field.
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
   options[11] = debug_get_bool_option("TU_FRANE_MOMENTUM", true);
}""",
    "hash V67 momentum policy in Vulkan cache identity",
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
         compiler->frane_26367_momentum_sched,
      };
      static const char schema[] = "frane-a810-compile-options-v3";""",
    "hash V67 momentum policy in IR3 disk-cache identity",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V66 / Mesa ",
    "Drnas Turnip V67 / Mesa ",
    "V67 display identity",
)

# Audit guards.
compiler_c = (I / "ir3_compiler.c").read_text()
compiler_h = (I / "ir3_compiler.h").read_text()
sched = (I / "ir3_sched.c").read_text()
disk = (I / "ir3_disk_cache.c").read_text()
device = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

assert 'TU_FRANE_MOMENTUM", true' in compiler_c
assert "frane_26367_momentum_sched" in compiler_h
assert "frane_26367_momentum_window" in sched
assert "frane_26367_momentum_x4" in sched
assert "frane_26317_pressure_pct(ctx)" in sched
assert "frane_26367_pressure_valid = false" in sched

assert "frane-a810-compile-options-v3" in device
assert "frane-a810-compile-options-v3" in disk
assert 'options[11] = debug_get_bool_option("TU_FRANE_MOMENTUM", true);' in device
assert "compiler->frane_26367_momentum_sched" in disk

# Preserve the V66 broad-lab modules and V61 correctness stack.
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
assert "Drnas Turnip V67 / Mesa " in device

print("Drnas Turnip V67 MOMENTUM-SCHED applied", flush=True)
