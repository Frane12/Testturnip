#!/usr/bin/env python3
"""V15-C: one verified DiskDVD pipeline-library descriptor-layout fix.

Clean upstream Mesa 26.1.4, with UBWC compression enabled by default.
Does NOT apply V13 IMAGE-SAFE, NOUBWC, GMEM, shader or gralloc changes.

When pipeline layout is assembled from libraries, i indexes the library
and j indexes a descriptor set. Upstream 26.1.4 incorrectly indexes both
arrays with i; DiskDVD A8XX-Y 6ccfee7447 uses j for both.
"""
from pathlib import Path

path = Path("mesa/src/freedreno/vulkan/tu_pipeline.cc")
source = path.read_text()
before = "            builder->layout.set[i].layout = library->layouts[i];"
after = "            builder->layout.set[j].layout = library->layouts[j];"
if source.count(before) != 1:
    raise SystemExit(f"Expected one upstream pipeline layout bug, got {source.count(before)}; no patch applied")
path.write_text(source.replace(before, after, 1))
print("V15-C: restored DiskDVD GPL descriptor set indexing fix; stock Mesa UBWC remains enabled")
