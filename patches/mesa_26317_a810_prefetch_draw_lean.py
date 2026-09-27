#!/usr/bin/env python3
"""Frane Mesa 26.3.17 A810 PREFETCH-V2 + DRAW-LEAN.

Layered strictly on green 26.3.16 AUDIT-BOOST.

Two combined experiments, both default-on with same-binary opt-outs:

1) PREFETCH-V2
   - record candidate position in the first executable FS block;
   - count NIR uses of each legal texture result;
   - rank legal A810 candidates by early-use score instead of raw program order;
   - keep 26.3.16 diversity-aware bary selection;
   - adapt the 2/3/4 cap: a late single-use candidate in the final third of
     the block no longer automatically consumes a scarce pre-dispatch slot.

   TU_A810_26317_PREFETCH_SCORE=0
   TU_A810_26317_ADAPTIVE_PREFETCH_CAP=0
   restore the 26.3.16 selection/cap behavior.

2) DRAW-LEAN
   - track the cases where CP_SET_DRAW_STATE DISABLE_ALL_GROUPS is known to
     precede the next full draw-state restore;
   - only in that proven-disabled state, omit zero/disabled draw-state entries
     from the full restore packet;
   - after secondary command buffers, where hardware draw-state contents are
     unknown, fall back to the exact full Mesa restore.

   TU_A810_26317_DRAW_STATE_LEAN=0 restores the 26.3.16 draw-state path.

No legality expansion, no LRZ dirty suppression, no GMEM/SYSMEM threshold
change, no WSI change, and no synchronization change.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.17 source drift: {label}: expected 1 anchor, saw {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.17 PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# PREFETCH-V2 policy bits.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26315_prefetch_diversity;
   bool frane_26315_quad_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    """   bool frane_26315_prefetch_diversity;
   bool frane_26315_quad_tex_prefetch;

   /* 26.3.17: rank already-legal A810 prefetch candidates by live-range
    * proxy and adapt the 2/3/4 candidate budget.
    */
   bool frane_26317_prefetch_score;
   bool frane_26317_adaptive_prefetch_cap;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    "add PREFETCH-V2 compiler policy bits",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26315_quad_tex_prefetch =
         debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", true);
   }
""",
    """      compiler->frane_26315_quad_tex_prefetch =
         debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", true);
      compiler->frane_26317_prefetch_score =
         debug_get_bool_option("TU_A810_26317_PREFETCH_SCORE", true);
      compiler->frane_26317_adaptive_prefetch_cap =
         debug_get_bool_option("TU_A810_26317_ADAPTIVE_PREFETCH_CAP", true);
   }
""",
    "default-on PREFETCH-V2 switches",
)

edit(
    "src/freedreno/ir3/ir3_nir.h",
    """bool ir3_nir_lower_tex_prefetch(nir_shader *shader,
                                enum ir3_bary *prefetch_bary_type,
                                uint32_t max_prefetches,
                                bool allow_bindless,
                                bool prefer_unique_fixed_pairs);""",
    """bool ir3_nir_lower_tex_prefetch(nir_shader *shader,
                                enum ir3_bary *prefetch_bary_type,
                                uint32_t max_prefetches,
                                bool allow_bindless,
                                bool prefer_unique_fixed_pairs,
                                bool prefer_early_use,
                                bool adaptive_prefetch_cap);""",
    "extend prefetch API with score and adaptive-cap policy",
)

# Candidate metadata: instruction order is a live-range proxy once the fetch is
# hoisted to pre-dispatch. NIR use count mildly rewards results feeding more
# consumers without changing texture legality.
edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """typedef struct {
   nir_tex_instr *tex;
   enum ir3_bary bary;
} tex_prefetch_candidate;

typedef struct {
   struct u_vector candidates;
   uint32_t per_bary_candidates[IJ_COUNT];
} ir3_prefetch_state;""",
    """typedef struct {
   nir_tex_instr *tex;
   enum ir3_bary bary;
   uint32_t order;
   uint8_t use_count;
} tex_prefetch_candidate;

