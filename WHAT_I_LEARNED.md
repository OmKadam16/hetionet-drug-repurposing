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
