"""
explain.py - Explain WHY the final model ranks its top 15 new predictions high.

For each prediction we show two kinds of explanation:

1. FEATURE CONTRIBUTIONS (what the model itself used)
   Logistic regression scores a pair with a weighted sum:
       logit = intercept + sum over features of (weight x standardized value)
   So each feature's share of the score is exactly weight x standardized value.
   "Standardized" means 0 = an average pair, so a contribution of +3 means
   "this feature pushes the pair 3 units above an average pair".
   The 64 embedding features are added up into one "embedding" contribution.

2. SUPPORTING PATHS IN HETIONET (what a biologist can check)
   Path types (treats edges = the 755 known treatments the final model used):
     A. Drug -binds-> Gene <-associates- Disease
     B. Drug -resembles- Drug -treats-> Disease
     C. Drug <-includes- Pharmacologic Class -includes-> Drug -treats-> Disease
     D. Drug -treats-> Disease -resembles- Disease
   Ranking paths: Hetionet's tables have no edge strengths, so we rank by
   SPECIFICITY: weight = product over the middle nodes of degree^-0.5.
   A path through a hub (a node with thousands of edges) is weak evidence;
   a path through a node with few edges is specific. This is the same idea as
   the "degree-weighted path count" used in the original Hetionet paper.

If output/phase4_reality_check.csv exists, its labels and sources are merged
into the report.

Run:  .venv/bin/python src/explain.py
Writes: output/phase4_explanations.md, output/phase4_paths.csv
"""

import numpy as np
import pandas as pd

from common import OUTPUT_DIR, edges_of_type, load_edges, load_nodes
from model import BASELINE_FEATURES, train_final_model

TOP_N = 15
PATHS_SHOWN = 3
REALITY_FILE = OUTPUT_DIR / "phase4_reality_check.csv"


def both_directions(df):
    """For undirected edge types (resembles) stored once: add the reverse."""
    flipped = df.rename(columns={"source": "target", "target": "source"})
    return pd.concat([df, flipped], ignore_index=True)


def find_paths(drug, disease, e, degree, name):
    """All paths of types A-D between one drug and one disease.

    Returns a DataFrame with columns: type, path (readable text), weight.
    """
    rows = []

    # A. Drug -binds-> Gene <-associates- Disease
    genes = set(e["CbG"].loc[e["CbG"]["source"] == drug, "target"]) & set(
        e["DaG"].loc[e["DaG"]["source"] == disease, "target"])
    for g in genes:
        rows.append(("A shared gene", f"{name[drug]} -binds-> {name[g]} (gene) "
                     f"<-associates- {name[disease]}", degree[g] ** -0.5))

    # Drugs that are known to treat this disease
    treaters = set(e["CtD"].loc[e["CtD"]["target"] == disease, "source"])

    # B. Drug -resembles- Drug2 -treats-> Disease
    similar = set(e["CrC"].loc[e["CrC"]["source"] == drug, "target"])
    for c2 in similar & treaters:
        rows.append(("B similar drug", f"{name[drug]} -resembles- {name[c2]} "
                     f"-treats-> {name[disease]}", degree[c2] ** -0.5))

    # C. Drug <-includes- Class -includes-> Drug2 -treats-> Disease
    classes = e["PCiC"].loc[e["PCiC"]["target"] == drug, "source"]
    for pc in classes:
        members = set(e["PCiC"].loc[e["PCiC"]["source"] == pc, "target"]) - {drug}
        for c2 in members & treaters:
            rows.append(("C same drug class", f"{name[drug]} <-in- {name[pc]} (class) "
                         f"-in-> {name[c2]} -treats-> {name[disease]}",
                         (degree[pc] * degree[c2]) ** -0.5))

    # D. Drug -treats-> Disease2 -resembles- Disease
    treated = set(e["CtD"].loc[e["CtD"]["source"] == drug, "target"])
    similar_diseases = set(e["DrD"].loc[e["DrD"]["source"] == disease, "target"])
    for d2 in treated & similar_diseases:
        rows.append(("D similar disease", f"{name[drug]} -treats-> {name[d2]} "
                     f"-resembles- {name[disease]}", degree[d2] ** -0.5))

    return pd.DataFrame(rows, columns=["type", "path", "weight"])


def feature_contributions(clf, cols, X):
    """weight x standardized value for every feature, grouped into 4 parts."""
    scaler, lr = clf[0], clf[-1]
    z = (X[cols].to_numpy() - scaler.mean_) / scaler.scale_
    contrib = pd.DataFrame(z * lr.coef_[0], columns=cols, index=X.index)
    grouped = contrib[BASELINE_FEATURES].copy()
    grouped["embedding"] = contrib[[c for c in cols if c.startswith("emb")]].sum(axis=1)
    return grouped, lr.intercept_[0]