typedef struct {
   struct u_vector candidates;
   uint32_t per_bary_candidates[IJ_COUNT];
   uint32_t block_instr_count;
} ir3_prefetch_state;""",
    "record candidate order/use metadata",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """   bool progress = false;

   nir_foreach_instr_safe (instr, block) {
      if (instr->type != nir_instr_type_tex)
         continue;""",
    """   bool progress = false;
   uint32_t instr_order = 0;

   nir_foreach_instr_safe (instr, block) {
      const uint32_t order = instr_order++;

      if (instr->type != nir_instr_type_tex)
         continue;""",
    "track first-block instruction order",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """         tex_prefetch_candidate *candidate = u_vector_add(&state->candidates);
         candidate->tex = tex;
         candidate->bary = bary;

         progress |= true;""",
    """         tex_prefetch_candidate *candidate = u_vector_add(&state->candidates);
         candidate->tex = tex;
         candidate->bary = bary;
         candidate->order = order;

         uint32_t use_count = 0;
         nir_foreach_use(use, &tex->def) {
            if (use_count < UINT8_MAX)
               use_count++;
         }
         candidate->use_count = (uint8_t)use_count;

         progress |= true;""",
    "record texture-result use count",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """   return progress;
}

static bool
lower_tex_prefetch_func""",
    """   state->block_instr_count =
      MAX2(state->block_instr_count, instr_order);
   return progress;
}

static bool
lower_tex_prefetch_func""",
    "publish executable-block instruction count",
)

# Pure compile-time selection helpers. No runtime GPU state is touched.
p = ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c"
src = p.read_text()
anchor = """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,"""
if src.count(anchor) != 1:
    raise SystemExit("26.3.17 source drift: prefetch helper insertion anchor")
helpers = r"""
static uint32_t
frane_26317_prefetch_score(const tex_prefetch_candidate *candidate,
                           uint32_t block_instr_count)
{
   /* Earlier original texture instructions imply a shorter live range after
    * pre-dispatch hoisting. Normalize the position to 0..256 and add a small
    * bounded reward for results with multiple NIR consumers.
    */
   uint32_t early = 256;
   if (block_instr_count) {
      const uint32_t pos =
         MIN2(candidate->order, block_instr_count);
      early = (uint32_t)(((uint64_t)(block_instr_count - pos) * 256u) /
                         block_instr_count);
   }

   const uint32_t uses = MIN2((uint32_t)candidate->use_count, 4u);
   return early + uses * 32u;
}

static uint32_t
frane_26317_prefetch_cap(const ir3_prefetch_state *state,
                         enum ir3_bary chosen_bary,
                         uint32_t max_prefetches)
{
   if (max_prefetches <= 2)
      return max_prefetches;

   uint32_t useful = 0;
   tex_prefetch_candidate *candidate;
   u_vector_foreach(candidate, &state->candidates) {
      if (candidate->bary != chosen_bary)
         continue;

      /* Keep a late fetch if it has multiple consumers. A single-use sample
       * in the final third of the executable block is the main register-live
       * range risk this experiment avoids promoting to slot 3/4.
       */
      const bool early_enough =
         state->block_instr_count == 0 ||
         (uint64_t)candidate->order * 3u <=
            (uint64_t)state->block_instr_count * 2u;
      if (early_enough || candidate->use_count >= 2)
         useful++;
   }

   uint32_t cap = max_prefetches;
   if (useful <= 2)
      cap = MIN2(max_prefetches, 2u);
   else if (useful == 3)
      cap = MIN2(max_prefetches, 3u);

   return cap;
}

"""
src = src.replace(anchor, helpers + anchor, 1)
p.write_text(src)
print("26.3.17 PASS add early-use scoring and adaptive-cap helpers", flush=True)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type,
                           uint32_t max_prefetches,
                           bool allow_bindless,
                           bool prefer_unique_fixed_pairs)
{""",
    """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type,
                           uint32_t max_prefetches,
                           bool allow_bindless,
                           bool prefer_unique_fixed_pairs,
                           bool prefer_early_use,
                           bool adaptive_prefetch_cap)
{""",
    "thread PREFETCH-V2 policy into lowering pass",
)

