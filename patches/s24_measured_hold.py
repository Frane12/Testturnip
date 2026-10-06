#!/usr/bin/env python3
"""S2.4 MH1: measured-winner hold extension after S2.3 Q2.

Goal: raise warm-run throughput without touching the stable cold-start path.

Only an already-armed, fully saturated GMEM winner (state.score == 8) with a
very strong exact pre-Q S2/GF1 structural score may extend the old 40% PROFILED
ceiling into a narrow 41..46% uncertainty band. Mid-band decisions keep
measured SYSMEM control probes at 1/64, or 1/128 only in the strongest sub-band.

No cold-start, Q, LRZ, synchronization, attachment allocation, tile geometry,
shader order, or memory-layout rule changes.
"""
from pathlib import Path
import shutil

V = Path("mesa/src/freedreno/vulkan")


def edit(rel, old, new, label):
    p = V / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"S2.4 MH1 source drift {label}: expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"S2.4 MH1 PASS {label}", flush=True)


shutil.copyfile(
    "patches/frane_s24_measured_hold.h",
    V / "frane_s24_measured_hold.h",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    '#include "frane_s22_q_policy.h"\n',
    '#include "frane_s22_q_policy.h"\n'
    '#include "frane_s24_measured_hold.h"\n',
    "include measured-hold helper",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   if (state.armed) {
      if (sysmem_probability > 40)
         return out;

      uint8_t probe_log2 = 5; /* marginal winner: 1/32 */
      if (state.score >= 8 && eval.base_structure_score >= 75)
         probe_log2 = 7;      /* timing + S2 structure agree strongly: 1/128 */
      else if (state.score >= 7 || eval.base_structure_score >= 65)
         probe_log2 = 6;      /* normal strong case: 1/64 */""",
    """   if (state.armed) {
      const auto s24_hold = frane_s24_eval_measured_hold(
         state.score, eval.base_structure_score, sysmem_probability);

      if (sysmem_probability > 40 && !s24_hold.extend)
         return out;

      uint8_t probe_log2 = 5; /* marginal winner: 1/32 */
      if (s24_hold.extend)
         probe_log2 = s24_hold.probe_log2;
      else if (state.score >= 8 && eval.base_structure_score >= 75)
         probe_log2 = 7;      /* timing + S2 structure agree strongly: 1/128 */
      else if (state.score >= 7 || eval.base_structure_score >= 65)
         probe_log2 = 6;      /* normal strong case: 1/64 */""",
    "extend only saturated measured winners into 41..46% band",
)

h = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
assert '#include "frane_s24_measured_hold.h"' in h
assert "frane_s24_eval_measured_hold" in h
assert "sysmem_probability > 40 && !s24_hold.extend" in h
assert "state.armed ? eval.base_structure_score : eval.structure_score" in h
assert "int(sysmem_probability) - int(eval.q_score_delta)" in h
assert "sysmem_probability <= 46" not in h  # policy bound lives in helper only

print("S2.4 MH1 measured-hold refinement applied", flush=True)