def main():
    nodes = load_nodes()
    edges = load_edges()
    name = dict(zip(nodes["id"], nodes["name"]))

    # How connected each node is (all edge types, both directions).
    degree = pd.concat([edges["source"], edges["target"]]).value_counts()

    e = {t: edges_of_type(edges, t) for t in ["CbG", "DaG", "CtD", "PCiC"]}
    e["CrC"] = both_directions(edges_of_type(edges, "CrC"))
    e["DrD"] = both_directions(edges_of_type(edges, "DrD"))

    # Re-train the exact final model from model.py and take its top 15.
    clf, cols, new_pairs, X_new = train_final_model(nodes, edges)
    top = new_pairs.sort_values("score", ascending=False).head(TOP_N)
    contrib, intercept = feature_contributions(clf, cols, X_new.loc[top.index])
    raw = np.expm1(X_new.loc[top.index, BASELINE_FEATURES]).round().astype(int)

    reality = pd.read_csv(REALITY_FILE) if REALITY_FILE.exists() else None

    lines = ["# Phase 4: why the model makes its top 15 new predictions", "",
             "Generated by `src/explain.py`. Feature contributions = logistic-regression "
             "weight x standardized feature value (0 = an average pair). Paths ranked by "
             "specificity = product of (degree of middle nodes)^-0.5.", ""]
    all_paths = []
    for rank, (i, row) in enumerate(top.iterrows(), start=1):
        drug, disease = row["compound"], row["disease"]
        paths = find_paths(drug, disease, e, degree, name).sort_values(
            "weight", ascending=False, kind="stable")
        paths.insert(0, "rank", rank)
        all_paths.append(paths)
        c = contrib.loc[i]
        main_feature = c.idxmax()

        lines += [f"## {rank}. {name[drug]} → {name[disease]}  (score {row['score']:.4f})", ""]
        lines.append("Feature values: " + ", ".join(
            f"{f.replace('_', ' ')} = {raw.loc[i, f]}" for f in BASELINE_FEATURES))
        lines.append("")
        lines.append("Contributions to the score (logit units, intercept "
                     f"{intercept:+.2f}): " + ", ".join(
                         f"**{k.replace('_', ' ')} {v:+.2f}**" if k == main_feature
                         else f"{k.replace('_', ' ')} {v:+.2f}" for k, v in c.items()))
        lines.append(f"→ biggest contributor: **{main_feature.replace('_', ' ')}**")
        lines.append("")
        counts = paths["type"].value_counts()
        lines.append("Path counts: " + (", ".join(f"{t}: {n}" for t, n in counts.sort_index().items())
                                        if len(counts) else "none of types A-D"))
        lines.append("")
        lines.append(f"Top {PATHS_SHOWN} paths:")
        for _, p in paths.head(PATHS_SHOWN).iterrows():
            lines.append(f"- [{p['type']}] {p['path']}  (specificity {p['weight']:.3f})")
        if reality is not None:
            r = reality[(reality["compound"] == drug) & (reality["disease"] == disease)]
            if len(r):
                r = r.iloc[0]
                lines += ["", f"**Reality check: {r['label']}**. {r['note']}",
                          f"Sources: {r['sources']}"]
        lines.append("")

    if reality is not None:
        # Summary, computed from the reality-check table (not typed by hand).
        lines += ["## Summary of the reality check", "",
                  "Label rules: *already used/approved* = an official label lists the use; "
                  "*in clinical trials* = at least one registered or published human trial of "
                  "this drug for this disease; *some published evidence* = papers but no human "
                  "trial; *no evidence found* = the searches linked in that row found nothing "
                  "relevant (not proof that it can't work).", "",
                  "Sources were searched on the date in the CSV through the public openFDA, "
                  "ClinicalTrials.gov (API v2) and PubMed (E-utilities) interfaces. In an automated "
                  "link check, PubMed article pages answered HTTP 203 (likely bot protection) "
                  "instead of 200; their IDs and titles were confirmed through PubMed's API.", "",
                  "| Label | Count |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in reality["label"].value_counts().items()]
        lines += ["", "| My assessment | Count | Predictions |", "|---|---|---|"]
        for k, group in reality.groupby("assessment", sort=False):
            pairs = "; ".join(f"{d} → {s}" for d, s in zip(group["drug"], group["disease_name"]))
            lines.append(f"| {k} | {len(group)} | {pairs} |")
        lines.append("")

    pd.concat(all_paths).to_csv(OUTPUT_DIR / "phase4_paths.csv", index=False)
    (OUTPUT_DIR / "phase4_explanations.md").write_text("\n".join(lines))

    # Short console summary
    summary = top[["compound", "disease"]].copy()
    summary["drug"] = summary["compound"].map(name)
    summary["disease_name"] = summary["disease"].map(name)
    summary[["c_pop", "c_genes", "c_similar", "c_emb"]] = contrib.round(2).to_numpy()
    summary["n_paths"] = [len(p) for p in all_paths]
    print(summary.drop(columns=["compound", "disease"]).to_string(index=False))
    print(f"\nWrote {OUTPUT_DIR / 'phase4_explanations.md'} and phase4_paths.csv")


if __name__ == "__main__":
    main()
