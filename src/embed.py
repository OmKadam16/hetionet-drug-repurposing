"""
embed.py - Learn a vector ("embedding") for every node in Hetionet using
DeepWalk: random walks on the graph + word2vec.

WHAT IS AN EMBEDDING?
  A list of numbers (here 64) that describes a node. Nodes that sit in similar
  parts of the graph get similar lists of numbers. That turns "graph position"
  into something a normal machine-learning model can use.

HOW DEEPWALK WORKS
  1. Random walks: start at a node and repeatedly jump to a random neighbor,
     e.g.  Metformin -> gene PRKAB1 -> pathway X -> gene Y -> ...
     Nodes that are close together in the graph keep showing up in the same
     walks, so the walks record each node's "neighborhood".
  2. word2vec: treat each walk as a sentence and each node as a word. word2vec
     learns vectors so that words appearing near each other in sentences get
     similar vectors. Here that means nodes appearing near each other in walks.
  (node2vec is the same idea, with two extra knobs p and q that bias the walks.
   With p = q = 1 node2vec is exactly DeepWalk, which is what we use.)

NO LEAKAGE: the walk graph has NO Compound-treats-Disease edges at all
  - Removing the TEST treats edges is obviously needed (they are the answers).
  - We also remove the TRAINING treats edges. If they stayed, every training
    treatment would be a direct link in the graph, so its drug and disease
    would get very similar vectors. Hidden test treatments never have that
    link. The model would learn "directly linked = treats", a shortcut that
    can't work on the pairs we actually want to find.
  So the embeddings encode only biology (genes, pathways, side effects, ...).
  Treatment information enters the model only through the baseline features.

Because the walk graph is the same for every split, we learn one embedding
per random seed (0-4): split s uses seed s, so the spread of the results over
5 splits also includes the randomness of the walks. The final model uses seed 0.

Outputs: data/embeddings/seed{0..4}.npz, output/embed_log.txt (time and memory)

Run:  .venv/bin/python src/embed.py      (~1 minute per seed on an M3 Air)
"""

import resource
import time

import numpy as np
import pandas as pd
from gensim.models import Word2Vec

from common import EMBED_DIR, OUTPUT_DIR, SPLIT_SEEDS, load_edges, load_nodes

# --- Settings ---------------------------------------------------------------
WALKS_PER_NODE = 10  # how many walks start at each node
WALK_LENGTH = 40  # nodes per walk
DIMENSIONS = 64  # length of each node's vector
WINDOW = 5  # word2vec looks 5 steps left and right in a walk
EPOCHS = 1  # passes of word2vec over all walks
# workers=1 (one CPU thread) makes word2vec give identical results every run.
# With more threads it is ~4x faster but results change slightly each run.
WORKERS = 1


def build_adjacency(edges, node_ids):
    """Turn the edge table into fast neighbor lookups (CSR format).

    Edges are treated as undirected: if A-B is an edge, a walk may go
    A->B or B->A. For node i, its neighbors are
        neighbors[indptr[i] : indptr[i + 1]]
    """
    position = pd.Series(np.arange(len(node_ids)), index=node_ids)
    a = position[edges["source"]].to_numpy()
    b = position[edges["target"]].to_numpy()
    sources = np.concatenate([a, b])  # add every edge in both directions
    targets = np.concatenate([b, a])
    order = np.argsort(sources, kind="stable")  # group edges by source node
    sources, neighbors = sources[order], targets[order]
    degree = np.bincount(sources, minlength=len(node_ids))
    indptr = np.concatenate([[0], np.cumsum(degree)])
    return indptr, neighbors, degree


def random_walks(indptr, neighbors, degree, seed):
    """Uniform random walks, all computed at once with numpy.

    Returns an integer array of shape (number of walks, WALK_LENGTH).
    Nodes with no edges can't walk anywhere, so they get no walks.
    """
    rng = np.random.default_rng(seed)
    starts = np.repeat(np.flatnonzero(degree > 0), WALKS_PER_NODE)
    walks = np.empty((len(starts), WALK_LENGTH), dtype=np.int64)
    walks[:, 0] = starts
    for step in range(1, WALK_LENGTH):
        current = walks[:, step - 1]
        # pick a random neighbor: a random offset within the node's neighbor list
        offset = (rng.random(len(current)) * degree[current]).astype(np.int64)
        walks[:, step] = neighbors[indptr[current] + offset]
    return walks


def learn_embeddings(edges, node_ids, seed):
    """Random walks + word2vec. Returns an array (n_nodes, DIMENSIONS).

    Rows follow the order of node_ids. Nodes with no edges get all zeros.
    """
    indptr, neighbors, degree = build_adjacency(edges, node_ids)
    walks = random_walks(indptr, neighbors, degree, seed)

    # word2vec expects "sentences" of string "words": node 17 -> "17".
    words = np.array([str(i) for i in range(len(node_ids))], dtype=object)
    sentences = words[walks].tolist()

    model = Word2Vec(
        sentences,
        vector_size=DIMENSIONS,
        window=WINDOW,
        min_count=0,  # keep every node, even rare ones
        sg=1,  # skip-gram: predict neighbors from a node (as in DeepWalk)
        negative=5,  # negative sampling, word2vec's standard training trick
        epochs=EPOCHS,
        workers=WORKERS,
        seed=seed,
    )

    vectors = np.zeros((len(node_ids), DIMENSIONS), dtype=np.float32)
    for word in model.wv.index_to_key:
        vectors[int(word)] = model.wv[word]
    return vectors, int((degree == 0).sum())


def embedding_file(name):
    return EMBED_DIR / f"{name}.npz"


def load_embeddings(name):
    """Return a DataFrame: index = node id, 64 columns of numbers."""
    data = np.load(embedding_file(name))
    return pd.DataFrame(data["vectors"], index=data["ids"])


def peak_memory_mb():
    # On macOS ru_maxrss is in bytes (on Linux it would be kilobytes).
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20


def main():
    nodes = load_nodes()
    edges = load_edges()
    node_ids = nodes["id"].to_numpy()
    EMBED_DIR.mkdir(parents=True, exist_ok=True)

    # The walk graph: every edge EXCEPT Compound-treats-Disease.
    graph = edges[edges["metaedge"] != "CtD"]
    assert not (graph["metaedge"] == "CtD").any()
    log_lines = []

    def log(line):
        print(line, flush=True)
        log_lines.append(line)

    log(f"Walk graph: {len(graph):,} edges (all {len(edges) - len(graph)} treats edges removed)")

    total_start = time.perf_counter()
    for seed in SPLIT_SEEDS:
        start = time.perf_counter()
        vectors, n_isolated = learn_embeddings(graph, node_ids, seed)
        np.savez_compressed(embedding_file(f"seed{seed}"), vectors=vectors, ids=node_ids.astype(str))
        log(f"seed {seed}: nodes without edges={n_isolated}  "
              f"time={time.perf_counter() - start:.0f}s  peak memory={peak_memory_mb():.0f} MB")

    log(f"\nTotal time: {time.perf_counter() - total_start:.0f}s. Saved to {EMBED_DIR}/")
    # Times and memory vary a little between runs; the embeddings themselves don't.
    (OUTPUT_DIR / "embed_log.txt").write_text("\n".join(log_lines) + "\n")


if __name__ == "__main__":
    main()
