#include <cassert>
#include <cstdint>

static uint32_t
bandwidth(uint32_t color, uint32_t depth, uint32_t stencil,
          bool depth_write, bool depth_test, bool stencil_test)
{
   uint32_t v = color;
   if (depth_write) v += depth;
   if (depth_test) v += depth;
   if (stencil_test) v += stencil * 2;
   return v;
}

static bool
needs_refresh(bool valid, bool dynamic_dirty, uint32_t graphics_dirty)
{
   return !valid || dynamic_dirty || graphics_dirty != 0;
}

int main()
{
   /* Exhaust the boolean bandwidth combinations against the literal V39
    * arithmetic used by the new cache builder.
    */
   for (unsigned dw = 0; dw < 2; ++dw) {
      for (unsigned dt = 0; dt < 2; ++dt) {
         for (unsigned st = 0; st < 2; ++st) {
            const uint32_t color = 13, depth = 4, stencil = 1;
            uint32_t legacy = color;
            if (dw) legacy += depth;
            if (dt) legacy += depth;
            if (st) legacy += stencil * 2;
            assert(bandwidth(color, depth, stencil, dw, dt, st) == legacy);
         }
      }
   }

   /* Invalid cache always rebuilds.  Any graphics or dynamic dirtiness also
    * rebuilds.  Only a valid completely-clean draw may reuse.
    */
   assert(needs_refresh(false, false, 0));
   assert(needs_refresh(true, true, 0));
   assert(needs_refresh(true, false, 1));
   assert(needs_refresh(true, true, 0xffffffffu));
   assert(!needs_refresh(true, false, 0));

   return 0;
}
