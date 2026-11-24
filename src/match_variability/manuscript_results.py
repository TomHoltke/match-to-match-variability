"""
Final manuscript results.

Produces the outputs that go into the manuscript:

    Table 1   — Within-player CV% for the 19 metrics (main text)
    Figure 1  — Forest plot of per-metric position contrasts vs CM (main text)
    Table S1  — Player-season descriptives + CV% per position (supplement)
    Table S2  — Linear mixed-model fit & likelihood-ratio comparison (supplement)
    Table S3  — Per-metric Tukey HSD contrasts vs CM (supplement)

Everything is written to ``results/manuscript/``:
    Figure1_forest_position_vs_CM.png   (1200 dpi)
    Table1.csv  TableS1.csv  TableS2.csv  TableS3.csv
    Manuscript_tables_and_figure.docx
    Statistical_output.txt   (also printed: cohort, all descriptives, full model
                              output, likelihood-ratio tests and all Tukey pairs,
                              unrounded, plus any warnings raised during fitting)

The CSV tables are plain text, so ``git diff`` shows at once whether a rerun
changed any reported number. The Word file is written with fixed timestamps so
that a rerun on the same software versions gives an identical file.

Table S3 and Figure 1 are driven from one Tukey computation, so every number is
identical between them. Each contrast is reported as (Position − CM); the sign
is resolved from the actual statsmodels group order (``pairwise_tukeyhsd``
returns mean(group2) − mean(group1) with groups sorted alphabetically), so all
contrasts are consistently (Position − CM) and match the descriptive CV%.
"""

from __future__ import annotations

import io
import warnings
import zipfile
from datetime import datetime, timezone

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from scipy import stats as sps
from statsmodels.formula.api import mixedlm
from statsmodels.stats.multicomp import pairwise_tukeyhsd

from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

from match_variability.config import ANALYSIS_POSITIONS, CLEAN_FILE, PLAYER_SUMMARY_FILE, RESULTS_DIR

warnings.filterwarnings("ignore")

OUT = RESULTS_DIR

POS_ORDER = ANALYSIS_POSITIONS              # CM = reference (first)
CONTRAST = ["CB", "FB", "AM", "CF"]

PALETTE = {
    "CB": "#792829",   # claret (anchor)
    "FB": "#d99441",   # warm ochre
    "AM": "#5b8aa6",   # slate blue
    "CF": "#3f6b3a",   # deep moss green
}

# family | raw column stem | figure label | table label (with unit) | raw dp
METRICS = [
    ("Running volume",      "total_distance_per_90",              "TD",               "TD (m)",                0),
    ("Running volume",      "high_speed_running_distance_per_90", "HSRD",             "HSRD (m)",              0),
    ("Running volume",      "sprinting_distance_per_90",          "SpD",              "SpD (m)",               0),
    ("Running volume",      "n_sprints_per_90",                   "Sp-count",         "Sp-count (n)",          1),
    ("Change of Direction", "CoD_low_per_90",                     "CoD-low",          "CoD-low (n)",           1),
    ("Change of Direction", "CoD_medium_per_90",                  "CoD-med",          "CoD-med (n)",           1),
    ("Change of Direction", "CoD_high_per_90",                    "CoD-high",         "CoD-high (n)",          1),
    ("Change of Direction", "CoD_total_per_90",                   "CoD-total",        "CoD-total (n)",         1),
    ("Acc-Dec counts",      "n_acc_3_per_90",                     "Acc-count",        "Acc-count (n)",         0),
    ("Acc-Dec counts",      "n_dec_3_per_90",                     "Dec-count",        "Dec-count (n)",         0),
    ("Acc-Dec counts",      "dist_acc_3_m_per_90",                "Acc-dist",         "Acc-dist (m)",          0),
    ("Acc-Dec counts",      "dist_dec_3_m_per_90",                "Dec-dist",         "Dec-dist (m)",          0),
    ("Acc-Dec magnitudes",  "mean_acc_magnitude_ms2",            "Acc-avg",          "Acc-avg (m·s⁻²)",       2),
    ("Acc-Dec magnitudes",  "mean_dec_magnitude_ms2",            "Dec-avg",          "Dec-avg (m·s⁻²)",       2),
    ("Acc-Dec magnitudes",  "peak_acc_ms2",                      "Acc-peak",         "Acc-peak (m·s⁻²)",      2),
    ("Acc-Dec magnitudes",  "peak_dec_ms2",                      "Dec-peak",         "Dec-peak (m·s⁻²)",      2),
    ("Sprint magnitudes",   "mean_sprint_dist_m",                "Mean sprint dist", "Mean sprint dist (m)",  2),
    ("Sprint magnitudes",   "mean_sprint_duration_s",            "Mean sprint dur",  "Mean sprint dur (s)",   2),
    ("Sprint magnitudes",   "peak_speed_ms",                     "Peak speed",       "Peak speed (m·s⁻¹)",    2),
]
RAW_ORDER = [m[1] for m in METRICS]
FAMILY_ORDER = ["Running volume", "Change of Direction", "Acc-Dec counts",
                "Acc-Dec magnitudes", "Sprint magnitudes"]
