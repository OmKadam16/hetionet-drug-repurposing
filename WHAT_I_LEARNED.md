# What I learned – Phase 1

## What is a knowledge graph?

A knowledge graph is a way of storing facts as a network of **things** and the
**relationships** between them.

- The things are called **nodes** (for example: the drug *Doxorubicin*, or the
  disease *uterine cancer*).
- The relationships are called **edges** (for example: *Doxorubicin* —treats→
  *uterine cancer*).

Every node has a **type** (Gene, Compound, Disease, ...) and every edge has a
**type** too (treats, binds, is associated with, ...). Because there are many kinds of
nodes and edges, Hetionet is called a *heterogeneous network* ("hetnet").
The useful part is that you can follow chains of edges, such as
drug → binds → gene → is associated with → disease, to connect facts that come
from completely different databases.

## What does Hetionet contain?

Hetionet v1.0 combines facts from many public biomedical databases into one graph.
From the files I downloaded:

- **47,031 nodes** of **11 types**. Most are genes (20,945) and biological processes
  (11,381). There are 1,552 compounds and 137 diseases.
- **2,250,197 edges** of **24 types**. The largest are Gene–participates–Biological
  Process (559,504) and Anatomy–expresses–Gene (526,407).

Each edge type has a short code. The letters stand for the node types and the
relationship, for example `CtD` = **C**ompound **t**reats **D**isease, `CbG` =
Compound binds Gene, `DaG` = Disease associates Gene.

## Why the "treats" edges matter for drug repurposing

**Drug repurposing** means finding a new disease that an *existing, already approved*
drug could treat. It is attractive because the drug's safety is already known, so it
can be faster and cheaper than inventing a new drug.

Hetionet has **755 Compound–treats–Disease (CtD) edges**, connecting 387 drugs to 77
diseases. These are the *known* treatments, for example Doxorubicin treats uterine
cancer and Reserpine treats hypertension.

These edges matter because they are our **"right answers"**:

1. **Learning:** we can look at the paths that connect a drug to a disease it is known
   to treat (through genes, pathways, side effects, ...) and learn which kinds of
   paths are typical of real treatments.
2. **Predicting:** we can then score drug–disease pairs that are *not* connected by a
   treats edge yet. A pair that looks like a known treatment is a candidate for
   repurposing.
3. **Checking:** we can test a method by hiding some known treats edges and seeing
   whether it finds them again.

The CtD set is small: 755 edges out of more than 2.2 million. A model has very few
positive examples to learn from, which is something to keep in mind in later phases.

---

# Phase 2: what I learned

## A fair test

To find out whether a method can predict *new* treatments, I hid 20% of the known
treatments (151 of 755, chosen at random with seed 42) and let methods learn only
from the other 604. Each method then scores every drug–disease pair, and I check
whether the hidden 151 end up near the top.

- **Evaluation pairs:** all 1,552 × 137 = 212,624 Compound × Disease pairs, minus the
  604 training treatments (we already know those, so ranking them says nothing) and
  minus the 390 "palliates" pairs. That leaves 211,630 pairs, of which 151 are positives.
- **Why palliates is excluded:** a palliative drug relieves symptoms without changing
  the disease itself. It is not a real treatment, so it isn't a positive. It does help
  patients, so a method that ranks it highly isn't really wrong either, which means it
  isn't a fair negative. Because the label is unclear, those pairs are left out.
- **Only 1 in about 1,402 pairs is a positive.** This imbalance drives most of what follows.

## Data leakage

**Data leakage** happens when information about the answers slips into the method,
so the test score looks better than the method really is. It's like a student who
saw the exam beforehand. Here it would happen if any score used a test treatment,
for example counting "similar drugs that treat this disease" using *all* treats
edges, including the hidden ones. To prevent it, `baselines.py` deletes **every**
treats edge from the graph and passes in only the 604 training ones. It then checks
in code that no test pair appears anywhere in the data the baselines use.

## The four baselines

