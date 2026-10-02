#!/usr/bin/env python3
"""Drnas Turnip V59 A810 LRZ-CLEAN.

Base: V58 LRZ-KEEP.

V59 does two deliberately bounded things:

1) One more LRZ step on A8XX:
   when stencil can kill fragments but depth writes are disabled, do not make
   LRZ write-disable sticky for the whole render pass.  LRZ writes are already
   disabled for that draw, so the sticky state is redundant and only prevents
   later compatible depth-writing draws from using LRZ writes again.
   Pre-A8XX behavior is unchanged.

2) Clean the active Drnas hot path without changing the selected rendering
   policy:
   - fold the V57 Z/S load-store scan into the existing render-pass bandwidth
     scan and cache the result on tu_render_pass;
   - replace two repeated A810 policy/device checks with one cached tail-policy
     lookup;
   - cache TU_FRANE_EDGE once (environment options are process-static);
   - assert that the earlier KGSL/queue hang fixes, hot-cache ownership fixes,
     and removed stale experiment paths are still present/absent as intended.

No GMEM allocation, offsets, barriers, resolves, MSAA safety, shader scheduling,
CB policy, WSI, queue synchronization semantics, or V58 FS LRZ rule is changed.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V59 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V59 PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# Render-pass cleanup: V57 scanned every attachment again from autotune only
# to derive Z/S load-store pressure.  tu_render_pass_bandwidth_config() already
# walks the same attachments once, so fold the invariant there.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_pass.h",
    """   uint32_t gmem_bandwidth_per_pixel;
   uint32_t sysmem_bandwidth_per_pixel;

   unsigned num_views;
""",
    """   uint32_t gmem_bandwidth_per_pixel;
   uint32_t sysmem_bandwidth_per_pixel;

   /* V59: derived once beside bandwidth accounting instead of rescanning
    * attachments in the autotune hot path.
    */
   bool frane_zs_load_store;

   unsigned num_views;
""",
    "cache render-pass Z/S load-store pressure",
)

edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """static void
tu_render_pass_bandwidth_config(struct tu_render_pass *pass)
{
   pass->gmem_bandwidth_per_pixel = 0;
   pass->sysmem_bandwidth_per_pixel = 0;

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment *att = &pass->attachments[i];

      /* approximate tu_load_gmem_attachment */
      if (att->load)
         pass->gmem_bandwidth_per_pixel += att->cpp;

      /* approximate tu_store_gmem_attachment */
      if (att->store)
         pass->gmem_bandwidth_per_pixel += att->cpp;

      /* approximate tu_clear_sysmem_attachment */
      if (att->clear_mask)
         pass->sysmem_bandwidth_per_pixel += att->cpp;

      /* approximate tu6_emit_sysmem_resolves */
      if (att->will_be_resolved) {
         pass->sysmem_bandwidth_per_pixel +=
            att->cpp + att->cpp / att->samples;
      }
   }
}
""",
    """static void
