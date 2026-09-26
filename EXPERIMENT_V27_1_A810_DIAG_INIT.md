# Frane Turnip V27.1 A810 — Diagnostic INIT

Based directly on V27 Readable Profile.

V27.1 adds exactly one immediate diagnostic line when the autotuner creates its first render-pass history:

```
INIT app=FC3 rp=0x... sysmem_probability=50 preferred=SYSMEM
```

This happens before waiting for V26/V27 profile SAVE thresholds, so a short launch/gameplay test is enough to verify whether the driver can write to `TU_A810_PROFILE_LOG`.

Recommended Ludashi diagnostic path from the app-internal location visible in its file manager:

```
TU_A810_PROFILE_ID=FC3
TU_A810_PROFILE_LOG=/data/user/0/com.ludashi.benchmark/files/images/home/xuser-1/.wine/drive_c/users/xuser/FC3-V271.log
```

If INIT appears, file writing is working and any missing SAVE lines are due to profile maturity/measurement conditions rather than path access.
