#!/usr/bin/env python3
"""V15-F: V15-D proven image path + isolated advisory memory budget experiment.

No tu_suballoc changes, no eager reclamation, no change to the actual
heap size or reported heap usage. Isolate whether EXT_memory_budget
guidance changes DXVK's RAM footprint without V15-E initialization crash.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_device.cc")
s = p.read_text()
before = """   uint64_t heap_available = sys_available * 9 / 10;
   return MIN2(heap_size, heap_used + heap_available);"""
after = """   /* Frane V15-F: gen8-only advisory memory budget. Keep V15-D's
    * allocation, buffer lifetime and image path completely unchanged.
    */
   uint64_t heap_available =
      physical_device->info->chip >= A8XX
         ? sys_available * 3 / 5
         : sys_available * 9 / 10;
   return MIN2(heap_size, heap_used + heap_available);"""
if s.count(before) != 1:
    raise SystemExit(f"Expected exactly one upstream memory budget anchor, got {s.count(before)}")
p.write_text(s.replace(before, after, 1))
print("V15-F: V15-D + advisory budget only, no eager BO reclaim")
