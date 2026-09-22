# Frane Turnip V16 A830 LIFETIME RC1

Target: Adreno 830, especially Frane's 8 GB device / Winlator. Experimental
candidate, not a claim of fastest driver, zero leaks, or a proven GMEM fault fix.

## Reproducible base

- Frane V15N: e86b36182abf67da6e74d4d1c6717bff01d0f681, branch
  mesa-26.1.4-v15n-a830-lean-memory. V15L remains the field-tested comparison.
- Mesa 26.1.4: 6dfbc555b4128ee51139c5f78c5aba2594c9701b.
- Apply V15D/G/J/K/L/N scripts in that order, then v16_a830_lifetime.patch.
- Build with the checked-in V16 workflow: NDK r29, API 34, KGSL, ARM64.
- Artifact contains the exact patch-repository SHA, full applied Mesa delta,
  Mesa SHA, binary SHA256, and the AdrenoTools ZIP.

## Changes and evidence

1. **History ownership:** retain the lookup handle instead of converting a
   temporary owner to a raw pointer. Keep a named owner through render-mode
   selection and entry attachment. The old temporary drops its reference before
   the raw pointer is used, allowing concurrent history reaping (when the map
   exceeds its retention threshold). Move assignment also releases the previous
   reference instead of leaking its refcount. This latter path is defensive;
   no active leaking call site was established.
2. **KGSL synchronization:** when combining timestamps from different queues,
   export both timestamps before changing the accumulated state to FD. When
   combining a timestamp with an FD, export the timestamp, borrow the input FD,
   and close only owned temporary descriptors. The baseline instead used an
   invalid ret.fd or attempted to export an FD as a timestamp.
3. **Allocation failure:** after a BO mapping failure, clear the allocator's
   freed current BO pointer and offset, and propagate the actual error. This
   prevents reuse/double-release on retry or destruction during memory pressure.
4. **Less unnecessary sampling:** in the A830 bandwidth policy, skip new history
   and sample allocation for 5-9-draw passes or tier-0 memory pressure, where
   V15L already rejects optional GMEM. Explicit render modes, profiling and
   preemption optimization retain their previous behavior. Existing submitted
   batches still retire on normal submit processing; there is no early GPU free.
5. **Bounded idle cache:** retain ordinary 64 KiB BOs, but extend V15N's oversized
   last-reference cache exclusion to pipeline state as well as autotune.
   TU_A830_LEAN_CACHE=0 restores original cache retention. This may increase
   allocation churn in some workloads and needs an A/B test.
6. **Runtime identity:** Vulkan driverInfo includes `Frane V16 A830 RC1` so
   the loaded driver can be distinguished from fallback/stock drivers.
7. **GMEM startup:** no optional GMEM before a valid MemAvailable observation.
   Preserve V15L pressure thresholds, bandwidth margins, confidence heuristic,
   UBWC path, GMEM/cache offsets, tile layout, synchronization and attachment IO.

No extra A810/A825/A829/A840 changes. Generic CPU correctness fixes are compiled
into this A830-targeted build, but no compatibility claim is made for other GPUs.
V15N's advisory 60% available-memory fraction is preserved. This is neither a
60% total RAM limit nor a physical cap on application allocation.

8. **Cross-build configuration:** move `-static-libstdc++` from the compiler
   command into `cpp_link_args`. It is a linker option; in the old command it
   triggers `-Werror=unused-command-line-argument` in C++ feature probes,
   incorrectly rejecting supported warning/optimization flags. Static C++
   runtime linking remains enabled.

## Developer-source review

- Mesa main inspected at 5ff61a7646d29b54c324af0a60aa3bfb5cdd24d1. The same
  history temporary and suballocator failure patterns were present. Kept the
  user's working 26.1.4 base instead of replacing the renderer wholesale.
