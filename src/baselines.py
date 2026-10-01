"""
baselines.py - Score every evaluation pair with 4 simple methods and measure
how well each one ranks the held-out (test) treatments.

Baselines:
  random        - a random number per pair (the floor: "no information")
  popularity    - (# training treatments of the drug) x (# of the disease)
  shared_genes  - # of paths Compound -binds-> Gene <-associates- Disease
  similar_drugs - # of paths Compound -resembles- Compound -treats-> Disease
                  (using TRAINING treats edges only)

Metrics: AUROC, AUPRC (average precision), precision@20, precision@100.

Needs data/split/ from split.py.  Run:  .venv/bin/python src/baselines.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from common import (
    EVAL_PAIRS_FILE,
    OUTPUT_DIR,
    RANDOM_SEED,
    TEST_FILE,
    TRAIN_FILE,
    edges_of_type,
    load_edges,
    load_nodes,
)

TOP_K_VALUES = [20, 100]


# ---------------------------------------------------------------------------
# Baseline scores. Each function returns a Series of scores indexed by
# (compound, disease). Pairs missing from the Series get score 0 later.
# ---------------------------------------------------------------------------


def popularity_scores(train):
    """Drug's number of training treatments x disease's number of them.

    Uses ONLY training treats edges, so no test edge can leak in.
    """
    drug_degree = train["compound"].value_counts()
    disease_degree = train["disease"].value_counts()
    # Every drug-disease combination of the drugs/diseases that appear in training.
    pairs = pd.merge(
        drug_degree.rename("drug_deg").rename_axis("compound").reset_index(),
        disease_degree.rename("disease_deg").rename_axis("disease").reset_index(),
        how="cross",
    )
    pairs["score"] = pairs["drug_deg"] * pairs["disease_deg"]
    return pairs.set_index(["compound", "disease"])["score"]


def shared_gene_scores(edges):
    """Count genes that the drug binds AND that the disease is associated with.

    Uses CbG (Compound-binds-Gene) and DaG (Disease-associates-Gene) edges,
    which contain no treats information.
    """
    cbg = edges_of_type(edges, "CbG").rename(columns={"source": "compound", "target": "gene"})
    dag = edges_of_type(edges, "DaG").rename(columns={"source": "disease", "target": "gene"})
    # Joining on "gene" gives one row per path compound -> gene <- disease.
    paths = cbg.merge(dag, on="gene")
    return paths.groupby(["compound", "disease"]).size()


def similar_drug_scores(edges, train):
    """Count drugs that resemble this drug AND treat this disease (in training).

    Resemblance edges (CrC) are stored once per pair (A->B, never also B->A),
    but similarity goes both ways, so we add the reversed copy.
    """
    crc = edges_of_type(edges, "CrC").rename(columns={"source": "compound", "target": "similar"})
    crc_both_ways = pd.concat(
        [crc, crc.rename(columns={"compound": "similar", "similar": "compound"})],
        ignore_index=True,
    )
    # Training treats, with the drug column renamed to "similar" so we can join.
    similar_treats = train.rename(columns={"compound": "similar"})
    # One row per path: compound -resembles- similar -treats-> disease
    paths = crc_both_ways.merge(similar_treats, on="similar")
    return paths.groupby(["compound", "disease"]).size()


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def rank_order(scores, rng):
    """Indices that sort scores from highest to lowest, breaking ties randomly.

    Many pairs share the same score (often 0). Without random tie-breaking,
    the "top k" would depend on the arbitrary row order of the file.
    """
    tiebreak = rng.random(len(scores))
    # np.lexsort sorts by the LAST key first: first by -score, then by tiebreak.
    return np.lexsort((tiebreak, -scores))


def precision_at_k(labels, order, k):
    """Fraction of the k highest-ranked pairs that are real (test) treatments."""
    return labels[order[:k]].mean()


def evaluate(labels, scores, rng):
    result = {
        "AUROC": roc_auc_score(labels, scores),
        "AUPRC": average_precision_score(labels, scores),
    }
    order = rank_order(scores, rng)
    for k in TOP_K_VALUES:
        result[f"P@{k}"] = precision_at_k(labels, order, k)
    # How many test treatments got any signal at all (score > 0)?
    result["test_pos_with_score>0"] = int(((scores > 0) & (labels == 1)).sum())
    return result


def main():
    nodes = load_nodes()
    edges = load_edges()
    train = pd.read_csv(TRAIN_FILE, sep="\t")
    test = pd.read_csv(TEST_FILE, sep="\t")
    eval_pairs = pd.read_csv(EVAL_PAIRS_FILE, sep="\t")

    # --- Leakage guard -----------------------------------------------------
    # Remove ALL treats edges from the graph. The only treats information any
    # baseline may use is the `train` table. Then double-check that no test
    # pair is present in what remains.
    graph = edges[edges["metaedge"] != "CtD"]
    test_keys = set(test["compound"] + "|" + test["disease"])
    assert not test_keys & set(train["compound"] + "|" + train["disease"])
    assert not test_keys & set(graph["source"] + "|" + graph["target"])
    print("Leakage check passed: no test treatment is visible to any baseline.\n")

    # --- Compute all scores --------------------------------------------------
    rng = np.random.default_rng(RANDOM_SEED)
    index = pd.MultiIndex.from_frame(eval_pairs[["compound", "disease"]])
    score_table = pd.DataFrame(index=index)
    score_table["random"] = rng.random(len(eval_pairs))
    for name, scores in [
        ("popularity", popularity_scores(train)),
        ("shared_genes", shared_gene_scores(graph)),
        ("similar_drugs", similar_drug_scores(graph, train)),
    ]:
        # reindex lines the scores up with our evaluation pairs; missing -> 0
        score_table[name] = scores.reindex(index).fillna(0).to_numpy()

    # --- Evaluate -----------------------------------------------------------
    labels = eval_pairs["label"].to_numpy()
    rows = []
    for name in score_table.columns:
        rows.append({"baseline": name, **evaluate(labels, score_table[name].to_numpy(), rng)})
    results = pd.DataFrame(rows)

    prevalence = labels.mean()
    print(f"Evaluation pairs: {len(labels):,}  test positives: {labels.sum()}  "
          f"(AUPRC of a random guess ~ {prevalence:.5f})\n")
    print(results.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    OUTPUT_DIR.mkdir(exist_ok=True)
    results.to_csv(OUTPUT_DIR / "baseline_results.csv", index=False)

    # --- Chart: one small panel per metric -----------------------------------
    metrics = ["AUROC", "AUPRC", "P@20", "P@100"]
    colors = ["#999999", "#4C72B0", "#55A868", "#C44E52"]
    fig, axes = plt.subplots(1, 4, figsize=(14, 4))
    for ax, metric in zip(axes, metrics):
        values = results[metric]
        ax.bar(results["baseline"], values, color=colors)
        for x, v in enumerate(values):
            ax.text(x, v, f"{v:.3f}", ha="center", va="bottom", fontsize=8)
        ax.set_title(metric)
        ax.set_ylim(0, max(values.max() * 1.2, 0.05))
        ax.tick_params(axis="x", rotation=45)
    axes[0].axhline(0.5, color="black", linestyle="--", linewidth=0.8)  # AUROC chance
    fig.suptitle("Baselines on 151 held-out treatments (higher is better)")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "baseline_comparison.png", dpi=150)
    plt.close(fig)
    print(f"\nSaved results to {OUTPUT_DIR}/baseline_results.csv and baseline_comparison.png")

    # --- Top 10 predictions from the best baseline (by AUPRC) ----------------
    best = results.sort_values("AUPRC", ascending=False)["baseline"].iloc[0]
    order = rank_order(score_table[best].to_numpy(), np.random.default_rng(RANDOM_SEED))
    top = eval_pairs.iloc[order[:10]].copy()
    top["score"] = score_table[best].to_numpy()[order[:10]]
    id_to_name = dict(zip(nodes["id"], nodes["name"]))
    top["drug"] = top["compound"].map(id_to_name)
    top["disease_name"] = top["disease"].map(id_to_name)
    top["held_out_treatment?"] = np.where(top["label"] == 1, "YES", "-")
    print(f"\nTop 10 predictions from best baseline by AUPRC: {best}")
    print(top[["drug", "disease_name", "score", "held_out_treatment?"]].to_string(index=False))


if __name__ == "__main__":
    main()
