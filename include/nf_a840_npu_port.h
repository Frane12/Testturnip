/* SPDX-License-Identifier: MIT
 * Optional adapter CONTRACT only for later Qualcomm QNN/HTP experimentation.
 * This header does not link libQnn*, allocate NPU memory, or touch KGSL.
 */
#ifndef NF_A840_NPU_PORT_H
#define NF_A840_NPU_PORT_H
#include "nf_a840_temporal.h"

/* enqueue_copy MUST deep-copy the entire request and return without waiting
 * for inference. Call it from a CPU worker, NEVER from render hot path.
 * Prediction completion must be delivered by a thread-safe application queue
 * to the controller's ONE owning thread, which calls offer_prediction().
 */
typedef bool (*nf_a840_enqueue_copy_fn)(
   void *userdata, const struct nf_a840_request *immutable_request);

struct nf_a840_npu_port {
   void *userdata;
   nf_a840_enqueue_copy_fn enqueue_copy;
};

/* No fake fallback to "AI on CPU" here: absent backend means no NPU request. */
static inline bool
nf_a840_enqueue_async(const struct nf_a840_npu_port *port,
                       const struct nf_a840_request *request)
{
   return port && port->enqueue_copy &&
          port->enqueue_copy(port->userdata, request);
}

#endif /* NF_A840_NPU_PORT_H */
