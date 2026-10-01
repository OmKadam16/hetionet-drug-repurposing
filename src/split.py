"""
split.py - Build a fair train/test setup for predicting Compound-treats-Disease.

The idea: pretend we don't know 20% of the real treatments (the TEST set).
Methods may only learn from the other 80% (TRAINING). Then we check whether
they rank the hidden 20% near the top of all possible drug-disease pairs.

Outputs (in data/split/):
  train_ctd.tsv   - training positives (compound, disease)
  test_ctd.tsv    - held-out test positives (compound, disease)
  eval_pairs.tsv  - every pair we will score, with label 1 (test treatment)
                    or 0 (not known to treat or palliate)

Run:  .venv/bin/python src/split.py
"""

import numpy as np
import pandas as pd

from common import (
    EVAL_PAIRS_FILE,
    RANDOM_SEED,
    SPLIT_DIR,
    TEST_FILE,
    TRAIN_FILE,
    edges_of_type,
    load_edges,
    load_nodes,
)

TEST_FRACTION = 0.20


def main():
    nodes = load_nodes()
    edges = load_edges()

    # --- 1. Positives: the known treatments --------------------------------
    ctd = edges_of_type(edges, "CtD").rename(
        columns={"source": "compound", "target": "disease"}
    )
    print(f"Known treats (CtD) edges: {len(ctd)}")

    # Shuffle the rows with a fixed seed, then cut off the first 20% as test.
    # Fixed seed = anyone who reruns this gets exactly the same split.
    rng = np.random.default_rng(RANDOM_SEED)
    shuffled = ctd.iloc[rng.permutation(len(ctd))].reset_index(drop=True)
    n_test = int(round(TEST_FRACTION * len(shuffled)))
    test = shuffled.iloc[:n_test].reset_index(drop=True)
    train = shuffled.iloc[n_test:].reset_index(drop=True)
    print(f"  -> training positives: {len(train)}")
    print(f"  -> test positives:     {len(test)}")

    # --- 2. Candidates: every Compound x Disease pair -----------------------
    compounds = nodes.loc[nodes["kind"] == "Compound", "id"]
    diseases = nodes.loc[nodes["kind"] == "Disease", "id"]
    # merge(how="cross") makes every combination of the two lists.
    candidates = pd.merge(
        compounds.rename("compound"), diseases.rename("disease"), how="cross"
    )
    print(f"\nAll Compound x Disease pairs: {len(compounds)} x {len(diseases)} "
          f"= {len(candidates):,}")

    # --- 3. Decide which pairs are evaluated, and their label ---------------
    # We build a "key" string per pair so we can test membership easily.
    def pair_key(df):
        return df["compound"] + "|" + df["disease"]

    cpd = edges_of_type(edges, "CpD").rename(
        columns={"source": "compound", "target": "disease"}
    )
    candidates["key"] = pair_key(candidates)
    train_keys = set(pair_key(train))
    test_keys = set(pair_key(test))
    cpd_keys = set(pair_key(cpd))

    # Training treatments are removed: they are already "known", so ranking
    # them highly says nothing about predicting NEW treatments.
    # Palliates pairs are removed: a palliative drug does help the patient
    # (it relieves symptoms), so calling it a "negative" would be wrong; and
    # calling it a positive would be wrong too. Its label is ambiguous, so
    # we leave it out of the test entirely.
    is_train = candidates["key"].isin(train_keys)
    is_cpd = candidates["key"].isin(cpd_keys)
    eval_pairs = candidates[~is_train & ~is_cpd].copy()
    eval_pairs["label"] = eval_pairs["key"].isin(test_keys).astype(int)
    eval_pairs = eval_pairs.drop(columns="key").reset_index(drop=True)

    print(f"  removed (training treats):   {is_train.sum():,}")
    print(f"  removed (palliates, CpD):    {is_cpd.sum():,}")
    print(f"  evaluation pairs:            {len(eval_pairs):,}")
    n_pos = eval_pairs["label"].sum()
    print(f"    positives (test treats):   {n_pos}")
    print(f"    negatives:                 {len(eval_pairs) - n_pos:,}")
    print(f"    share of positives:        {n_pos / len(eval_pairs):.5f} "
          f"(about 1 in {round(len(eval_pairs) / n_pos):,})")

    # --- 4. Safety checks ---------------------------------------------------
    # No pair may be in both train and test.
    assert not (train_keys & test_keys), "train and test overlap!"
    # Every test positive must be in the evaluation set.
    assert n_pos == len(test), "some test positives are missing!"

    # --- 5. Save ------------------------------------------------------------
    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    train.to_csv(TRAIN_FILE, sep="\t", index=False)
    test.to_csv(TEST_FILE, sep="\t", index=False)
    eval_pairs.to_csv(EVAL_PAIRS_FILE, sep="\t", index=False)
    print(f"\nSaved split files to {SPLIT_DIR}/")


if __name__ == "__main__":
    main()
