# Frane Mesa 26.3.5 A810 SHADER-PIPELINE EXP

**Experimental downstream name, not an official Mesa release.**

Baseline: fully green **Frane Mesa 26.3.4 A810 GMEM-RUNTIME EXP**.

Goal: reduce CPU-side shader/pipeline creation hitches while preserving the
same NIR lowering, IR3 optimizer behavior and generated GPU shader semantics.

Changes:

- Adds a dedicated **RAM-only** A810 intermediate-NIR cache. It is separate
  from the application/final pipeline cache and is created with
  `skip_disk_cache=true`, so this experiment adds no synchronous disk-cache
  miss on the shader front-end.
- The intermediate cache is bounded to **384 insertion reservations** to avoid
  unbounded RAM growth. After the cap, existing entries can still hit but new
  intermediate NIR is not retained.
- Stage key uses Turnip's stage/layout/key hash plus a dedicated `'N'` suffix.
- On a hit, the compiler skips SPIR-V -> initial NIR translation for that stage;
  normal Turnip NIR lowering, cross-stage linking and IR3 backend still run.
- Compiled-shader cache lookup no longer stops at the first missing stage.
  Later stages are probed and reused when present.
- Already cached shader stages are not reinserted/re-serialized after a partial
  pipeline miss.
- Mixed partial-cache compile failure cleanup uses
  `vk_pipeline_cache_object_unref()`, which is valid for both lookup refs and
  newly created refcount-1 shader objects.
- Graphics and compute pipeline timing calls are skipped unless the application
  actually requested pipeline creation feedback. Per-stage timing is likewise
  disabled when feedback is absent.
- Compute pipelines are intentionally left out of the intermediate-NIR cache
  experiment for now.

No change to IR3 optimization passes, descriptor lowering, GMEM policy, WSI,
sync behavior or the 26.3.4 GMEM runtime.

Optional rollback:
`TU_A810_STAGE_NIR_CACHE=0`

Normal testing still only needs:
`TU_FRANE_PROFILE_ID=<game>`