# Replace only the post-bary candidate selection. 26.3.16 bary diversity logic
# remains intact and feeds chosen_bary into this stage.
p = ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c"
src = p.read_text()
sel_start = src.index("      uint32_t converted = 0;", src.index("best_unique_pairs"))
sel_end_marker = "      progress = converted > 0;"
sel_end = src.index(sel_end_marker, sel_start) + len(sel_end_marker)
old_sel = src[sel_start:sel_end]
new_sel = r"""      const uint32_t effective_prefetches =
         adaptive_prefetch_cap && !allow_bindless
            ? frane_26317_prefetch_cap(&state, chosen_bary, max_prefetches)
            : max_prefetches;

      uint32_t converted = 0;

      if (prefer_early_use && !allow_bindless) {
         uint16_t selected_keys[IR3_MAX_SAMPLER_PREFETCH] = {};
         uint32_t selected_key_count = 0;

         /* Diversity first, but choose the highest-value candidate for each
          * scarce slot instead of whichever legal sample appeared first.
          */
         if (prefer_unique_fixed_pairs) {
            while (converted < effective_prefetches) {
               tex_prefetch_candidate *best = NULL;
               uint32_t best_score = 0;
               uint16_t best_key = 0;

               tex_prefetch_candidate *candidate;
               u_vector_foreach(candidate, &state.candidates) {
                  if (candidate->bary != chosen_bary ||
                      candidate->tex->op != nir_texop_tex)
                     continue;

                  nir_tex_instr *tex = candidate->tex;
                  const uint16_t key =
                     ((uint16_t)tex->texture_index << 4) |
                     (uint16_t)tex->sampler_index;

                  bool duplicate = false;
                  for (uint32_t i = 0; i < selected_key_count; i++) {
                     if (selected_keys[i] == key) {
                        duplicate = true;
                        break;
                     }
                  }
                  if (duplicate)
                     continue;

                  const uint32_t score =
                     frane_26317_prefetch_score(candidate,
                                               state.block_instr_count);
                  if (!best || score > best_score ||
                      (score == best_score &&
                       candidate->order < best->order)) {
                     best = candidate;
                     best_score = score;
                     best_key = key;
                  }
               }

               if (!best)
                  break;

               best->tex->op = nir_texop_tex_prefetch;
               selected_keys[selected_key_count++] = best_key;
               converted++;
            }
         }

         /* Fill remaining slots by score, allowing repeated fixed pairs only
          * after the diversity wave has exhausted useful unique pairs.
          */
         while (converted < effective_prefetches) {
            tex_prefetch_candidate *best = NULL;
            uint32_t best_score = 0;

            tex_prefetch_candidate *candidate;
            u_vector_foreach(candidate, &state.candidates) {
               if (candidate->bary != chosen_bary ||
                   candidate->tex->op != nir_texop_tex)
                  continue;

               const uint32_t score =
                  frane_26317_prefetch_score(candidate,
                                             state.block_instr_count);
               if (!best || score > best_score ||
                   (score == best_score &&
                    candidate->order < best->order)) {
                  best = candidate;
                  best_score = score;
               }
            }

            if (!best)
               break;

            best->tex->op = nir_texop_tex_prefetch;
            converted++;
         }
      } else {
         /* Exact 26.3.16 ordering policy, with only the optional adaptive cap
          * substituted for the old fixed maximum.
          */
         if (prefer_unique_fixed_pairs && !allow_bindless) {
            uint16_t selected_keys[IR3_MAX_SAMPLER_PREFETCH] = {};
            uint32_t selected_key_count = 0;

            tex_prefetch_candidate *candidate;
            u_vector_foreach(candidate, &state.candidates) {
               if (candidate->bary != chosen_bary ||
                   converted >= effective_prefetches)
                  continue;

               nir_tex_instr *tex = candidate->tex;
               const uint16_t key =
                  ((uint16_t)tex->texture_index << 4) |
                  (uint16_t)tex->sampler_index;

               bool duplicate = false;
               for (uint32_t i = 0; i < selected_key_count; i++) {
                  if (selected_keys[i] == key) {
                     duplicate = true;
                     break;
                  }
               }
               if (duplicate)
                  continue;

               tex->op = nir_texop_tex_prefetch;
               selected_keys[selected_key_count++] = key;
               converted++;
            }
         }

         tex_prefetch_candidate *candidate;
         u_vector_foreach(candidate, &state.candidates) {
            if (candidate->bary == chosen_bary &&
                candidate->tex->op == nir_texop_tex &&
                converted < effective_prefetches) {
               candidate->tex->op = nir_texop_tex_prefetch;
               converted++;
            }
         }
      }

      progress = converted > 0;"""
