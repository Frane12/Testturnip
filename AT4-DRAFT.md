A810 AT4 S1Guard — experimental draft

Pinned Mesa: eda9aceb39d5ff169b096444abe366bdf2269e24 (26.3.0-devel).
Baseline: AT3 CollisionFix 306f6c8317bc42568d8abbf8d9d96eddfd772823.
Android ARM64 KGSL, NDK r29, minimum API 34. Installable ZIP contains only meta.json and libvulkan_freedreno.so.

AT4 preserves the completed S1 Smart/Turbo/Tail choice outside sparse context probes until its own learner has at least eight samples per mode, confidence >= 6, low volatility and fresh paired data. It separates bounded draw-count and submitted-geometry classes, indirect/geometry-shader workloads, render area, subpass/view count, average draw bandwidth and the allocator's actual tile grid. Secondary and suspended passes merge geometry counters with saturation. Contextual control respects the existing layout policy and GMEM safety gate. No new register, barrier, shader or allocation tuning beyond AT3.

Use plain PROFILED. AT4 is enabled by default on exact A810 chip IDs only. TU_FRANE_AT4=0 restores the AT3 selector and legacy RP key/cache namespace for comparisons. TU_FRANE_AT4_TRACE=1 logs final decisions, eligibility, measurements and accepted contextual samples; its counters describe recorded choices and completed timestamps, not submitted FPS. Untagged/ineligible samples are not counted as contextual learning. Learned state is not exported in the old probability cache; the AT4 prefix prevents reuse of AT3 priors.

Validation: sanitizer tests extract the real selector and RP-key constructor from patched source. They check legacy-selector parity, cold S1 preservation, paired confidence, finite exploration, stale renewal, drift reset, tag eviction and workload separation. CI cross-compiles the entire driver and checks AArch64 ELF, Android HAL HMI export, package metadata and absence of a shared C++ runtime dependency.

There is no physical A810 GPU in the build environment. Device loading, Vulkan CTS, runtime crash/pagefault freedom and FPS are not established by these host tests. Other Turnip implementations informed the audit; their different hardware cache/tile settings were not copied without A810 evidence. Keep this release draft until device testing.
