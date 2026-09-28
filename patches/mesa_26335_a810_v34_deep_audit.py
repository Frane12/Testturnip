#!/usr/bin/env python3
"""26.3.35 A810 V34 deep-audit clean.

Continue the deep-audit workstream on the validated 26.3.34 baseline.
This patch deliberately does NOT retune shader/compiler output, normal render
decisions, autotuner probabilities, or GMEM/SYSMEM policy thresholds.

Changes are semantics-preserving cleanup / hardening:
- avoid constructing/evaluating the V34 lifetime candidate for render passes
  where it cannot create lifetime reuse (single-subpass or <=1 GMEM alloc);
- use a strict mathematical upper bound to skip candidate packing when the
  candidate cannot possibly beat the already-selected V34 pixel capacity;
- cache the V34 lifetime feature decision once per render-pass config;
- avoid heap allocation at exactly 16 poll fds in KGSL wait-any and allocate
  exactly the required count above that boundary;
- initialize A810 power bookkeeping before the emulated-queue early return;
- guard the optional suballocator name before strcmp.

A810 V34 render policy remains the baseline.
"""
from pathlib import Path

R = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = R / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.35 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.35 PASS {label}", flush=True)

# ---- tu_pass.cc: preserve V34 decisions, remove provably useless work ----

anchor = r'''   return pixels;
}

static struct tu_gmem_alloc *
tu_gmem_alloc(struct tu_gmem_alloc *allocs,
'''

replacement = r'''   return pixels;
}

/* A candidate using N allocations with cpp_i bytes/pixel must spend at
 * least pixels * sum(cpp_i) bytes. Ignoring block alignment can only make
 * this bound more optimistic, therefore if even this optimistic capacity
 * cannot beat the V34 baseline there is no reason to run the packer.
 */
static bool
frane_lifetime_candidate_can_beat(const struct tu_gmem_alloc *allocs,
                                  uint32_t num_allocs,
                                  uint32_t gmem_size,
                                  uint32_t baseline_pixels)
{
   if (!num_allocs)
      return false;

   uint64_t cpp_total = 0;
   for (uint32_t i = 0; i < num_allocs; i++)
      cpp_total += allocs[i].cpp;

   if (!cpp_total)
      return false;

   const uint64_t optimistic_pixels = (uint64_t) gmem_size / cpp_total;
   return optimistic_pixels > baseline_pixels;
}

static struct tu_gmem_alloc *
tu_gmem_alloc(struct tu_gmem_alloc *allocs,
'''
edit("tu_pass.cc", anchor, replacement, "add lifetime candidate upper bound")

edit(
    "tu_pass.cc",
    r'''   STACK_ARRAY(struct tu_gmem_alloc, gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, att_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc, lifetime_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, lifetime_att_gmem_alloc, 2 * pass->attachment_count);

   for (enum tu_gmem_layout layout = (enum tu_gmem_layout) 0;
''',
    r'''   STACK_ARRAY(struct tu_gmem_alloc, gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, att_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc, lifetime_gmem_alloc, 2 * pass->attachment_count);
   STACK_ARRAY(struct tu_gmem_alloc *, lifetime_att_gmem_alloc, 2 * pass->attachment_count);

   const bool frane_lifetime_pack =
      frane_a810_lifetime_tile_pack_enabled(phys_dev);

   for (enum tu_gmem_layout layout = (enum tu_gmem_layout) 0;
''',
    "cache V34 lifetime feature decision",
)

edit(
    "tu_pass.cc",
    r'''      uint32_t num_lifetime_alloc = 0;
      for (int i = 0; i < 2 * pass->attachment_count; i++)
         lifetime_att_gmem_alloc[i] = NULL;

      if (frane_a810_lifetime_tile_pack_enabled(phys_dev)) {
''',
    r'''      uint32_t num_lifetime_alloc = 0;
      for (int i = 0; i < 2 * pass->attachment_count; i++)
         lifetime_att_gmem_alloc[i] = NULL;

      /* A single subpass has no disjoint subpass lifetime to reuse, and a
       * baseline with one GMEM allocation cannot reduce below one allocation.
       * Skip the O(attachments^2) candidate construction in both cases.
       */
      const bool try_lifetime_pack =
         frane_lifetime_pack &&
         pass->subpass_count > 1 &&
         num_gmem_alloc > 1;

      if (try_lifetime_pack) {
''',
    "skip impossible lifetime candidate construction",
)

