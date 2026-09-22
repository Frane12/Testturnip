# V15-P A810 RENDER RECOVERY: missing-texture isolation

User reported V15-O A810 shows incomplete scene/absent background textures, like earlier faulty A830 test. **Successful Mesa compilation does not establish image correctness.**

Source lineage: V15-O, new changes only in `patches/v15p_a810_render_recovery.py`. Leave V15-O, A830 V15-L and V15-N untouched.

## Addressed A810-specific issues

- A810 has ~576 KiB, one-slice GMEM. Whitebelyash's A8xx work documented that an unconditional A8xx `0x78000` initial GMEM offset can underflow this small GMEM. V15-P restricts that offset to chips with more than one GMEM slice, preserving A830 behavior.
- Apply A810-specific small-cache/VPC parameters based on whitebelyash/mesa-tu8, instead of treating an A810 KGSL chip-ID alias as an A830.
- Default `TU_A810_GMEM_PROFILE=0` and prefer_sysmem to obtain a picture-correctness baseline. `TU_DEBUG=sysmem` overrides the selector and *strictly forces* sysmem for diagnosis. A810 Lean Budget/Cache experiments default off during image validation. Opt-in profiles 1/2 remain behind env flags.

The stock GPU's texture sampling/compression and Android gralloc must also be correct. If textures remain missing with **TU_DEBUG=sysmem** and profile 0, GMEM cost-model improvements cannot fix the issue. Compare with a known-good A810 driver at the same DXVK and game settings; inspect Vulkan image layout, UBWC import, prefetch flags, descriptor/sampler setup and Winlator render mode, and capture KGSL faults/logcat. Do NOT continue promoting GMEM without a working SYSMEM image.

## A/B steps

1. Restart with `TU_DEBUG=sysmem` and `TU_A810_GMEM_PROFILE=0` on V15-P. Confirm full textures and screenshots; compare with known-good A810 driver.
2. When full SYSMEM picture renders, restart after removing `TU_DEBUG=sysmem`, setting `TU_A810_GMEM_PROFILE=1`. Check texture completeness and crashes/frametime. Never test profile 2 unless profile 1 actually works.
3. Revert on missing images, page faults, or excessive RAM, and don't confuse DXVK HUD being drawn with real 3D framebuffer correctness.

The profile 0 setting is a preference, *not* a guarantee that no GMEM pass can occur; keep `TU_DEBUG=sysmem` for strict isolation. The offset fix by itself is not a proven repair for the missing textures.
