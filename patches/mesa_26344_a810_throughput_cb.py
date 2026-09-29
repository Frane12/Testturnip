#!/usr/bin/env python3
"""Drnas Turnip V44 THROUGHPUT-CB.

Layered on V42/V39.  This experiment turns on Turnip's existing A7XX+ concurrent
binning machinery selectively on A810 instead of leaving it globally disabled
by Mesa's desktop-oriented default.

The goal is throughput, not command-recording micro-optimization: overlap BV
(binning/visibility) work with BR rendering on sufficiently heavy renderpasses
while keeping all of Turnip's existing dynamic CB disable/synchronization logic.

Safety:
  * A810 only for the custom override;
  * TU_DEBUG=nocb still wins and disables the experiment;
  * explicit Mesa/DRI concurrent-binning enable still behaves exactly as before;
  * A810 override only starts CB for renderpasses with at least N draws
    (default 8) to avoid paying CB setup overhead on tiny passes;
  * all existing LRZ, partial-fast-clear, query, barrier and overflow CB disable
    paths remain intact.

A/B:
  TU_A810_26344_SMART_CB=0
restores V42's default concurrent-binning policy.

Tuning:
  TU_A810_26344_CB_MIN_DRAWS=8
default threshold.  Lower values are more aggressive.
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
            f"V44 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V44 PASS {label}", flush=True)


anchor = r'''/* "Normal" cache flushes outside the renderpass, that don't require any special handling */
template <chip CHIP>
void
tu_emit_cache_flush(struct tu_cmd_buffer *cmd_buffer)
'''

helpers = r'''/* V44: A810 throughput experiment.
 *
 * Mesa leaves concurrent binning disabled by default because broad enablement
 * regresses some desktop workloads.  A810 gets a narrow override which keeps
 * every existing correctness/dynamic-disable path, but avoids enabling CB for
 * tiny renderpasses where setup overhead is unlikely to amortize.
 */
static inline bool
frane_26344_is_a810(const struct tu_cmd_buffer *cmd)
{
   if (!cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == UINT64_C(0x44010000) ||
          chip == UINT64_C(0xffff44010000);
}

static inline bool
frane_26344_a810_cb_override(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26344_SMART_CB", true);

   /* An explicit nocb request must remain authoritative. */
   return enabled &&
          !TU_DEBUG(NO_CONCURRENT_BINNING) &&
          frane_26344_is_a810(cmd);
}

static inline bool
frane_26344_cb_capable(const struct tu_cmd_buffer *cmd)
{
   return cmd->device->instance->drirc.perf.allow_concurrent_binning ||
          frane_26344_a810_cb_override(cmd);
}

static inline bool
frane_26344_cb_policy_allows(const struct tu_cmd_buffer *cmd)
{
   /* Preserve Mesa's explicit/DRI enable exactly, including force-CB. */
   if (cmd->device->instance->drirc.perf.allow_concurrent_binning)
      return true;

   if (!frane_26344_a810_cb_override(cmd))
      return false;

   static const unsigned min_draws =
      MAX2(1, debug_get_num_option("TU_A810_26344_CB_MIN_DRAWS", 8));

   return cmd->state.rp.drawcall_count >= min_draws;
}

/* "Normal" cache flushes outside the renderpass, that don't require any special handling */
template <chip CHIP>
void
tu_emit_cache_flush(struct tu_cmd_buffer *cmd_buffer)
'''

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    helpers,
    "add A810 smart concurrent-binning policy",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if ((flushes & TU_CMD_FLAG_WAIT_FOR_BR) && CHIP >= A7XX &&
       !(cmd_buffer->state.pass && cmd_buffer->state.renderpass_cb_disabled) &&
       cmd_buffer->device->instance->drirc.perf.allow_concurrent_binning) {
""",
    """   if ((flushes & TU_CMD_FLAG_WAIT_FOR_BR) && CHIP >= A7XX &&
       !(cmd_buffer->state.pass && cmd_buffer->state.renderpass_cb_disabled) &&
       frane_26344_cb_capable(cmd_buffer)) {
""",
    "enable CB barrier plumbing for A810 override",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """       tu7_cb_disable_reason(!cmd->device->instance->drirc.perf.allow_concurrent_binning, cmd,
                             "globally disabled")) {
""",
    """       tu7_cb_disable_reason(!frane_26344_cb_policy_allows(cmd), cmd,
                             "globally disabled / A810 pass too small")) {
""",
    "gate CB start by A810 heavy-pass policy",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V42 / Mesa ",
    "Drnas Turnip V44 / Mesa ",
    "V44 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
dev = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()

for needle in (
    "TU_A810_26344_SMART_CB",
    "TU_A810_26344_CB_MIN_DRAWS",
    "frane_26344_is_a810",
    "frane_26344_cb_capable",
    "frane_26344_cb_policy_allows",
    "TU_DEBUG(NO_CONCURRENT_BINNING)",
    "globally disabled / A810 pass too small",
):
    assert needle in cmd, needle

# Existing Turnip CB synchronization and dynamic-disable machinery must remain.
for needle in (
    "TU_ONCHIP_CB_RESLIST_OVERFLOW",
    "PIPE_BV_WAIT_FOR_BR",
    "PIPE_BR_WAIT_FOR_BV",
    "TU_PREDICATE_CB_ENABLED",
    "tu_add_cb_barrier_info",
    "partial LRZ fast clear",
):
    assert needle in cmd, needle

# Keep the proven rendering baseline and V42 draw-cache work.
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert "frane_26342_initiator_dynamic_dirty" in cmd
assert "frane_26342_bandwidth_dynamic_dirty" in cmd
assert "Drnas Turnip V44 / Mesa " in dev

print("Drnas Turnip V44 THROUGHPUT-CB applied", flush=True)
