# A810 S1.2 Zelda X1

Internal experimental Switch/Zelda draft, based on the exact A810 S1.2 source at `5bd2bad98fe3b499ac0bff11c23416ce6d8454cf`, pinned Mesa `eda9aceb39d5ff169b096444abe366bdf2269e24`. The reference S1.2 driver ZIP has SHA256 `37cf245fd915e172504abdcb50d0f5ce8d82944ae5e41b4540352e7a68e1df8e`.

The target is Vulkan rendering in Switch emulators, with Breath of the Wild and Tears of the Kingdom as intended test workloads. This is a driver policy experiment, not a game-specific fix or a measured Zelda FPS improvement. No title-ID detection is used. The exact emulator and Zelda title have not been specified or tested on a device.

## Changes

- Render-history keys on A810 include the actual render area, offsets, subpass count and a bounded draw-count band. A short effect, a cropped pass and a heavier scene using the same attachment identities no longer share the same key solely because framebuffer dimensions match. Existing image identity, view offset and load/store fields remain in the key. Zero-to-four draws use exact bands; larger counts use 5–15, 16–63, 64–255 and 256+ bands. The common key stays on the stack; no second lookup or new lock is added.
- Selected two-to-four-draw depth/MRT passes can enter the existing profiled Smart path. Admission requires a one-time command buffer, plain PROFILED mode, enabled A810 safety, full-frame single-layer single-subpass rendering, at least 262144 pixels, one-to-sixteen actual tiles and estimated attachment transfer bytes no greater than resident attachment bytes. Single-color postprocessing, zero/one-draw passes and rejected layouts keep the prior small-pass policy. This gate admits measurement; it does not force GMEM.
- The existing fresh-pair learning, costly-loser probe budget, scene reversal, exact S1.2 GMEM planning cache and final A810 safety admission remain active. No new workers, pipeline-cache format changes, barrier removal, shader precision reduction or synchronization changes are introduced.

The thresholds are conservative experimental choices, not calibrated Zelda measurements. Area and draw-band partitioning can create more histories and require additional warm-up. Short depth/MRT passes may still prefer SYSMEM, and measurement can cost more than it saves. GPU timings decide the learned preference.

## Defaults and rollback

Install the driver ZIP through the emulator's custom GPU-driver importer. Android API 34+ / ARM64 KGSL, matching S1.2. The Switch layer is ON by default and A810-only; no environment variables are required. `TU_FRANE_PROFILE_ID` is not required.

- `TU_FRANE_SWITCH=0`: disable both Switch policy changes and restore S1.2 policy/key behavior. Restart the emulator process after changing it.
- `TU_FRANE_SMART=0`: inherited Smart-layer control; this does not disable the Switch area-key partition.
- `TU_FRANE_GMEM_PLAN=0`: inherited S1.2 planning-cache comparison.

If the emulator does not expose driver environment variables, compare by importing the original S1.2 ZIP instead. Explicit autotune algorithm choices remain authoritative. The Switch additions do not make Winlator/DXVK benchmark results predictive for Zelda.

## Validation

Local ASan/UBSan checks passed: 42240 Switch gate boundary cases, render-area/offset/subpass/draw-band separation, inherited Smart cadence and fresh-pair checks, eighteen loss-budget boundary cases, 256 reversal simulations, 28000 actual C++ allocator equivalence cases, 140000 exact threshold checks and four independent allocator-cache threads.

CI repeats the inherited suites and Switch tests, applies both patches to pristine pinned Mesa, compiles a real Android ARM64 driver using NDK r29, checks ELF/ZIP/identity and creates only this DRAFT release. Source ZIP includes both patches and test logs. Build success is separate from on-device validation. Vulkan CTS, Android stress and Zelda gameplay have not been run.

Compare the same emulator/version, game/version, save, resolution, accuracy settings and shader cache with S1.2. Warm both drivers, then run the same route at least three times and inspect graphics, crashes, sustained FPS/frametime, RAM and temperature. Test longer outdoor traversal and a separate indoor scene. Report BOTW and TOTK separately.

Source references reviewed: Mesa Freedreno autotune documentation (`https://docs.mesa3d.org/drivers/freedreno.html`) and archived yuzu Vulkan scheduler (`https://github.com/JamesDoesGaming/yuzu/blob/master/src/video_core/renderer_vulkan/vk_scheduler.cpp`). The archived scheduler uses render-pass boundaries and one-time command buffers; this is not evidence about every current fork.

AI-generated experimental implementation provenance: Generated-by: LLM; biblioklept.
