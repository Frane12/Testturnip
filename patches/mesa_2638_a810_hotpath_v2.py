#!/usr/bin/env python3
"""Frane Mesa 26.3.8 A810 HOTPATH-V2 EXP.

Layered on the proven 26.3.7 core-fastpath build.

This experiment keeps shader/pipeline, GMEM/SYSMEM policy, synchronization,
WSI and rendering decisions unchanged. It only removes bookkeeping overhead
from histories which 26.3.7 already pins for the lifetime of tu_autotune.

Changes:
  * enlarge the no-replacement A810 hot render-pass cache from 16 to 64 slots;
  * add a borrowed rp_history_handle mode for permanently pinned histories;
  * on a verified hot-cache hit, skip per-use refcount inc/dec and timestamp;
  * preserve normal owning/refcounted handles for every fallback path.
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
            f"26.3.8 HOTPATH-V2 source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.8 HOTPATH-V2 PASS {label}", flush=True)


def replace_count(rel, old, new, expected, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != expected:
        raise SystemExit(
            f"26.3.8 HOTPATH-V2 source drift: {label}: "
            f"expected {expected} anchors, saw {n}: {old!r}"
        )
    p.write_text(s.replace(old, new))
    print(f"26.3.8 HOTPATH-V2 PASS {label} ({n})", flush=True)


# 64 entries are still tiny, but materially reduce direct-map collisions
# between startup/menu and gameplay render passes. Entries remain one-shot,
# no-replacement and permanently pinned exactly like 26.3.7.
edit(
    "src/freedreno/vulkan/tu_autotune.h",
    """   static constexpr uint32_t FRANE_2637_HOT_RP_SLOTS = 16;
   static_assert((FRANE_2637_HOT_RP_SLOTS &
                  (FRANE_2637_HOT_RP_SLOTS - 1u)) == 0u);""",
    """   static constexpr uint32_t FRANE_2638_HOT_RP_SLOTS = 64;
   static_assert((FRANE_2638_HOT_RP_SLOTS &
                  (FRANE_2638_HOT_RP_SLOTS - 1u)) == 0u);""",
    "grow hot-RP cache to 64 slots",
)
replace_count(
    "src/freedreno/vulkan/tu_autotune.h",
    "FRANE_2637_HOT_RP_SLOTS",
    "FRANE_2638_HOT_RP_SLOTS",
    1,
    "rename hot-RP array extent",
)
replace_count(
    "src/freedreno/vulkan/tu_autotune.cc",
    "FRANE_2637_HOT_RP_SLOTS",
    "FRANE_2638_HOT_RP_SLOTS",
    1,
    "use 64-slot mask in lookup",
)


# rp_history_handle normally owns one temporary ref. A 26.3.7 hot-cache
# history already owns a permanent pin, therefore a hot hit can safely borrow
# that lifetime without touching the atomic refcount or last-use timestamp.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """struct tu_autotune::rp_history_handle {
   rp_history *history;

   /* Note: Must be called with rp_mutex held. */
   rp_history_handle(rp_history &history);

   constexpr rp_history_handle(std::nullptr_t): history(nullptr)
   {
   }

   rp_history_handle(const rp_history_handle &) = delete;
   rp_history_handle &operator=(const rp_history_handle &) = delete;

   constexpr rp_history_handle(rp_history_handle &&other): history(other.history)
   {
      other.history = nullptr;
   }

   rp_history_handle &operator=(rp_history_handle &&other);""",
    """struct tu_autotune::rp_history_handle {
   rp_history *history;
   bool owns_ref;

   /* Owning handle: caller follows Mesa's normal rp_mutex/refcount path. */
   rp_history_handle(rp_history &history);

   /* 26.3.8 borrowed handle: legal only after the permanent hot-cache pin
    * has been release-published through the matching slot hash. */
   rp_history_handle(rp_history &history, bool owns_ref);

   constexpr rp_history_handle(std::nullptr_t): history(nullptr), owns_ref(false)
   {
   }

   rp_history_handle(const rp_history_handle &) = delete;
   rp_history_handle &operator=(const rp_history_handle &) = delete;

   constexpr rp_history_handle(rp_history_handle &&other)
       : history(other.history), owns_ref(other.owns_ref)
   {
      other.history = nullptr;
      other.owns_ref = false;
   }

   rp_history_handle &operator=(rp_history_handle &&other);""",
    "teach V16 history handle owning vs borrowed lifetime",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """tu_autotune::rp_history_handle &
tu_autotune::rp_history_handle::operator=(rp_history_handle &&other)
{
   if (this != &other) {
      rp_history_handle previous(std::move(*this));
      history = other.history;
      other.history = nullptr;
   }
   return *this;
}""",
    """tu_autotune::rp_history_handle &
tu_autotune::rp_history_handle::operator=(rp_history_handle &&other)
{
   if (this != &other) {
      rp_history_handle previous(std::move(*this));
      history = other.history;
      owns_ref = other.owns_ref;
      other.history = nullptr;
      other.owns_ref = false;
   }
   return *this;
}""",
    "preserve V16 move-assignment ownership with borrowed handles",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """tu_autotune::rp_history_handle::~rp_history_handle()
{
   if (!history)
      return;

   if (!history->frane_2637_hot_pinned.load(std::memory_order_acquire))
      history->last_use_ts.store(os_time_get_nano(), std::memory_order_relaxed);
   ASSERTED uint32_t old_refcount =
      history->refcount.fetch_sub(1, std::memory_order_relaxed);
   assert(old_refcount != 0); /* Underflow check. */
}

tu_autotune::rp_history_handle::rp_history_handle(rp_history &history): history(&history)
{
   history.refcount.fetch_add(1, std::memory_order_relaxed);
}""",
    """tu_autotune::rp_history_handle::~rp_history_handle()
{
   if (!history || !owns_ref)
      return;

   if (!history->frane_2637_hot_pinned.load(std::memory_order_acquire))
      history->last_use_ts.store(os_time_get_nano(), std::memory_order_relaxed);
   ASSERTED uint32_t old_refcount =
      history->refcount.fetch_sub(1, std::memory_order_relaxed);
   assert(old_refcount != 0); /* Underflow check. */
}

tu_autotune::rp_history_handle::rp_history_handle(rp_history &history)
    : rp_history_handle(history, true)
{
}

tu_autotune::rp_history_handle::rp_history_handle(rp_history &history,
                                                   bool owns_ref)
    : history(&history), owns_ref(owns_ref)
{
   if (!owns_ref) {
      /* Hash publication in the hot slot is release-ordered after pinning,
       * while the hit path acquires that hash. A borrowed handle therefore
       * cannot observe an unpinned history. */
      assert(history.frane_2637_hot_pinned.load(std::memory_order_acquire));
      return;
   }

   history.refcount.fetch_add(1, std::memory_order_relaxed);
}""",
    "remove refcount and clock traffic from borrowed hot handles",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      if (cached &&
          hot_slot->hash.load(std::memory_order_acquire) == key.hash)
         return rp_history_handle(*cached);""",
    """      if (cached &&
          hot_slot->hash.load(std::memory_order_acquire) == key.hash)
         return rp_history_handle(*cached, false);""",
    "borrow permanently pinned history on hot hit",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.7 A810 CORE-FASTPATH EXP / Mesa ",
    "Frane Mesa 26.3.8 A810 HOTPATH-V2 EXP / Mesa ",
    "experimental driver identity",
)

# Hard guards: this layer is not allowed to perturb the already successful
# shader/pipeline path, GMEM runtime decision logic, WSI or sync work.
combined = "\n".join(
    (V / name).read_text()
    for name in (
        "tu_pipeline.cc",
        "tu_shader.cc",
        "tu_autotune.cc",
        "tu_device.cc",
        "tu_cmd_buffer.cc",
        "tu_wsi.cc",
    )
)
for needle in (
    "FRANE_2635_STAGE_NIR_MAX_ENTRIES",
    "frane_2635_record_stage_probe",
    "frane_2634_decide_gmem_runtime",
    "frane_2633_profile_interval",
    "V28-CLEAN: no driver present-mode override",
    "TU_A810_2637_CORE_FASTPATH",
):
    if needle not in combined:
        raise SystemExit(f"26.3.8 prerequisite missing: {needle}")

src = (V / "tu_autotune.cc").read_text()
hdr = (V / "tu_autotune.h").read_text()
find_start = src.index("tu_autotune::find_rp_history")
find_end = src.index("tu_autotune::find_or_create_rp_history", find_start)
find_body = src[find_start:find_end]

assert "FRANE_2638_HOT_RP_SLOTS" in hdr
assert "FRANE_2637_HOT_RP_SLOTS" not in hdr
assert "rp_history_handle(*cached, false)" in find_body
assert "history.frane_2637_hot_pinned.load" in src
assert "if (!history || !owns_ref)" in src

# Publication safety inherited from 26.3.7 must remain: permanent ref is taken
# before pointer publication, pin bit is visible before hash publication.
pub = src[src.index("tu_autotune::find_rp_history"):src.index(
    "tu_autotune::find_or_create_rp_history")]
assert pub.index("refcount.fetch_add(1") < pub.index("compare_exchange_strong")
assert pub.index("frane_2637_hot_pinned.store") < pub.index("hot_slot->hash.store")

print("Frane Mesa 26.3.8 A810 HOTPATH-V2 EXP applied", flush=True)
