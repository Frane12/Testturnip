#!/usr/bin/env python3
"""Frane Mesa 26.3.10 A810 UBO-LOCALITY EXP.

Layered strictly on 26.3.9 GEN8-GMEM-DIM.

One experiment only: allow A810's IR3 UBO-promotion planner to coalesce
nearby ranges into one constant-file upload.  This trades a small number of
otherwise-unused copied bytes for fewer memory-backed UBO windows in hot
shaders.

Default gap: 64 bytes.
A/B: TU_A810_26310_UBO_GAP=0|32|64|128

Safety:
  * A810 only; other GPUs are exact 26.3.9 behavior.
  * Only load_ubo range analysis is changed; global-load lowering stays gap=0.
  * Existing constant-file upload_remaining budget remains a hard bound.
  * Bridge-merges account for the newly-covered hole bytes too (unlike the
    older community prototype, which could under-account secondary merges).
  * can_speculate is ANDed when planned ranges merge.
  * no register-pressure, FP16, unroll, barrier, shader scheduling, GMEM,
    autotune, sync, WSI, or render-state changes.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.10 UBO-LOCALITY source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.10 UBO-LOCALITY PASS {label}", flush=True)


edit(
    "src/freedreno/ir3/ir3_compiler.c",
    '#include "util/u_call_once.h"\n#include "util/os_misc.h"\n',
    '#include "util/u_call_once.h"\n#include "util/u_debug.h"\n#include "util/os_misc.h"\n',
    "explicit debug option include",
)

edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   const struct fd_dev_info *info;

   /* The maximum number of constants, in vec4's, across the entire graphics
    * pipeline.
    */""",
    """   const struct fd_dev_info *info;

   /* 26.3.10: maximum byte hole the A810 UBO promotion planner may absorb
    * while coalescing nearby ranges. Zero preserves upstream behavior.
    */
   uint16_t frane_26310_ubo_gap;

   /* The maximum number of constants, in vec4's, across the entire graphics
    * pipeline.
    */""",
    "add A810 UBO locality compiler policy",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      ir3_shader_debug |= IR3_DBG_NODESCPREFETCH;

   /* TODO see if older GPU's were different here */""",
    """      ir3_shader_debug |= IR3_DBG_NODESCPREFETCH;

   /* 26.3.10 A810 UBO-LOCALITY.
    *
    * Keep this intentionally discrete so hardware A/B can use one binary.
    * Unsupported values fall back to the conservative 64-byte default.
    */
   const uint64_t frane_chip_id = dev_id->chip_id;
   const bool frane_is_a810 =
      frane_chip_id == UINT64_C(0x44010000) ||
      frane_chip_id == UINT64_C(0xffff44010000);
   if (frane_is_a810) {
      int gap = debug_get_num_option("TU_A810_26310_UBO_GAP", 64);
      switch (gap) {
      case 0:
      case 32:
      case 64:
      case 128:
         break;
      default:
         gap = 64;
         break;
      }
      compiler->frane_26310_ubo_gap = gap;
   }

   /* TODO see if older GPU's were different here */""",
    "initialize A810-only 0/32/64/128 byte policy",
)

edit(
    "src/freedreno/ir3/ir3_nir_analyze_ubo_ranges.c",
    """static void
merge_neighbors(struct ir3_ubo_analysis_state *state, int index)
{
   struct ir3_ubo_range *a = &state->range[index];

   /* index is always the first slot that would have neighbored/overlapped with
    * the new range.
    */
   for (int i = index + 1; i < state->num_enabled; i++) {
      struct ir3_ubo_range *b = &state->range[i];
      if (memcmp(&a->ubo, &b->ubo, sizeof(a->ubo)))
         continue;

      if (a->start > b->end || a->end < b->start)
         continue;

      /* Merge B into A. */
      a->start = MIN2(a->start, b->start);
      a->end = MAX2(a->end, b->end);

      /* Swap the last enabled range into B's now unused slot */
      *b = state->range[--state->num_enabled];
   }
}""",
    """static uint32_t
range_gap(const struct ir3_ubo_range *a, const struct ir3_ubo_range *b)
{
   if (a->end < b->start)
      return b->start - a->end;
   if (b->end < a->start)
      return a->start - b->end;
   return 0;
}

static void
merge_neighbors(struct ir3_ubo_analysis_state *state, int index,
                uint32_t max_coalesce_gap, uint32_t *upload_remaining)
{
   struct ir3_ubo_range *a = &state->range[index];

   /* Re-check the swapped slot after every merge. This matters when a newly
    * extended range bridges two previously-independent planned ranges.
    */
   for (int i = index + 1; i < state->num_enabled;) {
      struct ir3_ubo_range *b = &state->range[i];
      if (memcmp(&a->ubo, &b->ubo, sizeof(a->ubo))) {
         i++;
         continue;
      }

      const uint32_t gap = range_gap(a, b);
      if (gap > max_coalesce_gap ||
          (gap && gap >= *upload_remaining)) {
         i++;
         continue;
      }

      /* Both existing ranges have already consumed their own sizes from the
       * budget. A disjoint merge only adds the hole between them.
       */
      if (gap)
         *upload_remaining -= gap;

      a->start = MIN2(a->start, b->start);
      a->end = MAX2(a->end, b->end);
      a->can_speculate &= b->can_speculate;

      /* Swap the last enabled range into B's slot, then inspect that new
       * occupant before advancing.
       */
      *b = state->range[--state->num_enabled];
   }
}""",
    "budget-safe bridge merge",
)

edit(
    "src/freedreno/ir3/ir3_nir_analyze_ubo_ranges.c",
    """static void