tu_render_pass_bandwidth_config(struct tu_render_pass *pass)
{
   pass->gmem_bandwidth_per_pixel = 0;
   pass->sysmem_bandwidth_per_pixel = 0;
   pass->frane_zs_load_store = false;

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment *att = &pass->attachments[i];

      /* V59: this is exactly the V57 tail-pressure predicate, but evaluated
       * in the pass-construction scan we already have.
       */
      if (att->gmem &&
          (vk_format_has_depth(att->format) ||
           vk_format_has_stencil(att->format)) &&
          (att->load || att->store || att->load_stencil ||
           att->store_stencil))
         pass->frane_zs_load_store = true;

      /* approximate tu_load_gmem_attachment */
      if (att->load)
         pass->gmem_bandwidth_per_pixel += att->cpp;

      /* approximate tu_store_gmem_attachment */
      if (att->store)
         pass->gmem_bandwidth_per_pixel += att->cpp;

      /* approximate tu_clear_sysmem_attachment */
      if (att->clear_mask)
         pass->sysmem_bandwidth_per_pixel += att->cpp;

      /* approximate tu6_emit_sysmem_resolves */
      if (att->will_be_resolved) {
         pass->sysmem_bandwidth_per_pixel +=
            att->cpp + att->cpp / att->samples;
      }
   }
}
""",
    "fold duplicate Z/S scan into bandwidth scan",
)

# Dynamic inheritance does not know concrete load/store ops.  Make the cached
# field explicit rather than allowing a recycled dynamic-pass value.
edit(
    "src/freedreno/vulkan/tu_pass.cc",
    """tu_setup_dynamic_inheritance(struct tu_cmd_buffer *cmd_buffer,
                             const VkCommandBufferInheritanceRenderingInfo *info)
{
   struct tu_render_pass *pass = &cmd_buffer->dynamic_pass;
   struct tu_subpass *subpass = &cmd_buffer->dynamic_subpasses[0];
""",
    """tu_setup_dynamic_inheritance(struct tu_cmd_buffer *cmd_buffer,
                             const VkCommandBufferInheritanceRenderingInfo *info)
{
   struct tu_render_pass *pass = &cmd_buffer->dynamic_pass;
   struct tu_subpass *subpass = &cmd_buffer->dynamic_subpasses[0];

   /* No concrete attachment load/store ops are available for inheritance. */
   pass->frane_zs_load_store = false;
""",
    "reset cached Z/S pressure for dynamic inheritance",
)

# ---------------------------------------------------------------------------
# Autotune cleanup: one A810 check and one process-static option lookup instead
# of repeating device checks and reparsing TU_FRANE_EDGE on each decision.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static uint8_t
frane_a810_tail_edge_mode(const struct tu_device *device)
{
   if (!device || !device->physical_device)
      return 0;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   if (id != UINT64_C(0x44010000) &&
       id != UINT64_C(0xffff44010000))
      return 0;

   const int64_t mode =
      debug_get_num_option("TU_FRANE_EDGE", 1);
   return (uint8_t) std::clamp<int64_t>(mode, 0, 2);
}

static bool
frane_a810_tail_guard_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_TAIL", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}
""",
    """struct frane_a810_tail_runtime_policy {
   bool enabled = false;
   uint8_t edge_mode = 0;
};

static bool
frane_a810_tail_device(const struct tu_device *device)
{
   if (!device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static frane_a810_tail_runtime_policy
frane_a810_tail_policy(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_TAIL", true);
   static const uint8_t edge_mode = (uint8_t) std::clamp<int64_t>(
      debug_get_num_option("TU_FRANE_EDGE", 1), 0, 2);

   frane_a810_tail_runtime_policy out {};
   if (!enabled || !frane_a810_tail_device(device))
      return out;

   out.enabled = true;
   out.edge_mode = edge_mode;
   return out;
}
""",
    "collapse repeated A810 tail/edge policy lookup",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         runtime_input.tail_guard =
            frane_a810_tail_guard_enabled(device);
         runtime_input.tail_edge_mode =
            frane_a810_tail_edge_mode(device);

         for (uint32_t i = 0; i < pass->attachment_count; i++) {
            const struct tu_render_pass_attachment &att = pass->attachments[i];
            if (!att.gmem ||
                !(vk_format_has_depth(att.format) ||
                  vk_format_has_stencil(att.format)))
               continue;

            if (att.load || att.store || att.load_stencil || att.store_stencil) {
               runtime_input.zs_load_store = true;
               break;
            }
         }
""",
    """         const auto tail_policy = frane_a810_tail_policy(device);
         runtime_input.tail_guard = tail_policy.enabled;
         runtime_input.tail_edge_mode = tail_policy.edge_mode;
         runtime_input.zs_load_store = pass->frane_zs_load_store;
""",
    "remove duplicate per-decision attachment scan",
)

# ---------------------------------------------------------------------------
# LRZ step 2: if stencil may kill fragments but Z writes are off, the draw
# cannot write LRZ either.  On A8XX avoid making write-disable sticky for the
# whole render pass.  The existing stencil side-effect guard immediately below
# is untouched and can still temporarily disable LRZ testing for the draw.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """      if (frag_may_be_killed_by_stencil) {
         tu_lrz_disable_write_for_rp(cmd, "Stencil may kill fragments");
      }
""",
    """      if (frag_may_be_killed_by_stencil) {
         /* V59 A8XX LRZ-CLEAN:
          * With depth writes disabled, gras_lrz_cntl.lrz_write is already
          * false for this draw.  Do not make that write-disable sticky across
          * the render pass; later compatible depth-writing draws may resume
          * LRZ writes.  Keep the upstream conservative behavior everywhere
          * else.
          */
         if (CHIP < A8XX || z_write_enable)
            tu_lrz_disable_write_for_rp(cmd, "Stencil may kill fragments");
      }
""",
    "avoid redundant sticky LRZ write-disable on A8XX no-Z-write draws",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V58 / Mesa ",
    "Drnas Turnip V59 / Mesa ",
    "V59 display identity",
)

# ---------------------------------------------------------------------------
# End-to-end active-stack audit.  These are correctness/hang properties from
# earlier Drnas layers that V59 must not accidentally undo while cleaning.
# ---------------------------------------------------------------------------
autotune = (ROOT / "src/freedreno/vulkan/tu_autotune.cc").read_text()
pass_h = (ROOT / "src/freedreno/vulkan/tu_pass.h").read_text()
pass_cc = (ROOT / "src/freedreno/vulkan/tu_pass.cc").read_text()
lrz = (ROOT / "src/freedreno/vulkan/tu_lrz.cc").read_text()
cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
kgsl = (ROOT / "src/freedreno/vulkan/tu_knl_kgsl.cc").read_text()
queue = (ROOT / "src/freedreno/vulkan/tu_queue.cc").read_text()
device = (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

assert "frane_zs_load_store" in pass_h
assert "pass->frane_zs_load_store = false;" in pass_cc
assert "runtime_input.zs_load_store = pass->frane_zs_load_store;" in autotune
assert "frane_a810_tail_policy" in autotune
assert "frane_a810_tail_edge_mode" not in autotune
assert "frane_a810_tail_guard_enabled" not in autotune
assert autotune.count('debug_get_num_option("TU_FRANE_EDGE"') == 1
assert autotune.count('debug_get_bool_option("TU_FRANE_TAIL"') == 1

assert "V58 A810/A8XX LRZ-KEEP" in lrz
assert "(CHIP >= A8XX && !z_write_enable)" in lrz
assert "V59 A8XX LRZ-CLEAN" in lrz
assert "if (CHIP < A8XX || z_write_enable)" in lrz

# Known hang/correctness cleanups from 26.3.1+ must survive.
assert "FRANE_2631_POLL_READY" in kgsl
assert "frane_2631_deadline_ns" in kgsl
assert "for (uint32_t i = 0; sync = syncobjs[i], i < count; i++)" not in kgsl
assert "pthread_mutex_unlock(&device->submit_mutex);" in queue

# Hot-cache ownership and removed dead experimental paths stay clean.
assert "frane_2637_hot_pinned" in autotune
assert "compare_exchange_strong" in autotune
assert "decision_ticket.fetch_add" not in autotune
assert "rand_xorshift128plus(seed)" not in autotune
assert "frane_v29_neural" not in autotune
assert "TU_A810_26350_DEPTH_FRONTIER_MODE" not in autotune
assert "TU_A810_26349_GMEM_FRONTIER_MODE" not in autotune
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "same_lrz_signature" not in cmd

# Proven current defaults stay untouched.
assert 'TU_FRANE_EDGE", 1' in autotune
assert 'TU_FRANE_GMEM_TURBO", true' in autotune
assert 'TU_FRANE_DEPTH_DRAWS", 16' in autotune
assert 'TU_FRANE_DEPTH_MAX", 23' in autotune
assert "Drnas Turnip V59 / Mesa " in device

print("Drnas Turnip V59 LRZ-CLEAN applied and active stack audited", flush=True)