src = src[:sel_start] + new_sel + src[sel_end:]
p.write_text(src)
print("26.3.17 PASS score legal candidates and adapt 2/3/4 cap", flush=True)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, ~0u, true, false);""",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, ~0u, true, false, false, false);""",
    "keep generic Mesa prefetch behavior unchanged",
)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, frane_prefetch_cap, false,
                  compiler->frane_26315_prefetch_diversity);""",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, frane_prefetch_cap, false,
                  compiler->frane_26315_prefetch_diversity,
                  compiler->frane_26317_prefetch_score,
                  compiler->frane_26317_adaptive_prefetch_cap);""",
    "enable PREFETCH-V2 only on guarded A810 path",
)


# ---------------------------------------------------------------------------
# DRAW-LEAN: compact a full restore only when DISABLE_ALL_GROUPS is known to
# precede it. This avoids redundant zero-state disable records without making
# assumptions after secondary command buffers.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_cmd_buffer.h",
    """   struct tu_draw_state prim_order_gmem;

   struct tu_draw_state vs_params;""",
    """   struct tu_draw_state prim_order_gmem;

   /* 26.3.17: true only when this command stream is known to have executed
    * CP_SET_DRAW_STATE DISABLE_ALL_GROUPS before the next full restore.
    */
   bool frane_26317_draw_states_known_disabled;

   struct tu_draw_state vs_params;""",
    "track proven all-disabled draw-state state",
)

# Insert the A810 policy helper immediately before tu_disable_draw_states().
p = V / "tu_cmd_buffer.cc"
src = p.read_text()
anchor = """void
tu_disable_draw_states(struct tu_cmd_buffer *cmd, struct tu_cs *cs)
{"""
if src.count(anchor) != 1:
    raise SystemExit("26.3.17 source drift: tu_disable_draw_states anchor")
helper = r"""static bool
frane_26317_a810_draw_state_lean(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26317_DRAW_STATE_LEAN", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == UINT64_C(0x44010000) ||
          chip == UINT64_C(0xffff44010000);
}

"""
src = src.replace(anchor, helper + anchor, 1)
p.write_text(src)
print("26.3.17 PASS add A810 DRAW-LEAN policy", flush=True)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   tu_cs_emit_qw(cs, 0);

   cmd->state.dirty |= TU_CMD_DIRTY_DRAW_STATE;
}""",
    """   tu_cs_emit_qw(cs, 0);

   cmd->state.dirty |= TU_CMD_DIRTY_DRAW_STATE;
   cmd->state.frane_26317_draw_states_known_disabled =
      frane_26317_a810_draw_state_lean(cmd);
}""",
    "remember explicit DISABLE_ALL_GROUPS",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   cmd->state.dirty = ~0u; /* TODO: set dirty only what needs to be */

   if (!cmd->state.lrz.gpu_dir_tracking && cmd->state.pass) {""",
    """   cmd->state.dirty = ~0u; /* TODO: set dirty only what needs to be */
   /* Secondary CBs may leave arbitrary draw-state groups enabled. The compact
    * restore is legal only after our own explicit DISABLE_ALL_GROUPS.
    */
   cmd->state.frane_26317_draw_states_known_disabled = false;

   if (!cmd->state.lrz.gpu_dir_tracking && cmd->state.pass) {""",
    "force full restore after secondary command buffers",
)

# Replace the full-restore body while preserving Mesa's existing else branch.
p = V / "tu_cmd_buffer.cc"
src = p.read_text()
comment = src.index("/* for the first draw in a renderpass")
full_start = src.index("   if (dirty & TU_CMD_DIRTY_DRAW_STATE) {", comment)
else_marker = """   } else {
      /* emit draw states that were just updated */"""
