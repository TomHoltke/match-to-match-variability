"""
Final manuscript results.

Produces the outputs that go into the manuscript:

    Table 1   — Within-player CV% for the 19 metrics (main text)
    Figure 1  — Forest plot of per-metric position contrasts vs CM (main text)
    Table S1  — Player-season descriptives + CV% per position (supplement)
    Table S2  — Linear mixed-model fit & likelihood-ratio comparison (supplement)
    Table S3  — Per-metric Tukey HSD contrasts vs CM (supplement)

Everything is written to ``results/manuscript/``:
    Figure1_forest_position_vs_CM.png
    Table1.xlsx  TableS1.xlsx  TableS2.xlsx  TableS3.xlsx
    Manuscript_tables_and_figure.docx

Table S3 and Figure 1 are driven from one Tukey computation, so every number is
identical between them. Each contrast is reported as (Position − CM); the sign
is resolved from the actual statsmodels group order (``pairwise_tukeyhsd``
returns mean(group2) − mean(group1) with groups sorted alphabetically), so all
contrasts are consistently (Position − CM) and match the descriptive CV%.
"""

from __future__ import annotations

import warnings

import matplotlib.pyplot as plt
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

from src.config import CLEAN_FILE, PLAYER_SUMMARY_FILE, RESULTS_DIR

warnings.filterwarnings("ignore")

OUT = RESULTS_DIR / "manuscript"

POS_ORDER = ["CM", "CB", "FB", "AM", "CF"]   # CM = reference
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


