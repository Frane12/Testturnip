#!/usr/bin/env python3
"""Model/stress checks for 26.3.37 exact-subpass-mask GMEM packing."""

import random
from pathlib import Path

CPPS = (1, 2, 4, 8, 16)

def range_mask(first, last):
    assert 0 <= first <= last < 64
    return ((1 << (last - first + 1)) - 1) << first

def envelope_alloc(items):
    allocs = []
    assignment = []
    for cpp, first, last in items:
        best = None
        best_key = None
        span = last - first + 1
        for i, (acpp, af, al) in enumerate(allocs):
            if not (af > last or al < first) or acpp < cpp:
                continue
            gap = first - al - 1 if al < first else af - last - 1
            slack = acpp - cpp
            key = (gap * acpp + slack * span, slack, gap, i)
            if best_key is None or key < best_key:
                best = i
                best_key = key
        if best is None:
            allocs.append([cpp, first, last])
            best = len(allocs) - 1
        else:
            allocs[best][1] = min(allocs[best][1], first)
            allocs[best][2] = max(allocs[best][2], last)
        assignment.append(best)
    return allocs, assignment

def mask_alloc(items):
    order = sorted(
        range(len(items)),
        key=lambda i: (
            -items[i][0],
            -(items[i][2] - items[i][1] + 1),
            items[i][1],
            i,
        ),
    )
    tracks = []
    assignment = [None] * len(items)

    for idx in order:
        cpp, first, last = items[idx]
        mask = range_mask(first, last)
        best = None
        best_key = None
        for i, (acpp, af, al, busy) in enumerate(tracks):
            if busy & mask or acpp < cpp:
                continue
            key = (acpp - cpp, -busy.bit_count(), i)
            if best_key is None or key < best_key:
                best = i
                best_key = key

        if best is None:
            tracks.append([cpp, first, last, mask])
            best = len(tracks) - 1
        else:
            tracks[best][1] = min(tracks[best][1], first)
            tracks[best][2] = max(tracks[best][2], last)
            tracks[best][3] |= mask
        assignment[idx] = best

    return [t[:3] for t in tracks], assignment, tracks

def verify_no_overlap(items, assignment):
    for i in range(len(items)):
        for j in range(i):
            if assignment[i] != assignment[j]:
                continue
            _, fi, li = items[i]
            _, fj, lj = items[j]
            assert li < fj or lj < fi, (items, i, j, assignment[i])

def blocks_for_pixels(pixels, cpp, align=4096, shift=3):
    gran = max(1, cpp >> shift)
    n = (pixels * cpp + align - 1) // align
    n = max(n, gran)
    return (n + gran - 1) & ~(gran - 1)

def exact_pixels(allocs, total_blocks=64, align=4096, shift=3):
    if not allocs:
        return 0
    cpps = [a[0] for a in allocs]
    if sum(blocks_for_pixels(1, c, align, shift) for c in cpps) > total_blocks:
        return 0
    lo = 1
    hi = total_blocks * align // min(cpps)
    while lo < hi:
        mid = lo + (hi - lo + 1) // 2
        need = sum(blocks_for_pixels(mid, c, align, shift) for c in cpps)
        if need <= total_blocks:
            lo = mid
        else:
            hi = mid - 1
    return lo

# Deterministic "hole in the envelope" case:
# subpasses 0 and 3 may share a track, and a third attachment in 1..2 can
# legally use the same memory too. Envelope tracking loses that hole.
fixture = [
    (8, 0, 0),
    (8, 3, 3),
    (8, 1, 2),
]
env, ea = envelope_alloc(fixture)
mask, ma, tracks = mask_alloc(fixture)
verify_no_overlap(fixture, ma)
assert len(mask) == 1
assert len(env) >= 2
assert exact_pixels(mask) > exact_pixels(env)

# Order-dependency case: large cpp arrives after small cpp in API order.
fixture2 = [
    (1, 0, 0),
    (8, 2, 2),
    (1, 1, 1),
]
env2, _ = envelope_alloc(fixture2)
mask2, ma2, _ = mask_alloc(fixture2)
verify_no_overlap(fixture2, ma2)
assert sum(a[0] for a in mask2) <= sum(a[0] for a in env2)

rng = random.Random(0x26337A810)
wins = equal = losses = rescues = 0
checks = 0

for _ in range(250000):
    count = rng.randint(2, 12)
    items = []
    for _ in range(count):
        cpp = rng.choice(CPPS)
        first = rng.randint(0, 9)
        last = rng.randint(first, min(11, first + rng.randint(0, 3)))
        items.append((cpp, first, last))

    env, ea = envelope_alloc(items)
    mask, ma, tracks = mask_alloc(items)
    verify_no_overlap(items, ma)

    for total_blocks in (16, 24, 32, 48, 64, 96):
        ep = exact_pixels(env, total_blocks)
        mp = exact_pixels(mask, total_blocks)

        if mp > ep:
            wins += 1
        elif mp == ep:
            equal += 1
        else:
            losses += 1

        if ep == 0 and mp > 0:
            rescues += 1

        # Driver admission is strict: a worse mask candidate is ignored.
        selected = mp if mp > ep else ep
        assert selected >= ep
        checks += 1

assert wins > 1000
assert rescues > 0

root = Path("mesa/src/freedreno/vulkan")
src = (root / "tu_pass.cc").read_text()
dev = (root / "tu_device.cc").read_text()

assert 'TU_A810_26337_GMEM_MASK_PACK", true' in src
assert "frane_build_gmem_mask_candidate" in src
assert "frane_pack_gmem_exact" in src
assert "pass->subpass_count <= 64" in src
assert "rescued_pixels > 0" in src
assert "mask_pixels > pass->gmem_pixels[layout]" in src
assert "candidate_pixels > pixels" in src
assert "Turnip A810 V37 / Mesa " in dev

print(
    "26.3.37 GMEM-MASK-LAB PASS: "
    f"{checks} pack comparisons, {wins} strict wins, "
    f"{rescues} impossible-layout rescues, {losses} rejected losses"
)
