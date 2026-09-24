#!/usr/bin/env python3
"""Port WN's MIT IMapper backend to pinned Mesa 26.2.3. Strict anchors."""
from pathlib import Path
import shutil

root = Path('mesa/src/util/u_gralloc')

def edit(name, old, new):
    p = root / name
    s = p.read_text()
    if s.count(old) != 1:
        raise SystemExit(f'V19 source drift: {name}')
    p.write_text(s.replace(old, new, 1))

edit('meson.build', "  'u_gralloc_qcom.c',\n)",
     "  'u_gralloc_qcom.c',\n  'u_gralloc_aimapper.c',\n)")
edit('u_gralloc.h', '   U_GRALLOC_TYPE_GRALLOC4,\n',
     '   U_GRALLOC_TYPE_GRALLOC4,\n   U_GRALLOC_TYPE_AIMAPPER,\n')
edit('u_gralloc_internal.h', 'extern struct u_gralloc *u_gralloc_qcom_create(void);',
     'extern struct u_gralloc *u_gralloc_aimapper_create(void);\n'
     'extern struct u_gralloc *u_gralloc_qcom_create(void);')
edit('u_gralloc.c', '   {.type = U_GRALLOC_TYPE_LIBDRM, .create = u_gralloc_libdrm_create},',
     '   {.type = U_GRALLOC_TYPE_AIMAPPER, .create = u_gralloc_aimapper_create},\n'
     '   {.type = U_GRALLOC_TYPE_LIBDRM, .create = u_gralloc_libdrm_create},')
shutil.copyfile(Path(__file__).parent / 'wn_aimapper/u_gralloc_aimapper.c',
                root / 'u_gralloc_aimapper.c')
p = Path('mesa/src/freedreno/vulkan/tu_device.cc')
s = p.read_text()
old = 'Frane A810 V18-SAMPLED-DEPTH / Mesa '
assert s.count(old) == 1
p.write_text(s.replace(old, 'Frane A810 V19-IMAPPER / Mesa ', 1))
print('V19: IMapper5 metadata backend; TU_FRANE_AIMAPPER=0 restores fallback selection')
