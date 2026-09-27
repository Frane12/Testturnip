#!/usr/bin/env python3
"""Frane Mesa 26.3.16 A810 AUDIT-BOOST.

Layered strictly on the proven 26.3.15 PREFETCH-SELECT build.

Audit fixes / optimizations:
  1) Preserve borrowed hot-cache rp_history_handle ownership through
     find_or_create_rp_history(). 26.3.8 made find_rp_history() borrow the
     permanent hot-cache pin, but find_or_create_rp_history() immediately
     converted that handle to a raw pointer and reconstructed an owning handle,
     reintroducing the atomic refcount inc/dec on the main render-pass path.
  2) Actually reserve the render-pass history map up front on the guarded A810
     core-fastpath. 26.3.7 documented this optimization but never implemented it.
  3) Make diversity-aware texture prefetch selection choose the barycentric
     mode by useful distinct fixed texture/sampler pairs, rather than choosing
     a mode by raw candidate count and only applying diversity afterwards.
  4) Promote both 26.3.15 experiments (diversity + quad prefetch) to default-on,
     while preserving their same-binary opt-outs.

No LRZ dirty suppression is restored. No new texture instruction becomes legal.
No GMEM/SYSMEM decision thresholds, sync semantics, WSI policy, shader optimizer
knobs, or attachment layout behavior are changed.
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
            f"26.3.16 AUDIT-BOOST source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.16 AUDIT-BOOST PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# 1) Main CPU hot path: preserve borrowed ownership instead of dropping the
#    handle to a raw pointer and reconstructing an owning handle.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """tu_autotune::rp_history_handle
tu_autotune::find_or_create_rp_history(const rp_key &key)
{
   rp_history *existing = find_rp_history(key);
   if (existing)
      return *existing;
""",
    """tu_autotune::rp_history_handle
tu_autotune::find_or_create_rp_history(const rp_key &key)
{
   rp_history_handle existing = find_rp_history(key);
   if (existing)
      return existing;
""",
    "preserve borrowed hot handle through find-or-create",
)


# ---------------------------------------------------------------------------
# 2) 26.3.7 said the history map would be reserved, but the implementation
#    deliberately left constructor tuning out. Do the small bounded reserve
#    now: 2x the 64-slot hot cache = 128 buckets of startup headroom.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """{
   tu_bo_suballocator_init(&suballoc, device, 128 * 1024, TU_BO_ALLOC_INTERNAL_RESOURCE, "autotune_suballoc");

   if (supports_preempt_latency_tracking()) {""",
    """{
   tu_bo_suballocator_init(&suballoc, device, 128 * 1024, TU_BO_ALLOC_INTERNAL_RESOURCE, "autotune_suballoc");

   if (frane_2637_core_fastpath() && frane_a810_gpu(device))
      rp_histories.reserve(FRANE_2638_HOT_RP_SLOTS * 2u);

   if (supports_preempt_latency_tracking()) {""",
    "reserve A810 render-pass history map before first insert",
)


# ---------------------------------------------------------------------------
# 3) Diversity-aware barycentric-mode choice.
#
# 26.3.15 chose chosen_bary using raw candidate count first, then applied
# diversity only inside that chosen mode. With a capped prefetch budget this
# can pick (for example) five samples of one texture over four distinct
# textures in another bary mode. When diversity is enabled, rank bary modes by
# the number of distinct fixed tex/sampler pairs that can actually fit in the
# prefetch slots; raw candidate count remains the tie-breaker. Generic Mesa and
# diversity-off behavior stay byte-for-byte policy-equivalent.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """      uint32_t max_tex_with_bary = 0;
      uint32_t chosen_bary = 0;
      for (int i = 0; i < IJ_COUNT; i++) {
         if (state.per_bary_candidates[i] > max_tex_with_bary) {
            max_tex_with_bary = state.per_bary_candidates[i];
            chosen_bary = i;
         }
      }

      uint32_t converted = 0;
""",
    """      uint32_t max_tex_with_bary = 0;
      uint32_t chosen_bary = 0;

      if (prefer_unique_fixed_pairs && !allow_bindless) {
         uint32_t best_unique_pairs = 0;
         const uint32_t useful_cap =
            MIN2(max_prefetches, (uint32_t)IR3_MAX_SAMPLER_PREFETCH);

         for (int i = 0; i < IJ_COUNT; i++) {
            uint16_t unique_keys[IR3_MAX_SAMPLER_PREFETCH] = {};
            uint32_t unique_count = 0;

            tex_prefetch_candidate *candidate;
            u_vector_foreach(candidate, &state.candidates) {
               if (candidate->bary != i || unique_count >= useful_cap)
                  continue;

               nir_tex_instr *tex = candidate->tex;
               const uint16_t key =
                  ((uint16_t)tex->texture_index << 4) |
                  (uint16_t)tex->sampler_index;

               bool duplicate = false;
               for (uint32_t k = 0; k < unique_count; k++) {
                  if (unique_keys[k] == key) {
                     duplicate = true;
                     break;
                  }
               }

               if (!duplicate)
                  unique_keys[unique_count++] = key;
            }

            const uint32_t total = state.per_bary_candidates[i];
            if (unique_count > best_unique_pairs ||
                (unique_count == best_unique_pairs &&
                 total > max_tex_with_bary)) {
               best_unique_pairs = unique_count;
               max_tex_with_bary = total;
               chosen_bary = i;
            }
         }
      } else {
         for (int i = 0; i < IJ_COUNT; i++) {
            if (state.per_bary_candidates[i] > max_tex_with_bary) {
               max_tex_with_bary = state.per_bary_candidates[i];
               chosen_bary = i;
            }
         }
      }

      uint32_t converted = 0;
""",
    "choose bary mode by useful diversity when diversity policy is active",
)


# ---------------------------------------------------------------------------
# 4) User-confirmed 26.3.15 base stays intact; promote both remaining
#    same-binary prefetch experiments to default-on. Opt-out variables remain.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26315_prefetch_diversity =
         debug_get_bool_option("TU_A810_26315_PREFETCH_DIVERSITY", false);
      compiler->frane_26315_quad_tex_prefetch =
         debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", false);
""",
    """      compiler->frane_26315_prefetch_diversity =
         debug_get_bool_option("TU_A810_26315_PREFETCH_DIVERSITY", true);
      compiler->frane_26315_quad_tex_prefetch =
         debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", true);
""",
    "promote diversity and quad prefetch to defaults",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.15 A810 PREFETCH-SELECT EXP / Mesa ",
    "Frane Mesa 26.3.16 A810 AUDIT-BOOST / Mesa ",
    "experimental driver identity",
)


# Surgical invariants / regression guards.
autotune = (V / "tu_autotune.cc").read_text()
autotune_h = (V / "tu_autotune.h").read_text()
compiler_c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
context = (ROOT / "src/freedreno/ir3/ir3_context.c").read_text()
lower = (ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
pipeline = (V / "tu_pipeline.cc").read_text()
wsi = (V / "tu_wsi.cc").read_text()

# Borrowed ownership must survive the main lookup path.
assert "rp_history_handle existing = find_rp_history(key);" in autotune
assert "rp_history *existing = find_rp_history(key);" not in autotune
assert "if (existing)\n      return existing;" in autotune
assert "rp_history_handle(*cached, false)" in autotune
assert "if (!history || !owns_ref)" in autotune

# The previously documented reserve now really exists and is bounded.
assert "rp_histories.reserve(FRANE_2638_HOT_RP_SLOTS * 2u);" in autotune
assert "FRANE_2638_HOT_RP_SLOTS = 64" in autotune_h

# Default-on means default-on, but all opt-outs remain available.
assert 'TU_A810_26315_PREFETCH_DIVERSITY", true' in compiler_c
assert 'TU_A810_26315_QUAD_TEX_PREFETCH", true' in compiler_c
assert "compiler->frane_26315_quad_tex_prefetch ? 4u :" in context
assert "compiler->frane_26315_prefetch_diversity" in context

# Diversity-aware bary selection is isolated to the guarded fixed-ID path.
assert "best_unique_pairs" in lower
assert "prefer_unique_fixed_pairs && !allow_bindless" in lower
assert "MIN2(max_prefetches, (uint32_t)IR3_MAX_SAMPLER_PREFETCH)" in lower
assert "state.per_bary_candidates[i]" in lower
assert "selected_keys[IR3_MAX_SAMPLER_PREFETCH]" in lower
assert "candidate->tex->op == nir_texop_tex" in lower

# Never restore the rejected 26.3.13 FS-signature LRZ suppression.
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "same_lrz_signature" not in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd

# Keep the rest of the proven stack.
assert "TU_A810_GMEM_RUNTIME" in autotune
assert "frane_2634_decide_gmem_runtime" in autotune
assert "FRANE_2635_STAGE_NIR_MAX_ENTRIES" in (V / "tu_shader.cc").read_text()
assert "TU_A810_2639_GMEM_DIM_GATING" in cmd
assert "TU_A810_26313_LRZ_FASTPATH" in pipeline
assert "V28-CLEAN: no driver present-mode override" in wsi
assert "Frane Mesa 26.3.16 A810 AUDIT-BOOST" in (V / "tu_device.cc").read_text()

print("Frane Mesa 26.3.16 A810 AUDIT-BOOST applied", flush=True)
