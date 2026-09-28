#!/usr/bin/env python3
"""26.3.32 A810 GMEM performance baseline.

Consolidates the combinations that have now tested well:
- simple depth GMEM enabled;
- simple combined depth+stencil GMEM enabled;
- packed depth/stencil GMEM enabled;
- simple color conditional load/store enabled.

Still intentionally blocked:
- depth/stencil conditional load/store;
- stencil load/store split path remains conservative;
- resolve/unresolve;
- MSAA;
- input-attachment / feedback-loop cases;
- multiview, FDM, MSRTSS, layered, partial and multi-subpass cases.

The purpose of this build is to create a stable "known-good performance"
baseline before touching GMEM allocation/packing policy itself.
"""
from pathlib import Path
R=Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p=R/path
    s=p.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.32 source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old,new,1))
    print(f"26.3.32 PASS {label}", flush=True)

edit(
 "tu_autotune.cc",
 'debug_get_bool_option("TU_A810_26330_GMEM_PACKED_DS", false)',
 'debug_get_bool_option("TU_A810_26330_GMEM_PACKED_DS", true)',
 "enable packed DS by default",
)

edit(
 "tu_device.cc",
 "Frane Mesa 26.3.31 A810 COLOR-COND-LS EXP / Mesa ",
 "Frane Mesa 26.3.32 A810 GMEM-PERF-BASE EXP / Mesa ",
 "driver identity",
)

a=(R/"tu_autotune.cc").read_text()
d=(R/"tu_device.cc").read_text()
for needle in (
    'TU_A810_26327_GMEM_SIMPLE_DEPTH", true',
    'TU_A810_26328_GMEM_SIMPLE_DS", true',
    'TU_A810_26330_GMEM_PACKED_DS", true',
    'TU_A810_26331_GMEM_COLOR_COND_LS", true',
    'TU_A810_26329_GMEM_STENCIL_LOADSTORE", false',
):
    assert needle in a, needle

# Preserve the major risk gates before we start reorganizing GMEM allocation.
for needle in (
    'subpass.resolve_count',
    'subpass.unresolve_count',
    'subpass.resolve_depth_stencil',
    'subpass.feedback_loop_color',
    'subpass.feedback_loop_ds',
    'subpass.samples != VK_SAMPLE_COUNT_1_BIT',
):
    assert needle in a, needle

assert a.count("!frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") == 3
assert "Frane Mesa 26.3.32 A810 GMEM-PERF-BASE EXP" in d
print("26.3.32 A810 GMEM performance baseline applied", flush=True)
