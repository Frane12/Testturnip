#!/usr/bin/env python3
"""A810 V27.1: immediate diagnostic INIT log to verify V27 file-writing path."""
from pathlib import Path

p = Path('mesa/src/freedreno/vulkan/tu_autotune.cc')
s = p.read_text()

def edit(old, new):
    global s
    assert s.count(old) == 1, (old[:120], s.count(old))
    s = s.replace(old, new, 1)

edit('''   auto history = rp_histories.emplace(std::make_pair(key, key.hash));
   uint32_t saved = 0;''',
'''   auto history = rp_histories.emplace(std::make_pair(key, key.hash));
   static std::atomic<bool> frane_v271_init_logged { false };
   bool expected = false;
   if (frane_v271_init_logged.compare_exchange_strong(
          expected, true, std::memory_order_relaxed))
      frane_log_profile("INIT", key.hash, 50);

   uint32_t saved = 0;''')

d = Path('mesa/src/freedreno/vulkan/tu_device.cc')
x = d.read_text()
assert x.count('Frane A810 V27-READABLE-PROFILE / Mesa ') == 1
d.write_text(x.replace('Frane A810 V27-READABLE-PROFILE / Mesa ',
                       'Frane A810 V27.1-DIAG-INIT / Mesa ', 1))

p.write_text(s)
print('V27.1 immediate INIT diagnostic log applied')
