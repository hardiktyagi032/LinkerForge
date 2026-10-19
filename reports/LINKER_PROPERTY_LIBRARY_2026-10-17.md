# Linker property library and property classifier

Date: 17 October 2026. Status: curated template library plus a two-axis property
caller, with an honest coverage audit. This is **not** detector training, does
not touch the DFL split, and launches no GPU job. It is forward-looking scope
for the fusion-linker *design* model, which README Sections 1-16 retain as
future context.

Scope note against the frozen decisions in `AGENTS.md`: the MVP demonstration
linker is flexible, non-cleavable and GS-rich, and protease-cleavable linker
design is listed as an MVP non-goal. Nothing here changes that. The library
exists so that a later conditional design model has a cited set of templates to
be conditioned against, and so the cleavable axis is characterised before anyone
builds for it.

## What was asked, and what the answer turned out to be

The task was to build a curated library of known fusion-protein linkers labelled
for cleavability and rigidity, write a classifier that predicts both from an
arbitrary sequence with calibrated confidence, and answer two questions: whether
the four property combinations are genuinely orthogonal, and whether a template
library plus substitution beats generative modelling here.

The short version of what came back:

1. The four combinations are **not** orthogonal, and the strongest evidence is a
   count rather than an argument. In the canonical review, every cleavable
   linker is unassigned on the rigid/flexible axis. The literature does not
   treat cleavability as one axis of a 2x2; it treats it as a third category
   parallel to flexible and rigid.
2. Only one of the two axes is a learning problem. Cleavability is a cited
   motif lookup. Rigidity is compositional and does carry real signal, but on
   this much data a learned model is a restatement of a published sentence.
3. "Calibrated confidence" is not deliverable at this sample size and is not
   claimed. Out-of-fold probabilities are published instead.

## Prior art: this library is infrastructure, not a contribution

SynLinker (Liu et al. 2015, doi:10.1093/bioinformatics/btv447) already did most
of this: roughly 2,150 natural plus 110 engineered linkers, searchable by
length, composition, end-to-end distance, amino-acid enrichment and **protease
sensitivity**, with fusion-structure prediction from two uploaded domains. A
curated, property-labelled linker library is therefore not novel, and nothing
in this report should be presented as a contribution. The library is built to
be used downstream, which is why the work went into structure, provenance and
honest labels rather than into exhaustive coverage.

Two corrections to how this prior art has been described inside the project.

First, SynLinker was already on record here. It is the first row of the
closest-work table in
`literature/LINKER_MOTIF_DISCOVERY_SURVEY_2026-10-12.md`, with the same counts
and the same conclusion that cataloguing natural linkers is not novel. This was
known five days ago, not newly discovered.

Second, "already exists" overstates what is reachable. Its home page states the
service changed URL in March 2016 and does not give the new address, which is
also what the October survey concluded when it tried to acquire the rows. So
SynLinker establishes prior art decisively and supplies no usable data, which
is the worst of both worlds: it removes the novelty claim without removing the
need to build something. That is the situation this library is responding to.

## The library

`data/curated/linker_property_library_sources.v1.json`, validated by
`schemas/linker_property_library.v1.schema.json`.

- 30 entries, 27 with an exact sequence; 13 of them carry a usable rigid/flexible label.
- Every entry carries a source, a locator inside that source, and the primary
  work the source attributes it to.
- Curation source: Chen, Zaro and Shen, *Fusion protein linkers: property,
  design and functionality*, Adv Drug Deliv Rev 65 (2013) 1357-1369,
  doi:10.1016/j.addr.2012.09.039. `pmc.ncbi.nlm.nih.gov` served this
  environment a reCAPTCHA interstitial, so the text was read from the copy
  filed at the USPTO; the exact URL is recorded in the library file.

### Evidence tier

This is **literature-reported engineered use**. It is a strictly weaker tier
than the function-tested criterion defined in
`reports/EXPERIMENTALLY_TESTED_LINKER_SOURCE_SEARCH_2026-10-12.md`, which
requires an exact sequence, a named context, and a measured readout for that
sequence. Most entries here satisfy the first two and report a readout only
qualitatively. No count in this report may be carried into a claim about
function-tested linkers.

### What was deliberately not done

Three entries have `sequence: null`, because the source gives a pattern, a
length range, or a compressed notation rather than a string. A fourth has a
sequence but no label on either axis. All four are excluded from modelling:

- `(Ala-Pro)n`, 10-34 residues. The source gives a length-activity trend, not a
  per-construct sequence.
- `(Cys-Trp)n`, recorded as a published **negative** control that did not
  improve activity.
