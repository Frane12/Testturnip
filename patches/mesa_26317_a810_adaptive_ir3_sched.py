#!/usr/bin/env python3
"""Frane Mesa 26.3.17 A810 ADAPTIVE-IR3-SCHED EXP.

Layered strictly on 26.3.16 PREFETCH-SCORE.

This is intentionally a higher-risk compiler scheduling experiment.  It does
NOT alter Vulkan synchronization, LRZ correctness, GMEM layout, descriptors,
or command submission.  It changes only IR3 pre-RA instruction scheduling for
A810 when enabled.

Default-on A810 experiment:
  TU_A810_26317_ADAPTIVE_SCHED=1

Opt-out:
  TU_A810_26317_ADAPTIVE_SCHED=0

Optional low-pressure texture window:
  TU_A810_26317_TEX_WINDOW_MAX=12
  clamped to [8, 16].

Policy:
  * Track the scheduler's own live_effect() estimate as a per-block live-GPR
    pressure signal.
  * Upstream uses a fixed outstanding (sy) producer cap of 8.
  * A810 adaptive mode uses:
       pressure < 20%  -> up to TEX_WINDOW_MAX (default 12)
       pressure < 35%  -> up to min(max, 10)
       pressure < 50%  -> 8
       pressure < 65%  -> 6
       otherwise       -> 4
  * When CSR must pick an instruction that grows register pressure, prefer the
    candidate with the smallest live-effect growth before the existing nearest-
    use tie-break.
  * When choosing among register-pressure-reducing candidates of equal rank,
    prefer the one which frees more live registers before the existing
    max-delay tie-break.

The goal is to trade instruction-level parallelism against occupancy instead of
using one fixed texture-flight window for every shader/block.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.17 ADAPTIVE-IR3-SCHED source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.17 ADAPTIVE-IR3-SCHED PASS {label}", flush=True)


edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26316_prefetch_use_score;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    """   bool frane_26316_prefetch_use_score;

   /* 26.3.17: A810-only adaptive pre-RA scheduling experiment. */
   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    "add adaptive scheduler policy fields",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26316_prefetch_use_score =
         debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false);
   }
""",
    """      compiler->frane_26316_prefetch_use_score =
         debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false);

      compiler->frane_26317_adaptive_sched =
         debug_get_bool_option("TU_A810_26317_ADAPTIVE_SCHED", true);

      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 12);
      compiler->frane_26317_tex_window_max =
         MIN2(16u, MAX2(8u, frane_tex_window));
   }
""",
    "enable A810 adaptive scheduler by default with clamped max window",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   int sy_index, first_outstanding_sy_index;
   int ss_index, first_outstanding_ss_index;
};""",
    """   int sy_index, first_outstanding_sy_index;
   int ss_index, first_outstanding_ss_index;

   /* 26.3.17 A810 experiment: running estimate using this scheduler's own
    * live_effect() model.  Units are GPR scalar elements.
    */
   int frane_live_gpr_elems;
};""",
    "track per-block live GPR pressure estimate",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """static void sched_node_add_dep(struct ir3_sched_ctx *ctx,
                               struct ir3_instruction *instr,
                               struct ir3_instruction *src, int i);

static bool
is_scheduled""",
    """static void sched_node_add_dep(struct ir3_sched_ctx *ctx,
                               struct ir3_instruction *instr,
                               struct ir3_instruction *src, int i);
static int live_effect(struct ir3_instruction *instr);

static bool
is_scheduled""",
    "forward-declare scheduler live-effect helper",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """static void
schedule(struct ir3_sched_ctx *ctx, struct ir3_instruction *instr)
{
   assert(ctx->block == instr->block);

   /* remove from depth list:
    */""",
    """static void
schedule(struct ir3_sched_ctx *ctx, struct ir3_instruction *instr)
{
   assert(ctx->block == instr->block);

   /* live_effect() must be sampled before marking this instruction scheduled,
    * because it checks which source uses remain unscheduled.
    */
   int frane_live_delta = 0;
   if (ctx->compiler->frane_26317_adaptive_sched)
      frane_live_delta = live_effect(instr);

   /* remove from depth list:
    */""",
    "sample live-pressure delta before scheduling",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   instr->flags |= IR3_INSTR_MARK;

   di(instr, "schedule");""",
    """   instr->flags |= IR3_INSTR_MARK;

   if (ctx->compiler->frane_26317_adaptive_sched) {
      ctx->frane_live_gpr_elems =
         MAX2(0, ctx->frane_live_gpr_elems + frane_live_delta);
   }

   di(instr, "schedule");""",
    "update running live-pressure estimate",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """static bool
