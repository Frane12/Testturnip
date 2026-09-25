# Frane DXVK 3.1.1 A810 compatibility experiment

This is an **experimental source patch** for upstream `doitsujin/dxvk` tag `v3.1.1`, targeting Frane Turnip V25 on Adreno A810.

It is NOT a compiled DXVK DLL/WCP or proof of compatibility. It is NOT an ARM64-specific compiler port. Apply it to the exact source version of the DXVK build installed in Wine; an unofficial ARM64/ARM64EC fork may differ.

## Changes
* Opt-in only with `DXVK_A810_COMPAT=1` and only on `VK_DRIVER_ID_MESA_TURNIP`.
* Disable only OPTIONAL Vulkan paths that may interact badly with mobile driver and compositor: graphics pipeline library, descriptor buffer, unified image layouts, present-id and present-wait (v1/v2).
* Log the Vulkan API version, driver name, push constant limit, and **all** missing mandatory features, instead of exposing only the first unsupported feature.
* It does NOT fake VK_KHR_maintenance5/6, VK_EXT_robustness2, or Vulkan 1.4 capabilities. If the driver does not implement a required feature, correct implementation or a different DXVK version is necessary.

## Source
Upstream: https://github.com/doitsujin/dxvk/tree/v3.1.1

```sh
git checkout v3.1.1
git apply --check frane-dxvk-3.1.1-a810-compat.patch
git apply frane-dxvk-3.1.1-a810-compat.patch
```

For a Winlator custom ARM64 DXVK package, the build chain depends on whether the DLLs are x86/x64, ARM64 or ARM64EC. This patch alone does not produce an installable package.

## Test
In a separate Winlator/Bannerlator container using V25 and FEX 2609:

```ini
DXVK_A810_COMPAT=1
DXVK_LOG_LEVEL=debug
DXVK_HUD=version,devinfo,fps
TU_AUTOTUNE_ALGO=profiled
```

Record `*_d3d11.log` and `*_dxgi.log` from the executable working directory (or set `DXVK_LOG_PATH` to a writable directory).
Compare identical runs with and without `DXVK_A810_COMPAT=1`. If you see `Device does not support required feature`, that cannot safely be fixed by making the check return true.

The V25 driver branch remains unchanged. Keep the known-good Sarek DXVK 1.10.8 available for rollback.
