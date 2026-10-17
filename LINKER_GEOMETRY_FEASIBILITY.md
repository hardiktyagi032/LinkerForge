# Linker geometry feasibility — specification and sources

Module: `src/linkerforge/geometry/`. Tool: `scripts/evaluate_linker_geometry.py`.
Record schema: `schemas/linker-junction-geometry.v1.schema.json`.
Tests: `tests/test_linker_geometry_*.py` (80 tests, no GPU, no network, standard library only).

This is deterministic geometry for the fusion-design side of LinkerForge. It is
not part of the active DFL detector research and it trains nothing. It exists
because one real question in fusion design has a closed-form answer that no
published tool returns: **given two domain structures and a pair of candidate
attachment points, how long does the linker have to be, and what fails
geometrically if it is not.**

## 1. What it computes

Primary output, per candidate site pair: **the required linker length**.

| Quantity | Meaning |
| --- | --- |
| `minimum_residues` | Physical lower bound, at the 3.8 Å virtual Cα–Cα bond. Nothing shorter can reach. |
| `minimum_residues_design` | At the 3.5 Å per-residue rise usually quoted for extended linkers. One or two residues longer for short spans; use it to avoid a linker that only just reaches. |
| `minimum_residues_range` | The bound across the published 3.3–3.8 Å range. |
| `unstrained_residues` | Length at which the *unstretched* chain already reaches, from the published Gaussian-chain statistics of GS linkers. |
| `maximum_residues` | `null` for a flexible linker: there is no geometric ceiling, only entropic cost. A real number for a helical linker, because a rigid rod that is too long holds the domains apart. |

A verdict (`bridgeable` / `too_short` / `too_long`) is derived from that window
only when the caller names a length, so the same calculation answers both "how
long should it be" and "is this one acceptable".

Alongside the length, each junction report carries the reasoning, which is the
reason to prefer this over a learned score:

- **Span and path.** Straight Cα–Cα distance; whether the straight path crosses
  either domain's volume, with the minimum clearance and the blocking atom
  count; and, when it is blocked, a detour lower bound around the blocking
  atoms (tangent, great-circle arc, tangent). Where an anchor lies inside the
  blocking cluster no detour bound is defined, and the report says so and falls
  back to the straight distance, which is still a valid lower bound.
- **Accessibility.** Solvent accessible surface area at each attachment point by
  Shrake–Rupley sampling with a 1.4 Å probe and Bondi radii, normalised to
  relative solvent accessibility with the Tien et al. MaxASA table, reported
  with its band.
- **Orientation.** The angle between the chain's exit direction at each anchor
  and the span between the anchors, the angle between the anchor's outward
  direction from its own domain centroid and that span, and the anchor's
  distance from its domain centroid against the domain's mean radius. An anchor
  that points away from the partner needs a longer linker than the straight-line
  distance suggests, and these numbers say so explicitly.

## 2. Constants, and where each one comes from

Every constant lives in `src/linkerforge/geometry/constants.py` with its source
in `CITATIONS`, and every record embeds that dictionary. Nothing here is fitted
to LinkerForge data.

