#!/usr/bin/env python3
"""Frane Mesa 26.3.16 A810 PREFETCH-SCORE EXP.

Layered strictly on 26.3.15 PREFETCH-SELECT.

Promotions from confirmed 26.3.15:
  - diversity-aware candidate selection becomes default-on;
  - quad-prefetch (4 legal candidates) becomes default-on.

New independent experiment:
  TU_A810_26316_PREFETCH_USE_SCORE=1

When there are more legal candidates than available pre-dispatch slots,
rank candidates by direct NIR SSA use count.  The score is intentionally
small and deterministic:
  - more direct consumers of the texture result = higher priority;
  - if diversity mode is enabled, an as-yet-unselected texture/sampler pair
    wins ties over a duplicate pair;
  - remaining ties preserve original program order.

This changes only WHICH already-legal texture fetches are prefetched.
It does not expand legality, does not touch LRZ, GMEM, barriers or runtime
submission state, and adds no runtime GPU overhead (compile-time heuristic).
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.16 PREFETCH-SCORE source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.16 PREFETCH-SCORE PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# Promote 26.3.15's confirmed options to default-on and add scoring switch.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26315_prefetch_diversity;
   bool frane_26315_quad_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    """   bool frane_26315_prefetch_diversity;
   bool frane_26315_quad_tex_prefetch;

   /* 26.3.16: optional compile-time ranking of legal prefetch candidates by
    * direct NIR SSA consumer count.
    */
   bool frane_26316_prefetch_use_score;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    "add compile-time prefetch score policy bit",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26315_prefetch_diversity =
         debug_get_bool_option("TU_A810_26315_PREFETCH_DIVERSITY", false);
      compiler->frane_26315_quad_tex_prefetch =
         debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", false);
   }
""",
    """      compiler->frane_26315_prefetch_diversity =
         debug_get_bool_option("TU_A810_26315_PREFETCH_DIVERSITY", true);
      compiler->frane_26315_quad_tex_prefetch =
         debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", true);
      compiler->frane_26316_prefetch_use_score =
         debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false);
   }
