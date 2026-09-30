#!/usr/bin/env python3
"""Seeded policy simulation for V61.

This is not a GPU simulator. It stress-tests the learning/router logic against
synthetic duration distributions to catch policy pathologies before hardware
A/B: false early lock, wasted scans, profiler disagreement and regime reversal.
"""
import random
import statistics

def step_toward(current, sample, shift):
    if current == sample:
        return current
    delta = abs(sample - current)
    step = (delta >> shift) + (1 if delta & ((1 << shift) - 1) else 0)
    step = max(step, 1)
    return current + step if sample > current else current - step

class Mode:
    def __init__(self):
        self.mean = 0
        self.tail = 0
        self.samples = 0

class State:
    def __init__(self):
        self.sys = Mode()
        self.gm = Mode()
        self.paired = 0
        self.score = 0
        self.ready = False

def update_mode(s, sample):
    sample = max(1, int(sample))
    if not s.samples:
        s.mean = s.tail = sample
        s.samples = 1
        return
    s.mean = step_toward(s.mean, sample, 3)
    if sample > s.tail:
        s.tail = step_toward(s.tail, sample, 1)
    else:
        s.tail = step_toward(s.tail, sample, 5)
    s.tail = max(s.tail, s.mean)
    s.samples = min(65535, s.samples + 1)

def cost(s):
    if not s.samples or not s.mean:
        return 0
    return s.mean + max(0, s.tail - s.mean) // 2

def ratio_le(lhs, rhs, num, den):
    return lhs * den <= rhs * num

def update_state(st, is_sys, sample):
    update_mode(st.sys if is_sys else st.gm, sample)
    paired = min(st.sys.samples, st.gm.samples)
    if paired <= st.paired:
        return
    st.paired = paired
    if paired < 6:
        return
    st.ready = True
    sysc, gmc = cost(st.sys), cost(st.gm)
    delta = 0
    if ratio_le(gmc, sysc, 7, 8):
        delta = 2
    elif ratio_le(gmc, sysc, 15, 16):
        delta = 1
    elif ratio_le(sysc, gmc, 7, 8):
        delta = -2
    elif ratio_le(sysc, gmc, 15, 16):
        delta = -1

    if delta:
        st.score = max(-8, min(8, st.score + delta))
    elif st.score > 0:
        st.score -= 1
    elif st.score < 0:
        st.score += 1

def learner_actionable(st, sysmem_probability):
    if not st.ready or abs(st.score) < 4:
        return False
    confidence = abs(st.score)
    prefer_sys = st.score < 0
    if not prefer_sys and sysmem_probability > 65 and confidence < 7:
        return False
    if prefer_sys and sysmem_probability < 35 and confidence < 7:
        return False
    return True

def target(occ):
    if occ < 16:
        return 1
    if occ < 64:
        return 2
    if occ < 256:
        return 4
    if occ < 512:
        return 6
    if occ < 1024:
        return 8
    return 10

def simulate(mu_sys, mu_gm, sigma, probability, early, seed, occurrences=2000):
    rng = random.Random(seed)
    st = State()
    forced = 0
    takeover = None

    for occ in range(1, occurrences + 1):
        actionable = learner_actionable(st, probability)
        if early and st.paired >= 8 and actionable:
            if takeover is None:
                takeover = occ
            continue

        t = target(occ)
        need_sys = st.sys.samples < t
        need_gm = st.gm.samples < t
        if not (need_sys or need_gm):
            continue

        if need_sys and need_gm:
            if st.sys.samples != st.gm.samples:
                choose_sys = st.sys.samples < st.gm.samples
            else:
                choose_sys = bool(occ & 1)
        else:
            choose_sys = need_sys

        mu = mu_sys if choose_sys else mu_gm
        sample = round(rng.gauss(mu, mu * sigma))
        update_state(st, choose_sys, sample)
        forced += 1

    return forced, takeover, st

def main():
    strong_reductions = []
    near_tie_early = 0

    for seed in range(256):
        v60 = simulate(120, 90, 0.03, 50, False, seed)
        v61 = simulate(120, 90, 0.03, 50, True, seed)
        assert v61[0] <= v60[0]
        strong_reductions.append(v60[0] - v61[0])

        tie = simulate(100, 99, 0.05, 50, True, seed)
        if tie[1] is not None:
            near_tie_early += 1

    # Strong stable winner should save real scan work.
    assert statistics.mean(strong_reductions) >= 3.0

    # Noise around a near tie should almost never manufacture a mature lock.
    assert near_tie_early <= 8  # <= 3.125% of these deterministic seeds

    # Strong PROFILED disagreement must block a merely moderate learner.
    st = State()
    for _ in range(9):
        update_state(st, True, 100)
        update_state(st, False, 93)
    assert abs(st.score) >= 4
    if abs(st.score) < 7:
        assert not learner_actionable(st, 85)

    # Regime changes are not permanent locks: enough opposite measured pairs
    # must be able to drive the hysteretic score through zero.
    st = State()
    for _ in range(8):
        update_state(st, True, 120)
        update_state(st, False, 85)
    assert st.score > 0
    for _ in range(64):
        update_state(st, True, 90)
        update_state(st, False, 125)
    assert st.score < 0

    # Rare-pass budget: once one sample/mode exists, no more forced scan work
    # is required below 16 occurrences.
    assert target(3) == 1

    print(
        "V61 simulation PASS:",
        f"mean strong-winner scans saved={statistics.mean(strong_reductions):.2f},",
        f"near-tie early-lock seeds={near_tie_early}/256",
    )

if __name__ == "__main__":
    main()
