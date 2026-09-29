# Turnip A810 V37 — GMEM MASK LAB

V37 returns to the validated V35 base and intentionally drops the unrelated
V36 scheduler/prefetch/GMEM-TURBO defaults.

The experiment attacks two structural limitations in the GMEM lifetime
allocator.

## 1. Exact subpass occupancy instead of one lifetime envelope

V34/V35 merge reuse into one \`first_subpass..last_subpass\` range. If a track
contains attachments used at subpasses 0 and 3, that representation loses the
free hole at 1..2.

V37 keeps a 64-bit occupancy mask for render passes with up to 64 subpasses.
An attachment can reuse a track whenever its complete lifetime interval has no
occupied bit in common with that track.

## 2. Remove attachment-order dependence

Entries are processed by descending cpp. A large-cpp track therefore exists
before smaller attachments are considered, allowing smaller non-overlapping
attachments to reuse it. This avoids the old case where an early cpp=1
allocation cannot later host a cpp=4/8 attachment.

## 3. Exact pack and impossible-layout rescue

The mask candidate uses a direct max-min block packer. It does not depend on
the baseline greedy pack succeeding.

- Normal case: mask layout is adopted only when it strictly increases
  \`pass->gmem_pixels\`.
- Baseline-impossible case: V37 may rescue the pass only when the exact packer
  returns a valid non-zero capacity with aligned offsets.

This can potentially turn a pass that previously had no valid GMEM layout into
a GMEM-capable pass.

## A/B

- \`TU_A810_26337_GMEM_MASK_PACK=1\` — default
- \`TU_A810_26337_GMEM_MASK_PACK=0\` — exact V35 behavior

No V36 scheduler/prefetch/TURBO defaults are included. Display name:
**Turnip A810 V37**.