should_defer(struct ir3_sched_ctx *ctx, struct ir3_instruction *instr)
{
   if (ctx->ss_delay) {""",
    """static unsigned
frane_26317_pressure_pct(struct ir3_sched_ctx *ctx)
{
   if (!ctx->compiler->frane_26317_adaptive_sched)
      return 0;

   /* compiler->reg_size_vec4 is the theoretical per-wave register-file budget
    * in vec4 units; live_effect() counts scalar elements.
    */
   const unsigned capacity =
      MAX2(1u, ctx->compiler->reg_size_vec4 * 4u);
   const unsigned live =
      (unsigned)MAX2(0, ctx->frane_live_gpr_elems);

   return MIN2(100u, (live * 100u) / capacity);
}

static unsigned
frane_26317_sy_window(struct ir3_sched_ctx *ctx)
{
   if (!ctx->compiler->frane_26317_adaptive_sched)
      return 8;

   const unsigned p = frane_26317_pressure_pct(ctx);
   const unsigned max_window = ctx->compiler->frane_26317_tex_window_max;

   if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 10u);
   if (p < 50)
      return 8;
   if (p < 65)
      return 6;
   return 4;
}

static bool
should_defer(struct ir3_sched_ctx *ctx, struct ir3_instruction *instr)
{
   if (ctx->ss_delay) {""",
    "add adaptive outstanding-texture window policy",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   if (ctx->sy_index - ctx->first_outstanding_sy_index >= 8 && is_sy_producer(instr))
      return true;

   if (ctx->ss_index - ctx->first_outstanding_ss_index >= 8 && is_ss_producer(instr))
      return true;""",
    """   if ((unsigned)(ctx->sy_index - ctx->first_outstanding_sy_index) >=
          frane_26317_sy_window(ctx) &&
       is_sy_producer(instr))
      return true;

   /* Keep the SFU queue at the upstream cap.  This experiment deliberately
    * changes only the texture/memory (sy) side first.
    */
   if (ctx->ss_index - ctx->first_outstanding_ss_index >= 8 && is_ss_producer(instr))
      return true;""",
    "replace fixed sy=8 cap with adaptive A810 window",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   struct ir3_sched_node *chosen = NULL;
   enum choose_instr_dec_rank chosen_rank = DEC_NEUTRAL;

   foreach_sched_node (n, &ctx->dag->heads) {""",
    """   struct ir3_sched_node *chosen = NULL;
   enum choose_instr_dec_rank chosen_rank = DEC_NEUTRAL;
   int chosen_live = 0;

   foreach_sched_node (n, &ctx->dag->heads) {""",
    "track chosen live-effect for pressure-reducing CSR choices",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """      if (!chosen || rank > chosen_rank ||
          (rank == chosen_rank && chosen->max_delay < n->max_delay)) {
         chosen = n;
         chosen_rank = rank;
      }""",
    """      bool better = !chosen || rank > chosen_rank;

      if (!better && rank == chosen_rank) {
         if (ctx->compiler->frane_26317_adaptive_sched &&
             live < chosen_live) {
            /* Among equally ranked freeing/neutral choices, free more first. */
            better = true;
         } else if ((!ctx->compiler->frane_26317_adaptive_sched ||
                     live == chosen_live) &&
                    chosen->max_delay < n->max_delay) {
            better = true;
         }
      }

      if (better) {
         chosen = n;
         chosen_rank = rank;
         chosen_live = live;
      }""",
    "bias equal-rank CSR choices toward greater register freeing",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   unsigned chosen_distance = 0;

   /* Pick the max delay of the remaining ready set. */""",
    """   unsigned chosen_distance = 0;
   int chosen_live_growth = 0;

   /* Pick the max delay of the remaining ready set. */""",
    "track register-growth cost for increasing choices",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """      unsigned distance = nearest_use(n->instr);

      if (!chosen || rank > chosen_rank ||
          (rank == chosen_rank && distance < chosen_distance)) {
         chosen = n;
         chosen_distance = distance;
         chosen_rank = rank;
      }""",
    """      unsigned distance = nearest_use(n->instr);
      int live_growth = live_effect(n->instr);

      bool better = !chosen || rank > chosen_rank;

      if (!better && rank == chosen_rank) {
         if (ctx->compiler->frane_26317_adaptive_sched &&
             live_growth < chosen_live_growth) {
            /* When we must grow pressure, pick the smallest growth first. */
            better = true;
         } else if ((!ctx->compiler->frane_26317_adaptive_sched ||
                     live_growth == chosen_live_growth) &&
                    distance < chosen_distance) {
            better = true;
         }
      }

      if (better) {
         chosen = n;
         chosen_distance = distance;
         chosen_rank = rank;
         chosen_live_growth = live_growth;
      }""",
    "bias pressure-increasing choices toward smaller live growth",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   ctx->sy_index = ctx->first_outstanding_sy_index = 0;
   ctx->ss_index = ctx->first_outstanding_ss_index = 0;

   /* The terminator has to stay at the end.""",
    """   ctx->sy_index = ctx->first_outstanding_sy_index = 0;
   ctx->ss_index = ctx->first_outstanding_ss_index = 0;
   ctx->frane_live_gpr_elems = 0;

   /* The terminator has to stay at the end.""",
    "reset adaptive pressure estimate per block",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.16 A810 PREFETCH-SCORE EXP / Mesa ",
    "Frane Mesa 26.3.17 A810 ADAPTIVE-IR3-SCHED EXP / Mesa ",
    "experimental driver identity",
)

# Surgical guards.
compiler_c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
compiler_h = (ROOT / "src/freedreno/ir3/ir3_compiler.h").read_text()
sched = (ROOT / "src/freedreno/ir3/ir3_sched.c").read_text()
cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
pipeline = (ROOT / "src/freedreno/vulkan/tu_pipeline.cc").read_text()

assert 'TU_A810_26317_ADAPTIVE_SCHED", true' in compiler_c
assert 'TU_A810_26317_TEX_WINDOW_MAX' in compiler_c
assert 'MIN2(16u, MAX2(8u, frane_tex_window))' in compiler_c
assert 'frane_26317_adaptive_sched' in compiler_h
assert 'frane_26317_tex_window_max' in compiler_h

assert 'frane_live_gpr_elems' in sched
assert 'frane_26317_pressure_pct' in sched
assert 'frane_26317_sy_window' in sched
assert 'return max_window;' in sched
assert 'return MIN2(max_window, 10u);' in sched
assert 'return 6;' in sched
assert 'return 4;' in sched
assert 'live_growth < chosen_live_growth' in sched
assert 'live < chosen_live' in sched
assert 'ctx->frane_live_gpr_elems = 0;' in sched

# Upstream exact behavior remains reachable through the single opt-out.
assert 'if (!ctx->compiler->frane_26317_adaptive_sched)\n      return 8;' in sched

# Keep prior correctness fences intact.
assert 'frane_26313_same_lrz_fs_signature' not in cmd
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'TU_A810_26313_LRZ_FASTPATH' in pipeline

assert 'Frane Mesa 26.3.17 A810 ADAPTIVE-IR3-SCHED EXP' in (
    ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

print("Frane Mesa 26.3.17 A810 ADAPTIVE-IR3-SCHED EXP applied", flush=True)
