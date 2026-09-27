#include <cassert>
#include <cstdint>
#include <cstdio>

enum BlendStatus {
   SAFE,
   ALL_COLOR_WRITES_SKIPPED,
   READS_DEST_OR_PARTIAL_WRITE,
};

struct BlendModel {
   uint32_t attachment_count;
   uint32_t defined_mask;
   uint32_t write_enable_mask;
   uint32_t nonzero_write_mask;
   uint32_t full_write_mask;
   uint32_t blend_enable_mask;
   bool logic_reads_dest;
};

static BlendStatus
classify(const BlendModel &m, bool fastpath)
{
   if (!fastpath && m.logic_reads_dest)
      return READS_DEST_OR_PARTIAL_WRITE;

   uint32_t total = 0;
   uint32_t written = 0;

   for (uint32_t i = 0; i < m.attachment_count; i++) {
      const uint32_t bit = 1u << i;
      if (!(m.defined_mask & bit))
         continue;
      total++;
      if ((m.write_enable_mask & bit) && (m.nonzero_write_mask & bit))
         written++;
   }

   if (!total)
      return SAFE;
   if (!written)
      return ALL_COLOR_WRITES_SKIPPED;
   if (m.logic_reads_dest)
      return READS_DEST_OR_PARTIAL_WRITE;

   const uint32_t comparison_count = fastpath ? total : m.attachment_count;
   if (written < comparison_count)
      return READS_DEST_OR_PARTIAL_WRITE;

   for (uint32_t i = 0; i < m.attachment_count; i++) {
      const uint32_t bit = 1u << i;
      if (!(m.defined_mask & bit))
         continue;
      if (m.blend_enable_mask & bit)
         return READS_DEST_OR_PARTIAL_WRITE;
      if (!(m.write_enable_mask & bit))
         return READS_DEST_OR_PARTIAL_WRITE;
      if (!(m.full_write_mask & bit))
         return READS_DEST_OR_PARTIAL_WRITE;
   }
   return SAFE;
}

struct FsSig {
   bool writes_pos;
   bool early_fragment_tests;
   uint8_t depth_layout;
   bool has_kill;
   bool writes_smask;
   uint32_t lrz_status;
   bool force_late_z;
   bool sample_shading;
   uint16_t dynamic_input_attachments_used;
};

static bool
same_sig(const FsSig &a, const FsSig &b)
{
   return a.writes_pos == b.writes_pos &&
          a.early_fragment_tests == b.early_fragment_tests &&
          a.depth_layout == b.depth_layout &&
          a.has_kill == b.has_kill &&
          a.writes_smask == b.writes_smask &&
          a.lrz_status == b.lrz_status &&
          a.force_late_z == b.force_late_z &&
          a.sample_shading == b.sample_shading &&
          a.dynamic_input_attachments_used ==
             b.dynamic_input_attachments_used;
}

int main()
{
   {
      /* Sparse RT slots: two defined attachments in four slots, both fully
       * written. Legacy code classified this as partial solely because 2 < 4.
       */
      BlendModel m = {
         4, 0b0101, 0b0101, 0b0101, 0b0101, 0, false,
      };
      assert(classify(m, false) == READS_DEST_OR_PARTIAL_WRITE);
      assert(classify(m, true) == SAFE);
   }

   {
      /* Stale logic-op state cannot read a color destination when no actual
       * color attachment is written.
       */
      BlendModel m = {
         2, 0b0011, 0, 0, 0, 0, true,
      };
      assert(classify(m, false) == READS_DEST_OR_PARTIAL_WRITE);
      assert(classify(m, true) == ALL_COLOR_WRITES_SKIPPED);
   }

   {
      /* Real blending remains conservative. */
      BlendModel m = {
         2, 0b0011, 0b0011, 0b0011, 0b0011, 0b0010, false,
      };
      assert(classify(m, true) == READS_DEST_OR_PARTIAL_WRITE);
   }

   {
      /* Partial channel writes remain conservative. */
      BlendModel m = {
         1, 0b0001, 0b0001, 0b0001, 0, 0, false,
      };
      assert(classify(m, true) == READS_DEST_OR_PARTIAL_WRITE);
   }

   FsSig a = {
      false, false, 0, false, false, 0, false, false, 0,
   };
   FsSig b = a;

   assert(same_sig(a, b));

   b.has_kill = true;
   assert(!same_sig(a, b));
   b = a;

   b.writes_pos = true;
   assert(!same_sig(a, b));
   b = a;

   b.lrz_status = 1;
   assert(!same_sig(a, b));
   b = a;

   b.dynamic_input_attachments_used = 4;
   assert(!same_sig(a, b));

   std::puts("26.3.13 LRZ fastpath policy PASS");
   return 0;
}
