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