edit(
    "tu_pass.cc",
    r'''      if (num_lifetime_alloc > 0 &&
          frane_a810_lifetime_tile_pack_enabled(phys_dev)) {
         const uint32_t candidate_pixels =
''',
    r'''      if (num_lifetime_alloc > 0 &&
          try_lifetime_pack &&
          frane_lifetime_candidate_can_beat(lifetime_gmem_alloc,
                                            num_lifetime_alloc,
                                            gmem_size,
                                            pixels)) {
         const uint32_t candidate_pixels =
''',
    "skip candidate pack below optimistic upper bound",
)

# ---- KGSL wait-any: no semantic change, less transient allocation ----

edit(
    "tu_knl_kgsl.cc",
    r'''   if ((convert_ts_to_fd || num_fds > 0) && count >= STACK_POLL_FDS) {
      fds = (struct pollfd *) malloc((size_t(count) + 1u) * sizeof(*fds));
''',
    r'''   if ((convert_ts_to_fd || num_fds > 0) && count > STACK_POLL_FDS) {
      fds = (struct pollfd *) malloc((size_t) count * sizeof(*fds));
''',
    "tighten wait-any stack/heap boundary",
)

# ---- queue bookkeeping: initialize before emulated-queue early return ----

edit(
    "tu_queue.cc",
    r'''   queue->priority = -1;
   queue->msm_queue_id = 0;

   if (shared_queue) {
''',
    r'''   queue->priority = -1;
   queue->msm_queue_id = 0;
   queue->frane_a810_pwr_active = false;
   queue->frane_a810_pwr_submissions = 0;

   if (shared_queue) {
''',
    "initialize power bookkeeping for every queue",
)

# ---- suballocator robustness: name is optional API data ----

edit(
    "tu_suballoc.cc",
    r'''      ((frane_lean_cache && frane_a830) ||
       (frane_a810_lean_cache && frane_a810)) &&
      strcmp(suballoc->name, "autotune_suballoc") == 0 &&
''',
    r'''      ((frane_lean_cache && frane_a830) ||
       (frane_a810_lean_cache && frane_a810)) &&
      suballoc->name &&
      strcmp(suballoc->name, "autotune_suballoc") == 0 &&
''',
    "guard optional suballocator name",
)

edit(
    "tu_device.cc",
    "Frane Mesa 26.3.34 A810 LIFETIME-TILE-PACK EXP / Mesa ",
    "Frane Mesa 26.3.35 A810 V34-DEEP-AUDIT-CLEAN EXP / Mesa ",
    "driver identity",
)

# Final invariants.
p = (R / "tu_pass.cc").read_text()
k = (R / "tu_knl_kgsl.cc").read_text()
q = (R / "tu_queue.cc").read_text()
s = (R / "tu_suballoc.cc").read_text()
d = (R / "tu_device.cc").read_text()

assert "frane_lifetime_candidate_can_beat" in p
assert "pass->subpass_count > 1" in p
assert "num_gmem_alloc > 1" in p
assert "optimistic_pixels > baseline_pixels" in p
assert "candidate_pixels > pixels" in p
assert "count > STACK_POLL_FDS" in k
assert "(size_t) count * sizeof(*fds)" in k
assert "(size_t(count) + 1u)" not in k
assert q.index("queue->frane_a810_pwr_active = false;") < q.index("if (shared_queue) {")
assert "suballoc->name &&" in s
assert "Frane Mesa 26.3.35 A810 V34-DEEP-AUDIT-CLEAN EXP" in d

print("26.3.35 A810 V34 deep-audit clean applied", flush=True)
