# A830 S2-QP1 — DRAFT

BW1 reference: 1cdfbd985b036906296b9b4637747ad34f369a11.
Mesa base: f1a6b0d71ade2b1304cc9b466ae6d27402b7e7c8, 26.3.0-devel.

QP1 counts submitted direct vertices/indices including instances, with a saturating cap and sticky unknown flag. Indirect and multi-draw commands, geometry amplification and vertex side effects keep the original path. Counts and unknown state merge with secondary/suspended passes and reset with the render-pass state.

For simple color-only single-subpass A830 rendering, 3–16 tiles, at most 16 draws and 192 submitted vertices, QP1 can skip hardware binning when the bounded tile replay work is at most 2048 vertices. This uses Mesa's existing non-binned GMEM command path. Existing all-visible visibility setup, concurrent-binning disable handling, cache flushes and synchronization remain in place.

PROFILED may measure selected 2–4 draw color passes that the baseline ignores: direct geometry at most 192 vertices, 262144–2097152 pixels, at most 16 tiles and a bounded attachment-traffic criterion. Selection still belongs to the existing Smart/PROFILED learner; QP1 does not force GMEM. Reusable/simultaneous-use buffers, preemption-sensitive configuration, explicit algorithm choices and mandatory safety overrides retain their existing behavior.

History keys distinguish the small draw count, geometry class and unknown geometry. Persistent policy cache uses a separate namespace. Shader scheduling remains BW1. A830 vertex variants now receive the existing side-effect metadata from NIR writes_memory; this field was previously filled only for fragment variants. It is serialized with the variant. Mesa build-ID based shader and Vulkan pipeline-cache UUIDs prevent reuse of stale metadata.

Controls:
- TU_FRANE_A830_QP1=1: default.
- TU_FRANE_A830_QP1=0: BW1 policy, original hash/cache namespace.
- TU_FRANE_A830_QP1_LOG=1: optional logcat diagnostics for eligible paths; leave disabled for timing comparisons.

Reference evidence:
- User-supplied Qualcomm v891.7 ZIP: binary only, no Qualcomm source copied. Strings include accumulated draws/vertices/instances and low-draw/high-GMEM-load decisions; thresholds and the complete decision algorithm are unknown.
- Mesa pinned source: tu_util.cc uses a tile-count binning heuristic; tu_autotune.cc ordinarily ignores passes below five draws. QP1 is an independent bounded experiment motivated by these observations.
- Compared A830 tiling/cache configuration and fallback paths with p33k-a-b00/mesa-turnip-a830 and whitebelyash/mesa-unified; undocumented cache/register values were not changed.
- faux123 public repository was reviewed; its implementation patches are not public and were not copied.

Validation: policy boundary tests with ASan/UBSan; actual Mesa eligibility, binning and history-key functions compiled/executed with mocked Vulkan objects; source dataflow/reset/merge/visibility guards; Android ARM64 release compilation and ZIP/ELF/package checks. No physical A830 GPU execution, Vulkan CTS, device page-fault test or FPS claim.

Keep this release draft. No public release is authorized.