def lrt(small, big):
    chi = 2 * (big.llf - small.llf)
    ddf = len(big.params) - len(small.params)
    return chi, ddf, 1 - sps.chi2.cdf(chi, ddf)


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


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(PLAYER_SUMMARY_FILE)
    df = df[df["position_group_primary"].isin(POS_ORDER)].copy()
    df["position_group_primary"] = pd.Categorical(df["position_group_primary"], categories=POS_ORDER)

    n_players = len(df)
    n_teams = df["team_id"].nunique()
    pos_n = {p: int((df["position_group_primary"] == p).sum()) for p in POS_ORDER}
    print(f"Cohort: n={n_players} players, {n_teams} teams; per-position n = {pos_n}")

    # Cohort descriptives reported in the Results (first paragraph). Computed from
    # the cleaned match table restricted to the analysis cohort.
    obs = pd.read_excel(CLEAN_FILE)
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
    m1 = mixedlm("cv_percent ~ C(metric_raw)", df_long,
                 groups=df_long["player_id"], re_formula="1").fit(method="lbfgs", maxiter=400)
    m2 = mixedlm("cv_percent ~ C(metric_raw) + C(position_group_primary)", df_long,
                 groups=df_long["player_id"], re_formula="1").fit(method="lbfgs", maxiter=400)
    m3 = mixedlm("cv_percent ~ C(metric_raw) * C(position_group_primary)", df_long,
                 groups=df_long["player_id"], re_formula="1").fit(method="lbfgs", maxiter=500)
    m1_ci = m1.conf_int()

    # ----- Tukey contrasts (one source of truth for Figure 1 and Table S3) -----
    def tukey_vs_cm(cv_col):
        sub = df[[cv_col, "position_group_primary"]].dropna().rename(columns={cv_col: "y"})
        sub["pos"] = sub["position_group_primary"].astype(str)
        tuk = pairwise_tukeyhsd(sub["y"], sub["pos"], alpha=0.05)
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

    tukey = {raw: tukey_vs_cm(f"{raw}_cv") for raw in RAW_ORDER}

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
    S2_COLS = ["Model", "k", "LogLik", "σ²Player", "σ²Resid", "ICC", "Δdf", "LRT χ², p (vs prior)"]
    v1p, v1r, icc1 = model_var(m1)
    v2p, v2r, icc2 = model_var(m2)
    v3p, v3r, icc3 = model_var(m3)
    chi12, ddf12, p12 = lrt(m1, m2)
    chi23, ddf23, p23 = lrt(m2, m3)
    s2_rows = [
        {"kind": "data", "cells": ["M1: CV% ~ Metric + (1|Player)", str(len(m1.params)),
                                   f"{m1.llf:.1f}", f"{v1p:.2f}", f"{v1r:.2f}", f"{icc1:.3f}", "—", "—"]},
        {"kind": "data", "cells": ["M2: M1 + Position main effect", str(len(m2.params)),
                                   f"{m2.llf:.1f}", f"{v2p:.2f}", f"{v2r:.2f}", f"{icc2:.3f}",
                                   str(ddf12), lrt_str(chi12, p12)]},
        {"kind": "data", "cells": ["M3: M2 + Metric × Position", str(len(m3.params)),
                                   f"{m3.llf:.1f}", f"{v3p:.2f}", f"{v3r:.2f}", f"{icc3:.3f}",
                                   str(ddf23), lrt_str(chi23, p23)]},
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

    # ----- Excel -----
    rows_to_df(T1_COLS, t1_rows).to_excel(OUT / "Table1.xlsx", index=False)
    rows_to_df(S1_COLS, s1_rows).to_excel(OUT / "TableS1.xlsx", index=False)
    rows_to_df(S2_COLS, s2_rows).to_excel(OUT / "TableS2.xlsx", index=False)
    rows_to_df(S3_COLS, s3_rows).to_excel(OUT / "TableS3.xlsx", index=False)
    print("Saved Excel: Table1, TableS1, TableS2, TableS3")

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
        ax.plot([r["ci_l"], r["ci_h"]], [y, y], color=col, lw=1.6, alpha=0.85, zorder=2)
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

    leg_p = [Line2D([0], [0], marker="o", color="w", markerfacecolor=PALETTE[p],
                    markeredgecolor=PALETTE[p], markersize=9, label=p) for p in CONTRAST]
    leg_s = [Line2D([0], [0], marker="o", color="w", markerfacecolor="grey",
                    markeredgecolor="grey", markersize=9, label="p < 0.05"),
             Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
                    markeredgecolor="grey", markersize=9, label="n.s.")]
    leg1 = ax.legend(handles=leg_p, title="Position", loc="upper right", frameon=False)
    ax.add_artist(leg1)
    ax.legend(handles=leg_s, loc="lower right", frameon=False)

    ax.grid(axis="x", alpha=0.3)
    ax.set_axisbelow(True)
    plt.subplots_adjust(left=0.30)
    fig_png = OUT / "Figure1_forest_position_vs_CM.png"
    fig.savefig(fig_png, dpi=600, bbox_inches="tight")
    plt.close(fig)
    print("Saved Figure 1 (png 600 dpi)")

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
    add_table(doc, S2_COLS, s2_rows, [1.70, 0.35, 0.75, 0.80, 0.80, 0.55, 0.45, 1.20])
    add_footnote(doc, "Abbreviations: k, number of fixed-effect parameters; LogLik, restricted "
                      "log-likelihood; σ²Player and σ²Resid, between-player and residual variance "
                      "components; ICC = σ²Player / (σ²Player + σ²Resid); Δdf, change in fixed-effect "
                      "degrees of freedom relative to the prior model; LRT, likelihood-ratio test.")

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
    doc.save(str(doc_path))
    print(f"Saved Word: {doc_path}")

    print("\n--- Table S3 / Figure 1 contrasts (Position - CM), sign-corrected ---")
    print(forest.pivot(index="Metric", columns="Position", values="beta")
          .reindex(FIG_LABELS)[CONTRAST].round(2).to_string())
    print(f"\nLRT M1->M2: chi2({ddf12})={chi12:.2f}, p={fmt_p(p12)} | "
          f"M2->M3: chi2({ddf23})={chi23:.2f}, p={fmt_p(p23)}")
    print(f"\nAll outputs in:\n  {OUT}")


if __name__ == "__main__":
    run()
