# Drug Repurposing with the Hetionet Knowledge Graph

A learning project: exploring the [Hetionet v1.0](https://github.com/hetio/hetionet)
biomedical knowledge graph to understand how known drug–disease treatment
relationships could be used to find new uses for existing drugs
(*drug repurposing*).

## Status

**Phase 1 – data exploration** (done): load the graph, count nodes and edges by
type, look at the Compound-treats-Disease edges, make summary charts.

**Phase 2 – fair evaluation + baselines** (done): hold out 20% of treatments as a
test set, score all Compound × Disease pairs with 4 simple baselines (random,
popularity, shared genes, similar drugs), report AUROC / AUPRC / precision@k.

**Phase 3 – graph embeddings + model** (done): DeepWalk embeddings (random walks +
word2vec) learned on Hetionet with all treats edges removed, a logistic regression
on embedding + baseline features, two ablations, all evaluated over 5 random
splits (mean ± std). Lists the model's top new candidate pairs.

## Project layout

```
data/        raw Hetionet files (downloaded, NOT committed to git)
src/         Python code
  common.py    shared file paths, random seed and loaders
  explore.py   Phase 1: loads the graph and prints/plots summary statistics
  split.py     Phase 2: train/test split of treats edges + evaluation pairs
  baselines.py Phase 2: scores and evaluates the baselines
  embed.py     Phase 3: DeepWalk node embeddings (treats-free graph)
  model.py     Phase 3: logistic regression, ablations, 5-split evaluation
output/      generated charts
```

## Setup

Requires **Python 3.13** (gensim 4.4 has no Python 3.14 build yet).

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Download the data (about 14 MB in total) into `data/`:

```bash
mkdir -p data
curl -L -o data/hetionet-v1.0-nodes.tsv \
  https://raw.githubusercontent.com/hetio/hetionet/main/hetnet/tsv/hetionet-v1.0-nodes.tsv
curl -L -o data/hetionet-v1.0-edges.sif.gz \
  https://media.githubusercontent.com/media/hetio/hetionet/main/hetnet/tsv/hetionet-v1.0-edges.sif.gz
```

(The edges file is stored with Git LFS, so it comes from `media.githubusercontent.com`.
Its SHA-256 should be `611f0411ac666be4e0270e54bbca67407e14720bfc3099311f0f5eec25c5a947`.)

## Run

```bash
.venv/bin/python src/explore.py     # Phase 1
.venv/bin/python src/split.py       # Phase 2: creates data/split/
.venv/bin/python src/baselines.py   # Phase 2: writes output/baseline_results.csv
.venv/bin/python src/embed.py       # Phase 3: ~5 min, writes data/embeddings/
.venv/bin/python src/model.py       # Phase 3: writes output/phase3_*.csv/png
```

## Data source and license

Data: **Hetionet v1.0** by Daniel Himmelstein et al. (https://github.com/hetio/hetionet).
Hetionet's original content is released under **CC0 1.0** (public domain). However, it
integrates many source databases, each with its own license. See the
[source license table](https://github.com/dhimmel/integrate/blob/d482033bcaa913a976faf4a6ee08497281c739c3/licenses/README.md)
before reusing the data beyond personal/educational use.

Reference: Himmelstein DS et al. "Systematic integration of biomedical knowledge
prioritizes drugs for repurposing." *eLife* (2017). https://doi.org/10.7554/eLife.26726

## License

The code in this repository is released under the MIT License (see `LICENSE`).
The Hetionet data is not part of this repository.
