# A810 S1.1

Internal draft experiment based on A810 S1 Smart Performance 2, pinned to Mesa eda9aceb39d5ff169b096444abe366bdf2269e24.

## Idea: spend less time testing a proven expensive loser

Eight consecutive fresh pairs must show the loser costs at least twice as much as the winner. Only LOCKED histories with zero instability penalty and no structural tail risk qualify. Their measurement cadence changes from 2/256 to 2/512 pattern occurrences, and forced loser selections from 1/256 to 1/512. All other histories retain S1 Smart 2 policy.

The expensive-cost flag is computed only when timing feedback arrives and packed into a previously unused histogram bit. No additional allocation, lock, atomic ticket or clock read is added to the decision path. Fresh pairs remain adjacent and jittered. A tie, weaker margin or opposing pair clears the flag immediately. Final GMEM safety checks remain authoritative.

The freshness window grows to 1024 occurrences only while the sparse policy qualifies. This is an explicit tradeoff: fewer expensive probes in stable scenes, potentially slower detection when the winner changes. Counts are render-pattern recurrences, not frames or milliseconds.

## Controls

Enabled by default, no variables required.

- TU_FRANE_SMART_BUDGET=0: disable only S1.1 loss budgeting, preserving the S1 Smart 2 selection and measurement schedule.
- TU_FRANE_SMART=0: disable the whole Smart layer and return to the inherited S1 path.
- TU_FRANE_PROFILE_ID is not needed.

## Validation

Host UBSan checks passed: inherited 716,040 boundary combinations with budgeting disabled; exact cadence and counter rollover for both winner modes; risky-pass exclusion; tie and <2x boundary withdrawal; extreme 64-bit costs; 256 synthetic abrupt-winner-reversal simulations.

Across those 256 simulations, the largest observed delay to the new TRUSTED winner was 636 pattern occurrences. They requested 25,274 measurements out of 2,560,000 decisions (0.987%). These are synthetic policy results, not GPU overhead or game FPS results. A successful build additionally runs ASan+UBSan, applies the complete patch against pristine pinned Mesa, compiles Android ARM64 with NDK r29 and checks the ZIP/ELF.

## Device test

Compare S1.1 default versus TU_FRANE_SMART_BUDGET=0 using whole warm runs and longer gameplay, with DXVK 1.9.4 as reference. Use Crysis three passes, Dirt 3 repeated runs, and Far Cry 2/3 including level or scene changes. Watch average performance, frametime, visuals and recovery after scene changes. No on-device FPS improvement is claimed yet.

Release remains DRAFT; the workflow refuses to modify a published release. Source branches and Actions logs in this public repository are public; draft release assets are not publicly released.
