#!/usr/bin/env python3
"""A830 IR3-LS1 overlay on *exact* tested S2-BW1. No BW2/CX1.
One switch TU_FRANE_A830_IR3_LS1=0 returns the BW1 compiler policy.
This is a pre-register-allocation shader compile tweak, NOT frame-time work.
"""
from pathlib import Path
import shutil
import hashlib

ROOT = Path("mesa/src/freedreno")
I = ROOT / "ir3"
V = ROOT / "vulkan"
before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in ROOT.rglob("*") if p.is_file()}

def edit(path, old, new, what):
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"IR3-LS1 source collision/drift {what}: expected 1, saw {n}")
    path.write_text(s.replace(old, new, 1))
    print("IR3-LS1 PASS", what, flush=True)

shutil.copyfile("patches/frane_a830_ir3_ls1.h", I / "frane_a830_ir3_ls1.h")
edit(I / "ir3_sched.c",
     '#include "frane_a830_s2d2_sched.h"',
     '#include "frane_a830_s2d2_sched.h"\n#include "frane_a830_ir3_ls1.h"',
     "include new policy into IR3 scheduler")

edit(I / "ir3_compiler.h",
     "   uint8_t frane_a830_s2d2_pressure_threshold;",
     """   uint8_t frane_a830_s2d2_pressure_threshold;

   /* A830-only IR3-LS1 shader compile policy, default on. */
   bool frane_a830_ir3_ls1_enabled;""",
     "A830-only compiler gate")

edit(I / "ir3_compiler.c",
     """      compiler->frane_a830_s2d2_pressure_threshold =
         frane_a830_s2d2_pressure_threshold(
            debug_get_num_option("TU_FRANE_A830_SHADER_PRESSURE", 42));
   }""",
     """      compiler->frane_a830_s2d2_pressure_threshold =
         frane_a830_s2d2_pressure_threshold(
            debug_get_num_option("TU_FRANE_A830_SHADER_PRESSURE", 42));

      /* The enclosing exact-A830 chip-ID guard prevents A810 or other GPUs
       * from receiving this experimental scheduler policy.
       */
      compiler->frane_a830_ir3_ls1_enabled =
         compiler->frane_26317_adaptive_sched &&
         debug_get_bool_option("TU_FRANE_A830_IR3_LS1", true);
   }""",
     "initialize gated A830 compiler knob")

edit(I / "ir3_sched.c",
     """   if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 10u);
   if (p < 50)
      return 8;
   if (p < 65)
      return 6;
   return 4;
}""",
     """   unsigned bw1_window;
   if (p < 20)
      bw1_window = max_window;
   else if (p < 35)
      bw1_window = MIN2(max_window, 10u);
   else if (p < 50)
      bw1_window = 8;
   else if (p < 65)
      bw1_window = 6;
   else
      bw1_window = 4;

   return frane_a830_ir3_ls1_sy_window(
      ctx->compiler->frane_a830_ir3_ls1_enabled,
      p, bw1_window, max_window);
}""",
     "extend existing adaptive sy window without second scheduler")

sched = I / "ir3_sched.c"
s = sched.read_text()
old = """      ctx->compiler->frane_26317_adaptive_sched,
      frane_26317_pressure_pct(ctx),
      ctx->compiler->frane_a830_s2d2_pressure_threshold);"""
new = """      ctx->compiler->frane_26317_adaptive_sched,
      frane_26317_pressure_pct(ctx),
      frane_a830_ir3_ls1_pressure_threshold(
         ctx->compiler->frane_a830_ir3_ls1_enabled,
         ctx->compiler->frane_a830_s2d2_pressure_threshold));"""
assert s.count(old) == 2, f"IR3-LS1 unexpected tie-break call count: {s.count(old)}"
sched.write_text(s.replace(old, new))
print("IR3-LS1 PASS existing S2-D2 tie-break x2", flush=True)

edit(I / "ir3_disk_cache.cpp",
     """   _mesa_blake3_update(&ctx, &compiler->frane_a830_s2d2_pressure_threshold,
                     sizeof(compiler->frane_a830_s2d2_pressure_threshold));
   _mesa_blake3_final(&ctx, blake3);""",
     """   _mesa_blake3_update(&ctx, &compiler->frane_a830_s2d2_pressure_threshold,
                     sizeof(compiler->frane_a830_s2d2_pressure_threshold));
   /* Never reuse BW1 shader cache entries for a different LS1 instruction
    * order; the switch is processed at shader compiler initialization.
    */
   _mesa_blake3_update(&ctx, &compiler->frane_a830_ir3_ls1_enabled,
                     sizeof(compiler->frane_a830_ir3_ls1_enabled));
   _mesa_blake3_final(&ctx, blake3);""",
     "include LS1 policy in IR3 disk-cache key")

edit(V / "tu_device.cc",
     "Turnip-Drnas A830 S2-BW1 / Mesa ",
     "Turnip-Drnas A830 S2-IR3-LS1 / Mesa ",
     "driver display identity")

c = (I / "ir3_compiler.c").read_text()
s = sched.read_text()
cache = (I / "ir3_disk_cache.cpp").read_text()
assert 'TU_FRANE_A830_IR3_LS1", true' in c
assert 'compiler->frane_26317_adaptive_sched &&' in c
assert 'frane_a830_ir3_ls1_sy_window' in s
assert s.count("frane_a830_ir3_ls1_pressure_threshold(") == 2
assert 'compiler->frane_a830_ir3_ls1_enabled' in cache
assert "return frane_a830_ir3_ls1_sy_window(" in s
assert "Turnip-Drnas A830 S2-IR3-LS1 / Mesa " in (V/"tu_device.cc").read_text()

after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in ROOT.rglob("*") if p.is_file()}
changed = {k for k in before.keys() | after.keys()
           if before.get(k) != after.get(k)}
expected = {
    "ir3/frane_a830_ir3_ls1.h",
    "ir3/ir3_sched.c",
    "ir3/ir3_compiler.h",
    "ir3/ir3_compiler.c",
    "ir3/ir3_disk_cache.cpp",
    "vulkan/tu_device.cc",
}
if changed != expected:
    raise SystemExit(f"IR3-LS1 unexpected source scope: {sorted(changed ^ expected)}")
print("A830 IR3-LS1 runtime/cache/collision and source-scope audit PASS", flush=True)
