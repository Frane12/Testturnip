#!/usr/bin/env python3
"""Port the Frane A830 V16 / A810 V15-Q patch stacks onto pinned Mesa main.

Fail-closed porting: exact source anchors are required, no blind offsets or
GPU geometry guesses. Keep Mesa main's new Vulkan system-budget helper rather
than reinstating the older Mesa 26.1.4 budget implementation.
"""
import ast
import sys
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"


def replace(path, old, new, label):
    p = ROOT / path
    src = p.read_text()
    hits = src.count(old)
    if hits != 1:
        raise RuntimeError(f"{label}: expected 1 source anchor, got {hits} at {p}: {old[:90]!r}")
    p.write_text(src.replace(old, new, 1))
    print(f"PASS {label}", flush=True)


class DropOldBudget(ast.NodeTransformer):
    """Only remove obsolete budget rewrites; implement them on Mesa main below."""
    def __init__(self):
        self.removed = 0

    def visit_Expr(self, node):
        v = node.value
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name)
            and v.func.id in ("edit", "replace_once") and len(v.args) >= 3
            and isinstance(v.args[0], ast.Constant)
            and v.args[0].value == "src/freedreno/vulkan/tu_device.cc"
            and isinstance(v.args[1], ast.Constant)):
            old = v.args[1].value
            if ("sys_available" in old or "heap_available" in old
                or "TU_A810_LEAN_BUDGET" in old or
                "const uint64_t fraction" in old):
                self.removed += 1
                return ast.copy_location(ast.Pass(), node)
        return self.generic_visit(node)


def run_legacy(name, skip_budget=False, upgrade_autotune_config=False):
    p = Path("patches") / name
    txt = p.read_text()
    if upgrade_autotune_config:
        old = "device->instance->autotune_algo"
        hits = txt.count(old)
        if hits != 4:
            raise RuntimeError(f"{name}: Mesa main autotune config port expected 4 refs, got {hits}")
        txt = txt.replace(old, "device->instance->drirc.perf.autotune_algo")
    tree = ast.parse(txt, filename=str(p))
    if skip_budget:
        remover = DropOldBudget()
        tree = remover.visit(tree)
        ast.fix_missing_locations(tree)
        if remover.removed != 1:
            raise RuntimeError(f"{name}: expected exactly one legacy budget edit, got {remover.removed}")
        print(f"PORT {name}: replaced obsolete 26.1.4 memory-budget edit with native Mesa main helper", flush=True)
    exec(compile(tree, str(p), "exec"), {"__name__": "__main__", "__file__": str(p)})


def main_budget(mode):
    # The newer upstream uses vk_physical_device_heap_budget_from_system:
    # vary ONLY its advisory available-RAM percentage, never real heap size.
    marker = "   const float percent = 0.9f;\n\n   return vk_physical_device_heap_budget_from_system("
    if mode == "a830":
        policy = """   /* Frane V15G/V15N, ported to the native Mesa-main budget helper.
    * Advisory percentages: A830 60% normally / 70% with lean disabled;
    * other A8xx 70%; every other GPU retains upstream 90%.
    */
   static const bool frane_lean_budget = []() {
      const char *env = os_get_option("TU_A830_LEAN_BUDGET");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t id = physical_device->dev_id.chip_id;
   const bool frane_a830 =
      id == 0x44050001ull || id == 0x44050000ull ||
      id == 0xffff44050000ull;
   const float percent = frane_a830 && frane_lean_budget ? 0.6f :
                         physical_device->info->chip >= A8XX ? 0.7f : 0.9f;

   return vk_physical_device_heap_budget_from_system("""
    else:
        policy = """   /* Frane V15Q: V15P keeps A810 budget experiment opt-in.
    * A830 policy stays as V15N; no physical heap size / usage changes.
    */
   static const bool frane_lean_budget = []() {
      const char *env = os_get_option("TU_A830_LEAN_BUDGET");
      return !env || strcmp(env, "0") != 0;
   }();
   static const bool frane_a810_lean_budget = []() {
      const char *env = os_get_option("TU_A810_LEAN_BUDGET");
      return env && strcmp(env, "1") == 0;
   }();
   const uint64_t id = physical_device->dev_id.chip_id;
   const bool frane_a830 =
      id == 0x44050001ull || id == 0x44050000ull ||
      id == 0xffff44050000ull;
   const bool frane_a810 =
      id == 0x44010000ull || id == 0xffff44010000ull;
   const float percent =
      (frane_a830 && frane_lean_budget) ||
      (frane_a810 && frane_a810_lean_budget) ? 0.6f :
      physical_device->info->chip >= A8XX ? 0.7f : 0.9f;

   return vk_physical_device_heap_budget_from_system("""
    replace("src/freedreno/vulkan/tu_device.cc", marker, policy, "Native upstream memory budget")