| Baseline | Idea |
|---|---|
| Random | Random number. Shows what "no knowledge at all" scores. |
| Popularity | (drug's # of training treatments) × (disease's # of training treatments) |
| Shared genes | # of genes the drug binds that are also associated with the disease |
| Similar drugs | # of chemically similar drugs that treat the disease (training only) |

**Why the popularity baseline matters:** it knows *nothing* about biology. It only
knows that some drugs treat many diseases and some diseases have many drugs, so
those pairs are more likely to have a treatment edge. If a fancy model can't beat
this, its "predictions" may just be reflecting which drugs and diseases are
well-studied, not real biology.

## The metrics

- **AUROC:** if you pick one real treatment and one non-treatment at random, AUROC is
  the chance the method scores the real one higher. 0.5 means guessing; 1.0 is perfect.
- **AUPRC (average precision):** roughly, the average precision as you walk down the
  ranked list and collect the real treatments. A random method scores about the
  fraction of positives (here ~0.0007), so it is judged against *that*, not 0.5.
- **Why AUPRC matters when positives are rare:** AUROC mostly rewards pushing the huge
  pile of 211,479 negatives down. A method can get a good AUROC while its top picks are
  still mostly wrong. AUPRC focuses on the top of the list, which is the part a
  researcher would actually test in the lab.
- **Precision@k:** of the top k predictions, the fraction that are real held-out
  treatments. It is easy to explain ("2 of our top 20 were right"), but with only 20
  or 100 pairs it is very noisy.
- **Ties:** many pairs share the same score (often 0). I break ties randomly with the
  fixed seed so the top-k lists don't depend on file order.

## Results (from `output/baseline_results.csv`)

| Baseline | AUROC | AUPRC | AUPRC vs random | hits in top 20 | hits in top 100 |
|---|---|---|---|---|---|
| random | 0.493 | 0.0007 | 1.0× | 0 | 0 |
| popularity | 0.762 | 0.0186 | 26× | 1 | 5 |
| shared genes | 0.772 | 0.0083 | 12× | 2 | 3 |
| similar drugs | 0.717 | 0.0218 | 31× | 1 | 6 |

What I take from this:

1. **All three real baselines clearly beat random.** There is real signal in the graph.
2. **The "dumb" popularity baseline is almost as good as the biology-based ones.** It
   beats shared genes on AUPRC (0.0186 vs 0.0083). This is exactly why it is needed
   as a reference point.
3. **AUROC and AUPRC disagree.** Shared genes has the best AUROC but the worst
   AUPRC among the real baselines. Judged only by AUROC, I'd pick the wrong method
   for making a short list of candidates.
4. **Absolute performance is still low.** The best AUPRC is about 0.02, and at most 6 of
   the top 100 picks are real held-out treatments.
5. **Coverage limits the count-based methods.** Similar drugs gives a score above 0 to
   only 67 of the 151 test treatments, so the rest are tied with tens of thousands of
   zero-scored pairs. Combining several kinds of evidence should help, and that is the
   point of Phase 3.

## Top predictions of the best baseline (similar drugs)

All top 10 are corticosteroid-type drugs predicted for **asthma**, because asthma has
many corticosteroid treatments in training and these drugs resemble each other
chemically. Only one (Dexamethasone → asthma) is a held-out treatment. "Not a
held-out treatment" only means *Hetionet doesn't list it*. It doesn't prove the
prediction is wrong, and it doesn't prove it's right. This also shows a weakness:
the method keeps recommending the same kind of drug for the same disease, which is
"more of the same," not a surprising new use.

---

# Phase 3: what I learned

## Five splits instead of one

One 80/20 split can be lucky or unlucky. I repeated everything over **5 different random
splits** (seeds 0–4) and report the **mean ± standard deviation**. If two methods' ranges
overlap a lot, the difference might just be luck. I also compared methods **split by split**
(a "paired" comparison): some splits are harder than others for every method, and
comparing on the same split cancels that out.

## Embeddings, in plain words

An **embedding** is a list of numbers (here 64) that describes a node. Nodes in similar
parts of the graph get similar lists. That turns "where a node sits in the graph" into
numbers that a normal machine-learning model can use.

I used **DeepWalk** (node2vec with its two extra settings at their neutral value):

1. **Random walks:** start at a node and keep hopping to a random neighbor, 40 steps,
   10 walks from every node. Nodes that are close in the graph keep appearing in the
   same walks, so the walks record each node's **neighborhood**.
2. **word2vec:** treat each walk as a sentence and each node as a word. word2vec gives
   similar vectors to words that appear near each other, so here nodes that appear near
   each other in walks get similar vectors.

Practical details: word2vec runs on one CPU thread, so results are identical on every
run (I checked this). It takes about 50 s per embedding and ~760 MB peak memory on my M3
MacBook Air, 255 s for all five. gensim printed ~20 harmless-looking internal warnings per
run, affecting at most a handful of the roughly billion small updates. 1,873 nodes (including 14
compounds and 1 disease) have no edges once treats edges are removed. They can't be walked
to, so they get all-zero vectors.

**Python version:** gensim 4.4 has no Python 3.14 build yet (pip silently installed a 2014
version that crashes), so the project now uses Python 3.13. Phase 1–2 results came out
identical on 3.13.

## A second kind of leakage: shortcuts in the training data

Phase 2's leakage was about **test answers** sneaking in. Phase 3 has a subtler kind:
**training examples that look different from the cases we want to find**, so the model
learns a shortcut that only works on training data.

- **In the graph:** if training treats edges stay in the random-walk graph, every training
  treatment is a *direct link*, and its drug and disease get very close vectors.
  Hidden test treatments never have that link. The model would learn "directly linked =
  treats", a rule that can never fire on the pairs we actually want to discover. So I
  removed **all** Compound-treats-Disease edges from the walk graph. The embeddings then
  describe only biology (genes, pathways, side effects...).
- **In the popularity feature:** a training treatment counts *itself* in its drug's and
  disease's treatment counts, so its popularity is always at least 1. With split 0, **0%**
  of training positives had popularity 0, versus **42%** of test positives. With a
  **leave-one-out** correction (don't count the pair's own edge), **38%** of training
  positives have popularity 0, much closer to the test set. (Shared genes uses no
  treats edges, and similar drugs only uses *other* drugs' treatments, so they need no
  correction.)

Treatment information now enters the model **only** through the three baseline
features, all computed from training treatments with the leave-one-out rule.

## The model

- **Features** for a pair: drug vector × disease vector, element by element (64 numbers;
  large when both vectors are large in the same directions, a learnable "closeness"),
  plus the 3 baseline scores (log-transformed because counts are very skewed).
- **Logistic regression:** a weighted sum of the features turned into a 0–1 score. Each
  weight says how much a feature pushes a pair towards "treats".
- **Training data:** 604 training treatments as positives, 6,040 random other pairs as
  negatives (10 per positive).
- **"Negatives" that might be treatments:** a random pair with no treats edge is not
  proven to be useless. It may be a treatment nobody has recorded yet. In fact, 2–8 hidden
  test treatments per split were drawn as negatives, which I couldn't avoid without
  peeking at the test set. It's acceptable because real treatments are so rare (about 1 in
  1,400 pairs) that almost all random negatives really are negatives, and the noise only
  makes the model's job slightly *harder*, never artificially easier.
