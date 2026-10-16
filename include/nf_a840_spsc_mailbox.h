/* SPDX-License-Identifier: MIT
 * NeuroFlow A840: fixed-capacity, NONBLOCKING CPU <-> NPU-worker transport.
 * Two single-slot SPSC (single producer, single consumer) handoffs.
 *
 * NO sleeps, loops, syscalls, mutexes, allocations, GPU calls, QNN calls,
 * time queries, or waits. A full slot immediately returns false (DROP).
 * This is NOT a hardware mailbox: it is an application-level CPU queue
 * ready to connect to a separate QNN worker when available.
 *
 * Producer/consumer must each be a SINGLE distinct logical thread.
 * Initialize before starting either thread. Neither side may touch the
 * other's payload while "full" is set. Never copy the mailbox struct.
 */
#ifndef NF_A840_SPSC_MAILBOX_H
#define NF_A840_SPSC_MAILBOX_H
#include "nf_a840_temporal.h"
#include <stdatomic.h>

struct nf_a840_request_slot {
   atomic_bool full;
   struct nf_a840_request payload;
};
struct nf_a840_result_slot {
   atomic_bool full;
   struct nf_a840_prediction payload;
};

static inline void
nf_a840_request_slot_init(struct nf_a840_request_slot *s)
{
   atomic_init(&s->full, false);
}
static inline void
nf_a840_result_slot_init(struct nf_a840_result_slot *s)
{
   atomic_init(&s->full, false);
}

/* CPU owner -> worker; returns false immediately when worker is busy. */
static inline bool
nf_a840_request_try_push(struct nf_a840_request_slot *s,
                         const struct nf_a840_request *in)
{
   if (atomic_load_explicit(&s->full, memory_order_acquire))
      return false;
   s->payload = *in;
   atomic_store_explicit(&s->full, true, memory_order_release);
   return true;
}

/* Worker -> local request; never called from GPU/render thread. */
static inline bool
nf_a840_request_try_pop(struct nf_a840_request_slot *s,
                        struct nf_a840_request *out)
{
   if (!atomic_load_explicit(&s->full, memory_order_acquire))
      return false;
   *out = s->payload;
   atomic_store_explicit(&s->full, false, memory_order_release);
   return true;
}

/* Worker -> CPU controller; drop response if CPU still has unread result. */
static inline bool
nf_a840_result_try_push(struct nf_a840_result_slot *s,
                        const struct nf_a840_prediction *in)
{
   if (atomic_load_explicit(&s->full, memory_order_acquire))
      return false;
   s->payload = *in;
   atomic_store_explicit(&s->full, true, memory_order_release);
   return true;
}

/* CPU controller -> local result; stale/unsafe predictions rejected later. */
static inline bool
nf_a840_result_try_pop(struct nf_a840_result_slot *s,
                       struct nf_a840_prediction *out)
{
   if (!atomic_load_explicit(&s->full, memory_order_acquire))
      return false;
   *out = s->payload;
   atomic_store_explicit(&s->full, false, memory_order_release);
   return true;
}

/* Dispatch exclusively on the CPU owner thread, outside the GPU hot path.
 * Never enqueue if the worker is still busy. On full, abort the request
 * bookkeeping so no stale in-flight flag causes permanent deadlock.
 * Caller is free to continue its Mesa fallback forever.
 */
static inline bool
nf_a840_try_dispatch(struct nf_a840_controller *c,
                     struct nf_a840_request_slot *slot)
{
   struct nf_a840_request req;
   if (!nf_a840_take_request(c, &req))
      return false;
   if (nf_a840_request_try_push(slot, &req))
      return true;
   nf_a840_cancel_request(c, req.request_id);
   return false;
}

#endif /* NF_A840_SPSC_MAILBOX_H */
