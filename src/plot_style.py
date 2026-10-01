"""
plot_style.py - One shared look for every chart in the project.

Colors do a job, they are not decoration:
  GRAY   = the random reference (the floor)
  BLUE   = single-signal baselines / a single series
  ORANGE = learned models (logistic regression)
Blue + orange were checked with a colorblind-safety validator (they stay
distinguishable for the common types of color blindness).
"""

import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
GRAY = "#9a9994"
BLUE = "#2a78d6"
ORANGE = "#eb6834"

ROLE_COLORS = {"reference": GRAY, "baseline": BLUE, "model": ORANGE}
ROLE_LABELS = {"reference": "random reference", "baseline": "single-signal baseline",
               "model": "learned model (logistic regression)"}


def setup():
    """Global matplotlib defaults: readable sizes, quiet axes."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.edgecolor": GRID,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT,
        "text.color": TEXT,
    })


def tidy(ax, value_axis="x"):
    """Light grid on the value axis only, no box around the plot."""
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.grid(axis=value_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def role_legend(fig, roles, **kwargs):
    """Legend explaining what each color means (identity is never color-only)."""
    handles = [plt.Rectangle((0, 0), 1, 1, color=ROLE_COLORS[r]) for r in roles]
    fig.legend(handles, [ROLE_LABELS[r] for r in roles], frameon=False, **kwargs)


def metric_panels(names, roles, means, title, path, stds=None, note=None):
    """2 x 2 grid, one panel per metric, one horizontal bar per method.

    names: method names (top to bottom); roles: "reference"/"baseline"/"model"
    means: dict metric -> list of values; stds: same shape, drawn as error bars.
    """
    metrics = list(means)
    colors = [ROLE_COLORS[r] for r in roles]
    y = list(range(len(names)))[::-1]  # first method at the top
    fig, axes = plt.subplots(2, 2, figsize=(11, 2.2 + 0.55 * len(names) * 2), sharey=True)
    for ax, metric in zip(axes.flat, metrics):
        vals = means[metric]
        errs = stds[metric] if stds else None
        ax.barh(y, vals, xerr=errs, color=colors, height=0.68,
                error_kw={"ecolor": TEXT_SECONDARY, "elinewidth": 1, "capsize": 3})
        top = max(v + (e if errs else 0) for v, e in zip(vals, errs or [0] * len(vals)))
        for i, v in enumerate(vals):
            end = v + (errs[i] if errs else 0)
            digits = 4 if metric == "AUPRC" else 3  # AUPRC values are tiny
            label = f"{v:.{digits}f}" + (f" ± {errs[i]:.{digits}f}" if errs else "")
            ax.text(end + top * 0.02, y[i], label, va="center", fontsize=9, color=TEXT_SECONDARY)
        if metric == "AUROC":
            ax.axvline(0.5, color=TEXT_SECONDARY, linestyle="--", linewidth=1)
            ax.text(0.5, len(names) - 0.45, " chance = 0.5", fontsize=8, color=TEXT_SECONDARY)
        ax.set_xlim(0, top * 1.45)
        if metric == "AUROC":  # AUROC can't exceed 1, so no ticks past it
            ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_title(metric, loc="left")
        ax.set_yticks(y, names)
        tidy(ax)
    fig.suptitle(title, x=0.01, y=0.995, ha="left", fontsize=14, fontweight="bold")
    if note:  # subtitle under the title
        fig.text(0.01, 0.955, note, ha="left", fontsize=10, color=TEXT_SECONDARY)
    present = [r for r in ["reference", "baseline", "model"] if r in roles]
    role_legend(fig, present, loc="lower left", ncol=len(present), bbox_to_anchor=(0.01, 0.0))
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig(path, dpi=150)
    plt.close(fig)
