#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
a=(v/"tu_autotune.cc").read_text()
d=(v/"tu_device.cc").read_text()
cb=(v/"tu_cmd_buffer.cc").read_text()
cbh=(v/"tu_cmd_buffer.h").read_text()
q=(v/"tu_queue.cc").read_text()
h=(v/"frane_a810_cpu_pipeline_probe.h").read_text()
for token in ("frane_cpu_sample(false)","frane_cpu_record_cb(",
              "CLOCK_THREAD_CPUTIME_ID","frane_cpu_probe_seq"):
    assert token in cb,token
for token in ("frane_cpu_sample(true)","frane_cpu_record_queue(",
              "frane_q_driver_begin","frane_q_driver_end",
              "pthread_mutex_unlock(&device->submit_mutex)"):
    assert token in q,token
assert q.index("pthread_mutex_unlock(&device->submit_mutex);\n   if (frane_q_seq)") < q.index("frane_cpu_record_queue(")
assert "frane_cpu_probe_seq" in cbh
assert "TU_FRANE_CPU_CB_TRACE_PATH" in h
assert "TU_FRANE_CPU_QUEUE_TRACE_PATH" in h
assert "process_rss_kib" in h
assert "Drnas-Turnip A810 S Ultimate v1.4" in d
assert "frane_s1at4_coordinate(" in a and "frane_a810_gmem_pass_safe" in a
print("A810 v1.4 source audit: CB, queue and CPU-only probes; S1/AT4 safety retained PASS")
