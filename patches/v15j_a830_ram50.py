#!/usr/bin/env python3
"""Apply after V15-D/G/I: lower A830 advisory budget headroom, preserve GMEM.

Default 50% of currently available system memory, plus existing heap usage.
TU_A830_BUDGET_PERCENT overrides to 30..90 (clamped); 70 matches V15-I.
This is not a limit on total Android RAM usage and does not free live BOs.
"""
from pathlib import Path
p = Path('mesa/src/freedreno/vulkan/tu_device.cc')
s = p.read_text()
before = '''   const uint64_t heap_available =
      physical_device->info->chip >= A8XX
         ? sys_available * 7 / 10
         : sys_available * 9 / 10;'''
after = '''   /* V15-J: allow applications to see a smaller remaining allocation
    * budget on A830. This is advisory, not an allocator cap or an eviction.
    * Keep heapUsage accurate and retain V15-G policy on other GPUs.
    */
   static const uint64_t a830_budget_percent = []() {
      const int64_t value = debug_get_num_option("TU_A830_BUDGET_PERCENT", 50);
      return uint64_t(CLAMP(value, 30, 90));
   }();
   const uint64_t chip_id = physical_device->dev_id.chip_id;
   const bool is_a830 = chip_id == 0x44050001ull ||
                        chip_id == 0x44050000ull ||
                        chip_id == 0xffff44050000ull;
   const uint64_t budget_percent = is_a830 ? a830_budget_percent :
      (physical_device->info->chip >= A8XX ? 70 : 90);
   const uint64_t heap_available = sys_available * budget_percent / 100;'''
if s.count(before) != 1 or s.count('Frane-V15I-A830-GMEM-DEV') != 1:
    raise SystemExit('V15-J requires exact V15-G + V15-I source; no files changed')
s = s.replace(before, after, 1).replace('Frane-V15I-A830-GMEM-DEV', 'Frane-V15J-A830-RAM50', 1)
p.write_text(s)
print('V15-J: A830 advisory headroom 50%; TU_A830_BUDGET_PERCENT=70 restores V15-I budget')
