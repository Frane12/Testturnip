#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

static constexpr unsigned MAX_RTS = 8;
static constexpr int UNUSED = -1;

enum class Format {
   Color,
   D32,
   S8,
   D32S8,
};

struct Subpass {
   bool custom_resolve = false;
   std::array<int, MAX_RTS> color = {UNUSED, UNUSED, UNUSED, UNUSED,
                                     UNUSED, UNUSED, UNUSED, UNUSED};
   Format zs = Format::Color;
   bool has_zs = false;
};

struct Usage {
   bool gate = false;
   uint8_t mrt_mask = 0;
   bool depth = false;
   bool stencil = false;
};

static bool
has_depth(Format f)
{
   return f == Format::D32 || f == Format::D32S8;
}

static bool
has_stencil(Format f)
{
   return f == Format::S8 || f == Format::D32S8;
}

static Usage
model(bool enabled, bool is_a810, bool dynamic_rendering,
      const std::vector<Subpass> &subpasses)
{
   Usage u = {};

   if (!enabled || !is_a810 || dynamic_rendering)
      return u;

   for (const auto &sp : subpasses) {
      if (sp.custom_resolve)
         continue;

      for (unsigned i = 0; i < MAX_RTS; i++) {
         if (sp.color[i] != UNUSED)
            u.mrt_mask |= uint8_t(1u << i);
      }

      if (!sp.has_zs)
         continue;

      const bool d = has_depth(sp.zs);
      const bool s = has_stencil(sp.zs);
      u.depth |= d;
      u.stencil |= d || s;
   }

   u.gate = true;
   return u;
}

static uint32_t
dimension_word(bool gate, bool active, uint32_t w, uint32_t h)
{
   if (gate && !active)
      return 0;

   assert(w < (1u << 15));
   assert(h < (1u << 15));
   return w | (h << 16);
}

int main()
{
   {
      Subpass sp;
      sp.color[0] = 0;
      auto u = model(true, true, false, {sp});
      assert(u.gate);
      assert(u.mrt_mask == 0x01);
      assert(!u.depth);
      assert(!u.stencil);
      assert(dimension_word(u.gate, u.mrt_mask & 1, 512, 256) ==
             (512u | (256u << 16)));
      assert(dimension_word(u.gate, u.mrt_mask & 2, 512, 256) == 0);
   }

   {
      /* Later subpasses must keep their MRTs live: pass-wide union, not
       * first-subpass state.
       */
      Subpass a, b;
      a.color[0] = 0;
      b.color[3] = 1;
      auto u = model(true, true, false, {a, b});
      assert(u.mrt_mask == ((1u << 0) | (1u << 3)));
   }

   {
      /* Custom resolve is sysmem-only and must not keep a GMEM slot live. */
      Subpass main, resolve;
      main.color[1] = 0;
      resolve.custom_resolve = true;
      resolve.color[7] = 1;
      auto u = model(true, true, false, {main, resolve});
      assert(u.mrt_mask == (1u << 1));
   }

   {
      /* Match Mesa's TODO semantics exactly:
       * depth-only => depth dimension live AND stencil dimension live;
       * stencil-only => only stencil dimension live.
       */
      Subpass d;
      d.has_zs = true;
      d.zs = Format::D32;
      auto ud = model(true, true, false, {d});
      assert(ud.depth);
      assert(ud.stencil);

      Subpass s;
      s.has_zs = true;
      s.zs = Format::S8;
      auto us = model(true, true, false, {s});
      assert(!us.depth);
      assert(us.stencil);

      Subpass ds;
      ds.has_zs = true;
      ds.zs = Format::D32S8;
      auto uds = model(true, true, false, {ds});
      assert(uds.depth && uds.stencil);
   }

   {
      /* A/B off, non-A810, and dynamic rendering all preserve 26.3.8's
       * legacy all-dimensions behavior by returning gate=false.
       */
      Subpass sp;
      sp.color[0] = 0;
      assert(!model(false, true, false, {sp}).gate);
      assert(!model(true, false, false, {sp}).gate);
      assert(!model(true, true, true, {sp}).gate);

      const auto legacy = model(false, true, false, {sp});
      assert(dimension_word(legacy.gate, false, 320, 192) ==
             (320u | (192u << 16)));
   }

   {
      /* Empty classic render pass: gating is valid and every attachment
       * dimension becomes exactly zero.
       */
      auto u = model(true, true, false, {});
      assert(u.gate);
      assert(u.mrt_mask == 0);
      assert(!u.depth && !u.stencil);
      for (unsigned i = 0; i < MAX_RTS; i++)
         assert(dimension_word(u.gate, false, 1024, 512) == 0);
   }

   std::puts("26.3.9 GMEM dimension policy PASS");
   return 0;
}
