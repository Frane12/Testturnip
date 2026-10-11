#!/usr/bin/env python3
"""U1 RC1 identity and default-feature guard.

No tuning policy, shader, depth/stencil correctness, GPU queries or command
queue behavior is modified here: derived directly from tested AT6.3 ->
experimental AT7 -> CP1 build. Performance features are enabled by the
existing A810 defaults; CPU/GPU disk logging remains opt-in.
"""
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
auto=V/"tu_autotune.cc"
dev=V/"tu_device.cc"
queue=V/"tu_queue.cc"
cpu=V/"frane_a810_cp1.h"
gpu=V/"frane_a810_at4_rfc1.h"

s=dev.read_text()
old="Drnas-Turnip A810 AT7 Utility Winner / Mesa "
new="Turnip-Drnas U1 RC1 A810 Universal / Mesa "
if s.count(old)!=1:
    raise SystemExit("U1 failed closed: upstream driverInfo changed")
dev.write_text(s.replace(old,new,1))

a=auto.read_text()
q=queue.read_text()
h=cpu.read_text()
g=gpu.read_text()
default_enabled={
    "AT1":'debug_get_bool_option("TU_FRANE_AT1", true)',
    "AT3":'debug_get_bool_option("TU_FRANE_AT3", true)',
    "AT4":'debug_get_bool_option("TU_FRANE_AT4", true)',
    "AT6":'debug_get_bool_option("TU_FRANE_AT6", true)',
    "AT63":'debug_get_bool_option("TU_FRANE_AT63", true)',
    "AT7":'debug_get_bool_option("TU_FRANE_AT7", true)',
}
for name, token in default_enabled.items():
    if token not in a: raise SystemExit(f"U1: {name} is not ON by default")
for name,token in {
    "CP1": 'if (!num_entries && frane_cp1_a810(dev) &&',
    "CP1 reset":'frane_cp1_zero_entries_enabled()',
    "AT7 runtime": 'frane_at7_utility_winner(',
    "AT6.3 runtime":'frane_at63_measured_winner(',
    "safety": 'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)',
}.items():
    if token not in q+a: raise SystemExit(f"U1: {name} not active")

if "return !env || env[0] != '0' || env[1] != '\\0';" not in h:
    raise SystemExit("U1: CP1 must default ON and allow 0 as OFF")
if "TU_FRANE_A810_CP1_TRACE_PATH" not in h or \
   "TU_FRANE_A810_RFC1_TRACE_PATH" not in g:
    raise SystemExit("U1: both diagnostic traces must be individually available")
if "path && path[0] == '/' && path[1]" not in h or \
   "path && path[0] == '/' && path[1]" not in g:
    raise SystemExit("U1: tracing must remain opt-in")
if "TU_FRANE_AT5" in a:
    raise SystemExit("U1 must not accidentally resurrect AT5")
if new not in dev.read_text():
    raise SystemExit("U1 branding not applied")
print("U1 RC1: all A810 AT/CP1 opt-in features ON by default, logs opt-in, rollbacks present PASS")
