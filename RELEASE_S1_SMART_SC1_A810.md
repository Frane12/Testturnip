## A810 S1 Smart SC1 — internal experiment

Base: A810 S1 Smart DS2, repository commit 8f600489302c103b35bf378d2b29a73b23652032. Mesa source is pinned to eda9aceb39d5ff169b096444abe366bdf2269e24. Existing Smart 2 and DS2 patches are applied before the SC1 delta.

Changes:

- A810 opts into 128 cache-local direct slots for fully formed shader objects. Lookups check complete key bytes, key length and object type. Slots borrow existing strong cache ownership: no shader pinning, additional shader copies or added worker threads. Collision replacement is safe while the source cache exists. Weak caches, raw blobs and disabled caches stay on the original path. Allocation failure disables the optional lookup acceleration.
- Ordinary graphics groups and compute shaders coordinate cold compilation by exact existing Mesa BLAKE3 identity, cache identity and pipeline domain. A completed cache lookup takes the normal path. A cold claim rechecks only the in-memory cache, avoiding duplicate disk reads. Different-key collisions use the original independent path. Capture-internal-representation requests and graphics retained-NIR requests keep the original path. FAIL_ON_PIPELINE_COMPILE_REQUIRED never waits for compilation. Guards release on successful publication and on error paths.
- Supplemental adaptive watch measurements are limited to four per one-time command-buffer batch. Every scheduled GMEM/SYSMEM pair remains eligible, including cold training and change-driven pairs. This budget changes timestamp allocation only; DS2 render-mode selection, load banks and native correctness guards remain intact.

Enabled by default. TU_FRANE_SC=0 restores the DS2 cache/compilation/watch behavior for A/B comparison. HUD device name remains Turnip-Drnas A810.

Validation covers the actual shared coordination helper with concurrent identical requests, exact-key collisions, different cache/domain identity, reentrant fallback and failure wakeup; extracted Mesa hot-cache and memory-only functions with full-key/type/size isolation, replacement, refcount balance and concurrent lookups; adaptive pair preservation; DS2 regression tests; clean patch application; and a real Android ARM64 compile/link/package verification. Model and host tests establish these invariants, not on-device rendering correctness or performance.

FPS, frame-time and power changes require device testing. Compare complete Crysis runs (three passes), Dirt 3 (two or three runs), and longer gameplay at the same settings and temperature. DXVK 1.9.4 remains the reference; Sarek 1.10.5 async is a separate intentional comparison.

Design inspiration: newer DXVK-Sarek cache lookup and queued-compilation coordination, https://github.com/pythonlover02/dxvk-sarek. SC1 uses existing Mesa identities and ownership rules. Mesa and DXVK-Sarek remain credited for their upstream work. This is a downstream internal draft and is not submitted to Mesa upstream.
