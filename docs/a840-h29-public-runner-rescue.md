# A840 H2.9 rescue via PUBLIC GitHub runner, PRIVATE source (2026-10-31)

This workflow uses public `Frane12/Testturnip` **only for compute** after private-repository Actions jobs failed before acquiring a runner (0 billable runner milliseconds). The validated Stage 1 ARM64 build proves this public runner can compile a Mesa27 KGSL Turnip library.

## One-time GitHub credential setup

1. Create a **fine-grained Personal Access Token** at GitHub > Settings > Developer settings > Personal access tokens > Fine-grained tokens. Set *Repository access* to **Only selected repositories → Frane12/Turnip-Neuro-Private**, with **Contents: Read and write** (Metadata: Read implicit). Do not enable extra permissions or set an unnecessarily long expiration.
2. In public `Frane12/Testturnip`, open **Settings → Secrets and variables → Actions → New repository secret**. Name it **`DRNAS_NEURO_PRIVATE_TOKEN`** and paste the token there. **Never commit, paste into workflow YAML, or send the PAT in chat.**
3. Re-run the failed build `41182108446` (or trigger a new push to `experiment/a840-public-ci-1031`). Only the selected private repository is accessible with the PAT.
4. If compilation succeeds, a **DRAFT** release is created **inside private** `Frane12/Turnip-Neuro-Private`. No source, installer ZIP or Actions artifact is uploaded to the public Testturnip repo. On compiler/patch failures, detailed logs go into a separate private DRAFT release.

## Source and build pins

- Public baseline: `Frane12/Testturnip`, experimental branch `experiment/a840-public-ci-1031`, inheriting Stage 1 observer from commit `e982877c9d250abaa7cf0fca76ac45757204e681`.
- PRIVATE H2.9 source immutable commit: `f1536cb39855cd904fab85387bdbb8bb13ce09e3`.
- Mesa 27 immutable upstream commit: `1c3a936490f9f0951188218e136cd03bca497386`.
- Test output: `DRNAS-A840-MESA27-H29-POLICY-PRIVATE.zip` in a private draft release.

## Exact scope and safety

This experimental port links the Stage1 CPU observer plus the ORIGINAL A840 H2.9 CPU policy for GMEM/SYSMEM decisions, with completed-pass GPU feedback. `TU_FRANE_A840_ADAPTIVE=1` **explicitly enables** the port; its default is **OFF**. Inactive/invalid policy decisions preserve native Mesa fallback. `TU_FRANE_A840_AGGRESSIVE` chooses historical aggressive thresholds after policy activation.

**NOT YET PORTED:** legacy H2.7 shader/TEX alternate variants, extensive A810 S Ultimate overlays, IR3 scheduling, original depth/UBWC tweaks, or NPU integration. Compile success alone cannot prove clean A840 rendering. Keep known-working H2.9 unchanged and use an isolated Winlator container.

Private-source code is temporarily present on a public GitHub-hosted runner during compilation. Build/patch logs are redirected away from public Actions output and, if present on failure, saved in PRIVATE draft releases. Review repository collaborators and avoid untrusted workflow modifications because public-repository code that can use a private-repo PAT is security-sensitive.

## Known status

Public rescue workflow run `41182108446` **executed** (unlike private runner attempts) but failed at the explicit missing-secret preflight. No source was cloned, no driver compiled, and no ZIP created at that run.