""",
    "promote diversity+quad defaults and add use-score A/B switch",
)

# ---------------------------------------------------------------------------
# Extend only the explicit A810 policy call with optional use-aware ranking.
# Generic property-backed devices remain exact upstream/program-order.
# ---------------------------------------------------------------------------
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
                                bool prefer_more_used_results);""",
    "add optional result-use scoring policy argument",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type,
                           uint32_t max_prefetches,
                           bool allow_bindless,
                           bool prefer_unique_fixed_pairs)
{""",
    """static uint32_t
frane_26316_tex_use_count(const nir_tex_instr *tex)
{
   uint32_t uses = 0;
   nir_foreach_use_including_if(src, &tex->def)
      uses++;
   return uses;
}

static bool
frane_26316_key_selected(uint16_t key, const uint16_t *keys,
                         uint32_t key_count)
{
   for (uint32_t i = 0; i < key_count; i++) {
      if (keys[i] == key)
         return true;
   }
   return false;
}

bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type,
                           uint32_t max_prefetches,
                           bool allow_bindless,
                           bool prefer_unique_fixed_pairs,
                           bool prefer_more_used_results)
{""",
    "add deterministic direct-use scoring helpers",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """      uint32_t converted = 0;

      /* Optional A810 experiment: if the shader offers more legal fixed
       * candidates than we can issue, spread the first wave across distinct
       * texture/sampler pairs.  This never makes an illegal instruction
       * eligible; it only changes which already-legal candidates win the
       * limited pre-dispatch slots.
       */
      if (prefer_unique_fixed_pairs && !allow_bindless) {
         uint16_t selected_keys[IR3_MAX_SAMPLER_PREFETCH] = {};
         uint32_t selected_key_count = 0;

         tex_prefetch_candidate *candidate;
         u_vector_foreach(candidate, &state.candidates) {
            if (candidate->bary != chosen_bary ||
                converted >= max_prefetches)
               continue;

            nir_tex_instr *tex = candidate->tex;

            /* Guarded A810 path rejects bindless and dynamic offsets before
             * reaching here, so a compact fixed pair key is sufficient.
             */
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

      /* Fill any remaining slots in original program order.  Also preserves
       * the exact legacy behavior when diversity mode is disabled.
       */
      tex_prefetch_candidate *candidate;
      u_vector_foreach(candidate, &state.candidates) {
         if (candidate->bary == chosen_bary &&
             candidate->tex->op == nir_texop_tex &&
             converted < max_prefetches) {
            candidate->tex->op = nir_texop_tex_prefetch;
            converted++;
         }
      }

      progress = converted > 0;
""",
    """      uint32_t converted = 0;
      uint16_t selected_keys[IR3_MAX_SAMPLER_PREFETCH] = {};
      uint32_t selected_key_count = 0;

      if (prefer_more_used_results && !allow_bindless) {
         /* At most four slots exist, so repeated linear selection keeps this
          * compile-time-only experiment tiny and deterministic.
          */
         while (converted < max_prefetches) {
            tex_prefetch_candidate *best = NULL;
            uint32_t best_uses = 0;
            bool best_unique = false;

            tex_prefetch_candidate *candidate;
            u_vector_foreach(candidate, &state.candidates) {
               if (candidate->bary != chosen_bary ||
                   candidate->tex->op != nir_texop_tex)
                  continue;

               nir_tex_instr *tex = candidate->tex;
               const uint16_t key =
                  ((uint16_t)tex->texture_index << 4) |
                  (uint16_t)tex->sampler_index;
               const bool unique =
                  !frane_26316_key_selected(key, selected_keys,
                                           selected_key_count);
               const uint32_t uses = frane_26316_tex_use_count(tex);

               if (!best ||
                   uses > best_uses ||
                   (uses == best_uses &&
                    prefer_unique_fixed_pairs && unique && !best_unique)) {
                  best = candidate;
                  best_uses = uses;
                  best_unique = unique;
               }
            }

            if (!best)
               break;

            nir_tex_instr *tex = best->tex;
            const uint16_t key =
               ((uint16_t)tex->texture_index << 4) |
               (uint16_t)tex->sampler_index;

            tex->op = nir_texop_tex_prefetch;
            if (!frane_26316_key_selected(key, selected_keys,
                                          selected_key_count) &&
                selected_key_count < IR3_MAX_SAMPLER_PREFETCH) {
               selected_keys[selected_key_count++] = key;
            }
            converted++;
         }
      } else {
         /* 26.3.15 behavior: spread the first wave across distinct fixed
          * texture/sampler pairs when requested.
          */
         if (prefer_unique_fixed_pairs && !allow_bindless) {
            tex_prefetch_candidate *candidate;
            u_vector_foreach(candidate, &state.candidates) {
               if (candidate->bary != chosen_bary ||
                   converted >= max_prefetches)
                  continue;

               nir_tex_instr *tex = candidate->tex;
               const uint16_t key =
                  ((uint16_t)tex->texture_index << 4) |
                  (uint16_t)tex->sampler_index;

               if (frane_26316_key_selected(key, selected_keys,
                                            selected_key_count))
                  continue;

               tex->op = nir_texop_tex_prefetch;
               selected_keys[selected_key_count++] = key;
               converted++;
            }
         }

         /* Fill remaining slots in original program order. */
         tex_prefetch_candidate *candidate;
         u_vector_foreach(candidate, &state.candidates) {
            if (candidate->bary == chosen_bary &&
                candidate->tex->op == nir_texop_tex &&
                converted < max_prefetches) {
               candidate->tex->op = nir_texop_tex_prefetch;
               converted++;
            }
         }
      }

      progress = converted > 0;
""",
    "rank legal candidates by direct use count with diversity tie-break",
)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, ~0u, true, false);
""",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, ~0u, true, false, false);
""",
    "preserve exact generic upstream-capability policy",
)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, frane_prefetch_cap, false,
                  compiler->frane_26315_prefetch_diversity);
""",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, frane_prefetch_cap, false,
                  compiler->frane_26315_prefetch_diversity,
                  compiler->frane_26316_prefetch_use_score);
""",
    "wire use-aware ranking only into guarded A810 path",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.15 A810 PREFETCH-SELECT EXP / Mesa ",
    "Frane Mesa 26.3.16 A810 PREFETCH-SCORE EXP / Mesa ",
    "experimental driver identity",
)

# Surgical guards.
compiler_c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
compiler_h = (ROOT / "src/freedreno/ir3/ir3_compiler.h").read_text()
context = (ROOT / "src/freedreno/ir3/ir3_context.c").read_text()
lower = (ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c").read_text()
nir_h = (ROOT / "src/freedreno/ir3/ir3_nir.h").read_text()
cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
pipeline = (ROOT / "src/freedreno/vulkan/tu_pipeline.cc").read_text()
devs = (ROOT / "src/freedreno/common/freedreno_devices.py").read_text()

assert 'TU_A810_26315_PREFETCH_DIVERSITY", true' in compiler_c
assert 'TU_A810_26315_QUAD_TEX_PREFETCH", true' in compiler_c
assert 'TU_A810_26316_PREFETCH_USE_SCORE' in compiler_c
assert 'frane_26316_prefetch_use_score' in compiler_h

assert 'bool prefer_more_used_results' in nir_h
assert 'frane_26316_tex_use_count' in lower
assert 'nir_foreach_use_including_if' in lower
assert 'frane_26316_key_selected' in lower
assert 'uses > best_uses' in lower
assert 'prefer_unique_fixed_pairs && unique && !best_unique' in lower

assert '&so->prefetch_bary_type, ~0u, true, false, false' in context
assert 'compiler->frane_26316_prefetch_use_score' in context
assert 'compiler->frane_26315_quad_tex_prefetch ? 4u :' in context

# Legality and correctness fences stay intact.
assert 'if (!allow_bindless)' in lower
assert 'ok_tex_samp(tex, allow_bindless)' in lower
assert 'frane_26313_same_lrz_fs_signature' not in cmd
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'TU_A810_26313_LRZ_FASTPATH' in pipeline

a810_pos = devs.index('GPUId(chip_id=0xffff44010000, name="Adreno (TM) 810")')
assert 'has_fs_tex_prefetch = True' not in devs[max(0, a810_pos - 2500):a810_pos + 1800]

assert 'Frane Mesa 26.3.16 A810 PREFETCH-SCORE EXP' in (
    ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

print("Frane Mesa 26.3.16 A810 PREFETCH-SCORE EXP applied", flush=True)
