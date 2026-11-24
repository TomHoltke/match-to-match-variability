# Changelog

Every change to code, data or results after the first submission is listed
here, newest first. Each submitted version is tagged in git (`v1.0.0`, ...).

## Unreleased

- Shared data: `shirt_num` and `column_id` (`home_<shirt>`) removed from all
  files in `data/shared/` (step 3), because with the public fixture list the
  shirt number could identify players. Not used by the analysis; all tables
  and the figure unchanged.
- Repository restructured: installable package (`src/match_variability/`),
  numbered scripts per stage, shared data and tables as CSV, tests that check
  the reproduction, documentation of every column and of the tracking pipeline.
  All numbers unchanged.
- The tracking pipeline (raw data to shared input) is now included as runnable
  code (steps 1 to 3), including the pseudonymisation step.
- Likelihood-ratio tests (Table S2) now compare maximum-likelihood fits; REML
  log-likelihoods are not comparable between models with different fixed
  effects. `k` now counts fixed-effect parameters only. Coefficients, variance
  components and ICC are still from REML fits and did not change.
