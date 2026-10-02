#include <cassert>
#include <cstdint>
#include <iostream>

struct Risk {
   bool msaa = false;
   bool ds = false;
   bool resolve = false;
   bool store = false;
};

static bool quarantine(uint8_t mode, Risk r)
{
   switch (mode) {
   case 3: return r.resolve;
   case 4: return r.msaa;
   case 5: return r.ds;
   case 6: return r.store;
   case 7: return r.resolve || r.msaa || r.ds;
   default: return false;
   }
}

static bool force_sysmem(uint8_t mode, Risk r)
{
   if (mode == 1)
      return true;
   return quarantine(mode, r);
}

static bool force_gmem(uint8_t mode, bool mesa_legal)
{
   return mode == 2 && mesa_legal;
}

static bool v2_enabled(uint8_t mode)
{
   return mode != 8;
}

int main()
{
   const Risk clean{};
   const Risk resolve{false, false, true, true};
   const Risk msaa{true, false, false, true};
   const Risk ds{false, true, false, true};
   const Risk store{false, false, false, true};

   assert(!force_sysmem(0, clean));
   assert(force_sysmem(1, clean));

   assert(force_gmem(2, true));
   assert(!force_gmem(2, false));

   assert(quarantine(3, resolve));
   assert(!quarantine(3, msaa));

   assert(quarantine(4, msaa));
   assert(!quarantine(4, ds));

   assert(quarantine(5, ds));
   assert(!quarantine(5, resolve));

   assert(quarantine(6, store));
   assert(!quarantine(6, clean));

   assert(quarantine(7, resolve));
   assert(quarantine(7, msaa));
   assert(quarantine(7, ds));
   assert(!quarantine(7, clean));

   assert(v2_enabled(0));
   assert(!v2_enabled(8));

   std::cout << "A830 PF-AUDIT V1.0 mode policy: PASS\n";
   return 0;
}
