# Frane Turnip V25 A810 POWER PERF — experimental, NOT clock-unlock

**Base:** V24 A810 Lean Hotpath including V23 WSI, V22 Lean Profiled,
V18 sampled-depth and DiskDVD A810 descriptor-prefetch workaround.
Mesa 26.2.3, pinned source
`31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.
Those reference branches are unchanged.

## Qualcomm ZIP audit (supplied by Frane)

Inspected these original binary ZIPs and their Vulkan library:
- `qcom-842.19.zip`: `vulkan.adreno.so`, 4,393,376 bytes,
  SHA256 `338e23a9839c0227036e9ae7993f3dd74f56c1277300ff0a9917b937bdaf2226`.
- `adreno-driver-842.8.zip`: `vulkan.adreno.so`, 4,669,976 bytes,
  SHA256 `aa2f92b1815e348e486a83ca343197d43f05e8dd970d24d4eb593256a3d1ec7c`.
- `8eGen5-842.6.zip`: `vulkan.adreno.so`, 4,652,816 bytes,
  SHA256 `8cbefaf1d3a68cb5320f27f847cd4761cad43b71fb37918c8092f36f002ba3ea`.

These contain **proprietary compiled Adreno code**, not C/C++ source or a
verified A810 MMIO register dump. Visible diagnostic strings include
`GmemSize`, `UBWC`, `OsGslSetPwrctrl`, but do NOT identify safe
A810-specific register offsets or values. Do not invent/port guessed
register writes. No Qualcomm library is repackaged in this driver.

## V25 verified-source changes

- Port the **KGSL PWR_MAX constraint request** pattern from
  WinNative-Emu/Drivers `patches/apply_perf_variant.py`, adapting it
  strictly to A810 chip IDs and Mesa 26.2.3's `msm_kgsl.h`.
  `KGSL_CONTEXT_PWR_CONSTRAINT` is set only on opted-in A810 queues.
  If the flagged context creation fails, retry Mesa's original flags;
  if `KGSL_PROP_PWR_CONSTRAINT` fails, silently revert to ordinary
  GPU management after a warning. Never disable kernel/Android thermal
  governor or use `KGSL_PROP_PWRCTRL`.
- Request `KGSL_CONSTRAINT_PWR_MAX` at queue creation and re-request
  it every 256 successful graphics submissions. A simple bit-mask
  schedules reasserts without a per-frame timer or extra GPU wait.
  Track power status per actual Vulkan queue to avoid affecting other
  chips/queues if the ioctl fails.
- V22's sampling interval changes from 4 to 8 **only for already
  confident (>=95%) preferred render-pass histories**. The warm-up,
  under-confident histories, losing-mode probes and original
  DiskDVD code stay unchanged. This trades slower adjustment to scene
  changes for fewer optional GPU timestamps and result allocations.
- Retain V24 CPU shortcuts and the original safety/ordering code.

## A/B controls (restart game after changing environment)

| Environment | Effect |
| --- | --- |
| `TU_A810_PWR_MAX` unset or `1` | Ask kernel for high GPU clocks on A810 (not guaranteed) |
| `TU_A810_PWR_MAX=0` | Original V24 power policy |
| `TU_A810_PROFILED_SAMPLE_INTERVAL` unset | V25: 8 at high confidence |
| `TU_A810_PROFILED_SAMPLE_INTERVAL=4` | V24 original sampling |
| `TU_A810_PROFILED_SAMPLE_INTERVAL=1` | Full profiling / no 1/N skip |
| `TU_A810_V24_FASTPATH=0` | Disable V24 CPU shortcuts |
| `TU_FRANE_PRESENT_MODE=off` | Disable experimental V23 WSI override |

Suggested controls: V24 baseline, then V25 power-off/interval-4,
V25 power-on/interval-4, V25 power-on/interval-8. Keep resolution,
DXVK Sarek 1.10.8, FEX 2609, graphics settings, cooler and affinity
identical. Log uncapped FPS/frametimes after warm-up and device temperature.
Cap again for normal play.

## Limitations

Asking for maximum clocks does not change thermal, voltage, firmware or
hardware ceilings. Power use and device temperatures can increase;
at thermal throttling, performance can fall. GPU-bound scenes could
benefit, CPU-bound scenes probably won't. No FPS increase is established
until Frane's on-device A/B tests. The A810 POWER path is not designed for
A830 and no shared registers or geometry have been transplanted.

CI compiles the complete Android AArch64 KGSL driver and verifies the
resulting AdrenoTools ZIP. It compares IR3 workaround and WSI sources with
V24, checks shader/codegen and cache/barrier code untouched, runs
existing V22/V23/V24 unit tests and the V25 A810/256-submission test.