FIG_LABELS = [m[2] for m in METRICS]
FAMILY_OF = {m[2]: m[0] for m in METRICS}


# --------------------------------------------------------------------------- #
# Format helpers
# --------------------------------------------------------------------------- #
def msd(x, dp):
    x = pd.to_numeric(x, errors="coerce").dropna()
    return "NA" if x.empty else f"{x.mean():.{dp}f} ± {x.std(ddof=1):.{dp}f}"


def msd_range(x, dp):
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty:
        return "NA"
    return f"{x.mean():.{dp}f} ± {x.std(ddof=1):.{dp}f} ({x.min():.{dp}f}–{x.max():.{dp}f})"


def fmt_p(p):
    if p < 0.001:
        return "<.001"
    s = f"{p:.3f}"
    return s[1:] if s.startswith("0") else s


def p_eq(p):
    return "p<.001" if p < 0.001 else f"p={fmt_p(p)}"


def model_var(m):
    vp = float(m.cov_re.values[0][0])
    vr = float(m.scale)
    return vp, vr, vp / (vp + vr)


def r2_mixed(m):
    """Marginal and conditional R² (Nakagawa & Schielzeth, 2013).

    σ²fixed is the variance of the fixed-effect predictions Xβ over the fitted data;
    marginal R² = σ²fixed / (σ²fixed + σ²Player + σ²Resid) (fixed effects only),
    conditional R² = (σ²fixed + σ²Player) / (same)        (fixed + random effects).
    """
    vf = float(np.var(m.model.exog @ m.fe_params.to_numpy()))
    vp, vr, _ = model_var(m)
    total = vf + vp + vr
    return vf / total, (vf + vp) / total


def lrt(small, big):
    # log-likelihoods are not comparable across different fixed effects.
    # Δdf counts fixed effects only (k_fe); the random-effect variance
    # parameter is common to both models.
    assert not small.reml and not big.reml, "LRT on fixed effects requires ML (reml=False) fits"
    chi = 2 * (big.llf - small.llf)
    ddf = big.k_fe - small.k_fe
    return chi, ddf, sps.chi2.sf(chi, ddf)


def lrt_str(chi, p):
    return f"{chi:.2f}, p < .001" if p < 0.001 else f"{chi:.2f}, p = {fmt_p(p)}"


# --------------------------------------------------------------------------- #
# Word helpers
# --------------------------------------------------------------------------- #
def set_run(run, name="Times New Roman", size=None, bold=None, italic=None):
    run.font.name = name
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts"); rPr.append(rFonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rFonts.set(qn(a), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
         "right": WD_ALIGN_PARAGRAPH.RIGHT, "both": WD_ALIGN_PARAGRAPH.JUSTIFY}


def cell_text(cell, text, size=9, bold=False, italic=False, align="left", indent=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = ALIGN[align]
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    if indent is not None:
        p.paragraph_format.left_indent = Pt(indent)
    run = p.add_run(text)
    set_run(run, size=size, bold=bold, italic=italic)


def _border(cell, edge, sz):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = tcPr.find(qn("w:tcBorders"))
    if borders is None:
        borders = OxmlElement("w:tcBorders"); tcPr.append(borders)
    e = borders.find(qn(f"w:{edge}"))
    if e is None:
        e = OxmlElement(f"w:{edge}"); borders.append(e)
    e.set(qn("w:val"), "single"); e.set(qn("w:sz"), str(sz))
    e.set(qn("w:space"), "0"); e.set(qn("w:color"), "auto")


def booktabs(table):
    tblPr = table._tbl.tblPr
    nil = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}"); e.set(qn("w:val"), "nil"); nil.append(e)
    tblPr.append(nil)
    rows = table.rows
    for c in rows[0].cells:
        _border(c, "top", 8)
        _border(c, "bottom", 4)
    for c in rows[-1].cells:
        _border(c, "bottom", 8)


def fixed_widths(table, widths_in):
    table.autofit = False
    table.allow_autofit = False
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)
    for row in table.rows:
        for i, w in enumerate(widths_in):
            row.cells[i].width = Inches(w)


