#!/usr/bin/env python3
"""S2.3 Q2 refinement applied after S2.2 Q-LRZ.

Measured Crysis A/B showed equal warm average but a repeatable lower minimum
with S2.2 Q enabled. Q2 therefore:
  * keeps the Q prior hard-bounded to +/-4 (helper file),
  * requires BW + draw density + LRZ quality for any positive bias,
  * records the pre-Q structure score,
  * uses that exact pre-Q score for every armed-runtime decision/probe cadence.

Thus Q2 may only influence cold/unarmed exploration. Once timing is armed,
S2 behaviour is restored exactly for SMART-GMEM decision thresholds/cadence.
"""
from pathlib import Path

V = Path("mesa/src/freedreno/vulkan")

def edit(rel, old, new, label):
    p = V / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"S2.3 Q2 source drift {label}: expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"S2.3 Q2 PASS {label}", flush=True)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """struct frane_26318_smart_gmem_eval {
   bool eligible = false;
   uint8_t structure_score = 0; /* 0..100 */
   uint64_t estimated_tiles = 0;
};""",
    """struct frane_26318_smart_gmem_eval {
   bool eligible = false;
   uint8_t structure_score = 0;      /* Q-adjusted, used only while unarmed */
   uint8_t base_structure_score = 0; /* exact pre-Q S2 score */
   uint64_t estimated_tiles = 0;
};""",
    "store exact pre-Q structure score",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   const auto q_eval = frane_s22_q_eval(q_in);
   if (q_eval.valid)
      score += q_eval.score_delta;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    """   /* Freeze the exact S2/GF1 score before Q2. Armed timing must use
    * this value so Q2 cannot alter the selected mode or control-probe cadence.
    */
   out.base_structure_score = uint8_t(std::clamp(score, 0, 100));

   const auto q_eval = frane_s22_q_eval(q_in);
   if (q_eval.valid)
      score += q_eval.score_delta;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    "freeze base score before Q2 delta",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   const auto eval = frane_26318_eval_smart_gmem(in);
   out.structure_score = eval.structure_score;
   if (!eval.eligible)
      return out;""",
    """   const auto eval = frane_26318_eval_smart_gmem(in);
   if (!eval.eligible)
      return out;

   /* Q2 is cold-start only. Once runtime timing is armed, expose/use the
    * exact pre-Q score so mode selection and probe cadence match S2.
    */
   out.structure_score =
      state.armed ? eval.base_structure_score : eval.structure_score;""",
    "select pre-Q score when timing is armed",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """      if (state.score >= 8 && eval.structure_score >= 75)
         probe_log2 = 7;      /* timing + structure agree strongly: 1/128 */
      else if (state.score >= 7 || eval.structure_score >= 65)
         probe_log2 = 6;      /* normal strong case: 1/64 */""",
    """      if (state.score >= 8 && eval.base_structure_score >= 75)
         probe_log2 = 7;      /* timing + S2 structure agree strongly: 1/128 */
      else if (state.score >= 7 || eval.base_structure_score >= 65)
         probe_log2 = 6;      /* normal strong case: 1/64 */""",
    "remove Q2 from armed probe cadence",
)

h = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
assert "base_structure_score" in h
assert "state.armed ? eval.base_structure_score : eval.structure_score" in h
assert "state.score >= 8 && eval.base_structure_score >= 75" in h
assert "state.score >= 7 || eval.base_structure_score >= 65" in h
assert "state.score >= 8 && eval.structure_score >= 75" not in h
assert "state.score >= 7 || eval.structure_score >= 65" not in h

print("S2.3 Q2 cold-start-only refinement applied", flush=True)
