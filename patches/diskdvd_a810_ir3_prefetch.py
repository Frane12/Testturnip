#!/usr/bin/env python3
"""Port the *audited* DiskDVD A8XX A810 descriptor-prefetch workaround.

Source: DiskDVD/A8XX-Y branch A8XX, ir3_compiler.c, 2026-09-21 commit
6ccfee74478e63f2993e63697d8b730dd547b03e.
The full fork is NOT wholesale merged: its ~148 divergent Freedreno files
include other upstream commits, GPU profiles and register changes.
Do not copy its default 90% advertised heap budget or change the reserved GMEM
or CCU on-chip geometry without device proof.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/ir3/ir3_compiler.c")
s = p.read_text()
def once(old,new,why):
   global s
   n=s.count(old)
   if n!=1: raise RuntimeError(f"{why}: expected 1 anchor, got {n}")
   s=s.replace(old,new,1)
   print("PASS "+why,flush=True)
once('#include "util/u_call_once.h"',
     '#include "util/u_call_once.h"\n#include "util/os_misc.h"\n#include <string.h>',
     "A810 env option include")
once("""   compiler->info = dev_info;

   /* TODO see if older GPU's were different here */""",
"""   compiler->info = dev_info;

   /* DiskDVD A8XX-Y: disable descriptor prefetch on Adreno 810.
    * This is shader/codegen diagnostic for flickering sampled sunlight,
    * NOT a claimed fix. Keep fully optional to permit A/B comparisons.
    *
    * A810 is the only GPU affected. The existing global IR3 debug flag
    * is initialized once per driver process and checked by shader compilation.
    */
   const char *a810_env = os_get_option("IR3_A810_DISKDVD_PREFETCH");
   const bool a810_diskdvd_prefetch = !a810_env || strcmp(a810_env, "0") != 0;
   if (a810_diskdvd_prefetch &&
       (dev_id->chip_id == 0x44010000ull ||
        dev_id->chip_id == 0xffff44010000ull))
      ir3_shader_debug |= IR3_DBG_NODESCPREFETCH;

   /* TODO see if older GPU's were different here */""",
     "DiskDVD A810 shader descriptor prefetch workaround")
p.write_text(s)