- The412Banner/Banners-Turnip A8xx at
  7ec62b4d08fd2a5a0c198cf188d17ec3184bbc27: reviewed whitebelyash-derived
  gralloc and A8xx patches. Required gralloc workaround is already in V15D.
  Did not restore the older speculative 0x78000 GMEM offset.
- WinNative-Emu/Drivers at 8407c8012d7b3096621becec73d836f4fbe7b3ce:
  reviewed balanced/performance policy and GPU quirks. Did not import forced
  maximum clocks, relaxed bandwidth costing, or other-GPU changes.
- faux123/turnip-faux123-driver at aaae932ec85716a23ee0e05e576406a5b79b6dbd:
  public README describes one-device testing; companion patch/build source is
  not public there. No uninspectable implementation was copied or credited as
  an imported fix. The KGSL change above follows direct review of Mesa code.
- whitebelyash/mesa-tu8 tu/gen8 was inspected at
  958a51540beb64ecd9ac78028692ce113a2d1b3b. Remote gen8 head was resolved as
  d185f62a24305a2ea0d2fa7f3d156e0595025d54 but fetch failed with HTTP 502;
  do not treat that branch as fully reviewed.

## Qualcomm 842.19 inspection

User ZIP meta.json says extracted from Gamehub, author GameNative, Vulkan
1.4.304. It contains compiled libraries, not Qualcomm source code.

- vulkan.adreno.so SHA256:
  338e23a9839c0227036e9ae7993f3dd74f56c1277300ff0a9917b937bdaf2226
- libgsl.so SHA256:
  ba67671bfc13cbcaf72b7ca13d0a17f39b58f3abeceff1d7701857a11f289cee

The Vulkan library references gsl_command_freememontimestamp_pure, timestamp
checks/waits, and diagnostics 'Low Draws, Gmem Load', 'Failed to retire old viz
stream memory', and trim-attempt timestamps. These support investigation of
deferred retirement and unnecessary sampling, but do not reveal its algorithm,
thresholds, allocator correctness, or prove how a given game uses those paths.
No proprietary code, libraries, inferred register values or timer-based frees
are injected into Turnip. Mesa's GPU lifetime remains authoritative.

## Validation and device test

Host tests compile actual edited Mesa functions with fake BO/kernel backends:
TS/TS, TS/FD, FD/TS, FD/FD ownership; mapping-failure retry/destruction; ordinary,
oversized and still-referenced BO retention; history move ownership. ASan and
UBSan cover these CPU paths. Local LeakSanitizer cannot run under this runtime's
ptrace; CI enables it. Neither host tests nor a successful build validate GPU IO.

For the first comparison, use the same FC4 save/route, 720p, High textures,
40 FPS cap, same Winlator/FEX/DXVK/display backend as V15L/N. Leave TU_DEBUG
and TU_AUTOTUNE_ALGO/FLAGS unset so old forced settings do not bypass policy.
Record startup, 15, 30 and 60 minute RAM/frametime observations and repeat the
same driving loop. Repeated load/unload cycles are needed to distinguish a
cache plateau from unbounded growth. Optional TU_A830_SMART_GMEM_LOG=1 emits
mode/pressure statistics (log label remains V15-K for parser compatibility).
Compare TU_A830_LEAN_CACHE=0 in a separate launch if allocation churn appears.
If artifacts or a GPU fault occur, preserve logs and compare V15L; the known
TU_DEBUG=sysmem mode can isolate the GMEM path. No zero-leak claim before device
measurements, and no claim this addresses a particular historical GPU fault.

## Completed local build

Full NDK r29 ARM64 build completed successfully (895 Ninja steps). ELF is
AArch64 DYN, exports Android HMI and embeds `Frane V16 A830 RC1` in driverInfo.
C++ runtime is statically linked. Host ASan/UBSan tests passed; the KGSL
regression test fails against pristine Mesa 26.1.4, as expected. On-device
rendering, driver import, prolonged RAM growth, FPS and power remain untested.
