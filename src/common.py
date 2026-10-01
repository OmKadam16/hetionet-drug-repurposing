"""
common.py - File paths and loading helpers shared by the Phase 2 scripts.

Keeping these in one place means split.py and baselines.py always read
the same files in the same way.
"""

from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
SPLIT_DIR = DATA_DIR / "split"
OUTPUT_DIR = PROJECT_DIR / "output"

NODES_FILE = DATA_DIR / "hetionet-v1.0-nodes.tsv"
EDGES_FILE = DATA_DIR / "hetionet-v1.0-edges.sif.gz"

# Files written by split.py and read by baselines.py
TRAIN_FILE = SPLIT_DIR / "train_ctd.tsv"  # 80% of treats edges
TEST_FILE = SPLIT_DIR / "test_ctd.tsv"  # 20% of treats edges (held out)
EVAL_PAIRS_FILE = SPLIT_DIR / "eval_pairs.tsv"  # pairs we score + true label

EMBED_DIR = DATA_DIR / "embeddings"  # node vectors learned by embed.py

# One fixed seed for everything random, so results are reproducible.
RANDOM_SEED = 42  # Phase 2 single split

# Phase 3: repeat the whole evaluation over 5 different 80/20 splits.
SPLIT_SEEDS = [0, 1, 2, 3, 4]


def load_nodes():
    """Node table with columns: id, name, kind."""
    return pd.read_csv(NODES_FILE, sep="\t")


def load_edges():
    """Edge table with columns: source, metaedge, target."""
    return pd.read_csv(EDGES_FILE, sep="\t")


def edges_of_type(edges, metaedge):
    """Return just the (source, target) columns for one edge type, e.g. 'CtD'."""
    return edges.loc[edges["metaedge"] == metaedge, ["source", "target"]].reset_index(
        drop=True
    )
