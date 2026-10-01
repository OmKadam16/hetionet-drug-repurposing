"""
model.py - Train a logistic regression to score drug-disease pairs, compare
it with the Phase 2 baselines over 5 random splits, and list new predictions.

FEATURES for a pair (drug, disease)
  - embedding features: drug vector * disease vector, element by element
    (64 numbers). If both vectors are large in the same dimensions, the
    products are large: a learnable version of "these two nodes are close".
  - baseline features: popularity, shared genes, similar drugs (3 numbers,
    log-transformed because counts are very skewed).

MODELS (all logistic regression)
  - full:            embeddings + baseline features
  - embeddings_only: ablation (a)
  - baselines_only:  ablation (b)
Logistic regression = a weighted sum of the features squashed into 0..1.
Each weight says how much a feature pushes a pair towards "treats".

TRAINING DATA per split
  positives: the split's training treats edges
  negatives: random pairs that are not known treats/palliates, 10 per positive.
  Some "negatives" may really be unknown treatments (even hidden test ones);
  we accept that, see WHAT_I_LEARNED.md.

Needs data/embeddings/ from embed.py.  Run:  .venv/bin/python src/model.py
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from baselines import precision_at_k, rank_order, shared_gene_scores, similar_drug_scores
from common import OUTPUT_DIR, SPLIT_SEEDS, edges_of_type, load_edges, load_nodes
from embed import load_embeddings
from split import make_split, pair_key

NEGATIVES_PER_POSITIVE = 10
BASELINE_FEATURES = ["popularity", "shared_genes", "similar_drugs"]
METHODS = [
    "random",
    "popularity",
    "shared_genes",
    "similar_drugs",
    "baselines_only",
    "embeddings_only",
    "full",
]
METRICS = ["AUROC", "AUPRC", "P@20", "P@100"]


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------


def baseline_features(pairs, treats, graph, positive_keys):
    """The 3 Phase 2 scores for each pair, computed from `treats` only.

    positive_keys: pairs that are themselves in `treats` (training positives).
    For those, popularity is computed "leave-one-out": the pair's own edge is
    not counted. Otherwise every training positive would have popularity >= 1
    while hidden test positives often have 0, and the model would learn a
    pattern that can never hold for the pairs we actually want to find.
    """
    index = pd.MultiIndex.from_frame(pairs[["compound", "disease"]])
    drug_deg = pairs["compound"].map(treats["compound"].value_counts()).fillna(0)
    disease_deg = pairs["disease"].map(treats["disease"].value_counts()).fillna(0)
    own_edge = pair_key(pairs).isin(positive_keys).astype(int)
    features = pd.DataFrame(index=pairs.index)
    features["popularity"] = (drug_deg - own_edge) * (disease_deg - own_edge)
    # These two never count a pair's own treats edge, so no correction needed:
    # shared genes uses no treats edges; similar drugs uses OTHER drugs' edges.
    features["shared_genes"] = shared_gene_scores(graph).reindex(index).fillna(0).to_numpy()
    features["similar_drugs"] = (
        similar_drug_scores(graph, treats).reindex(index).fillna(0).to_numpy()
    )
    return features


def embedding_features(pairs, vectors):
    """Element-wise product of drug vector and disease vector."""
    drug = vectors.loc[pairs["compound"]].to_numpy()
    disease = vectors.loc[pairs["disease"]].to_numpy()
    product = drug * disease
    return pd.DataFrame(product, index=pairs.index, columns=[f"emb{i}" for i in range(product.shape[1])])


def feature_table(pairs, treats, graph, positive_keys, vectors):
    base = np.log1p(baseline_features(pairs, treats, graph, positive_keys))
    return pd.concat([base, embedding_features(pairs, vectors)], axis=1)


def feature_columns(model_name, table):
    emb = [c for c in table.columns if c.startswith("emb")]
    return {"baselines_only": BASELINE_FEATURES, "embeddings_only": emb,
            "full": BASELINE_FEATURES + emb}[model_name]


def make_classifier():
    # StandardScaler puts every feature on the same scale (mean 0, std 1) so
    # the regularization treats them equally. C=1.0 is sklearn's default
    # strength of regularization (it keeps weights from growing too large).
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=5000))


def sample_training_pairs(all_pairs, treats, excluded_keys, seed):
    """Training positives + random negatives (pairs not in excluded_keys)."""
    rng = np.random.default_rng(seed)
    pool = all_pairs[~pair_key(all_pairs).isin(excluded_keys)]
    n_neg = NEGATIVES_PER_POSITIVE * len(treats)
    negatives = pool.iloc[rng.choice(len(pool), size=n_neg, replace=False)]
    positives = treats[["compound", "disease"]]
    pairs = pd.concat([positives, negatives[["compound", "disease"]]], ignore_index=True)
    labels = np.r_[np.ones(len(positives)), np.zeros(n_neg)]
    return pairs, labels


# ---------------------------------------------------------------------------
# One split
# ---------------------------------------------------------------------------


def evaluate(labels, scores, seed):
    order = rank_order(scores, np.random.default_rng(seed))
    return {
        "AUROC": roc_auc_score(labels, scores),
        "AUPRC": average_precision_score(labels, scores),
        "P@20": precision_at_k(labels, order, 20),
        "P@100": precision_at_k(labels, order, 100),
    }


def run_split(seed, nodes, edges, all_pairs, cpd_keys):
    train, test, eval_pairs = make_split(nodes, edges, seed)
    graph = edges[edges["metaedge"] != "CtD"]  # treats info comes only from `train`
    train_keys = set(pair_key(train))
    vectors = load_embeddings(f"seed{seed}")  # walk seed = split seed

    # --- Training set -------------------------------------------------------
    # Negatives are drawn from everything except known training treats and
    # palliates. We do NOT exclude test treatments: we're not allowed to know them.
    train_pairs, y_train = sample_training_pairs(all_pairs, train, train_keys | cpd_keys, seed)
    sampled_test_pos = int(pair_key(train_pairs[y_train == 0]).isin(set(pair_key(test))).sum())

    # --- Evaluation set: Phase 2 pairs minus anything we trained on ---------
    trained_on = set(pair_key(train_pairs))
    eval_pairs = eval_pairs[~pair_key(eval_pairs).isin(trained_on)].reset_index(drop=True)
    y_eval = eval_pairs["label"].to_numpy()

    X_train = feature_table(train_pairs, train, graph, train_keys, vectors)
    X_eval = feature_table(eval_pairs, train, graph, set(), vectors)

    scores = {"random": np.random.default_rng(seed).random(len(eval_pairs))}
    for name in BASELINE_FEATURES:  # raw baseline scores (log doesn't change ranking)
        scores[name] = X_eval[name].to_numpy()
    for name in ["baselines_only", "embeddings_only", "full"]:
        cols = feature_columns(name, X_train)
        clf = make_classifier().fit(X_train[cols], y_train)
        scores[name] = clf.predict_proba(X_eval[cols])[:, 1]

    print(f"split seed {seed}: train {int(y_train.sum())} pos + {int((y_train == 0).sum())} neg "
          f"({sampled_test_pos} test treats were drawn as negatives); "
          f"eval {len(eval_pairs):,} pairs, {int(y_eval.sum())} positives")
    return [{"seed": seed, "method": m, **evaluate(y_eval, scores[m], seed)} for m in METHODS]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    nodes = load_nodes()
    edges = load_edges()
    compounds = nodes.loc[nodes["kind"] == "Compound", "id"].rename("compound")
    diseases = nodes.loc[nodes["kind"] == "Disease", "id"].rename("disease")
    all_pairs = pd.merge(compounds, diseases, how="cross")
    ctd = edges_of_type(edges, "CtD").rename(columns={"source": "compound", "target": "disease"})
    cpd = edges_of_type(edges, "CpD").rename(columns={"source": "compound", "target": "disease"})
    cpd_keys = set(pair_key(cpd))

    # --- 1. Evaluate over 5 splits -------------------------------------------
    rows = []
    for seed in SPLIT_SEEDS:
        rows += run_split(seed, nodes, edges, all_pairs, cpd_keys)
    per_split = pd.DataFrame(rows)
    OUTPUT_DIR.mkdir(exist_ok=True)
    per_split.to_csv(OUTPUT_DIR / "phase3_results_per_split.csv", index=False)

    summary = per_split.groupby("method", sort=False)[METRICS].agg(["mean", "std"])
    summary.to_csv(OUTPUT_DIR / "phase3_results.csv")
    print("\n=== Mean +/- std over 5 splits ===")
    table = pd.DataFrame({m: summary[(m, "mean")].map("{:.4f}".format) + " +/- "
                          + summary[(m, "std")].map("{:.4f}".format) for m in METRICS})
    print(table.to_string())

    # --- 2. Is full better than popularity beyond the noise? -----------------
    # Compare on the SAME split each time (a "paired" comparison): split-to-split
    # differences in difficulty cancel out.
    # We also compare full vs baselines_only: do the embeddings add anything?
    wide = per_split.pivot(index="seed", columns="method")
    for other in ["popularity", "baselines_only"]:
        print(f"\n=== full minus {other}, per split ===")
        for metric in METRICS:
            diff = wide[(metric, "full")] - wide[(metric, other)]
            print(f"{metric:6s} diffs: {', '.join(f'{d:+.4f}' for d in diff)}  "
                  f"mean {diff.mean():+.4f} +/- {diff.std():.4f}  full better in {(diff > 0).sum()}/5")

    # --- 3. Chart -------------------------------------------------------------
    colors = ["#999999", "#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974", "#DD8452"]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
    for ax, metric in zip(axes, METRICS):
        means, stds = summary[(metric, "mean")], summary[(metric, "std")]
        ax.bar(means.index, means, yerr=stds, capsize=3, color=colors)
        for x, (m, s) in enumerate(zip(means, stds)):
            ax.text(x, m + s, f"{m:.3f}", ha="center", va="bottom", fontsize=7)
        ax.set_title(metric)
        ax.set_ylim(0, (means + stds).max() * 1.2)
        ax.tick_params(axis="x", rotation=60)
    axes[0].axhline(0.5, color="black", linestyle="--", linewidth=0.8)
    fig.suptitle("Phase 3: mean over 5 random splits (error bars = 1 standard deviation)")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "phase3_comparison.png", dpi=150)
    plt.close(fig)

    # --- 4. Final model on the full graph -> new predictions -----------------
    # Train on ALL 755 treatments (embeddings from walk seed 0), then score
    # every pair that is not already a known treats or palliates edge.
    graph = edges[edges["metaedge"] != "CtD"]
    ctd_keys = set(pair_key(ctd))
    vectors = load_embeddings("seed0")
    train_pairs, y_train = sample_training_pairs(all_pairs, ctd, ctd_keys | cpd_keys, seed=0)
    X_train = feature_table(train_pairs, ctd, graph, ctd_keys, vectors)
    cols = feature_columns("full", X_train)
    clf = make_classifier().fit(X_train[cols], y_train)

    new_pairs = all_pairs[~pair_key(all_pairs).isin(ctd_keys | cpd_keys)].reset_index(drop=True)
    X_new = feature_table(new_pairs, ctd, graph, set(), vectors)
    new_pairs["score"] = clf.predict_proba(X_new[cols])[:, 1]
    new_pairs[BASELINE_FEATURES] = np.expm1(X_new[BASELINE_FEATURES]).round().astype(int)
    id_to_name = dict(zip(nodes["id"], nodes["name"]))
    new_pairs["drug"] = new_pairs["compound"].map(id_to_name)
    new_pairs["disease_name"] = new_pairs["disease"].map(id_to_name)
    top = new_pairs.sort_values("score", ascending=False).head(15)
    top.to_csv(OUTPUT_DIR / "phase3_top15_new_predictions.csv", index=False)
    print("\n=== Top 15 NEW predictions (not known treats/palliates) from the full model ===")
    print(top[["drug", "disease_name", "score"] + BASELINE_FEATURES]
          .to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # Which features does the final model lean on? (weights on standardized features)
    weights = pd.Series(clf[-1].coef_[0], index=cols)
    print("\nFinal model weights for the 3 baseline features:",
          ", ".join(f"{k} {weights[k]:+.2f}" for k in BASELINE_FEATURES))


if __name__ == "__main__":
    main()