full_else = src.index(else_marker, full_start)
new_full = r"""   if (dirty & TU_CMD_DIRTY_DRAW_STATE) {
      tu_pipeline_update_rp_state(&cmd->state);

      const bool frane_lean =
         frane_26317_a810_draw_state_lean(cmd) &&
         cmd->state.frane_26317_draw_states_known_disabled;

      if (frane_lean) {
         auto live = [](struct tu_draw_state state) {
            return state.size != 0 && state.iova != 0;
         };

         uint32_t draw_state_count = 0;
         draw_state_count += live(program->config_state);
         draw_state_count += live(program->vs_state);
         draw_state_count += live(program->vs_binning_state);
         draw_state_count += live(program->hs_state);
         draw_state_count += live(program->ds_state);
         draw_state_count += live(program->gs_state);
         draw_state_count += live(program->gs_binning_state);
         draw_state_count += live(program->fs_state);
         draw_state_count += live(program->vpc_state);
         draw_state_count += live(cmd->state.prim_order_gmem);
         draw_state_count += live(cmd->state.shader_const);
         draw_state_count += live(cmd->state.desc_sets);
         draw_state_count += live(cmd->state.load_state);
         draw_state_count += live(cmd->state.vertex_buffers);
         draw_state_count += live(cmd->state.vs_params);
         draw_state_count += live(cmd->state.fs_params);
         draw_state_count += live(cmd->state.lrz_and_depth_plane_state);
         for (uint32_t i = 0; i < ARRAY_SIZE(cmd->state.dynamic_state); i++)
            draw_state_count += live(cmd->state.dynamic_state[i]);

         if (draw_state_count)
            tu_cs_emit_pkt7(cs, CP_SET_DRAW_STATE, 3 * draw_state_count);

         auto emit_live = [&](uint32_t id, struct tu_draw_state state) {
            if (live(state))
               tu_cs_emit_draw_state(cs, id, state);
         };

         emit_live(TU_DRAW_STATE_PROGRAM_CONFIG, program->config_state);
         emit_live(TU_DRAW_STATE_VS, program->vs_state);
         emit_live(TU_DRAW_STATE_VS_BINNING, program->vs_binning_state);
         emit_live(TU_DRAW_STATE_HS, program->hs_state);
         emit_live(TU_DRAW_STATE_DS, program->ds_state);
         emit_live(TU_DRAW_STATE_GS, program->gs_state);
         emit_live(TU_DRAW_STATE_GS_BINNING, program->gs_binning_state);
         emit_live(TU_DRAW_STATE_FS, program->fs_state);
         emit_live(TU_DRAW_STATE_VPC, program->vpc_state);
         emit_live(TU_DRAW_STATE_PRIM_MODE_GMEM, cmd->state.prim_order_gmem);
         emit_live(TU_DRAW_STATE_CONST, cmd->state.shader_const);
         emit_live(TU_DRAW_STATE_DESC_SETS, cmd->state.desc_sets);
         emit_live(TU_DRAW_STATE_DESC_SETS_LOAD, cmd->state.load_state);
         emit_live(TU_DRAW_STATE_VB, cmd->state.vertex_buffers);
         emit_live(TU_DRAW_STATE_VS_PARAMS, cmd->state.vs_params);
         emit_live(TU_DRAW_STATE_FS_PARAMS, cmd->state.fs_params);
         emit_live(TU_DRAW_STATE_LRZ_AND_DEPTH_PLANE,
                   cmd->state.lrz_and_depth_plane_state);

         for (uint32_t i = 0; i < ARRAY_SIZE(cmd->state.dynamic_state); i++)
            emit_live(TU_DRAW_STATE_DYNAMIC + i, cmd->state.dynamic_state[i]);
      } else {
         /* Exact Mesa/26.3.16 fallback. Required when state may have been
          * changed by a secondary command buffer.
          */
         tu_cs_emit_pkt7(cs, CP_SET_DRAW_STATE,
                         3 * (TU_DRAW_STATE_COUNT - 2));

         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_PROGRAM_CONFIG, program->config_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_VS, program->vs_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_VS_BINNING, program->vs_binning_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_HS, program->hs_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_DS, program->ds_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_GS, program->gs_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_GS_BINNING, program->gs_binning_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_FS, program->fs_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_VPC, program->vpc_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_PRIM_MODE_GMEM, cmd->state.prim_order_gmem);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_CONST, cmd->state.shader_const);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_DESC_SETS, cmd->state.desc_sets);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_DESC_SETS_LOAD, cmd->state.load_state);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_VB, cmd->state.vertex_buffers);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_VS_PARAMS, cmd->state.vs_params);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_FS_PARAMS, cmd->state.fs_params);
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_LRZ_AND_DEPTH_PLANE,
                               cmd->state.lrz_and_depth_plane_state);

         for (uint32_t i = 0; i < ARRAY_SIZE(cmd->state.dynamic_state); i++) {
            tu_cs_emit_draw_state(cs, TU_DRAW_STATE_DYNAMIC + i,
                                  cmd->state.dynamic_state[i]);
         }
      }

      /* From this point onward at least one draw-state group may be enabled.
       * A future full compact restore requires another explicit disable-all.
       */
      cmd->state.frane_26317_draw_states_known_disabled = false;
"""
src = src[:full_start] + new_full + src[full_else:]
p.write_text(src)
print("26.3.17 PASS compact proven-disabled full draw-state restores", flush=True)


edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.16 A810 AUDIT-BOOST / Mesa ",
    "Frane Mesa 26.3.17 A810 PREFETCH-V2 DRAW-LEAN / Mesa ",
    "experimental driver identity",
)


# ---------------------------------------------------------------------------
# Regression / scope guards.
# ---------------------------------------------------------------------------
compiler_c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
compiler_h = (ROOT / "src/freedreno/ir3/ir3_compiler.h").read_text()
context = (ROOT / "src/freedreno/ir3/ir3_context.c").read_text()
lower = (ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c").read_text()
nir_h = (ROOT / "src/freedreno/ir3/ir3_nir.h").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
cmd_h = (V / "tu_cmd_buffer.h").read_text()
autotune = (V / "tu_autotune.cc").read_text()
wsi = (V / "tu_wsi.cc").read_text()

assert 'TU_A810_26317_PREFETCH_SCORE", true' in compiler_c
assert 'TU_A810_26317_ADAPTIVE_PREFETCH_CAP", true' in compiler_c
assert "frane_26317_prefetch_score" in compiler_h
assert "frane_26317_adaptive_prefetch_cap" in compiler_h
assert "bool prefer_early_use" in nir_h
assert "bool adaptive_prefetch_cap" in nir_h
assert "frane_26317_prefetch_score" in context
assert "frane_26317_adaptive_prefetch_cap" in context
assert "&so->prefetch_bary_type, ~0u, true, false, false, false" in context

assert "candidate->order = order;" in lower
assert "nir_foreach_use(use, &tex->def)" in lower
assert "frane_26317_prefetch_score" in lower
assert "frane_26317_prefetch_cap" in lower
assert "effective_prefetches" in lower
assert "best_unique_pairs" in lower
assert "selected_keys[IR3_MAX_SAMPLER_PREFETCH]" in lower

# Existing legality remains mandatory.
assert "if (!allow_bindless)" in lower
assert "ok_tex_samp(tex, allow_bindless)" in lower
assert "GLSL_SAMPLER_DIM_2D" in lower
assert "tex->is_array" in lower
assert "tex->is_sparse" in lower

assert "TU_A810_26317_DRAW_STATE_LEAN" in cmd
assert "frane_26317_draw_states_known_disabled" in cmd_h
assert "cmd->state.frane_26317_draw_states_known_disabled = false;" in cmd
assert "3 * (TU_DRAW_STATE_COUNT - 2)" in cmd
assert "if (live(state))" in cmd
assert "CP_SET_DRAW_STATE__0_DISABLE_ALL_GROUPS" in cmd

# Preserve 26.3.16 and earlier safety decisions.
assert "FRANE_2638_HOT_RP_SLOTS = 128" in (V / "tu_autotune.h").read_text()
assert "rp_histories.reserve(FRANE_2638_HOT_RP_SLOTS * 2u);" in autotune
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "same_lrz_signature" not in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd
assert "TU_A810_GMEM_RUNTIME" in autotune
assert "V28-CLEAN: no driver present-mode override" in wsi
assert "Frane Mesa 26.3.17 A810 PREFETCH-V2 DRAW-LEAN" in (
    V / "tu_device.cc").read_text()

print("Frane Mesa 26.3.17 A810 PREFETCH-V2 DRAW-LEAN applied", flush=True)
