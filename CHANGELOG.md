# Changelog

Every change to code, data or results after the first submission is listed
here, newest first. Each submitted version is tagged in git (`v1.0.0`, ...).

## Unreleased

- Table S2 and the statistical output now report marginal and conditional R²
  (Nakagawa & Schielzeth, 2013) per model (REML fits): metric alone explains
  74.1% of the variance in CV% (R²m = 0.741), position adds 0.05% and the
  metric × position interaction 1.8%; with the player random intercept,
  R²c = 0.799–0.817. No other number changed.
- Step 5 now also writes `results/manuscript/Statistical_output.txt` (and
  prints it): cohort, all descriptives, complete output of every mixed model,
  likelihood-ratio tests and all Tukey pairs, unrounded, with the optimizer used
  and any warnings raised during fitting (previously suppressed). No change to
  tables or figure.
- Mixed models: if the L-BFGS optimizer fails (numpy `LinAlgError: Singular
  matrix`, seen on a Windows installation), the fit falls back to BFGS, then
  Powell. These reach the same optimum; all tables are identical.
- Figure 1: confidence-interval bars end exactly at the CI limits (before, the
  line cap extended them by half a line width, so CIs ending just above zero
  looked as if they crossed it); legend keys drawn in the position colours;
  saved at 1200 dpi (was 600). No change to any number.
- Documentation: no event data were used. Only the Opta line-up file (f7) is
  used, for playing positions; the event file (f24) is read by DataBallPy
  but not used. No change to code or results.
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