gather_ubo_ranges(nir_shader *nir, nir_intrinsic_instr *instr,
                  struct ir3_ubo_analysis_state *state, uint32_t alignment,
                  uint32_t *upload_remaining)
{""",
    """static void
gather_ubo_ranges(nir_shader *nir, nir_intrinsic_instr *instr,
                  struct ir3_ubo_analysis_state *state, uint32_t alignment,
                  uint32_t max_coalesce_gap, uint32_t *upload_remaining)
{""",
    "thread coalesce gap through UBO planner",
)

edit(
    "src/freedreno/ir3/ir3_nir_analyze_ubo_ranges.c",
    """      /* Don't extend existing uploads unless they're
       * neighboring/overlapping.
       */
      if (r.start > plan_r->end || r.end < plan_r->start)
         continue;

      r.start = MIN2(r.start, plan_r->start);
      r.end = MAX2(r.end, plan_r->end);

      uint32_t added = (plan_r->start - r.start) + (r.end - plan_r->end);
      if (added >= *upload_remaining)
         return;

      plan_r->start = r.start;
      plan_r->end = r.end;
      plan_r->can_speculate &=
         !!(nir_intrinsic_access(instr) & ACCESS_CAN_SPECULATE);
      *upload_remaining -= added;

      merge_neighbors(state, i);
      return;""",
    """      const uint32_t gap = range_gap(&r, plan_r);
      if (gap > max_coalesce_gap)
         continue;

      const uint32_t old_size = plan_r->end - plan_r->start;
      const uint32_t new_start = MIN2(r.start, plan_r->start);
      const uint32_t new_end = MAX2(r.end, plan_r->end);
      const uint32_t new_size = new_end - new_start;
      const uint32_t added = new_size - old_size;
      if (added >= *upload_remaining)
         return;

      plan_r->start = new_start;
      plan_r->end = new_end;
      plan_r->can_speculate &=
         !!(nir_intrinsic_access(instr) & ACCESS_CAN_SPECULATE);
      *upload_remaining -= added;

      merge_neighbors(state, i, max_coalesce_gap, upload_remaining);
      return;""",
    "coalesce nearby ranges with exact byte accounting",
)

edit(
    "src/freedreno/ir3/ir3_nir_analyze_ubo_ranges.c",
    """                  gather_ubo_ranges(nir, nir_instr_as_intrinsic(instr), &state,
                                    align_vec4,
                                    &upload_remaining);""",
    """                  gather_ubo_ranges(nir, nir_instr_as_intrinsic(instr), &state,
                                    align_vec4, 0,
                                    &upload_remaining);""",
    "keep global-load promotion exact upstream behavior",
)

edit(
    "src/freedreno/ir3/ir3_nir_analyze_ubo_ranges.c",
    """                  gather_ubo_ranges(nir, nir_instr_as_intrinsic(instr), state,
                                    align_vec4,
                                    &upload_remaining);""",
    """                  gather_ubo_ranges(nir, nir_instr_as_intrinsic(instr), state,
                                    align_vec4, compiler->frane_26310_ubo_gap,
                                    &upload_remaining);""",
    "enable locality only for A810 UBO analysis",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.9 A810 GEN8-GMEM-DIM EXP / Mesa ",
    "Frane Mesa 26.3.10 A810 UBO-LOCALITY EXP / Mesa ",
    "experimental driver identity",
)

# Surgical guards.
c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
h = (ROOT / "src/freedreno/ir3/ir3_compiler.h").read_text()
u = (ROOT / "src/freedreno/ir3/ir3_nir_analyze_ubo_ranges.c").read_text()
a = (ROOT / "src/freedreno/vulkan/tu_autotune.cc").read_text()
cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
wsi = (ROOT / "src/freedreno/vulkan/tu_wsi.cc").read_text()

for needle in (
    "TU_A810_26310_UBO_GAP",
    "case 0:",
    "case 32:",
    "case 64:",
    "case 128:",
):
    assert needle in c, needle

assert "uint16_t frane_26310_ubo_gap;" in h
assert "range_gap(" in u
assert "gap && gap >= *upload_remaining" in u
assert "*upload_remaining -= gap;" in u
assert "a->can_speculate &= b->can_speculate;" in u
assert "align_vec4, 0," in u
assert "align_vec4, compiler->frane_26310_ubo_gap," in u
assert "FRANE_2638_HOT_RP_SLOTS = 64" in (ROOT / "src/freedreno/vulkan/tu_autotune.h").read_text()
assert "TU_A810_2639_GMEM_DIM_GATING" in cmd
assert "TU_A810_GMEM_RUNTIME" in a
assert "V28-CLEAN: no driver present-mode override" in wsi
assert "Frane Mesa 26.3.10 A810 UBO-LOCALITY EXP" in (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

print("Frane Mesa 26.3.10 A810 UBO-LOCALITY EXP applied", flush=True)
