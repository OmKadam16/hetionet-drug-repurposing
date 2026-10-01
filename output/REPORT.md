# Predicting Drug Repurposing Candidates from the Hetionet Knowledge Graph

*Om Kadam · Code and full results: https://github.com/OmKadam16/hetionet-drug-repurposing*

## 1. Introduction

Drug repurposing looks for new uses of existing, already-approved drugs. Their safety is known, so this can be faster and cheaper than developing a new compound. Biomedical knowledge graphs combine many databases into one network of drugs, genes, diseases and other entities, which makes it possible to search for candidate drug–disease pairs systematically. This project asks: **using Hetionet v1.0, can a simple, explainable model recover hidden known treatments, and are its top new predictions credible?**

## 2. Data

Hetionet v1.0 (Himmelstein et al., *eLife* 2017; original content CC0) contains 47,031 nodes of 11 types and 2,250,197 edges of 24 types. The prediction target is the 755 Compound–treats–Disease (CtD) edges, which connect 387 drugs to 77 diseases. There are 1,552 × 137 = 212,624 possible Compound × Disease pairs. The 390 Compound–palliates–Disease pairs were excluded from both positives and negatives because their label is ambiguous.

## 3. Methods

**Evaluation.** For each of 5 random splits (seeds 0–4), 20% of CtD edges (151) were hidden as test positives. Every other pair that is not a known treatment or palliation served as a negative. The 10 sampled training negatives per positive were removed from the evaluation set, leaving 205,590 pairs and 143–149 positives per split, i.e. about 1 positive per 1,400 pairs. Metrics: AUROC, AUPRC (average precision) and precision at the top 20 / 100. Results are reported as mean ± standard deviation over splits, and methods were also compared per split (paired).

**Baselines.** Three counts were computed from training treatments only:
- *popularity*: the drug's number of treatments × the disease's;
- *shared genes*: Compound–binds–Gene–associates–Disease paths;
- *similar drugs*: Compound–resembles–Compound–treats–Disease paths.

A random score gives the floor.

**Embeddings.** DeepWalk (node2vec with p = q = 1) learned 64-dimensional node vectors: 10 uniform random walks of length 40 per node, then skip-gram word2vec (window 5; gensim, single thread for reproducibility). Each run took about 50 s on a laptop, with a peak of about 760 MB of memory.

**Model.** A logistic regression (standardized features, L2 regularization) used 67 features per pair: the element-wise product of drug and disease vectors (64), plus the three log-transformed baseline counts. Two ablations used embeddings only and baselines only.

**Leakage control.** Two kinds of leakage were handled:
1. **Test leakage.** No test edge is used by any score.
2. **Shortcut leakage.** Training positives must not look systematically different from the hidden test positives. Therefore:
   - all CtD edges (training and test) were removed from the random-walk graph, because directly linked training pairs would otherwise get artificially close embeddings;
   - popularity was computed leave-one-out for training positives. Without this, 0% of training positives had popularity 0, versus 42% of test positives in split 0; with it, 38%.

**Explanations and reality check.** For the top 15 new predictions of a final model trained on all 755 treatments, I decomposed each logit into feature contributions (weight × standardized value). I listed supporting Hetionet paths, ranked by specificity (the product of intermediate-node degree^−0.5). Each pair was searched in FDA labels (openFDA/DailyMed), ClinicalTrials.gov (API v2, restricted to the intervention and condition fields) and PubMed. Each pair received one label with a source link.

## 4. Results

| Method | AUROC | AUPRC | P@20 | P@100 |
|---|---|---|---|---|
| random | 0.511 ± 0.030 | 0.0007 ± 0.0001 | 0.00 ± 0.00 | 0.000 ± 0.000 |
| popularity | 0.767 ± 0.008 | 0.0199 ± 0.0031 | 0.05 ± 0.07 | 0.056 ± 0.019 |
| shared genes | 0.747 ± 0.026 | 0.0066 ± 0.0017 | 0.07 ± 0.03 | 0.030 ± 0.010 |
| similar drugs | 0.732 ± 0.026 | 0.0297 ± 0.0071 | 0.09 ± 0.04 | 0.082 ± 0.015 |
| model: baselines only | 0.918 ± 0.009 | 0.1118 ± 0.0252 | 0.42 ± 0.08 | 0.220 ± 0.053 |
| model: embeddings only | 0.888 ± 0.008 | 0.0159 ± 0.0061 | 0.06 ± 0.05 | 0.038 ± 0.011 |
| model: full | 0.943 ± 0.011 | 0.1175 ± 0.0383 | 0.43 ± 0.12 | 0.212 ± 0.065 |

![Results over 5 splits](phase3_comparison.png)

- **The full model beats popularity on every metric in all 5 splits.** The paired AUPRC difference is +0.098 ± 0.037, roughly 6× popularity's AUPRC.
- **The gain comes mainly from combining the three simple scores.** Simply summing them, with no training, already gave an AUPRC of 0.074–0.117 across splits.
- **The embeddings add a consistent AUROC gain** over baselines-only (+0.025 ± 0.009, 5/5 splits). They give **no reliable gain at the top of the ranking** (AUPRC +0.006 ± 0.027, better in 3/5; P@20 and P@100 better in 2/5).
- **Embeddings alone show why AUROC misleads with rare positives:** AUROC 0.888 but AUPRC 0.016.

## 5. Reality check of the top 15 predictions

"Similar drugs" was the largest contributor to every one of the top 15 scores. Against public sources:
- **1 is already approved:** hydrocortisone for leukemias and lymphomas. The FDA label lists it, but for *palliative* management.
- **6 have been tested in clinical trials:** daunorubicin and vincristine for breast cancer; paclitaxel for prostate cancer; budesonide, mometasone and desonide for psoriasis. Topical steroid labels cite "corticosteroid-responsive dermatoses" rather than psoriasis, so these may already be routine.
- **1 has published preclinical evidence:** budesonide for atopic dermatitis.
- **7 have no evidence found.**

By my assessment, 2 are plausible new hypotheses (budesonide for atopic dermatitis, estropipate for prostate cancer). The other 6 are likely artifacts:
- topical steroids predicted for asthma;
- ophthalmic beta-blockers (metipranolol, levobunolol) predicted for systemic hypertension;
- nateglinide, through chemical resemblance to ACE inhibitors;
- isoprenaline, a beta-agonist linked through resemblance to beta-blockers.

## 6. Limitations

- **Popularity and similarity bias.** The model favors diseases and drugs that already have many treatments, so its top predictions are mostly analogues of existing therapies.
- **Missing pharmacology in the graph.** Hetionet records neither the route of administration nor the direction of drug action. Gene paths often run through broadly connected drug-metabolism genes (e.g. CYP3A4, ABCB1).
- **Label noise.** Labels come from a single 2017 snapshot, and unlabeled pairs are treated as negatives.
- **Small test sets.** About 150 positives per split, so precision@k is noisy.
- **Manual reality check.** It was done once, by one person, on 2026-10-01. "No evidence found" reflects only the searches performed.

## 7. Next steps

1. Evaluate on drugs and diseases with few known treatments, and add an explicit popularity penalty, so the model is rewarded for non-obvious predictions.
2. Down-weight hub genes (for example with degree-weighted path counts as features) and use drug–target direction (agonist vs antagonist) from an external source.
3. Filter candidates by route of administration using FDA label metadata.
4. Compare against a supervised graph neural network or the original Hetionet "Project Rephetio" path-based model, and re-check top predictions against newer trial registrations.