def add_caption(doc, label, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    set_run(p.add_run(label + " "), size=11, bold=True)
    set_run(p.add_run(text), size=11)


def add_footnote(doc, text):
    p = doc.add_paragraph()
    p.alignment = ALIGN["both"]
    p.paragraph_format.space_before = Pt(4)
    set_run(p.add_run(text), size=9)


def add_table(doc, cols, rows, widths):
    table = doc.add_table(rows=1, cols=len(cols))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, c in enumerate(cols):
        cell_text(table.rows[0].cells[i], c, size=9, bold=True,
                  align="left" if i == 0 else "center")
    for r in rows:
        cells = table.add_row().cells
        if r["kind"] in ("family", "panel"):
            cell_text(cells[0], r["cells"][0], size=9,
                      bold=(r["kind"] == "panel"), italic=(r["kind"] == "family"))
            for j in range(1, len(cols)):
                cell_text(cells[j], "", size=9)
        else:
            cell_text(cells[0], r["cells"][0], size=9, indent=10)
            for j in range(1, len(cols)):
                cell_text(cells[j], r["cells"][j], size=9, align="center")
    fixed_widths(table, widths)
    booktabs(table)
    return table


def rows_to_df(cols, rows):
    return pd.DataFrame([r["cells"] for r in rows], columns=cols)


_FIXED_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def save_docx_reproducibly(doc, path):
    """Save a Word document with fixed timestamps, so reruns give identical bytes.

    python-docx stamps the current time into the document properties and into
    every entry of the .docx zip archive; both are replaced by a fixed date.
    """
    doc.core_properties.created = _FIXED_TIME
    doc.core_properties.modified = _FIXED_TIME
    buf = io.BytesIO()
    doc.save(buf)
    with zipfile.ZipFile(buf) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            info = zipfile.ZipInfo(item.filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(info, src.read(item.filename))


# --------------------------------------------------------------------------- #
# Full statistical output (unrounded), for reviewers and the supplement
# --------------------------------------------------------------------------- #
def _g(x):
    """Unrounded number, 6 significant digits (scientific for very small p)."""
    return f"{x:.6g}"


def _section(lines, title):
    lines += ["", "=" * 100, title, "=" * 100]


def describe(values):
    v = pd.to_numeric(values, errors="coerce").dropna()
    return {"n": len(v), "mean": v.mean(), "SD": v.std(ddof=1), "min": v.min(),
            "median": v.median(), "max": v.max()}


def tukey_table(tuk):
    """All pairs of a statsmodels Tukey HSD result, unrounded.

    ``meandiff`` is mean(group2) - mean(group1); q = |meandiff| / SE.
    """
    g = list(tuk.groupsunique)
    pairs = [(g[i], g[j]) for i in range(len(g)) for j in range(i + 1, len(g))]
    return pd.DataFrame({
        "group1": [a for a, _ in pairs], "group2": [b for _, b in pairs],
        "meandiff": tuk.meandiffs, "SE": tuk.std_pairs,
        "q": abs(tuk.meandiffs) / tuk.std_pairs,
        "lower_95": tuk.confint[:, 0], "upper_95": tuk.confint[:, 1],
        "p_adj": tuk.pvalues, "reject": tuk.reject,
    })


def fixed_effects_table(m):
    k = m.k_fe
    ci = m.conf_int().iloc[:k]
    return pd.DataFrame({"estimate": m.fe_params, "SE": m.bse_fe, "z": m.tvalues.iloc[:k],
                         "p": m.pvalues.iloc[:k], "lower_95": ci[0], "upper_95": ci[1]})


def statistical_report(df, obs, n_matches, fits, fit_warnings, lrts, tukey_objs, tukey_warnings):
    import platform, scipy, statsmodels
    L = ["FULL STATISTICAL OUTPUT: match-to-match variability (step 5)",
         "All numbers unrounded (6 significant digits) unless printed by statsmodels itself.",
         f"Software: Python {platform.python_version()}, numpy {np.__version__}, "
         f"pandas {pd.__version__}, scipy {scipy.__version__}, statsmodels {statsmodels.__version__}"]
    fmt = dict(float_format=_g)

    # ---- 1. Cohort ----
    _section(L, "1. COHORT")
    L.append(f"Players: {len(df)}   Teams: {df['team_id'].nunique()}   "
             f"Player-match observations: {len(obs)}   Matches: {n_matches}")
    L.append("Players per position: " + ", ".join(
        f"{p} = {int((df['position_group_primary'] == p).sum())}" for p in POS_ORDER))
    coh = pd.DataFrame({lab: describe(df[col]) for lab, col in [
        ("Matches played per player", "matches_played"),
        ("Mean playing duration per player (min)", "playing_duration_mean")]}).T
    L.append(coh.to_string(**fmt))

    # ---- 2. Descriptives ----
    for suffix, title in [("_mean", "2a. DESCRIPTIVES: player-season mean (raw units), across players"),
                          ("_cv", "2b. DESCRIPTIVES: within-player match-to-match CV%, across players")]:
        _section(L, title)
        rows = []
        for _, raw, _, tab_lab, _ in METRICS:
            col = f"{raw}{suffix}"
            rows.append({"metric": tab_lab, "group": "All", **describe(df[col])})
            for pos in POS_ORDER:
                rows.append({"metric": tab_lab, "group": pos,
                             **describe(df.loc[df["position_group_primary"] == pos, col])})
        L.append(pd.DataFrame(rows).to_string(index=False, **fmt))

    # ---- 3. Mixed models ----
    _section(L, "3. LINEAR MIXED-EFFECTS MODELS (statsmodels MixedLM, random intercept per player)")
    L.append("Reference levels: metric = TD (total_distance_per_90), position = CM.")
    L.append("REML fits give the estimates, variance components and ICC (Table 1, Table S2);")
    L.append("ML fits give the log-likelihoods for the likelihood-ratio tests (Table S2).")
    L.append("Warnings are recorded over the whole optimisation, including intermediate trial")
    L.append("values; 'Converged' and all estimates refer to the final solution.")
    for label, m in fits.items():
        vp, vr, icc = model_var(m)
        L += ["", "-" * 100, f"{label}   formula: {m.model.formula}", "-" * 100]
        L.append(f"Method: {'REML' if m.reml else 'ML'}   Optimizer: {m.optimizer_used}   "
                 f"Converged: {m.converged}   "
                 f"n obs: {int(m.nobs)}   n players: {len(m.model.group_labels)}   "
                 f"fixed effects k: {m.k_fe}")
        L.append(f"Log-likelihood: {_g(m.llf)}" +
                 ("" if m.reml else f"   AIC: {_g(m.aic)}   BIC: {_g(m.bic)}"))
        r2m, r2c = r2_mixed(m)
        L.append(f"Variance player (random intercept): {_g(vp)}   Residual variance: {_g(vr)}   "
                 f"ICC: {_g(icc)}")
        L.append(f"Marginal R2 (fixed effects): {_g(r2m)}   Conditional R2 (fixed + random): {_g(r2c)}")
        w = fit_warnings.get(label, [])
        L.append("Warnings during fitting: " + ("; ".join(w) if w else "none"))
        L += ["", "statsmodels summary:", m.summary().as_text(), "",
              "Fixed effects, unrounded (Wald z tests, 95% CI):",
              fixed_effects_table(m).to_string(**fmt)]

    # ---- 3b. Explained variance ----
    _section(L, "3b. EXPLAINED VARIANCE (Nakagawa & Schielzeth 2013 R2, REML fits)")
    L.append("Marginal R2 = var(fixed predictions) / (var(fixed predictions) + var player + var residual);")
    L.append("conditional R2 adds the player variance to the numerator. Delta = change vs the prior model.")
    rows, prev = [], None
    for label, m in fits.items():
        if not m.reml:
            continue
        r2m, r2c = r2_mixed(m)
        rows.append({"model": label, "marginal_R2": r2m, "conditional_R2": r2c,
                     "delta_marginal_R2": float("nan") if prev is None else r2m - prev})
        prev = r2m
    L.append(pd.DataFrame(rows).to_string(index=False, na_rep="-", **fmt))

    # ---- 4. Likelihood-ratio tests ----
    _section(L, "4. LIKELIHOOD-RATIO TESTS (ML fits)")
    for name, (chi, ddf, p) in lrts.items():
        L.append(f"{name}: chi2 = {_g(chi)}, df = {ddf}, p = {_g(p)}")

    # ---- 5. Tukey HSD ----
    _section(L, "5. TUKEY HSD PER METRIC (within-player CV%, all 10 position pairs, family-wise alpha = .05)")
    L.append("meandiff = mean(group2) - mean(group1). Figure 1 and Table S3 show Position - CM.")
    for _, raw, _, tab_lab, _ in METRICS:
        tuk = tukey_objs[raw]
        L += ["", f"--- {tab_lab} ---",
              f"q critical: {_g(tuk.q_crit)}   df (residual): {int(tuk.df_total)}"]
        w = tukey_warnings.get(raw, [])
        if w:
            L.append("Warnings: " + "; ".join(w))
        L.append(tukey_table(tuk).to_string(index=False, **fmt))
    return "\n".join(L) + "\n"


def _warning_texts(caught):
    return sorted({f"{w.category.__name__}: {w.message}" for w in caught})


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(PLAYER_SUMMARY_FILE)
    df = df[df["position_group_primary"].isin(POS_ORDER)].copy()
    df["position_group_primary"] = pd.Categorical(df["position_group_primary"], categories=POS_ORDER)

    n_players = len(df)
    n_teams = df["team_id"].nunique()
    pos_n = {p: int((df["position_group_primary"] == p).sum()) for p in POS_ORDER}
    print(f"Cohort: n={n_players} players, {n_teams} teams; per-position n = {pos_n}")

    # Cohort descriptives reported in the Results (first paragraph). Computed from
    # the cleaned match table restricted to the analysis cohort.
    obs = pd.read_csv(CLEAN_FILE)
    obs = obs[obs["player_id"].isin(df["player_id"])]
    n_match_obs = len(obs)                                   # player-match observations
    n_matches = obs.drop_duplicates(["team_id", "MD"]).shape[0] // 2   # distinct games (2 teams each)
    mp, dur = df["matches_played"], df["playing_duration_mean"]
    print(f"  {n_match_obs:,} player-match observations across {n_matches} matches")
    print(f"  matches per player = {mp.mean():.1f} ± {mp.std(ddof=1):.1f}; "
          f"playing duration = {dur.mean():.1f} ± {dur.std(ddof=1):.1f} min")

    cv_cols = [f"{raw}_cv" for raw in RAW_ORDER]
    df_long = df.melt(
        id_vars=["player_id", "team_id", "position_group_primary"],
        value_vars=cv_cols, var_name="metric", value_name="cv_percent",
    ).dropna(subset=["cv_percent"])
    df_long["metric_raw"] = df_long["metric"].str[:-3]
    df_long["metric_raw"] = pd.Categorical(df_long["metric_raw"], categories=RAW_ORDER)
    df_long["position_group_primary"] = pd.Categorical(df_long["position_group_primary"], categories=POS_ORDER)
    n_obs = len(df_long)

    # ----- Models 1-3 -----
    # [REVIEW FIX 2026-10-16] Each model is fitted twice:
    #   m*    — REML (statsmodels default): variance components, ICC, Table 1 β/CI/p
    #   m*_ml — ML (reml=False): log-likelihood and likelihood-ratio tests (Table S2)
    # Previously the LRTs compared REML fits, which is invalid for models that
    # differ in their fixed effects.
    formulas = [("cv_percent ~ C(metric_raw)", 400),
                ("cv_percent ~ C(metric_raw) + C(position_group_primary)", 400),
                ("cv_percent ~ C(metric_raw) * C(position_group_primary)", 500)]

    fit_warnings = {}

    def fit(label, formula, maxiter, reml):
        # L-BFGS first (gives the reported results). Depending on the numpy/scipy
        # build, an optimizer trial step can make the fixed-effect matrix exactly
        # singular (numpy LinAlgError, seen on Windows); then fall back to BFGS and
        # Powell, which reach the same optimum. Warnings are recorded (not shown)
        # and listed, with the optimizer used, in the statistical output.
        model = mixedlm(formula, df_long, groups=df_long["player_id"], re_formula="1")
        notes, m = [], None
        for method, iters in (("lbfgs", maxiter), ("bfgs", 2000), ("powell", 20000)):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    m = model.fit(method=method, maxiter=iters, reml=reml)
                except (np.linalg.LinAlgError, ValueError) as e:
                    notes.append(f"optimizer {method} failed ({type(e).__name__}: {e})")
                    continue
            if m.converged:
                break
            notes.append(f"optimizer {method} did not converge")
        if m is None:
            raise RuntimeError(f"{label}: no optimizer could fit the model: {notes}")
        m.optimizer_used = method
        if method != "lbfgs":
            print(f"NOTE: {label} fitted with {method} ({'; '.join(notes)})")
        fit_warnings[label] = notes + _warning_texts(caught)
        return m

    m1, m2, m3 = (fit(f"M{i} (REML)", f, it, reml=True) for i, (f, it) in enumerate(formulas, 1))
    m1_ml, m2_ml, m3_ml = (fit(f"M{i} (ML)", f, it, reml=False)
                           for i, (f, it) in enumerate(formulas, 1))
    for m in (m1, m2, m3, m1_ml, m2_ml, m3_ml):
        if not m.converged:
            print(f"WARNING: model did not converge (reml={m.reml}): {m.model.formula}")
    m1_ci = m1.conf_int()

    # ----- Tukey contrasts (one source of truth for Figure 1 and Table S3) -----
    tukey_objs, tukey_warnings = {}, {}

    def tukey_vs_cm(raw):
        cv_col = f"{raw}_cv"
        sub = df[[cv_col, "position_group_primary"]].dropna().rename(columns={cv_col: "y"})
        sub["pos"] = sub["position_group_primary"].astype(str)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            tuk = pairwise_tukeyhsd(sub["y"], sub["pos"], alpha=0.05)
        tukey_objs[raw], tukey_warnings[raw] = tuk, _warning_texts(caught)
        tdf = pd.DataFrame(tuk._results_table.data[1:], columns=tuk._results_table.data[0])
        out = {}
        for pos in CONTRAST:
            row = tdf[((tdf["group1"] == "CM") & (tdf["group2"] == pos)) |
                      ((tdf["group1"] == pos) & (tdf["group2"] == "CM"))].iloc[0]
            diff, lo, hi = float(row["meandiff"]), float(row["lower"]), float(row["upper"])
            if row["group1"] == pos:          # meandiff = CM - pos -> flip to pos - CM
                diff, lo, hi = -diff, -hi, -lo
            out[pos] = dict(diff=diff, lo=lo, hi=hi, p=float(row["p-adj"]), sig=bool(row["reject"]))
        return out

    tukey = {raw: tukey_vs_cm(raw) for raw in RAW_ORDER}

    forest_rows = []
    for fam, raw, fig_lab, *_ in METRICS:
        for pos in CONTRAST:
            t = tukey[raw][pos]
            forest_rows.append({"Metric": fig_lab, "Position": pos, "beta": t["diff"],
                                "ci_l": t["lo"], "ci_h": t["hi"], "p": t["p"], "sig": t["sig"]})
    forest = pd.DataFrame(forest_rows)

    # ----- Table 1 -----
    T1_COLS = ["Metric", "Player-season mean ± SD", "CV% mean ± SD (range)",
               "ΔCV% vs TD [95% CI] (β)", "p-value"]
    t1_rows = []
    for fam in FAMILY_ORDER:
        t1_rows.append({"kind": "family", "cells": [fam, "", "", "", ""]})
        for _, raw, fig_lab, tab_lab, dp in [m for m in METRICS if m[0] == fam]:
            mean_col, cv_col = f"{raw}_mean", f"{raw}_cv"
            if raw == "total_distance_per_90":
                beta_str, p_str = "—", "—"
            else:
                term = f"C(metric_raw)[T.{raw}]"
                b = m1.params[term]; lo, hi = m1_ci.loc[term].values
                beta_str = f"{b:.1f} [{lo:.1f}, {hi:.1f}]"
                p_str = fmt_p(m1.pvalues[term])
            t1_rows.append({"kind": "data", "cells": [
                tab_lab, msd(df[mean_col], dp), msd_range(df[cv_col], 1), beta_str, p_str]})

    # ----- Table S1 -----
    S1_COLS = ["Metric", "CM (ref.)", "CB", "FB", "AM", "CF"]
    s1_rows = []
    for panel_label, suffix, dp_mode in [
        ("A. Player-season mean ± SD (raw units)", "_mean", "raw"),
        ("B. Within-player match-to-match CV% mean ± SD (range)", "_cv", "cv"),
    ]:
        s1_rows.append({"kind": "panel", "cells": [panel_label] + [""] * 5})
        for fam in FAMILY_ORDER:
            s1_rows.append({"kind": "family", "cells": [fam] + [""] * 5})
            for _, raw, fig_lab, tab_lab, dp in [m for m in METRICS if m[0] == fam]:
                col = f"{raw}{suffix}"
                cells = [tab_lab]
                for pos in POS_ORDER:
                    vals = df.loc[df["position_group_primary"] == pos, col]
                    cells.append(msd(vals, dp) if dp_mode == "raw" else msd_range(vals, 1))
                s1_rows.append({"kind": "data", "cells": cells})

    # ----- Table S2 -----
    S2_COLS = ["Model", "k", "LogLik", "σ²Player", "σ²Resid", "ICC", "R²m", "R²c", "Δdf",
               "LRT χ², p (vs prior)"]
    v1p, v1r, icc1 = model_var(m1)
    v2p, v2r, icc2 = model_var(m2)
    v3p, v3r, icc3 = model_var(m3)
    (r2m1, r2c1), (r2m2, r2c2), (r2m3, r2c3) = r2_mixed(m1), r2_mixed(m2), r2_mixed(m3)
    # [REVIEW FIX 2026-10-16] LRT + LogLik from ML fits; k = fixed effects only
    # (was len(params), which also counted the random-intercept variance).
    chi12, ddf12, p12 = lrt(m1_ml, m2_ml)
    chi23, ddf23, p23 = lrt(m2_ml, m3_ml)
    s2_rows = [
        {"kind": "data", "cells": ["M1: CV% ~ Metric + (1|Player)", str(m1_ml.k_fe),
                                   f"{m1_ml.llf:.1f}", f"{v1p:.2f}", f"{v1r:.2f}", f"{icc1:.3f}",
                                   f"{r2m1:.3f}", f"{r2c1:.3f}", "—", "—"]},
        {"kind": "data", "cells": ["M2: M1 + Position main effect", str(m2_ml.k_fe),
                                   f"{m2_ml.llf:.1f}", f"{v2p:.2f}", f"{v2r:.2f}", f"{icc2:.3f}",
                                   f"{r2m2:.3f}", f"{r2c2:.3f}", str(ddf12), lrt_str(chi12, p12)]},
        {"kind": "data", "cells": ["M3: M2 + Metric × Position", str(m3_ml.k_fe),
                                   f"{m3_ml.llf:.1f}", f"{v3p:.2f}", f"{v3r:.2f}", f"{icc3:.3f}",
                                   f"{r2m3:.3f}", f"{r2c3:.3f}", str(ddf23), lrt_str(chi23, p23)]},
    ]

    # ----- Table S3 -----
    S3_COLS = ["Metric", "CB − CM", "FB − CM", "AM − CM", "CF − CM"]
    s3_rows = []
    for fam in FAMILY_ORDER:
        s3_rows.append({"kind": "family", "cells": [fam] + [""] * 4})
        for _, raw, fig_lab, tab_lab, dp in [m for m in METRICS if m[0] == fam]:
            cells = [tab_lab]
            for pos in CONTRAST:
                t = tukey[raw][pos]
                star = "*" if t["sig"] else ""
                cells.append(f"{t['diff']:+.2f}{star} [{t['lo']:+.2f}, {t['hi']:+.2f}] ({p_eq(t['p'])})")
            s3_rows.append({"kind": "data", "cells": cells})

    # ----- Tables as CSV (utf-8 with BOM so Excel shows ±, Δ and χ correctly) -----
    for name, cols, rows in [("Table1", T1_COLS, t1_rows), ("TableS1", S1_COLS, s1_rows),
                             ("TableS2", S2_COLS, s2_rows), ("TableS3", S3_COLS, s3_rows)]:
        rows_to_df(cols, rows).to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
    print("Saved tables: Table1, TableS1, TableS2, TableS3 (.csv)")

    # ----- Figure 1 -----
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    fig, ax = plt.subplots(figsize=(9.2, 11.5))
    y_pos = {lab: i for i, lab in enumerate(FIG_LABELS)}

    cursor = -0.5
    fam_blocks = []
    idx = 0
    for i, fam in enumerate(FAMILY_ORDER):
        members = [m for m in FIG_LABELS if FAMILY_OF[m] == fam]
        w = len(members)
        if i % 2 == 0:
            ax.axhspan(cursor, cursor + w, color="#f3eeec", zorder=0)
        fam_blocks.append((fam, idx, idx + w - 1))
        idx += w
        cursor += w

    offsets = {"CB": -0.30, "FB": -0.10, "AM": 0.10, "CF": 0.30}
    for _, r in forest.iterrows():
        y = y_pos[r["Metric"]] + offsets[r["Position"]]
        col = PALETTE[r["Position"]]
        # butt caps: the bar ends exactly at the CI limits (matplotlib's default
        # "projecting" cap extends it by half a line width, so a CI ending just
        # above zero, e.g. HSRD CB-CM lower limit +0.04, looked as if it crossed zero)
        ax.plot([r["ci_l"], r["ci_h"]], [y, y], color=col, lw=1.6, alpha=0.85, zorder=2,
                solid_capstyle="butt")
        ax.scatter(r["beta"], y, s=46,
                   facecolor=col if r["sig"] else "white",
                   edgecolor=col, linewidth=1.6, zorder=3)

    ax.axvline(0, color="black", ls="--", lw=1, alpha=0.6)
    ax.set_yticks(list(y_pos.values()))
    ax.set_yticklabels(FIG_LABELS, fontsize=10)
    ax.set_ylim(len(FIG_LABELS) - 0.5, -0.5)
    ax.set_xlabel("Δ CV% vs Central Midfielder (95% CI)", fontsize=11)

    trans = ax.get_yaxis_transform()
    LINE_X, TEXT_X = -0.255, -0.285
    for fam, first, last in fam_blocks:
        ax.plot([LINE_X, LINE_X], [first - 0.42, last + 0.42], transform=trans,
                color="#777", lw=1.2, clip_on=False, zorder=1)
        ax.text(TEXT_X, (first + last) / 2, fam, transform=trans, rotation=90,
                va="center", ha="center", fontsize=10, color="#444", clip_on=False)

    # Legend keys drawn like the plot marks: a CI bar in the same colour as the dot
    leg_p = [Line2D([0], [0], marker="o", color=PALETTE[p], lw=1.6, alpha=0.85,
                    solid_capstyle="butt", markerfacecolor=PALETTE[p],
                    markeredgecolor=PALETTE[p], markersize=9, label=p) for p in CONTRAST]
    leg_s = [Line2D([0], [0], marker="o", color="grey", lw=1.6, solid_capstyle="butt",
                    markerfacecolor="grey", markeredgecolor="grey", markersize=9,
                    label="p < 0.05"),
             Line2D([0], [0], marker="o", color="grey", lw=1.6, solid_capstyle="butt",
                    markerfacecolor="white", markeredgecolor="grey", markersize=9,
                    label="n.s.")]
    leg1 = ax.legend(handles=leg_p, title="Position", loc="upper right", frameon=False)
    ax.add_artist(leg1)
    ax.legend(handles=leg_s, loc="lower right", frameon=False)

    ax.grid(axis="x", alpha=0.3)
    ax.set_axisbelow(True)
    plt.subplots_adjust(left=0.30)
    fig_png = OUT / "Figure1_forest_position_vs_CM.png"
    fig.savefig(fig_png, dpi=1200, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    print("Saved Figure 1 (png 1200 dpi)")

    # ----- Word document -----
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    sec.left_margin = sec.right_margin = Cm(2.0)
    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(11)

    add_caption(doc, "Table 1.",
                f"Within-player CV% for the {len(METRICS)} metrics. Player-season mean ± SD in raw "
                f"units; CV% across each player's matches; n = {n_players} players.")
    add_table(doc, T1_COLS, t1_rows, [1.55, 1.45, 1.65, 1.55, 0.55])
    add_footnote(doc, "TD, total distance; HSRD, high-speed running distance; SpD, sprint distance; "
                      "CoD, change of direction; Acc/Dec, acceleration/deceleration; "
                      "CI, confidence interval.")

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = ALIGN["center"]
    p.add_run().add_picture(str(fig_png), width=Inches(5.3))
    add_caption(doc, "Figure 1.",
                "Per-metric position contrasts in CV% vs central midfielders (CM; dashed line at zero). "
                "Points are ΔCV% with 95% CI bars; filled = Tukey p < .05, open = non-significant. "
                "CB, centre-back; FB, full-back; AM, attacking midfielder; CF, centre-forward.")

    doc.add_page_break()
    hp = doc.add_paragraph()
    hp.paragraph_format.space_after = Pt(6)
    set_run(hp.add_run("Supplementary material"), size=13, bold=True)

    add_caption(doc, "Table S1.",
                "Player-season descriptives and within-player match-to-match coefficient of variation "
                f"(CV%) for each of the {len(METRICS)} physical-demand metrics per playing position. "
                "Panel A reports player-season means ± SD in the metric's raw unit; panel B reports "
                "within-player CV% mean ± SD (range). Sample sizes per position were "
                f"CM n = {pos_n['CM']}, CB n = {pos_n['CB']}, FB n = {pos_n['FB']}, "
                f"AM n = {pos_n['AM']}, CF n = {pos_n['CF']}. CM is the reference position in the "
                "linear mixed-effects models.")
    add_table(doc, S1_COLS, s1_rows, [1.30, 1.06, 1.06, 1.06, 1.06, 1.06])
    add_footnote(doc, "Abbreviations: CM, central midfielder; CB, centre-back; FB, full-back; "
                      "AM, attacking midfielder; CF, centre-forward. Running-volume, change-of-direction "
                      "and acceleration–deceleration count and distance metrics are normalised to 90 min "
                      "of playing time; per-event magnitudes (Acc-avg, Dec-avg, mean sprint distance, "
                      "mean sprint duration) and match-peak values (Acc-peak, Dec-peak, peak speed) are "
                      "not per-90 normalised. Speed-zone, acceleration–deceleration, sprint and "
                      "change-of-direction thresholds are defined in the Methods. CV%, within-player "
                      "coefficient of variation across the player's eligible matches.")

    add_caption(doc, "Table S2.",
                "Linear mixed-effects model fit and likelihood-ratio model comparison. Models were "
                f"fitted on within-player CV% values (n = {n_obs:,}; {n_players} players × {len(METRICS)} "
                "metrics). Model 1 establishes the metric hierarchy; Model 2 adds a main effect of "
                "Position; Model 3 adds the Metric × Position interaction.")
    add_table(doc, S2_COLS, s2_rows, [1.45, 0.30, 0.68, 0.62, 0.62, 0.48, 0.48, 0.48, 0.38, 1.10])
    # [REVIEW FIX 2026-10-16] footnote: LogLik/LRT are ML; variance components are REML.
    add_footnote(doc, "Abbreviations: k, number of fixed-effect parameters; LogLik, maximum "
                      "log-likelihood (ML fit); σ²Player and σ²Resid, between-player and residual "
                      "variance components (REML fit); ICC = σ²Player / (σ²Player + σ²Resid); "
                      "R²m and R²c, marginal (fixed effects) and conditional (fixed and random "
                      "effects) R² (Nakagawa & Schielzeth, 2013; REML fit); Δdf, "
                      "change in fixed-effect degrees of freedom relative to the prior model; LRT, "
                      "likelihood-ratio test computed from maximum-likelihood (ML) fits, as REML "
                      "likelihoods are not comparable between models with different fixed effects.")

    add_caption(doc, "Table S3.",
                "Per-metric Tukey HSD post-hoc contrasts of within-player CV% for each non-reference "
                "position relative to the central-midfielder reference (Position − CM, in CV percentage "
                "points). Each cell reports Δ CV%, 95% confidence interval, and Tukey-adjusted p-value. "
                "Family-wise α = 0.05 was controlled within each metric across the ten position pairs. "
                "These per-metric contrasts are the numbers plotted in Figure 1 in the main text.")
    add_table(doc, S3_COLS, s3_rows, [1.05, 1.40, 1.40, 1.40, 1.40])
    add_footnote(doc, "* indicates Tukey-adjusted p < 0.05. Abbreviations: CM, central midfielder "
                      "(reference); CB, centre-back; FB, full-back; AM, attacking midfielder; "
                      "CF, centre-forward. ΔCV%, difference in within-player coefficient of variation "
                      "(CV percentage points).")

    doc_path = OUT / "Manuscript_tables_and_figure.docx"
    save_docx_reproducibly(doc, doc_path)
    print(f"Saved Word: {doc_path}")

    # ----- Full statistical output (printed and saved) -----
    report = statistical_report(
        df, obs, n_matches,
        fits={"M1 (REML)": m1, "M2 (REML)": m2, "M3 (REML)": m3,
              "M1 (ML)": m1_ml, "M2 (ML)": m2_ml, "M3 (ML)": m3_ml},
        fit_warnings=fit_warnings,
        lrts={"M1 -> M2 (position main effect)": (chi12, ddf12, p12),
              "M2 -> M3 (metric x position interaction)": (chi23, ddf23, p23)},
        tukey_objs=tukey_objs, tukey_warnings=tukey_warnings)
    report_path = OUT / "Statistical_output.txt"
    report_path.write_text(report, encoding="utf-8")
    print("\n" + report)
    print(f"Saved full statistical output: {report_path}")

    print("\n--- Table S3 / Figure 1 contrasts (Position - CM), sign-corrected ---")
    print(forest.pivot(index="Metric", columns="Position", values="beta")
          .reindex(FIG_LABELS)[CONTRAST].round(2).to_string())
    print(f"\nLRT M1->M2: chi2({ddf12})={chi12:.2f}, p={fmt_p(p12)} | "
          f"M2->M3: chi2({ddf23})={chi23:.2f}, p={fmt_p(p23)}")
    print(f"\nAll outputs in:\n  {OUT}")