- The pyruvate dehydrogenase natural linker, printed in run-length compressed
  notation. Expanding it is mechanical but unverified, and this library must not
  contain a sequence no paper printed.
- The `LE` dipeptide, which the review assigns to no category.

The schema enforces this: a null sequence must be flagged excluded with a
reason. There is no code path that invents a string to fill the field.

Two databases were investigated and **not** incorporated. LinkerDB is live and
offers bulk downloads of natural inter-domain linkers split by helicity, but
this container's egress allowlist denies `ibi.vu.nl`, so nothing from it is in
the file. SynLinker advertises roughly 2,150 natural and 110 engineered linkers
searchable by protease sensitivity, but its home page states it changed URL in
March 2016 without giving the new address, matching the conclusion already in
`literature/LINKER_MOTIF_DISCOVERY_SURVEY_2026-10-12.md`. Both are recorded
under `acquisition_status` so a cited database cannot be mistaken for an
incorporated one.

### Transcription honesty

Three entries are flagged `transcription_confidence` because the source itself
is internally inconsistent, not because the transcription is doubtful. The
review prints its own flagship helical linker three different ways across the
main text, Table 4 and Figure 3, and its text and figure reference numbers
disagree for four cleavable examples. All four discrepancies are recorded in
the library file. Anyone taking a sequence from this library to the bench should
resolve it against the attributed primary paper first.

## Question 1: are the four combinations orthogonal?

No. The coverage matrix over all 30 entries:

| rigidity \ cleavability | cleavable | non-cleavable | unassigned |
|---|---:|---:|---:|
| rigid | **0** | 6 | 0 |
| flexible | **0** | 8 | 0 |
| unassigned | 13 | 0 | 3 |

Two things are visible here that an argument alone would not establish.

**The cleavable column is entirely unassigned on the rigidity axis.** All 13
cleavable entries sit in the unassigned row. This is not missing data to be
imputed. It is the shape of the source taxonomy: the review has sections for
flexible linkers, rigid linkers and in vivo cleavable linkers, as three
parallel categories. Asking for "rigid and cleavable" asks for a cell the
literature never filled in, so a generator conditioned on a 2x2 would be
conditioned on a grid that has no training examples in half its cells.

**The rigid-plus-cleavable combination is physically awkward, and this is now
confirmed rather than predicted.** A scissile bond needs local backbone freedom
to reach a protease active site. Hubbard, Eisenmenger and Thornton
(doi:10.1002/pro.5560030505) show limited-proteolysis sites require a local
conformational change before cleavage, and a thrombin study finds a scissile
bond inside an alpha-helix is not cleaved until the helix unfolds. An EAAAK
helix is the opposite of what a protease needs.

The library's own data agrees independently: the review's MMP-cleavable
construct places the `PLGLWA` motif **between two GGGGS sequences**, and its
Factor Xa site is glycine-padded. The standard practice is already composite.
A short scissile cassette with flexible padding does the cleaving, and whatever
else is in the construct does the spacing.

So the combination is buildable, but not as one sequence class. The library
records it as `composite_templates[rigid-cleavable-composite]`: a rigid spacer
carrying length and orientation, plus a short flexible protease cassette at one
end rather than inside the rigid element. A conditional generator should be
asked to emit the parts and their order, never a single homogeneous segment for
this cell.

One further note on the axes themselves. `PAPAP` and `(EAAAK)n` are both
labelled rigid by the same review, but by two different mechanisms, proline
rigidity and helical rigidity. Rigidity is not one direction in composition
space. That matters below.

## Question 2: template library plus substitution, or generative modelling?

Template library plus substitution, for the cleavable and length dimensions
without qualification, and for rigidity until there is far more labelled data.
The reasoning is now partly empirical rather than purely a prior.

**Cleavability is not a learning problem.** A protease recognition site is a
published consensus for a named protease. Deciding whether a linker carries a
known site is a table lookup; generating a *novel* site means predicting
protease specificity, which is a different and harder problem that no fusion
linker project needs to solve. `src/linkerforge/properties/cleavability.py` is
therefore explicitly not a model, and the negative call is `no_known_motif`,
never `non_cleavable`, because the table covers one review's proteases and its
recall against the protease universe is unknown and certainly low. A learned
classifier here would wrap a lookup in a model and lose the citation.

**Length is a repeat count**, not something to learn.

**Rigidity carries real compositional signal, and a tiny model captures it.**
`src/linkerforge/properties/rigidity.py` is an L2 logistic regression on six
features, chosen to be exactly the residue groups named by the review's two
composition sentences rather than tuned on this data.

