# Frane Mesa 26.3.35 A810 V34 DEEP-AUDIT CLEAN

This branch continues the deep-audit workstream on the user-validated
26.3.34 A810 LIFETIME-TILE-PACK baseline.

The goal is not another aggressive renderer heuristic. 26.3.35 preserves the
V34 render result and focuses on unnecessary work and robustness around the
existing implementation.

## Changes

### V34 lifetime packing hot/creation path

V34 builds a lifetime-aware GMEM candidate and only adopts it on a strict
\`candidate_pixels > baseline_pixels\` win. V35 preserves that admission rule.

V35 avoids candidate work when it is provably useless:

- single-subpass render passes are not scanned for lifetime aliasing because all
  attachments used by that pass overlap in the same subpass;
- a baseline with one GMEM allocation cannot reduce below one allocation;
- before the V34 candidate packer runs, V35 computes an optimistic byte-capacity
  upper bound. If even an alignment-free ideal candidate cannot beat the
  already selected V34 pixel capacity, the packer is skipped.

This only removes work. It does not make a different GMEM/SYSMEM decision.

### KGSL wait-any cleanup

The V34 stack array holds 16 poll descriptors. V35 keeps exactly 16 descriptors
on stack rather than switching to heap at the boundary, and allocates exactly
\`count\` descriptors only for counts above 16.

### Queue / BO robustness

- A810 power bookkeeping is initialized before an emulated-queue early return,
  avoiding uninitialized downstream-only fields.
- The optional suballocator name is checked before the downstream autotune BO
  name comparison.

## Deliberately unchanged

- shader compiler/codegen;
- normal render output;
- autotuner probability/selection policy;
- V34 lifetime/tile admission rule;
- packed depth+stencil policy;
- GMEM/SYSMEM thresholds;
- WSI present policy.

26.3.34 remains the direct A/B baseline.
