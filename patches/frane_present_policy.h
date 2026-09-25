/* SPDX-License-Identifier: MIT
 * Frane A810 experimental Vulkan WSI presentation policy.
 * An optional preference, not a Vulkan API layer, compositor or scheduler.
 */
#ifndef FRANE_PRESENT_POLICY_H
#define FRANE_PRESENT_POLICY_H
#include <string.h>

enum frane_present_choice {
   FRANE_PRESENT_OFF,
   FRANE_PRESENT_MAILBOX,
   FRANE_PRESENT_FIFO,
   FRANE_PRESENT_RELAXED,
   FRANE_PRESENT_IMMEDIATE
};

static inline enum frane_present_choice
frane_present_parse(const char *value)
{
   /* V23 default: prefer MAILBOX if supported; otherwise Mesa keeps the
    * application's requested mode using its existing WSI validation.
    */
   if (!value || !strcmp(value, "auto") || !strcmp(value, "mailbox"))
      return FRANE_PRESENT_MAILBOX;
   if (!strcmp(value, "fifo"))
      return FRANE_PRESENT_FIFO;
   if (!strcmp(value, "relaxed"))
      return FRANE_PRESENT_RELAXED;
   if (!strcmp(value, "immediate"))
      return FRANE_PRESENT_IMMEDIATE;
   /* "off" and invalid values fail closed (original client choice). */
   return FRANE_PRESENT_OFF;
}
#endif