def common_v16_fixes():
    # Merge Mesa V16's correctness changes directly into the current source;
    # use strict text checks rather than outdated patch hunk line numbers.
    a = "src/freedreno/vulkan/tu_autotune.cc"
    replace(a, """   constexpr rp_history_handle &operator=(rp_history_handle &&other)
   {
      if (this != &other) {
         history = other.history;
         other.history = nullptr;
      }
      return *this;
   }""", """   rp_history_handle &operator=(rp_history_handle &&other);""", "V16 history move declaration")
    replace(a,
            "tu_autotune::rp_history_handle::~rp_history_handle()\n{",
            """tu_autotune::rp_history_handle &
tu_autotune::rp_history_handle::operator=(rp_history_handle &&other)
{
   if (this != &other) {
      rp_history_handle previous(std::move(*this));
      history = other.history;
      other.history = nullptr;
   }
   return *this;
}

tu_autotune::rp_history_handle::~rp_history_handle()
{""", "V16 release old history ref on move")
    replace(a, """   rp_history *existing = find_rp_history(key);
   if (existing)
      return *existing;""", """   rp_history_handle existing = find_rp_history(key);
   if (existing)
      return existing;""", "V16 history lookup owner")
    replace(a, "   rp_history &history = *find_or_create_rp_history(key);",
            """   rp_history_handle history_owner = find_or_create_rp_history(key);
   rp_history &history = *history_owner;""", "V16 retain history during use")
    replace("src/freedreno/vulkan/tu_suballoc.cc",
            """      tu_bo_finish(suballoc->dev, suballoc->bo);
      return VK_ERROR_OUT_OF_HOST_MEMORY;""",
            """      tu_bo_finish(suballoc->dev, suballoc->bo);
      suballoc->bo = NULL;
      suballoc->next_offset = 0;
      return result;""", "V16 BO mapping error cleanup")
    k = "src/freedreno/vulkan/tu_knl_kgsl.cc"
    replace(k, """               ret.state = KGSL_SYNCOBJ_STATE_FD;
               int sync_fd = kgsl_syncobj_ts_to_fd(sync);
               ret.fd = sync_merge_close("tu_sync", ret.fd, sync_fd, true);""",
            """               int ret_fd = kgsl_syncobj_ts_to_fd(&ret);
               int sync_fd = kgsl_syncobj_ts_to_fd(sync);
               ret.state = KGSL_SYNCOBJ_STATE_FD;
               ret.fd = sync_merge_close("tu_sync", ret_fd, sync_fd, true);""", "V16 KGSL TS+TS ownership")
    replace(k, """            ret.state = KGSL_SYNCOBJ_STATE_FD;
            int sync_fd = kgsl_syncobj_ts_to_fd(sync);
            ret.fd = sync_merge_close("tu_sync", ret.fd, sync_fd, true);""",
            """            int ret_fd = kgsl_syncobj_ts_to_fd(&ret);
            ret.state = KGSL_SYNCOBJ_STATE_FD;
            ret.fd = sync_merge_close("tu_sync", ret_fd, sync->fd, false);""", "V16 KGSL TS+FD ownership")


def a830_v16():
    a = "src/freedreno/vulkan/tu_autotune.cc"
    replace(a, """   static std::atomic<bool> allow_gmem { true };
   /* Tier 0: pause optional GMEM; 1: caution; 2: healthy memory.
    * Start at caution until the first real Android memory observation.
    */
   static std::atomic<uint32_t> memory_tier { 1 };""",
            """   static std::atomic<bool> allow_gmem { false };
   /* No optional GMEM before the first successful Android RAM sample. */
   static std::atomic<uint32_t> memory_tier { 0 };""", "V16 fail-closed GMEM startup")
    replace(a, """   rp_key key(0);
   if (key_opt)""",
            """   /* Avoid history/sampling BO allocation when optional GMEM is
    * ineligible. Explicit modes/profiling/preemption retain original path.
    */
   const bool lean_bandwidth = frane_a830_smart_gmem(device) &&
      config.is_enabled(algorithm::BANDWIDTH) &&
      !config.is_enabled(algorithm::PROFILED) &&
      !config.is_enabled(algorithm::PROFILED_IMM) &&
      !config.test(mod_flag::PREEMPT_OPTIMIZE) && !early_return_mode;
   if (lean_bandwidth && (rp_state->drawcall_count < 10 ||
                          frane_a830_gmem_pressure_tier() == 0))
      return default_mode;

   rp_key key(0);
   if (key_opt)""", "V16 skip ineligible A830 sampling")
    path = "src/freedreno/vulkan/tu_suballoc.cc"
    replace(path, """      strcmp(suballoc->name, "autotune_suballoc") == 0 &&
      bo->bo->size > 64 * 1024;""",
            """      (strcmp(suballoc->name, "autotune_suballoc") == 0 ||
       strcmp(suballoc->name, "pipeline_suballoc") == 0) &&
      bo->bo->size > suballoc->default_size;""", "V16 bounded idle cache")
    replace("src/freedreno/vulkan/tu_device.cc",
            '"Mesa " PACKAGE_VERSION MESA_GIT_SHA1);',
            '"Frane V16 A830 UPSTREAM / Mesa " PACKAGE_VERSION MESA_GIT_SHA1);',
            "V16 A830 driver identity")


def a810_identity():
    replace("src/freedreno/vulkan/tu_device.cc",
            '"Mesa " PACKAGE_VERSION MESA_GIT_SHA1);',
            '"Frane V15Q A810 UPSTREAM / Mesa " PACKAGE_VERSION MESA_GIT_SHA1);',
            "V15Q A810 driver identity")


def main():
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in ("a830", "a810"):
        raise SystemExit("Usage: port_upstream_main.py a830|a810")
    run_legacy("v15d_gralloc_ubwc.py")
    run_legacy("v15g_budget70_leanpools.py", skip_budget=True)
    run_legacy("v15j_a830_smart_gmem.py", upgrade_autotune_config=True)
    run_legacy("v15k_a830_smart_stats.py")
    run_legacy("v15l_a830_q8428_guard.py")
    run_legacy("v15n_a830_lean_memory.py", skip_budget=True)
    if mode == "a810":
        run_legacy("v15o_a810_smart_gmem_lean.py", skip_budget=True)
        run_legacy("v15p_a810_render_recovery.py", skip_budget=True)
        run_legacy("v15q_a810_bounded_gmem.py")
    main_budget(mode)
    common_v16_fixes()
    if mode == "a830":
        a830_v16()
    else:
        a810_identity()
    print(f"ALL PATCHES PORTED: {mode}", flush=True)


if __name__ == "__main__":
    main()
