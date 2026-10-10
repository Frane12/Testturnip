#!/usr/bin/env python3
"""A830 S2-RFC3 measured, recoverable SYSMEM regime guard.
Use on the tested RFC2 base. Audits keep GMEM recoverable; original hardware
safety/allocator/timestamp accounting remain unchanged.
"""
from pathlib import Path
import hashlib,shutil
ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}
def edit(path,old,new,label):
    text=path.read_text()
    n=text.count(old)
    if n!=1:
        raise SystemExit(f"RFC3 source drift/collision: {label}: expected 1 got {n}")
    path.write_text(text.replace(old,new,1))
    print(f"RFC3 PASS {label}",flush=True)
shutil.copyfile("patches/frane_a830_rfc3.h",V/"frane_a830_rfc3.h")
smart=V/"frane_mesa_26318_a810_smart_gmem.h"
edit(smart,
     "   bool a830_rfc1 = false;",
     "   bool a830_rfc1 = false;\n   bool a830_rfc3 = false;",
     "add exact-A830 guard input")

auto=V/"tu_autotune.cc"
edit(auto,
     '#include "frane_a830_rfc2.h"',
     '#include "frane_a830_rfc2.h"\n#include "frane_a830_rfc3.h"',
     "include measured regime guard")

edit(auto,
     """static bool
frane_a830_rfc1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC1", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     """static bool
frane_a830_rfc1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC1", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_rfc3_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC3_GUARD", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     "runtime A/B toggle, exact A830 only")

edit(auto,
     """         runtime_input.a830_rfc1 =
            runtime_input.a830_bw2 && frane_a830_rfc1_enabled(device);

         if (runtime_input.a830_bw2) {""",
     """         runtime_input.a830_rfc1 =
            runtime_input.a830_bw2 && frane_a830_rfc1_enabled(device);
         runtime_input.a830_rfc3 =
            runtime_input.a830_rfc1 && frane_a830_rfc3_enabled(device);

         if (runtime_input.a830_bw2) {""",
     "feed guard gate only for valid A830/BW2")

edit(auto,
     """             frane_2634_eval_layout(gmem_runtime_input->layout).eligible) {
            const auto d = frane_26364_select(""",
     """             frane_2634_eval_layout(gmem_runtime_input->layout).eligible) {
            /* RFC2 evidence: SMART_V2 owns decisions before downstream
             * BW2 measured rollback can execute. Intercept only strongly
             * measured SYSMEM winners, with sparse GMEM re-audits.
             */
            if (gmem_runtime_input->a830_rfc3) {
               const auto guard = frane_a830_rfc3_select(
                  true, gmem_runtime_input->a830_history_ready,
                  gmem_runtime_input->a830_history_score,
                  gmem_runtime_input->a830_history_pairs,
                  history.sysmem_rp_average.count,
                  history.gmem_rp_average.count,
                  history.sysmem_rp_average.get(),
                  history.gmem_rp_average.get(),
                  occurrence, history.hash);
               if (guard.owns) {
                  *measure = guard.measure;
                  if (rfc2_reason)
                     *rfc2_reason = guard.audit
                        ? FRANE_A830_RFC2_REGIME_AUDIT
                        : FRANE_A830_RFC2_REGIME_GUARD;
                  return guard.sysmem ? render_mode::SYSMEM
                                      : render_mode::GMEM;
               }
            }
            const auto d = frane_26364_select(""",
     "measured early guard BEFORE SMART_V2 selector ownership")

rfc2=V/"frane_a830_rfc2.h"
edit(rfc2,
     "   FRANE_A830_RFC2_RUNTIME = 6,",
     "   FRANE_A830_RFC2_RUNTIME = 6,\n   FRANE_A830_RFC2_REGIME_GUARD = 7,\n   FRANE_A830_RFC2_REGIME_AUDIT = 8,",
     "include accountable measured guard decision source")
edit(rfc2,
     """   case FRANE_A830_RFC2_RUNTIME: return "RUNTIME";""",
     """   case FRANE_A830_RFC2_RUNTIME: return "RUNTIME";
   case FRANE_A830_RFC2_REGIME_GUARD: return "REGIME_GUARD";
   case FRANE_A830_RFC2_REGIME_AUDIT: return "REGIME_AUDIT";""",
     "trace guard/audit reasons separately")

# Correct RFC2 timestamp unit labels: Mesa's get_rp_duration returns GPU
# counter delta (CP_ALWAYS_ON_COUNTER 19.2MHz), NOT nanoseconds. Only names
# change, existing comparisons and stored values remain bit-identical.
r=rfc2.read_text()
for old,new in [("gpu_ns","gpu_ticks"),("sys_ema_ns","sys_ema_ticks"),
                ("gmem_ema_ns","gmem_ema_ticks")]:
    assert old in r,old
    r=r.replace(old,new)
rfc2.write_text(r)
print("RFC3 PASS GPU timestamp unit headers (ticks 19.2MHz not nanoseconds)",flush=True)

edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-RFC2 Measured Render / Mesa ",
     "Turnip-Drnas A830 S2-RFC3 Measured Guard / Mesa ",
     "new driver identity")
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a830_rfc3.h","vulkan/frane_a830_rfc2.h",
          "vulkan/frane_mesa_26318_a810_smart_gmem.h",
          "vulkan/tu_autotune.cc","vulkan/tu_device.cc"}
if changed!=expected:
    raise SystemExit(f"RFC3 unexpected code changes {sorted(changed^expected)}")
print("A830 RFC3 runtime, early-selector ordering, diagnostic units, scope PASS",flush=True)
