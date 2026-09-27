# Frane Mesa 26.3.19 A810 MEMORY-AUDIT

Downstream experimental build on 26.3.18 SMART-GMEM, commit 8ac32c7e65b6df0f6e886786e6b0c608c76a560b. Mesa base remains eeca16aa41e89a114e53e76439df623c7efb9519 (26.3.0-devel).

- Retained NIR objects have a 32 MiB charged-byte cap, including object/key overhead; individual serialized payloads above 2 MiB are not cached. Existing 384 insertion-reservation cap remains. This does not cap the whole driver, temporary serialization buffers, or allocator overhead.
- Atomic byte reservations prevent concurrent compilers exceeding the budget. Failed allocation and duplicate insertion refund their charge. Cache rejection leaves shader compilation working normally.
- GMEM confidence increases require a fresh sample from both paths. Adverse evidence can lower confidence immediately. Counter resets discard old confidence.
- Hot-cache hits validate the immutable history hash and the published pin, fixing the zero-hash window between pointer publication and slot-hash publication.
- SMART-GMEM no longer evaluates layout twice. Disabled adaptive scheduling skips an unused live-effect scan.

Default SMART-GMEM, adaptive IR3 scheduler with TEX window 12, and previous rendering settings are preserved. No FPS improvement is claimed without hardware measurement. No new variables are required. Existing opt-outs remain available.

Validation: source-extracted allocation/cleanup and zero-hash regression tests; eight-thread budget stress; stale/fresh timing state tests; full Android ARM64 CI build. CI success must be checked for the delivered commit. GPU execution is not tested by host tests.

AI-assisted downstream work. Provenance marker: biblioklept.
