# Frane Turnip V27 A810 — Readable Profile

Experimental A810 build based directly on V26 Adaptive Cache.

## What V27 adds

V27 keeps the V26 persistent Mesa disk-cache profile and adds a human-readable text log whenever a learned render-pass profile is loaded or saved.

Default text log path:

- `$XDG_CACHE_HOME/frane-turnip-v27-profiles.log`, when `XDG_CACHE_HOME` is set
- otherwise `$HOME/.cache/frane-turnip-v27-profiles.log`

Each line is intentionally simple, for example:

```
SAVE app=FC3 rp=0x1234567890abcdef sysmem_probability=67 preferred=SYSMEM
LOAD app=FC3 rp=0x1234567890abcdef sysmem_probability=67 preferred=SYSMEM
```

The readable log is diagnostic only. The actual fast persistent profile remains in Mesa disk cache.

## Useful variables

- `TU_A810_PROFILE_ID=FC3` — strongly recommended under Wine/DXVK so games do not share a generic DXVK/Wine identity.
- `TU_A810_PROFILE_CACHE=1` — V26/V27 binary persistent profile cache; default enabled.
- `TU_A810_PROFILE_TEXT_LOG=1` — readable V27 log; default enabled.
- `TU_A810_PROFILE_LOG=/path/file.log` — override exact readable log path.
- `TU_A810_PROFILE_LOG=0` — disable the readable log.
- `TU_AUTOTUNE_ALGO=profiled` — optional on A810; the A810 profiled path is selected automatically when the lean profiled mode is enabled.

Logging happens only on profile LOAD/SAVE events, not every frame.
