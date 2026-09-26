#!/usr/bin/env python3
"""A810 V27: add a human-readable per-game autotuner profile log on top of V26."""
from pathlib import Path

p = Path('mesa/src/freedreno/vulkan/tu_autotune.cc')
s = p.read_text()

def edit(old, new):
    global s
    assert s.count(old) == 1, (old[:120], s.count(old))
    s = s.replace(old, new, 1)

edit('#include "util/disk_cache.h"\n#include <cstdlib>',
     '#include "util/disk_cache.h"\n#include <cstdlib>\n#include <cstdio>\n#include <sys/stat.h>')

anchor = '''bool
tu_autotune::frane_profile_key(uint64_t rp_hash, cache_key key) const
{'''
assert s.count(anchor) == 1
helper = r'''void
tu_autotune::frane_log_profile(const char *event, uint64_t hash,
                               uint32_t value) const
{
   if (!frane_a810_gpu(device) ||
       !debug_get_bool_option("TU_A810_PROFILE_TEXT_LOG", true))
      return;

   const char *name = debug_get_option("TU_A810_PROFILE_ID", nullptr);
   if (!name || !*name)
      name = device->instance->vk.app_info.app_name;
   if (!name || !*name)
      name = "unknown";

   const char *override_path =
      debug_get_option("TU_A810_PROFILE_LOG", nullptr);
   if (override_path && !strcmp(override_path, "0"))
      return;

   std::string path;
   if (override_path && *override_path) {
      path = override_path;
   } else {
      const char *xdg = getenv("XDG_CACHE_HOME");
      const char *home = getenv("HOME");
      if (xdg && *xdg) {
         mkdir(xdg, 0700);
         path = std::string(xdg) + "/frane-turnip-v27-profiles.log";
      } else if (home && *home) {
         const std::string cache_dir = std::string(home) + "/.cache";
         mkdir(cache_dir.c_str(), 0700);
         path = cache_dir + "/frane-turnip-v27-profiles.log";
      } else {
         return;
      }
   }

   FILE *fp = fopen(path.c_str(), "a");
   if (!fp)
      return;

   fprintf(fp,
           "%s app=%s rp=0x%016llx sysmem_probability=%u preferred=%s\\n",
           event, name, (unsigned long long) hash, value,
           value >= 50 ? "SYSMEM" : "GMEM");
   fclose(fp);
}

'''
s = s.replace(anchor, helper + anchor, 1)

edit('''   if (valid)
      *value = *(uint32_t *)data;
   free(data);
   return valid;''',
'''   if (valid) {
      *value = *(uint32_t *)data;
      frane_log_profile("LOAD", hash, *value);
   }
   free(data);
   return valid;''')

edit('''   if (value > 0 && value < 100 && frane_profile_key(hash, key))
      disk_cache_put(device->physical_device->vk.disk_cache, key, &value, sizeof(value), nullptr);''',
'''   if (value > 0 && value < 100 && frane_profile_key(hash, key)) {
      disk_cache_put(device->physical_device->vk.disk_cache, key, &value, sizeof(value), nullptr);
      frane_log_profile("SAVE", hash, value);
   }''')

p.write_text(s)

h = Path('mesa/src/freedreno/vulkan/tu_autotune.h')
t = h.read_text()
old = '''   bool frane_profile_key(uint64_t hash, unsigned char *key) const;
   bool frane_load_profile(uint64_t hash, uint32_t *value) const;
   void frane_save_profile(uint64_t hash, uint32_t value) const;'''
new = '''   bool frane_profile_key(uint64_t hash, unsigned char *key) const;
   bool frane_load_profile(uint64_t hash, uint32_t *value) const;
   void frane_save_profile(uint64_t hash, uint32_t value) const;
   void frane_log_profile(const char *event, uint64_t hash,
                          uint32_t value) const;'''
assert t.count(old) == 1
h.write_text(t.replace(old, new, 1))

d = Path('mesa/src/freedreno/vulkan/tu_device.cc')
x = d.read_text()
assert x.count('Frane A810 V26-ADAPTIVE-CACHE / Mesa ') == 1
d.write_text(x.replace('Frane A810 V26-ADAPTIVE-CACHE / Mesa ',
                       'Frane A810 V27-READABLE-PROFILE / Mesa ', 1))

print('V27 readable per-game autotuner profile log applied')
