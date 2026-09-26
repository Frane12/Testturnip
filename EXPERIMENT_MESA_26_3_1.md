# Frane Mesa 26.3.1 EXP

**Experimental downstream name, not an official Mesa 26.3.1 release.**

Base upstream: Mesa `26.3.0-devel`, commit
`eeca16aa41e89a114e53e76439df623c7efb9519` (2026-09-26 snapshot), with the
existing V29 FAST-NOAI A810 patch stack.

This experiment deliberately avoids changing shader compilation, normal
GMEM/SYSMEM scoring, WSI present mode or graphics output. It targets failure
paths that can look like driver hangs.

## Audited/fixed paths

- KGSL WAIT_ANY iterator no longer reads `syncobjs[count]` before checking the bound.
- Same-queue WAIT_ANY timestamps now use the earliest timestamp (the existing
  `min_ts()` helper) rather than accidentally selecting the latest.
- `poll()` return semantics are corrected: ready => success, zero => timeout,
  negative => device-lost/error instead of the previous inverted mapping.
- Relative queue-fence deadlines saturate instead of overflowing on
  `UINT64_MAX` / very large waits.
- Millisecond conversion clamps finite waits to `INT_MAX` instead of allowing
  integer wrap to turn a long finite wait into an accidental infinite wait.
- Unexpected KGSL ioctl/condition/sync-fd errors are no longer disguised as
  ordinary timeouts.
- Queue submit error paths release `submit_mutex` on sparse-submit allocation
  failure, dynamic command-buffer preparation failure, regular submit
  allocation failure, and both pre-submit patchpoint failure paths.
- The existing V16 fixes are required and asserted: suballocator mapping failure
  clears the stale BO pointer, and TS/FD sync merging converts/owns the correct
  fence objects.

## Test intent

Compare first against **V29 FAST-NOAI Mesa-main**, with identical FEX, DXVK,
resolution, affinity, thermals and game scene. Normal FPS should not change much;
this build is aimed at fewer rare lockups, incorrect wait behavior and
failure-path deadlocks.
