#!/usr/bin/env python3
"""A810 v1.3 S1/AT4 coordination: narrow, reversible tie-break over v1.2.
No extra queries, no GMEM safety or sampling changes; strict source anchors.
"""
from pathlib import Path
import shutil
V=Path('mesa/src/freedreno/vulkan')
auto=V/'tu_autotune.cc'
dev=V/'tu_device.cc'
shutil.copyfile('patches/frane_a810_s1at4_coord.h', V/'frane_a810_s1at4_coord.h')

def change(path, old, new, label):
    src=path.read_text()
    count=src.count(old)
    if count != 1:
        raise SystemExit(f'v1.3 S1AT4 SOURCE DRIFT {label}: {count}')
    path.write_text(src.replace(old,new,1))
    print('v1.3 S1AT4 PASS',label,flush=True)

change(auto,'#include "frane_a810_s1_bandwidth_probe.h"',
  '#include "frane_a810_s1_bandwidth_probe.h"\n#include "frane_a810_s1at4_coord.h"',
  'coordinator available after AT4 types')
change(auto,
'''         bool *s1_override_out = nullptr,
         bool *s1_sysmem_out = nullptr)''',
'''         bool *s1_override_out = nullptr,
         bool *s1_sysmem_out = nullptr,
         bool *s1at4_coord_out = nullptr)''',
  'pass optional coordination provenance to selector')
change(auto,
'''                  at1 = s1at4_context ?
                     frane_at4_decide(at1_in, snapshot, decision_word) :
                     frane_s1at3_decide(at1_in, snapshot, decision_word);
                  at3_sampling = at1.override_mode;''',
'''                  at1 = s1at4_context ?
                     frane_at4_decide(at1_in, snapshot, decision_word) :
                     frane_s1at3_decide(at1_in, snapshot, decision_word);
                  /* S1/AT4 coordination is only an optional tie-break on a
                   * narrow conflict. Keep AT4 override_mode/force_measure
                   * intact, so AT4 sampling and the post-selector GMEM
                   * correctness gate always retain their authority. */
                  static const bool s1at4_coord_enabled =
                     debug_get_bool_option("TU_FRANE_S1AT4_COORD", true);
                  const auto s1at4_coord = frane_s1at4_coordinate(
                     s1at4_coord_enabled,
                     s1at4_context && at4_active,
                     runtime_decision.override_mode,
                     runtime_decision.select_sysmem,
                     runtime_decision.force_measure,
                     runtime_state.armed, unsigned(runtime_state.score),
                     at1.override_mode, at1.select_sysmem, at1.force_measure,
                     snapshot.signature == signature,
                     std::min(snapshot.samples[0], snapshot.samples[1]),
                     unsigned(std::abs(int(snapshot.score))),
                     snapshot.volatility,
                     snapshot.stale[0] || snapshot.stale[1]);
                  if (s1at4_coord.prefer_s1) {
                     at1.select_sysmem = runtime_decision.select_sysmem;
                     if (s1at4_coord_out) *s1at4_coord_out = true;
                  }
                  at3_sampling = at1.override_mode;''',
  'runtime coordinated winner preserving AT4 control and exploration')
change(auto,
'''      bool s1_runtime_override = false;
      bool s1_runtime_sysmem = false;''',
'''      bool s1_runtime_override = false;
      bool s1_runtime_sysmem = false;
      bool s1at4_coord_applied = false;''',
  'store AT4/S1 coordinator provenance')
change(auto,
'''         &s1_runtime_override, &s1_runtime_sysmem);''',
'''         &s1_runtime_override, &s1_runtime_sysmem,
         &s1at4_coord_applied);''',
  'pass coordinator provenance')

# All final-source views (AT4 RFC1, ATUltimate, and S1BP) must agree. This
# changes only logging labels, never their sample rate or selected mode.
s=auto.read_text()
needle='at4_applied ? "AT4_OVERRIDE" :'
n=s.count(needle)
if n < 3:
    raise SystemExit(f'v1.3 S1AT4 SOURCE DRIFT attribution count: {n}')
s=s.replace(needle,
'''s1at4_coord_applied ? "S1_AT4_COORD" :
            at4_applied ? "AT4_OVERRIDE" :''')
auto.write_text(s)
print('v1.3 S1AT4 PASS',n,'final-source attributions',flush=True)
change(dev,'Drnas-Turnip A810 S Ultimate v1.2 / Mesa ',
  'Drnas-Turnip A810 S Ultimate v1.3 / Mesa ',
  'Vulkan driverInfo identity')
change(dev,'"Drnas-Turnip A810 S Ultimate v1.2" : pdevice->name',
  '"Drnas-Turnip A810 S Ultimate v1.3" : pdevice->name',
  'DXVK adapter identity')

source=auto.read_text()
assert source.index('frane_s1at4_coordinate(') < source.index('at3_sampling = at1.override_mode;')
assert source.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)') < source.index('frane_s1bp_trace(s1bp_seq,bp)')
assert 'TU_FRANE_AT9' not in source
print('v1.3 S1AT4 overlay complete: AT4 probes and downstream safety retained')
