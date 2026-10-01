"""
diagrams.py - Draw the two explanatory figures for the README and report.

  output/pipeline.png             the whole project as a flow diagram
  output/example_explanation.png  one prediction with its top 3 supporting paths

Drawn with plain matplotlib (no extra dependency). The example figure reads its
paths and numbers from output/phase4_paths.csv and output/phase4_contributions.csv,
so nothing is typed in by hand. Run after explain.py:
    .venv/bin/python src/diagrams.py
"""

import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

import plot_style as style
from common import OUTPUT_DIR

EXAMPLE_RANK = 8  # Paclitaxel -> prostate cancer: short paths, easy to read
BOX_FILL = "#eef3fb"
GUARD_FILL = "#fdf0ea"


def box(ax, x, y, w, h, text, fill=BOX_FILL, edge=style.BLUE, dashed=False, size=10, bold=False):
    """A rounded box centered at (x, y) with wrapped text."""
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor=fill, edgecolor=edge, linewidth=1.4,
                                linestyle="--" if dashed else "-"))
    ax.text(x, y, text, ha="center", va="center", fontsize=size,
            fontweight="bold" if bold else "normal", color=style.TEXT, linespacing=1.35)


def arrow(ax, start, end, color=style.TEXT_SECONDARY, dashed=False, label=None, rad=0.0):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14,
                                 color=color, linewidth=1.4, linestyle="--" if dashed else "-",
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))
    if label:
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        ax.text(mx, my + 0.08, label, ha="center", va="bottom", fontsize=9,
                color=style.TEXT_SECONDARY, style="italic",
                bbox={"facecolor": style.SURFACE, "edgecolor": "none", "pad": 1.5})


def draw_pipeline():
    """Four columns, read left to right: data -> features -> model -> results.

    Dashed orange boxes are the steps where data leakage is prevented.
    """
    fig, ax = plt.subplots(figsize=(16, 8.6))
    ax.set_xlim(0, 16)
    ax.set_ylim(0.3, 8.9)
    ax.axis("off")
    W, H = 3.3, 1.2
    xa, xb, xc, xd = 2.0, 6.0, 10.0, 14.0
    top, mid, low = 7.0, 4.6, 2.2

    for x, label in [(xa, "1. Data"), (xb, "2. Features"), (xc, "3. Model"), (xd, "4. Results")]:
        ax.text(x, 8.35, label, ha="center", fontsize=13, fontweight="bold", color=style.TEXT_SECONDARY)

    guard = {"fill": GUARD_FILL, "edge": style.ORANGE, "dashed": True}
    model_style = {"fill": "#fdeee6", "edge": style.ORANGE}

    # Column 1: data
    box(ax, xa, top, W, H, "Hetionet v1.0 download\nnodes + edges\n47,031 nodes · 2,250,197 edges")
    box(ax, xa, mid, W, H, "explore.py\ncount nodes & edges by type")
    box(ax, xa, low, W, H, "Remove ALL 755 treats edges\nfrom the graph", bold=True, **guard)
    ax.text(xa, low - 0.85, "leakage guard: walks never see\nany treatment", ha="center", va="top",
            fontsize=9, color=style.ORANGE, style="italic")
    arrow(ax, (xa, top - H / 2), (xa, mid + H / 2))
    arrow(ax, (xa, mid - H / 2), (xa, low + H / 2))

    # Column 2: features
    box(ax, xb, top, W, H, "5 train/test splits\nof the 755 treats edges\n80/20, seeds 0-4")
    box(ax, xb, mid, W, H, "Baseline scores\npopularity · shared genes\n· similar drugs", **guard)
    ax.text(xb, mid - 0.68, "leakage guard: training treats only;\npopularity is leave-one-out",
            ha="center", va="top", fontsize=9, color=style.ORANGE, style="italic")
    box(ax, xb, low, W, H, "DeepWalk embeddings\nrandom walks → word2vec\n64 numbers per node")
    arrow(ax, (xa + W / 2, top), (xb - W / 2, top), label="treats edges")
    arrow(ax, (xb, top - H / 2), (xb, mid + H / 2 + 0.02))
    arrow(ax, (xa + W / 2, low), (xb - W / 2, low), label="treats-free graph")

    # Column 3: model
    box(ax, xc, mid, W, H, "Logistic regression\n67 features per\ndrug-disease pair", bold=True, **model_style)
    box(ax, xc, top, W, H, "Evaluation over 5 splits\nAUROC · AUPRC\nprecision@20 · @100")
    arrow(ax, (xb + W / 2, mid), (xc - W / 2, mid))
    arrow(ax, (xb + W / 2, low + 0.3), (xc - W / 2, mid - 0.3))
    arrow(ax, (xc, mid + H / 2), (xc, top - H / 2))

    # Column 4: results
    box(ax, xd, top, W, H, "Final model on all 755\n→ top 15 new predictions")
    box(ax, xd, mid, W, H, "Path explanations\nwhy is each pair predicted?")
    box(ax, xd, low, W, H, "Reality check\nFDA labels · ClinicalTrials.gov\n· PubMed")
    arrow(ax, (xc + W / 2, top), (xd - W / 2, top), label="beats baselines")
    arrow(ax, (xd, top - H / 2), (xd, mid + H / 2))
    arrow(ax, (xd, mid - H / 2), (xd, low + H / 2))

    # Legend for the dashed boxes
    ax.add_patch(FancyBboxPatch((10.9, 0.55), 0.5, 0.3, boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor=GUARD_FILL, edgecolor=style.ORANGE, linestyle="--"))
    ax.text(11.55, 0.7, "= step where data leakage is prevented", va="center", fontsize=10,
            color=style.TEXT_SECONDARY)

    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "pipeline.png", dpi=150)
    plt.close(fig)


