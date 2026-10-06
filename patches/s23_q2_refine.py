#!/usr/bin/env python3
"""S2.3 Q2 refinement applied after S2.2 Q-LRZ.

Crysis A/B: warm averages were effectively equal, while S2.2 Q produced a
repeatable lower minimum. Q2 therefore:
  * hard-bounds the Q signal to +/-4 in frane_s22_q_policy.h;
  * requires bandwidth + draw density + LRZ quality for positive Q bias;
  * stores the exact pre-Q S2/GF1 structural score;
  * removes Q from every armed decision/probe threshold, including TURBO;
  * permits only a tiny +/-4 percentage-point Q nudge while unarmed.

No LRZ correctness, synchronization, allocation or shader-order rule changes.
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
   uint8_t structure_score = 0;      /* Q-adjusted; unarmed only */
   uint8_t base_structure_score = 0; /* exact pre-Q S2/GF1 score */
   int8_t q_score_delta = 0;         /* S2.3 Q2: -4..+4 */
   uint64_t estimated_tiles = 0;
};""",
    "store base score and Q delta",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   const auto q_eval = frane_s22_q_eval(q_in);
   if (q_eval.valid)
      score += q_eval.score_delta;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    """   /* Freeze S2/GF1 before Q2 so armed mode can be byte-for-byte policy
    * equivalent to the pre-Q structural thresholds.
    */
   out.base_structure_score = uint8_t(std::clamp(score, 0, 100));

   const auto q_eval = frane_s22_q_eval(q_in);
   out.q_score_delta = q_eval.valid ? q_eval.score_delta : 0;
   score += out.q_score_delta;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    "freeze base score before Q delta",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   out.structure_score = eval.structure_score;
   if (!eval.eligible)
      return out;""",
    """   if (!eval.eligible)
      return out;

   /* Q2 is cold-start only. Once timing is armed, all structural thresholds
    * and reported decision score use the exact pre-Q S2/GF1 value.
    */
   out.structure_score =
      state.armed ? eval.base_structure_score : eval.structure_score;""",
    "use pre-Q score for armed evaluated decisions",
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
    "remove Q from armed control-probe cadence",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   /* 26.3.24 measured-first policy:
    * structural GMEM evidence is advisory until paired GPU timings arm the
    * runtime.  PROFILED remains solely responsible for cold-start sampling.
    * This avoids turning an unverified layout estimate into a near-forced
    * GMEM choice on a low-tier/single-slice A810.
    */
   return out;""",
    """   /* S2.3 Q2 cold-start nudge. The old measured-first S2 policy remains
    * intact except for the Q signal itself, which may move exploratory SYSMEM
    * probability by at most four percentage points. No base structural score
    * can trigger this path.
    */
   if (eval.q_score_delta != 0 && sysmem_probability >= 8 &&
       sysmem_probability <= 92) {
      const int adjusted_i = std::clamp(
         int(sysmem_probability) - int(eval.q_score_delta), 8, 92);
      const uint32_t adjusted = uint32_t(adjusted_i);

      if (adjusted != sysmem_probability) {
         out.override_mode = true;
         out.probe_log2 = 0;
         out.effective_sysmem_probability = adjusted;
         out.select_sysmem = (decision_word % 100u) < adjusted;
         out.force_measure = ((decision_word >> 8) & 15u) == 0u; /* 1/16 */
      }
   }
   return out;""",
    "add bounded unarmed Q-only probability nudge",
)

# Optional TURBO must obey the same no-Q-after-armed guarantee.
edit(
    "frane_mesa_26320_a810_gmem_turbo.h",
    """      if (state.score >= 8 && eval.structure_score >= 82 &&
          sysmem_probability <= 20) {
         probe_log2 = 8; /* 1/256 */
      } else if (state.score >= 7 && eval.structure_score >= 72 &&
                 sysmem_probability <= 30) {
         probe_log2 = 7; /* 1/128 */
      } else if (state.score >= 6 && eval.structure_score >= 65) {""",
    """      if (state.score >= 8 && eval.base_structure_score >= 82 &&
          sysmem_probability <= 20) {
         probe_log2 = 8; /* 1/256 */
      } else if (state.score >= 7 && eval.base_structure_score >= 72 &&
                 sysmem_probability <= 30) {
         probe_log2 = 7; /* 1/128 */
      } else if (state.score >= 6 && eval.base_structure_score >= 65) {""",
    "remove Q from armed TURBO thresholds",
)

h = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
t = (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()

assert "int8_t q_score_delta = 0" in h
assert "state.armed ? eval.base_structure_score : eval.structure_score" in h
assert "int(sysmem_probability) - int(eval.q_score_delta)" in h
assert "eval.base_structure_score >= 75" in h
assert "state.score >= 8 && eval.structure_score >= 75" not in h
assert "eval.base_structure_score >= 82" in t
assert "state.score >= 8 && eval.structure_score >= 82" not in t

print("S2.3 Q2 cold-start-only refinement applied", flush=True)
