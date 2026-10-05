## A810 S1 Smart CB1 — internal test build

S1 Smart Performance 2 plus a conservative concurrent-binning scheduler for A810.

### Why this build exists

Earlier A810 CB testing showed that concurrent binning can produce a real throughput gain, but also that a broad "pressure score" can lower warm-run performance. Smart CB1 therefore does **not** force CB across every heavy-looking renderpass.

The policy has two thresholds:

1. **Admission:** a GMEM renderpass has enough draws / tiles / attachment work to justify trying CB.
2. **Keep:** only a narrow, clearly heavy upper envelope bypasses Turnip's existing GPU-side "BR caught BV" performance feedback.

For ordinary admitted passes, Turnip still gets to turn CB off dynamically when overlap is not useful.

### Default behavior

Enabled by default:

`TU_FRANE_SMART_CB=1`

Disable only the new A810 CB override:

`TU_FRANE_SMART_CB=0`

`TU_DEBUG=nocb` remains authoritative and disables CB.

The Smart GMEM/SYSMEM layer from S1 Smart Performance 2 remains controlled by:

`TU_FRANE_SMART=1` (default)

### Optional CB modes

`TU_FRANE_SMART_CB_MODE=0` — runtime feedback only; never statically keep CB armed.

`TU_FRANE_SMART_CB_MODE=1` — **default Smart CB1** conservative keep gate.

`TU_FRANE_SMART_CB_MODE=2` — legacy V45 keep behavior for comparison.

`TU_FRANE_SMART_CB_MODE=3` — slightly more aggressive balanced gate.

`TU_FRANE_SMART_CB_MODE=4` — legacy broad V46 pressure policy, regression/reference only.

Optional structural log:

`TU_FRANE_SMART_CB_LOG=1`

Do not benchmark FPS with logging enabled.

### Safety / correctness

Smart CB1 does **not** remove or weaken the existing Turnip CB correctness machinery. The build keeps:

- LRZ fast-clear and partial-fast-clear restrictions;
- XFB / primitive-generation / vertex-stat query guards;
- resource-list overflow handling;
- CB patchpoints and predicates;
- BV-waits-for-BR and BR-waits-for-BV synchronization;
- `TU_DEBUG=nocb` and `TU_DEBUG=forcecb` authority.

A810's custom override is GMEM-only by default. Sysmem CB is not admitted by Smart CB1 unless Mesa/DRI explicitly enables concurrent binning.

### What to test

Use the same setup for A/B:

- DXVK 1.9.4 reference unless intentionally comparing another DXVK;
- Crysis 32-bit, same resolution/settings, three passes;
- compare warm-pass average, minimum, triangles/sec and subjective frametime;
- then test Dirt 3 and Far Cry 2/3 gameplay for stutter/regressions.

Best first comparison:

1. default Smart CB1;
2. `TU_FRANE_SMART_CB=0`;
3. only if needed, `TU_FRANE_SMART_CB_MODE=0`.

No FPS claim is made for Smart CB1 until the on-device runs are measured.

This is an **internal draft release**.
