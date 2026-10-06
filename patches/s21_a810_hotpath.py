#!/usr/bin/env python3
"""Turnip-Drnas A810 S2.1 HOTPATH.

Layered after the published S2 render policy (V38 SH1 GF1). This experiment deliberately keeps S2 shader ordering, GMEM/SYSMEM policy, GPU power policy, synchronization, LRZ and render-mode semantics.

Two bounded CPU-side changes:
1. Carry the exact GMEM capacity through the V38 DFS. Reusing an existing
   track changes only its busy lifetime mask, so cpp/track-count and therefore
   the capacity bound are unchanged. Recompute capacity only when a new track
   is created.
2. Give the existing 64-entry permanently-pinned render-pass hot cache a
   second deterministic candidate slot. The first hit path is unchanged; the
   second probe is attempted only after a first-slot miss. No replacement is
   introduced, so lifetime/ABA semantics stay identical to HOTPATH-V2.

A/B:
  TU_FRANE_HOT2=1   default: two-choice hot-RP cache
  TU_FRANE_HOT2=0   original V38 direct-mapped hot-RP cache

The GMEM carry transform is result-equivalent by construction and has no
runtime switch; compare against the original V38 SH1 binary for whole-build A/B.
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
            f"V38 O1 source drift: {label}: expected 1 anchor, saw {n}: "
            f"{old[:160]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V38 O1 PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# 1. V38 GMEM search: carry an exact capacity value through the DFS.
#
# frane_gmem_search_pixels() depends only on each track's cpp and the number
# of tracks. An existing-track branch is legal only when track.cpp >= item.cpp,
# therefore that branch only ORs the busy mask and cannot change capacity.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """frane_gmem_search_recurse(struct frane_gmem_search_ctx *ctx,
                          uint32_t pos,
                          struct frane_gmem_search_track *tracks,
                          uint32_t num_tracks)
{""",
    """frane_gmem_search_recurse(struct frane_gmem_search_ctx *ctx,
                          uint32_t pos,
                          struct frane_gmem_search_track *tracks,
                          uint32_t num_tracks,
                          uint32_t capacity)
{""",
    "add carried capacity to GMEM DFS",
)

edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """   /* Existing tracks only form an optimistic upper bound: every remaining
    * item can at best reuse them for free. If a future item needs a new track,
    * exact capacity can only stay equal or decrease.
    */
   if (num_tracks > 0) {
      const uint32_t upper =
         frane_gmem_search_pixels(tracks, num_tracks,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);
      if (upper <= ctx->best_pixels)
         return;
   }
""",
    """   /* O1: capacity is exact for the current cpp/track-count state.
    * Reusing a track changes only its busy lifetime mask, so descendants on
    * reuse edges inherit this value in O(1). A new-track edge recomputes it.
    */
   if (num_tracks > 0 && capacity <= ctx->best_pixels)
      return;
""",
    "remove repeated capacity binary search from reuse nodes",
)

edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """      const uint32_t pixels =
         frane_gmem_search_pixels(tracks, num_tracks,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);
""",
    """      const uint32_t pixels = capacity;
""",
    "reuse carried exact capacity at leaf",
)

edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """      frane_gmem_search_recurse(ctx, pos + 1, tracks, num_tracks);
""",
    """      frane_gmem_search_recurse(ctx, pos + 1, tracks, num_tracks,
                                      capacity);
""",
    "carry capacity across existing-track branch",
)

edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """      frane_gmem_search_recurse(ctx, pos + 1, tracks, num_tracks + 1);
""",
    """      const uint32_t child_capacity =
         frane_gmem_search_pixels(tracks, num_tracks + 1,
                                  ctx->gmem_size,
                                  ctx->gmem_align,
                                  ctx->block_align_shift);
      frane_gmem_search_recurse(ctx, pos + 1, tracks, num_tracks + 1,
                               child_capacity);
""",
    "recompute capacity only when cpp/track-count changes",
)

edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """   frane_gmem_search_recurse(&ctx, 0, tracks, 0);
""",
    """   frane_gmem_search_recurse(&ctx, 0, tracks, 0, UINT32_MAX);
""",
    "seed carried-capacity DFS",
)


# ---------------------------------------------------------------------------
# 2. HOTPATH-V2: keep the 64-entry no-replacement cache but add one alternate
# candidate. First-slot hits pay exactly the old lookup. Only misses mix/probe
# a second slot before falling back to shared_mutex + unordered_map.
# ---------------------------------------------------------------------------
autotune_path = V / "tu_autotune.cc"
src = autotune_path.read_text()
start_marker = """tu_autotune::rp_history_handle
tu_autotune::find_rp_history(const rp_key &key)
{"""
end_marker = """   return rp_history_handle(nullptr);
}
"""
start = src.find(start_marker)
end_start = src.find(end_marker, start)
if start < 0 or end_start < 0:
    raise SystemExit("V38 O1 source drift: find_rp_history boundaries")
end = end_start + len(end_marker)

old_find = src[start:end]
for needle in (
    "FRANE_2638_HOT_RP_SLOTS",
    "rp_history_handle(*cached, false)",
    "std::shared_lock lock(rp_mutex)",
    "compare_exchange_strong",
    "frane_2637_hot_pinned.store",
):
    if needle not in old_find:
        raise SystemExit(f"V38 O1 prerequisite missing in find_rp_history: {needle}")

new_find = r'''tu_autotune::rp_history_handle
tu_autotune::find_rp_history(const rp_key &key)
{
   /* Keep the V38/HOTPATH-V2 fast path narrow and semantics-preserving. */
   const config_t config = active_config.load();
   const bool frane_hot =
      frane_2637_core_fastpath() &&
      frane_a810_gpu(device) &&
      frane_a810_lean_profiled() &&
      config.is_enabled(algorithm::PROFILED) &&
      !config.is_enabled(algorithm::PROFILED_IMM) &&
      !config.test(mod_flag::PREEMPT_OPTIMIZE);

   static const bool frane_hot2 =
      debug_get_bool_option("TU_FRANE_HOT2", true);

   frane_2637_hot_rp_slot *hot_candidates[2] = { nullptr, nullptr };
   uint32_t hot_candidate_count = 0;

   if (frane_hot) {
      const uint32_t slot_mask = FRANE_2638_HOT_RP_SLOTS - 1u;
      const uint32_t first_index = uint32_t(key.hash) & slot_mask;
      hot_candidates[0] = &frane_2637_hot_rp[first_index];
      hot_candidate_count = 1;

      rp_history *cached =
         hot_candidates[0]->history.load(std::memory_order_acquire);
      if (cached &&
          hot_candidates[0]->hash.load(std::memory_order_acquire) == key.hash)
         return rp_history_handle(*cached, false);

      if (frane_hot2) {
         /* 64-bit avalanche: use high hash entropy instead of merely taking
          * another adjacent low-bit slot. Computed only after first miss.
          */
         uint64_t mixed = key.hash;
         mixed ^= mixed >> 33;
         mixed *= UINT64_C(0xff51afd7ed558ccd);
         mixed ^= mixed >> 33;
         mixed *= UINT64_C(0xc4ceb9fe1a85ec53);
         mixed ^= mixed >> 33;

         uint32_t second_index = uint32_t(mixed) & slot_mask;
         if (second_index == first_index)
            second_index = (first_index + 1u) & slot_mask;

         hot_candidates[1] = &frane_2637_hot_rp[second_index];
         hot_candidate_count = 2;

         cached =
            hot_candidates[1]->history.load(std::memory_order_acquire);
         if (cached &&
             hot_candidates[1]->hash.load(std::memory_order_acquire) == key.hash)
            return rp_history_handle(*cached, false);
      }
   }

   std::shared_lock lock(rp_mutex);
   auto it = rp_histories.find(key);
   if (it != rp_histories.end()) {
      for (uint32_t i = 0; i < hot_candidate_count; i++) {
         frane_2637_hot_rp_slot *hot_slot = hot_candidates[i];
         if (!hot_slot ||
             hot_slot->history.load(std::memory_order_relaxed) != nullptr)
            continue;

         rp_history *expected = nullptr;

         /* Preserve 26.3.7/26.3.8 publication ordering: permanent pin first,
          * pointer publication second, pin marker third, hash last. The
          * borrowed hit is allowed only after acquiring the matching hash.
          */
         it->second.refcount.fetch_add(1, std::memory_order_relaxed);
         if (hot_slot->history.compare_exchange_strong(
                expected, &it->second,
                std::memory_order_release,
                std::memory_order_relaxed)) {
            it->second.frane_2637_hot_pinned.store(
               true, std::memory_order_release);
            hot_slot->hash.store(key.hash, std::memory_order_release);
            break;
         }

         /* A race filled this slot after our empty check. Undo the pin and
          * stop rather than risk pinning the same history into both slots.
          */
         it->second.refcount.fetch_sub(1, std::memory_order_relaxed);
         break;
      }

      return rp_history_handle(it->second);
   }

   return rp_history_handle(nullptr);
}

'''

autotune_path.write_text(src[:start] + new_find + src[end:])
print("V38 O1 PASS two-choice no-replacement hot-RP cache", flush=True)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Turnip-Drnas A810 V38 SH1 GF1 / Mesa ",
    "Turnip-Drnas A810 S2.1 / Mesa ",
    "driver identity",
)

# Hard scope/correctness guards.
gmem = (V / "tu_pass.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
device = (V / "tu_device.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
sched = (ROOT / "src/freedreno/ir3/ir3_sched.c").read_text()

for needle in (
    "uint32_t capacity)",
    "num_tracks > 0 && capacity <= ctx->best_pixels",
    "const uint32_t pixels = capacity;",
    "const uint32_t child_capacity =",
    "frane_gmem_search_recurse(&ctx, 0, tracks, 0, UINT32_MAX)",
):
    assert needle in gmem, needle

for needle in (
    "tu_autotune::frane_load_profile(uint64_t hash, uint32_t *value) const",
    "tu_autotune::frane_save_profile(uint64_t hash, uint32_t value) const",
    'debug_get_bool_option("TU_FRANE_HOT2", true)',
    "hot_candidates[2]",
    "FRANE_2638_HOT_RP_SLOTS - 1u",
    "rp_history_handle(*cached, false)",
    "std::shared_lock lock(rp_mutex)",
):
    assert needle in autotune, needle

# Preserve the SH1 scheduling decision and prior correctness-sensitive layers.
assert 'TU_FRANE_SHADER_MODE' in (
    ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert "frane_sh1_pressure_priority" in sched
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd
assert "Turnip-Drnas A810 S2.1 / Mesa " in device

print("Turnip-Drnas A810 S2.1 applied: same S2 render policy, less CPU search/lookup work", flush=True)