| | |
|---|---|
| labelled entries | 13 (5 rigid, 8 flexible) |
| leave-one-out accuracy | 0.923 (12/13) |
| majority baseline | 0.615 |
| label-permutation p | 0.005 (200 rounds, the floor: no permutation matched) |
| linearly separable in sample | yes |

Composition beats the permutation null, so the signal is real. But read the
rest of the numbers before reading that as a win:

- The single out-of-fold miss is `PAPAP`, predicted flexible. The fitted
  coefficients put almost all the rigidity weight on alanine content (+1.04)
  and very little on proline (+0.29), because there is exactly one Pro-rich
  rigid exemplar. The model learned helical rigidity and is effectively blind to
  proline rigidity. This is the mechanism-count problem from Question 1 showing
  up as a concrete error, and it is pinned by a test that will fail if the
  library later gains Pro-rich entries.
- Out-of-fold probabilities span only 0.20 to 0.53. Under the regularisation
  the labelled set needs, the model is a weak separator, not a confident one.
  A reliability diagram on 13 points would be noise, so none is reported;
  the per-entry out-of-fold probabilities are published in the JSON instead.
  **The brief asked for calibrated confidence. At this sample size that is not
  deliverable and it is not claimed.**

The honest summary is that the learned rigidity model reproduces a sentence
from a 2013 review and currently reproduces only half of it. A hand-written
rule on the same features would score the same. That is an argument for
shipping the template library first and treating any model as the thing that
has to earn its place against it.

### One correction to the prior

An earlier version of this argument leaned on engineered fusion linkers
numbering in the low hundreds, which would make a generator mostly a memoriser.
That holds for *engineered* linkers but understates the eventual training set,
because natural inter-domain linkers run to thousands and this project mines
natural linkers. It weakens the memorisation argument without changing the
ranking: more natural linkers do not supply cleavability or design-intent
rigidity labels, which is what a conditional generator would need.

LinkerDB's helicity split is the most promising route to a labelled set an
order of magnitude larger than this one, and it is worth being precise about
what it would provide. Helicity measured from structure is **not** the same
axis as engineered rigid/flexible design intent: a helical natural linker is
not necessarily a rigid spacer, and a non-helical one may be extended or
Pro-rich rather than flexible. The library records this distinction rather than
merging the two axes. Acquiring LinkerDB is the top data task, and it is
currently blocked by the network policy, not by the science.

## The decisive experiment that should run next

Hold out natural linkers and test whether template retrieval plus substitution
reconstructs them from the flanking domains alone. If retrieval scores well, a
generator has little room to add value and that is known within about a week,
before anyone builds one. It is the cheapest decisive result available.

It is **not** run here, and the reason is concrete: it needs natural linkers
with their flanking domain context, which means LinkerDB or an equivalent, and
the acquisition is blocked above. Running it against the 27 sequence-bearing entries
in this library instead would be meaningless, because they have no natural
flanking context to retrieve from. Scoped, not done, and not quietly
substituted with a weaker proxy.

When it does run, it needs a retrieval baseline alongside the reconstruction
score: nearest library entry by flanking context, scored the same way. The
sharp question is not whether a generator can reconstruct held-out linkers, it
is whether it beats straightforward retrieval from a curated library. If
retrieval wins, that is a real finding about linker design and it is worth
publishing even though the library itself is not.

One caution on how to report whatever comes out of it. Mined natural linkers
have no functional labels at all, while a single 2026 screen (Li et al.,
doi:10.1016/j.synbio.2026.02.003) carries 370 experimentally measured ones.
Breadth without labels does not beat labels without breadth, so library size is
not a quality claim and must not be reported as one. The coverage matrix above
is a map of what the literature labelled, not a score.

## Reproducing

Standard library only; no backend environment is needed and none is claimed.

```bash
python3 -m unittest discover -s tests -p test_linker_property_library.py -v
python3 scripts/build_linker_property_report.py
```

The second command writes `reports/linker_property_library_2026-10-17.json`
with the coverage matrix, the label-basis audit, the out-of-fold predictions,
and SHA-256 hashes of the library, schema and script plus the commit SHA.

## Label-basis audit

Of the 30 entries, the rigidity and cleavability labels break down by how they
were obtained, and the split is in the JSON record. The one inference this
project makes is marking a non-cleavable entry as non-cleavable because the
source lists it under a non-cleavable category and names no scissile element.
That is recorded as `inferred_from_category_exclusion`, not as a source
statement, and a test fails if any non-cleavable label claims to be
source-stated. Every rigidity label is the source's own category heading.
