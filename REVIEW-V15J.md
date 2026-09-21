# V15-J RAM50 experiment

Parent: V15-I f14c97287e5fab003325b00076444589a593671e.
Trigger: user screenshot reports total RAM 92%, 11.6 FPS, CPU 85%, battery 46 C.
This does not establish a leak, nor identify RAM as the only frame-time cause.

Only the A830 advisory memory-budget headroom changes: from 70% to 50% of
currently available system memory. Accurate heap usage is added; heap size caps
reported budget as before. Other GPUs keep their existing policy. V15-I GMEM
selection, gralloc workaround, pool sizes and resource lifetimes are unchanged.

This does not impose a 50% total-RAM cap or forcibly reclaim live resources. An
application may ignore the budget. When only 500 MiB is available, the change
reduces reported remaining headroom by only 100 MiB (350 -> 250 MiB); it cannot
promise to bring total usage from 92% to 80%. Smaller budgets may increase asset
streaming and stutter. Restart the game for each comparison.

Default: TU_A830_BUDGET_PERCENT absent -> 50.
Set TU_A830_BUDGET_PERCENT=70 to reproduce V15-I budgeting in the same binary.
An optional 40 is available for a later test, not the first comparison. Values
are clamped to 30..90. Keep GMEM options and game settings identical between runs.
The driver identifies as Frane-V15J-A830-RAM50 in Vulkan driverInfo.

Compare the same save/route for 15-20 minutes. Record starting/peak/end RAM and
frame-time spikes. Establish which driver was used for the screenshot; use the
same Medium textures as the earlier 80-82% run if reproducing that result.
Do not simultaneously change DXVK, texture quality and budget.

Tests compile the actual patched budget calculation with minimal C++ type stubs,
checking zero available memory, heap bound, A830 IDs, unchanged other-GPU policy
and option clamping. The existing GMEM decision tests also run. Neither test
establishes Android memory savings; the device test is essential.
