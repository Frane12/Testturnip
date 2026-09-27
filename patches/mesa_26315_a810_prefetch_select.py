#!/usr/bin/env python3
"""Frane Mesa 26.3.15 A810 PREFETCH-SELECT EXP.

Layered strictly on 26.3.14 LRZ-SAFE + TRIPLE-PREFETCH.

Confirmed promotion:
  - the 26.3.14 A810 triple-prefetch switch becomes enabled by default.

New independent experiments:
  1) TU_A810_26315_PREFETCH_DIVERSITY=1
     When more legal fixed texture/sampler candidates exist than available
     pre-dispatch slots, prefer distinct texture/sampler pairs first, then
     fill any remaining slots in original program order.

  2) TU_A810_26315_QUAD_TEX_PREFETCH=1
     Raise the guarded A810 candidate cap from the new default of 3 to the
     hardware/Mesa limit of 4.

Both remain inside the existing 26.3.11 legality path:
  - simple non-bindless 2D samples only;
  - no array/sparse/lod/bias/projector/offset/ddx/ddy/MS cases;
  - only encodable fixed texture/sampler IDs.

LRZ behavior from 26.3.14 is untouched.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.15 PREFETCH-SELECT source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.15 PREFETCH-SELECT PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# Promote the proven 26.3.14 triple-prefetch path to default-on and add two
# new independent switches.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26314_triple_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    """   bool frane_26314_triple_tex_prefetch;

   /* 26.3.15: candidate-selection experiments layered on the proven
    * triple-prefetch path.
    */
   bool frane_26315_prefetch_diversity;
   bool frane_26315_quad_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    "add diversity and quad-prefetch compiler policy bits",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26314_triple_tex_prefetch =
         debug_get_bool_option("TU_A810_26314_TRIPLE_TEX_PREFETCH", false);
   }
""",
    """      compiler->frane_26314_triple_tex_prefetch =
         debug_get_bool_option("TU_A810_26314_TRIPLE_TEX_PREFETCH", true);
      compiler->frane_26315_prefetch_diversity =
         debug_get_bool_option("TU_A810_26315_PREFETCH_DIVERSITY", false);
      compiler->frane_26315_quad_tex_prefetch =
         debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", false);
   }
""",
    "promote triple default and add same-binary A/B switches",
)

# ---------------------------------------------------------------------------
# Extend the prefetch lowering policy with an optional selection mode.
# Generic upstream-capability devices keep exact program-order behavior.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_nir.h",
    """bool ir3_nir_lower_tex_prefetch(nir_shader *shader,
                                enum ir3_bary *prefetch_bary_type,
                                uint32_t max_prefetches,
                                bool allow_bindless);""",
    """bool ir3_nir_lower_tex_prefetch(nir_shader *shader,
                                enum ir3_bary *prefetch_bary_type,
                                uint32_t max_prefetches,
                                bool allow_bindless,
                                bool prefer_unique_fixed_pairs);""",
    "add optional candidate-selection policy argument",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type,
                           uint32_t max_prefetches,
                           bool allow_bindless)
{""",
    """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type,
                           uint32_t max_prefetches,
                           bool allow_bindless,
                           bool prefer_unique_fixed_pairs)
{""",
    "thread candidate-selection mode into lowering pass",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """      uint32_t converted = 0;
      tex_prefetch_candidate *candidate;
      u_vector_foreach(candidate, &state.candidates) {
         if (candidate->bary == chosen_bary &&
             converted < max_prefetches) {
            candidate->tex->op = nir_texop_tex_prefetch;
            converted++;
         }
      }

      progress = converted > 0;
""",
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
    "prefer unique fixed texture/sampler pairs before program-order fill",
)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, ~0u, true);
      } else if (compiler->frane_26311_safe_tex_prefetch) {
         /* A810 remains on the restricted non-bindless path.  26.3.12
          * only increases the candidate budget from one to two, still well
          * below IR3_MAX_SAMPLER_PREFETCH (4).
          */
         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type,
                  compiler->frane_26314_triple_tex_prefetch ? 3u :
                  (compiler->frane_26312_dual_tex_prefetch ? 2u : 1u), false);
      }
""",
    """         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, ~0u, true, false);
      } else if (compiler->frane_26311_safe_tex_prefetch) {
         /* A810 remains on the restricted non-bindless path.  Triple is now
          * the confirmed default; quad and diversity remain explicit A/B
          * experiments.
          */
         const uint32_t frane_prefetch_cap =
            compiler->frane_26315_quad_tex_prefetch ? 4u :
            (compiler->frane_26314_triple_tex_prefetch ? 3u :
             (compiler->frane_26312_dual_tex_prefetch ? 2u : 1u));

         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, frane_prefetch_cap, false,
                  compiler->frane_26315_prefetch_diversity);
      }
""",
    "wire default triple plus independent diversity and quad experiments",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.14 A810 LRZ-SAFE TRIPLE-PREFETCH EXP / Mesa ",
    "Frane Mesa 26.3.15 A810 PREFETCH-SELECT EXP / Mesa ",
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

assert 'TU_A810_26314_TRIPLE_TEX_PREFETCH", true' in compiler_c
assert 'TU_A810_26315_PREFETCH_DIVERSITY' in compiler_c
assert 'TU_A810_26315_QUAD_TEX_PREFETCH' in compiler_c
assert 'frane_26315_prefetch_diversity' in compiler_h
assert 'frane_26315_quad_tex_prefetch' in compiler_h

assert 'bool prefer_unique_fixed_pairs' in nir_h
assert 'bool prefer_unique_fixed_pairs' in lower
assert 'selected_keys[IR3_MAX_SAMPLER_PREFETCH]' in lower
assert 'candidate->tex->op == nir_texop_tex' in lower
assert '((uint16_t)tex->texture_index << 4)' in lower

assert '&so->prefetch_bary_type, ~0u, true, false' in context
assert 'compiler->frane_26315_quad_tex_prefetch ? 4u :' in context
assert 'compiler->frane_26314_triple_tex_prefetch ? 3u :' in context
assert 'compiler->frane_26315_prefetch_diversity' in context

# Existing legality restrictions remain mandatory.
assert 'if (!allow_bindless)' in lower
assert 'ok_tex_samp(tex, allow_bindless)' in lower
assert 'converted < max_prefetches' in lower

# LRZ correctness fix from 26.3.14 must remain untouched.
assert 'frane_26313_same_lrz_fs_signature' not in cmd
assert 'same_lrz_signature' not in cmd
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert 'TU_A810_26313_LRZ_FASTPATH' in pipeline

# Public capability stays disabled.
a810_pos = devs.index('GPUId(chip_id=0xffff44010000, name="Adreno (TM) 810")')
assert 'has_fs_tex_prefetch = True' not in devs[max(0, a810_pos - 2500):a810_pos + 1800]

assert 'Frane Mesa 26.3.15 A810 PREFETCH-SELECT EXP' in (
    ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

print("Frane Mesa 26.3.15 A810 PREFETCH-SELECT EXP applied", flush=True)