- **Never test on what you trained on:** the sampled negatives are removed from that split's
  evaluation set, for all methods equally (205,590 pairs and 143–149 positives remain per split).

## Results (mean ± std over 5 splits; `output/phase3_results.csv`)

| Method | AUROC | AUPRC | P@20 | P@100 |
|---|---|---|---|---|
| random | 0.511 ± 0.030 | 0.0007 ± 0.0001 | 0.00 ± 0.00 | 0.000 ± 0.000 |
| popularity | 0.767 ± 0.008 | 0.0199 ± 0.0031 | 0.05 ± 0.07 | 0.056 ± 0.020 |
| shared genes | 0.747 ± 0.026 | 0.0066 ± 0.0017 | 0.07 ± 0.03 | 0.030 ± 0.010 |
| similar drugs | 0.733 ± 0.026 | 0.0297 ± 0.0071 | 0.09 ± 0.04 | 0.082 ± 0.015 |
| baselines-only model | 0.918 ± 0.009 | 0.1118 ± 0.0252 | 0.42 ± 0.08 | 0.220 ± 0.053 |
| embeddings-only model | 0.888 ± 0.008 | 0.0159 ± 0.0061 | 0.06 ± 0.05 | 0.038 ± 0.011 |
| **full model** | **0.943 ± 0.011** | **0.1175 ± 0.0383** | **0.43 ± 0.12** | 0.212 ± 0.065 |

**Does the full model beat popularity beyond the noise? Yes.** It wins on every metric in
**all 5 splits**. AUPRC is higher by +0.098 ± 0.037 on average (about 6× popularity), and
on average 8.6 of its top 20 are hidden treatments versus 1 for popularity.

**But the ablations change the story about *why*:**

1. **Most of the gain comes from combining the three simple scores.** The baselines-only
   model (3 features) is about as good as the full model on AUPRC and precision@k. I
   checked this wasn't a training artifact: just adding up the three standardized scores,
   with no training at all, already gives AUPRC 0.074–0.117 across the splits. The scores
   are complementary: each alone is 0 for most pairs, so they can't rank pairs that score
   0. Together they break those ties.
2. **Embeddings help AUROC, not the top of the list.** Full vs baselines-only: AUROC higher
   in 5/5 splits (+0.025 ± 0.009), but AUPRC better in only 3/5 (+0.006 ± 0.027), P@20 in
   2/5, P@100 in 2/5. Those differences are within the noise. The embeddings help sort
   the big middle of the list, not the top candidates a researcher would test.
3. **Embeddings alone have a high AUROC (0.888) but low AUPRC (0.016), *below*
   popularity.** This is the AUROC-vs-AUPRC lesson from Phase 2 again: good at pushing
   obvious non-treatments down, not at putting real treatments at the very top.

Honest summary for an interview: *"A logistic regression combining simple graph features
beats the popularity baseline by about 6× in average precision across 5 splits. The
DeepWalk embeddings add a consistent AUROC gain, but no reliable gain in top-of-list
precision, so the useful signal comes mostly from the known-treatment features."*

## Top new predictions (for Phase 4, not claims)

`output/phase3_top15_new_predictions.csv` lists the 15 highest-scoring pairs that are not
known treats or palliates edges. Many are "more of the same": corticosteroids for asthma
and psoriasis, beta-blockers for hypertension, cancer drugs for other cancers. The model
leans heavily on the similar-drugs and popularity features. The scores (around 0.997–0.999) are only
useful for **ranking**. They are not real probabilities, because the model was trained on
1 positive per 10 negatives, while in reality it's about 1 per 1,400. Whether any of these
are real is for Phase 4 to check against outside evidence.