| Constant | Value | Source |
| --- | --- | --- |
| Virtual Cα–Cα bond / contour length per residue | 3.8 Å | van Rosmalen, Krom & Merkx (2017), *Biochemistry* 56(50):6565–6574, [10.1021/acs.biochem.7b00902](https://doi.org/10.1021/acs.biochem.7b00902) — `b0 = 3.8 Å` |
| Extended rise per residue (realistic) | 3.3–3.5 Å | Pauling & Corey (1951), *PNAS* 37(5):251–256, [10.1073/pnas.37.5.251](https://doi.org/10.1073/pnas.37.5.251) — pleated-sheet axial translation |
| α-helix rise per residue | 1.47–1.5 Å | Pauling, Corey & Branson (1951), *PNAS* 37(4):205–211, [10.1073/pnas.37.4.205](https://doi.org/10.1073/pnas.37.4.205) |
| Helical linkers form α-helices | — | Arai et al. (2001), *Protein Eng.* 14(8):529–532, [10.1093/protein/14.8.529](https://doi.org/10.1093/protein/14.8.529). CD and FRET trends only: the paper states **no** per-residue rise, so the rise above is used instead |
| GS-linker persistence length / C∞ | 3.7–6.2 Å / 1.9–3.4 | van Rosmalen et al. (2017), Table 1 and eq 7 |
| Worm-like chain | — | Kratky & Porod (1949), [10.1002/recl.19490681203](https://doi.org/10.1002/recl.19490681203) |
| Solvent probe radius | 1.4 Å | Lee & Richards (1971), [10.1016/0022-2836(71)90324-X](https://doi.org/10.1016/0022-2836%2871%2990324-X) |
| SASA sampling | — | Shrake & Rupley (1973), [10.1016/0022-2836(73)90011-9](https://doi.org/10.1016/0022-2836%2873%2990011-9) |
| van der Waals radii | C 1.70, N 1.55, O 1.52, S 1.80 Å | Bondi (1964), [10.1021/j100785a001](https://doi.org/10.1021/j100785a001) |
| MaxASA for RSA | per-residue table | Tien et al. (2013), *PLoS ONE* 8(11):e80635, [10.1371/journal.pone.0080635](https://doi.org/10.1371/journal.pone.0080635), theoretical column |
| Buried / exposed RSA bands | 0.09, 0.25 | Rost & Sander (1994), [10.1002/prot.340200303](https://doi.org/10.1002/prot.340200303). Published cutoffs span roughly 5–25%, so the value and all three bands are reported rather than one call |
| Disulfide Cα–Cα window | 3.8–6.5 Å | Sowdhamini et al. (1989), *Protein Eng.* 3(2):95–103, [10.1093/protein/3.2.95](https://doi.org/10.1093/protein/3.2.95) — candidates have Cα–Cα ≤ 6.5 Å and Cβ–Cβ ≤ 4.5 Å. The 3.8 Å floor is a steric modelling choice, not a published criterion |
| Optimal rigid superposition | — | Horn (1987), [10.1364/JOSAA.4.000629](https://doi.org/10.1364/JOSAA.4.000629) |

### Reconciliation of the per-residue extension figures

Two LinkerForge literature surveys reported 3.0–3.5 Å per residue for flexible
chains. That is a sound *design* figure and a wrong *bound*, and the difference
matters: a bound that is too small makes real protein segments look impossible.

Measured over every window of consecutive residues in both committed structures
(412 residues in total): consecutive Cα separations average 3.81 Å in the X-ray
protease dimer and 3.83 Å in the derived kinase file, with maxima of 3.84 Å and
3.91 Å; no window of any length exceeds 3.8 Å per residue; and short extended
segments routinely exceed 3.5 Å per residue. So 3.8 Å is used for the
bound and 3.5 Å is reported beside it as the design figure. Both tests are in
`tests/test_linker_geometry_structures.py`; the second asserts that real
segments *do* beat 3.5 Å, so the distinction cannot quietly rot.

The same reasoning fixed the steric tolerance. Across the native 4E43 protease
dimer interface the largest heavy-atom overlap against Bondi radii is 0.39 Å,
from hydrogen bonds, and nothing exceeds 0.5 Å — so 0.5 Å separates real packing
from interpenetration, and that is the clash tolerance, with the measurement
itself as a test.

## 3. Several tethers at once

Dorya's question is multi-point tethering: holding two domains in a defined
relative orientation with more than one simultaneous connection, rather than
letting a single linker leave them to flop. That is not per-pair scoring. It is
constraint satisfaction over the rigid-body placement of domain B, and it has no
closed-form solution in general. The module gives a two-sided answer and is
explicit about what each side proves.

- **`certified_infeasible` is a proof.** Domain B is rigid, so the separation of
  two of its own attachment points cannot change. For any two tethers *i*, *j*:
  `|d_A(i,j) − d_B(i,j)| ≤ max_span(i) + max_span(j)`. Violate it and no
  placement whatsoever can satisfy both tethers. The test uses upper span bounds
  only, which makes it a relaxation, so it never rejects something possible.
- **`feasible_with_witness` is a proof too, by exhibition.** The search returns
  the rotation and translation, every tether's span is rechecked at it, and the
  two domains are checked for heavy-atom overlap. The witness can be verified
  independently, which is the point.
- **`undetermined` means the search found nothing and that is all it means.**
  Alternating projection onto the span shells with a closed-form rigid refit,
  from 32 restarts, is a search with no global guarantee. A worked case is in the
  tests: a chiral anchor set against its own mirror image passes the pairwise
  condition — every distance is identical — yet no rotation can satisfy it, and
  the module reports `undetermined`, not `infeasible`.
- **`spans_satisfiable_but_domains_clash`** means every satisfying placement
  found overlapped the domains. The search optimises spans, not packing, so this
  is evidence against that attachment-point set rather than a proof.

Restart zero is always the input frame untouched, so for two domains already
positioned relative to each other the cheap question is asked first: do the
tethers already fit as things stand? For the native protease dimer they do, and
that placement is returned as the witness.

Tether types can be **mixed**. A disulfide contributes a fixed short Cα–Cα
window instead of a length-dependent reachable range, which is the cheaper way
to add a second tether: two cysteine substitutions and no chain crossing.

### Chain topology is reported, because geometry alone is not a design

Every peptide tether is one crossing of the chain between the domains, so *k*
peptide tethers need *k* crossings:

| Peptide tethers | Topology | What it requires |
| --- | --- | --- |
| 1 | tandem | The standard fusion. Both anchors are termini. |
| 2 | insertional | Domain B sits inside a surface loop of domain A: the anchors on A are that loop's two flanks, the anchors on B its two termini. |
| ≥ 3 | split or non-peptide | At least one domain must be built from two non-contiguous chain segments (split domain or circular permutation), or the construct leaves a single polypeptide: two chains, a circularised chain, or chemical crosslinks. |
| 0 (crosslinks only) | crosslink_only | Two separate chains held by crosslinks. No fusion protein and no linker length to choose. |

A geometrically satisfiable tether set with no realisable topology is not a
usable design, so the verdict and the topology are always reported together.

### Literature precedent, checked

Asked for honestly, so reported honestly.

**Two connection points are established practice**, mainly in structural
biology, where a fusion partner replaces a loop and is therefore attached twice:
BRIL replacing ECL3 of the A2A adenosine receptor (Chun et al. 2012, *Structure*
20(5):967–976, [10.1016/j.str.2012.04.010](https://doi.org/10.1016/j.str.2012.04.010)),
and T4 lysozyme replacing ICL3 of the β2 adrenergic receptor (Cherezov et al.
2007, *Science* 318:1258–1265). Both, plus the "termini restraining" format
where the target sits inside a split scaffold attached at both its termini, are
surveyed in Liu & Li (2022), *Crystals* 12(8):1041,
[10.3390/cryst12081041](https://doi.org/10.3390/cryst12081041). That review is
also the only source found with explicit geometric criteria for a two-junction
case: T4 lysozyme's terminal helices about 10 Å apart, GPCR TM5–TM6 gaps of
roughly 6–14 Å, and 8–21 Å tolerated in the termini-restraining format. A
two-linker construct with one rigid and one flexible linker exists in Choi et
al. 2019, *Chem. Sci.*, [10.1039/c9sc04158c](https://doi.org/10.1039/c9sc04158c),
though its linkers join split fragments of one fold rather than constraining two
independent domains, so it is weak precedent for this use.

**No published precedent was found for three or more simultaneous peptide
linkers between the same two independent domains**, nor for a general multi-tether
design framework. Searches covered doubly tethered domains, double-linker
fusions, bivalent tethering, conformationally constrained fusions, interleaved
domains, circular-permutation insertional fusions and the rigid-fusion
crystallography literature. A negative search result is not proof of absence,
and a separate LinkerForge thread reports a 2021 two-rigid-junction precedent
that is not verified here. Disulfide and staple-style crosslink literature was
not searched and may hold closer precedent.

**The nearest published tool does something else.** ProDomino (bioRxiv
[10.1101/2024.12.04.626757](https://doi.org/10.1101/2024.12.04.626757)) predicts
domain insertion sites from sequence alone, with ESM-2 embeddings and a
per-residue score; it uses no geometric criteria and knows nothing about the
partner domain or the linker. SynLinker (Liu, Chin & Lee 2015, *Bioinformatics*
31(22):3700–3702, [10.1093/bioinformatics/btv447](https://doi.org/10.1093/bioinformatics/btv447))
filters a linker library and accepts a target end-to-end distance in ångström,
but it selects linkers; it does not take two structures and return attachment
points. Neither answers the question above.

## 4. What is validated, and how

| Check | Evidence |
| --- | --- |
| SASA sampling | Isolated atom within 1% of 4π(r+p)²; two overlapping atoms within 2% of the spherical-cap formula; an enclosed atom gives exactly zero |
| Detour bound | Matches the tangent–arc–tangent closed form to 6 decimal places; never shorter than the straight line; an anchor inside the obstacle is an error, not a clamped number |
| Rigid superposition | Recovers a known rotation and translation to 6 decimal places; returns a rotation, never a reflection, for a mirrored set |
| Chain statistics | Gaussian and worm-like models agree within 10% for a 73-residue linker, as the source paper states; predicted end-to-end distance for (G2S4)₁ lands within 2.5 Å of the published 27.4 Å |
| Extension bound | No window of consecutive residues in 412 residues of real structure violates it (see §2) |
| Clash tolerance | A real packed dimer interface gives zero clashes; the worst real overlap is within 0.3 Å of the tolerance (see §2) |
| Required length on real coordinates | The protease dimer's C-terminus-to-N-terminus junction is 5.6 Å and needs one residue, which is why single-chain tethered protease dimers work |
| Multi-tether soundness | Mirror-image anchor set: pairwise condition passes, no placement exists, verdict is `undetermined` |
| Records | CLI output validates against the committed schema, carries input digests, commit SHA and a digest of the constants module, and is reproducible |

Fixtures are trimmed real structures with recorded provenance and digests
(`tests/fixtures/geometry/PROVENANCE.md`), rebuildable with
`scripts/build_geometry_test_fixtures.py`. They come from PyPI rather than RCSB
because this environment's network policy does not reach RCSB, PDBe or the
AlphaFold database; nothing was transcribed by hand.

## 5. Not covered

Geometry answers a geometric question. These are outside it, and the module says
so in every record rather than implying otherwise:

- **Whether the construct expresses, folds or works.** Not estimated, and no
  success probability is produced. The best published zero-shot signal is
  ESMFold pLDDT at about AUC 0.73, with every available metric combined reaching
  about 0.74, and there is no published dataset mapping fusion constructs to
  expression outcomes. If a viability flag is ever added it must be reported as
  a flag with its AUC, never as a probability.
- **Whether the two domains disrupt each other.** Clash detection at a candidate
  placement is not interface compatibility, allostery or misfolding.
- **Conformational ensembles.** One input conformation per domain, both treated
  as rigid bodies. A linker's conformational distribution is summarised by two
  published analytic chain models, not sampled. Where a sequence-level
  end-to-end distribution is wanted, ALBATROSS
  ([10.1038/s41592-023-02159-5](https://doi.org/10.1038/s41592-023-02159-5))
  predicts it from sequence and is complementary to this module, which supplies
  the *required* span that such a prediction has to meet.
- **Linker sequence design.** Only the flexible/helical/disulfide distinction is
  modelled. Composition enters solely through the published GS chain statistics.
- **Side-chain geometry of a disulfide.** Only the Cα–Cα window is checked, not
  Cβ–Cβ, χ3 or the redox environment.
- **Insertional geometry as such.** End-to-end fusion is the default. The
  two-junction case is modelled as a tether set, which is the right constraint
  structure, but loop-specific requirements (whether a given loop tolerates
  interruption, and what the two flanking junctions each need) are not modelled
  yet.

Where learning is genuinely needed rather than geometry: which loops and termini
tolerate interruption, whether two domains are compatible as folds rather than
as shapes, and construct viability. None of those is in here.

## 6. Usage

```bash
# Required linker length for one junction, and a verdict on a 5-residue linker
python scripts/evaluate_linker_geometry.py junction \
    --structure tests/fixtures/geometry/4e43_protease_dimer.pdb \
    --chain-a A --anchor-a 99 --chain-b B --anchor-b 1 \
    --linker-type flexible --residues 5

# Two simultaneous tethers, solving for the relative placement of domain B
python scripts/evaluate_linker_geometry.py tethers \
    --structure tests/fixtures/geometry/4e43_protease_dimer.pdb \
    --chain-a A --chain-b B \
    --tether 99:1:flexible:2 --tether 1:99:flexible:2

# Tests
PYTHONPATH=src python3 -m unittest discover -s tests -p "test_linker_geometry*.py"
```

`--structure-b` reads domain B from a second file, so two independently
predicted or downloaded domains can be combined. For a tether set, domain B's
input coordinates are treated as its internal geometry only; the search places
it and reports where.

The citations in this document are additional to
`LINKERFORGE_CURRENT_CITATIONS.md` and are deliberately not merged into it,
since that list is shared and has its own numbering and count.