def split_path(path):
    """'A -binds-> B (gene) <-associates- C'  ->  ['A', 'B (gene)', 'C'], ['binds', 'associated with']"""
    parts = re.split(r" (<-[a-z]+-|-[a-z]+->|-[a-z]+-) ", path)
    nodes, links = parts[0::2], [re.sub(r"[<>-]", "", p) for p in parts[1::2]]
    return nodes, links


def draw_example():
    paths = pd.read_csv(OUTPUT_DIR / "phase4_paths.csv")
    contrib = pd.read_csv(OUTPUT_DIR / "phase4_contributions.csv")
    row = contrib[contrib["rank"] == EXAMPLE_RANK].iloc[0]
    top3 = paths[paths["rank"] == EXAMPLE_RANK].head(3)  # already sorted by specificity

    fig, (ax, bx) = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [2.1, 1]})
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")
    drug, disease = row["drug"], row["disease_name"]
    box(ax, 1.3, 3, 2.2, 1.0, drug, bold=True, size=12)
    box(ax, 8.7, 3, 2.2, 1.0, disease, bold=True, size=12)
    for (_, p), y in zip(top3.iterrows(), [5.0, 3.0, 1.0]):
        nodes, links = split_path(p["path"])
        assert len(nodes) == 3, "the example figure only handles 3-node paths"
        assert nodes[0] == drug and nodes[2] == disease
        box(ax, 5.0, y, 2.4, 0.85, nodes[1], fill="#ffffff", size=11)
        arrow(ax, (2.4, 3), (3.8, y), label=links[0])
        arrow(ax, (6.2, y), (7.6, 3), label=links[1])
        ax.text(5.0, y - 0.62, f"{p['type'][2:]} · specificity {p['weight']:.3f}",
                ha="center", fontsize=8.5, color=style.TEXT_SECONDARY)
    ax.set_title(f"Why does the model predict {drug} → {disease}?\nTop 3 supporting paths in Hetionet",
                 loc="left", fontsize=13)

    parts = ["popularity", "shared_genes", "similar_drugs", "embedding"]
    values = [row[c] for c in parts]
    y = list(range(len(parts)))[::-1]
    bx.barh(y, values, color=style.BLUE, height=0.6)
    for yi, v in zip(y, values):
        bx.text(v, yi, f" +{v:.2f}" if v >= 0 else f" {v:.2f}", va="center", fontsize=10,
                color=style.TEXT_SECONDARY)
    bx.set_yticks(y, [c.replace("_", " ") for c in parts])
    bx.set_xlim(0, max(values) * 1.35)
    bx.set_title("Contribution to the score\n(weight × standardized value)", loc="left", fontsize=12)
    style.tidy(bx)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "example_explanation.png", dpi=150)
    plt.close(fig)


def main():
    style.setup()
    draw_pipeline()
    draw_example()
    print(f"Saved {OUTPUT_DIR / 'pipeline.png'} and {OUTPUT_DIR / 'example_explanation.png'}")


if __name__ == "__main__":
    main()
