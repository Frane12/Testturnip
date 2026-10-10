#!/usr/bin/env python3
"""AT5 after complete AT4+RFC1: guarded, A810-only contextual policy.
Keep the existing GMEM-safety, depth-frontier, GPU timestamp result path.
"""
from pathlib import Path
import hashlib, shutil

ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
def hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.rglob("*") if p.is_file()}
before=hashes()
def edit(path, old, new, label):
    s=path.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"AT5 collision or Mesa drift {label}: {n} matches")
    path.write_text(s.replace(old,new,1))
    print("AT5 PASS",label,flush=True)

shutil.copyfile("patches/frane_a810_at5.h",V/"frane_a810_at5.h")
auto=V/"tu_autotune.cc"

edit(auto,
     '#include "frane_a810_at4_rfc1.h"',
     '#include "frane_a810_at4_rfc1.h"\n#include "frane_a810_at5.h"',
     "AT5 opt-in policy header")

edit(auto,
     """static bool
frane_a810_s1at4_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT4", true);
   return enabled && frane_a810_s1at3_enabled(device);
}""",
     """static bool
frane_a810_s1at4_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT4", true);
   return enabled && frane_a810_s1at3_enabled(device);
}

/* AT5 ON by default; TU_FRANE_AT5=0 restores the measured AT4 behavior.
 * RFC1 CSV remains separately off until an explicit absolute path is given.
 */
static bool
frane_a810_at5_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT5", true);
   return enabled && frane_a810_s1at4_enabled(device);
}""",
     "GPU-scoped AT5 rollback")

edit(auto,
     """         bool *at3_controlled = nullptr,
         bool *at4_applied = nullptr)""",
     """         bool *at3_controlled = nullptr,
         bool *at4_applied = nullptr,
         bool s1at5_context = false,
         bool *at5_applied = nullptr)""",
     "optional AT5 context and source reporting")

edit(auto,
     """                  at1 = s1at4_context ?
                     frane_at4_decide(at1_in, snapshot, decision_word) :
                     frane_s1at3_decide(at1_in, snapshot, decision_word);
                  at3_sampling = at1.override_mode;""",
     """                  if (s1at4_context) {
                     const auto baseline =
                        frane_at4_decide(at1_in, snapshot, decision_word);
                     at1 = s1at5_context
                        ? frane_at5_decide(at1_in, snapshot, decision_word, baseline)
                        : baseline;
                     if (at5_applied && s1at5_context &&
                         at1.override_mode &&
                         (!baseline.override_mode ||
                          at1.select_sysmem != baseline.select_sysmem ||
                          at1.force_measure != baseline.force_measure))
                        *at5_applied = true;
                  } else {
                     at1 = frane_s1at3_decide(at1_in, snapshot, decision_word);
                  }
                  at3_sampling = at1.override_mode;""",
     "AT4 fallback and AT5 evidence-based choice")

edit(auto,
     """      const bool at4 = frane_a810_s1at4_enabled(device);
      const bool context_eligible = !at4 ||""",
     """      const bool at4 = frane_a810_s1at4_enabled(device);
      const bool at5 = frane_a810_at5_enabled(device);
      const bool context_eligible = !at4 ||""",
     "enable AT5 only with AT4 hardware/eligibility gate")

edit(auto,
     """      bool at3_controlled = false;
      bool at4_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     """      bool at3_controlled = false;
      bool at4_applied = false;
      bool at5_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     "AT5 source flag without changing mode")

edit(auto,
     """         at4 && context_eligible, &at3_controlled, &at4_applied);""",
     """         at4 && context_eligible, &at3_controlled, &at4_applied,
         at5 && context_eligible, &at5_applied);""",
     "pass AT5 selector gate")

edit(auto,
     """         const uint16_t signature = measure && *rp_ctx ?
            (*rp_ctx)->frane_s1at1_signature : 0;
         const char *source = safety_forced ? "GMEM_SAFETY" :
            depth_overrode ? "DEPTH_FRONTIER" :
            at4_applied ? "AT4_OVERRIDE" :""",
     """         uint16_t signature = measure && *rp_ctx ?
            (*rp_ctx)->frane_s1at1_signature : 0;
         /* Fill context for unmeasured decisions too: this work is only
          * executed if the RFC1 trace path was explicitly configured.
          */
         if (!signature && runtime_input.layout.physical_gmem) {
            frane_s1at1_context_input ctx {};
            ctx.pass_pixels = runtime_input.layout.pass_pixels;
            ctx.estimated_tiles =
               frane_2634_eval_layout(runtime_input.layout).estimated_tiles;
            ctx.drawcalls = runtime_input.layout.drawcalls;
            ctx.sysmem_bandwidth_per_pixel =
               runtime_input.sysmem_bandwidth_per_pixel;
            ctx.gmem_bandwidth_per_pixel =
               runtime_input.gmem_bandwidth_per_pixel;
            ctx.occurrences = runtime_input.tail_occurrences;
            ctx.sysmem_probability = history.profiled.probability();
            ctx.zs_load_store = runtime_input.zs_load_store;
            signature = frane_s1at1_catalog_for(ctx).signature;
         }
         const char *source = safety_forced ? "GMEM_SAFETY" :
            depth_overrode ? "DEPTH_FRONTIER" :
            at5_applied ? "AT5_ADAPT" :
            at4_applied ? "AT4_OVERRIDE" :""",
     "AT5 provenance and measured/unmeasured signatures")

edit(V/"tu_device.cc",
     "Drnas-Turnip A810 AT4-RFC1 Trace / Mesa ",
     "Drnas-Turnip A810 AT5 Context Learner / Mesa ",
     "identifiable driver version")

s=auto.read_text()
for token in ("TU_FRANE_AT5", "frane_at5_decide(", "at5_applied ? \"AT5_ADAPT\"",
              "s1at5_context", "entry.frane_a810_rfc_occurrence",
              "frane_a810_rfc1_timing(", "frane_a810_gmem_pass_safe("):
    assert token in s,token
assert "TU_FRANE_A810_RFC1_TRACE_PATH" in (V/"frane_a810_at4_rfc1.h").read_text()
assert "A810 AT5 Context Learner / Mesa" in (V/"tu_device.cc").read_text()
after=hashes()
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a810_at5.h","vulkan/tu_autotune.cc","vulkan/tu_device.cc"}
if changed!=expected:
    raise SystemExit(f"AT5 touched unexpected files {sorted(changed ^ expected)}")
print("A810 AT5 guarded runtime integration; policy and trace separately toggled PASS",flush=True)
