"""
explore.py - First look at the Hetionet v1.0 knowledge graph.

What this script does:
  1. Loads the node table and the edge table with pandas.
  2. Prints how many nodes there are of each type (Gene, Compound, Disease, ...).
  3. Prints how many edges there are of each type (e.g. "CtD" = Compound-treats-Disease).
  4. Counts the Compound-treats-Disease edges and shows 5 examples with real names.
  5. Saves two bar charts to output/.

Run it from the project folder:
    .venv/bin/python src/explore.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw charts to files, without opening a window
import matplotlib.pyplot as plt
import pandas as pd

# --- File locations -------------------------------------------------------
# Path(__file__) is this script; .parent.parent is the project folder.
PROJECT_DIR = Path(__file__).resolve().parent.parent
NODES_FILE = PROJECT_DIR / "data" / "hetionet-v1.0-nodes.tsv"
EDGES_FILE = PROJECT_DIR / "data" / "hetionet-v1.0-edges.sif.gz"
OUTPUT_DIR = PROJECT_DIR / "output"

# In Hetionet, every edge type has a short code called a "metaedge".
# "CtD" means: Compound -treats-> Disease.
TREATS_METAEDGE = "CtD"


def load_data():
    """Read the two Hetionet tables into pandas DataFrames."""
    # The node file is tab-separated with columns: id, name, kind
    nodes = pd.read_csv(NODES_FILE, sep="\t")
    # The edge file is also tab-separated (and gzipped; pandas unzips it for us)
    # with columns: source, metaedge, target
    edges = pd.read_csv(EDGES_FILE, sep="\t")
    return nodes, edges


def main():
    nodes, edges = load_data()
    print(f"Loaded {len(nodes):,} nodes and {len(edges):,} edges.\n")

    # --- 1. Nodes per type --------------------------------------------------
    # value_counts() counts how many times each value appears in a column.
    node_counts = nodes["kind"].value_counts()
    print("=== Nodes per type ===")
    print(node_counts.to_string())
    print()

    # --- 2. Edges per type --------------------------------------------------
    # The node id looks like "Compound::DB00945", so the part before "::"
    # is the node type. We use that to label each metaedge in plain words.
    edges["source_kind"] = edges["source"].str.split("::").str[0]
    edges["target_kind"] = edges["target"].str.split("::").str[0]

    edge_counts = (
        edges.groupby(["metaedge", "source_kind", "target_kind"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    print("=== Edges per type ===")
    print(edge_counts.to_string(index=False))
    print()

    # --- 3. Compound-treats-Disease edges ----------------------------------
    treats = edges[edges["metaedge"] == TREATS_METAEDGE].copy()
    print(f"=== Compound-treats-Disease ({TREATS_METAEDGE}) edges ===")
    print(f"Number of treats edges: {len(treats):,}")

    # Sanity check: every CtD edge should go from a Compound to a Disease.
    all_compound_to_disease = (
        (treats["source_kind"] == "Compound").all()
        and (treats["target_kind"] == "Disease").all()
    )
    print(f"All CtD edges go Compound -> Disease: {all_compound_to_disease}")
    print(f"Distinct drugs in treats edges:    {treats['source'].nunique():,}")
    print(f"Distinct diseases in treats edges: {treats['target'].nunique():,}")
    print()

    # --- 4. Five examples with readable names ------------------------------
    # The edge table only has ids. To get names, we build a lookup
    # {id -> name} from the node table and "map" each id to its name.
    id_to_name = dict(zip(nodes["id"], nodes["name"]))
    treats["drug"] = treats["source"].map(id_to_name)
    treats["disease"] = treats["target"].map(id_to_name)

    print("=== 5 example treatment edges ===")
    examples = treats[["drug", "disease", "source", "target"]].head(5)
    print(examples.to_string(index=False))
    print()

    # --- 5. Charts ----------------------------------------------------------
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Chart 1: node counts by type (horizontal bars are easier to read
    # when the labels are long words like "Biological Process").
    fig, ax = plt.subplots(figsize=(8, 5))
    node_counts.sort_values().plot.barh(ax=ax, color="#4C72B0")
    ax.set_title("Hetionet v1.0: number of nodes per type")
    ax.set_xlabel("Number of nodes")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "node_counts_by_type.png", dpi=150)
    plt.close(fig)

    # Chart 2: edge counts by type. Counts range from a few hundred to
    # hundreds of thousands, so a log scale keeps the small ones visible.
    edge_labels = (
        edge_counts["source_kind"]
        + " -"
        + edge_counts["metaedge"]
        + "-> "
        + edge_counts["target_kind"]
    )
    edge_series = pd.Series(edge_counts["count"].values, index=edge_labels)

    fig, ax = plt.subplots(figsize=(9, 9))
    edge_series.sort_values().plot.barh(ax=ax, color="#55A868")
    ax.set_xscale("log")
    ax.set_title("Hetionet v1.0: number of edges per type (log scale)")
    ax.set_xlabel("Number of edges (log scale)")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "edge_counts_by_type.png", dpi=150)
    plt.close(fig)

    print(f"Charts saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
