# LinkerForge million-scale linker detector and streaming ranker

Status: implementation contract, 8 October 2026. The million-scale run has
**not** begun. The 120-chain CATH/RCSB baseline is a diagnostic only; its 91
accepted gaps all contain unresolved linker coordinates and are not gold labels.

## 1. Scientific separation

1. **Reference detector training:** residue-level IDL/DDL/non-linker annotations
   from DLD, supplemented by separately identified, experimentally curated
   DisProt flexible-linker annotations. DLD labels are systematically derived
   reference annotations, not all experimental gold labels. Hold out whole
   UniRef50 or more stringent homology clusters
   before selecting model, thresholds, or features. A chain with no positive
   linker residues is an explicit negative example.
2. **Detector output:** for each sequence and domain map, probability of IDL,
   DDL, and non-linker at each residue; start/end boundaries of contiguous
   regions; a sequence-level `none` decision; calibrated confidence; and an
   abstention flag when domain evidence or confidence is inadequate.
3. **Weak-label expansion:** stream UniProtKB sequences plus InterPro domain
   matches on the college cloud. Apply a cheap domain-order/gap filter first,
   then run the trained GPU detector only on candidates. A high-confidence
   prediction is a *pseudo-label*, never a confirmed natural linker. Retain
   both predicted linker and `none` records in the ledger.
4. **Ranker training:** use high-confidence pseudo-labeled A-linker-B examples
   as weak pairwise data, with lower weight than reference examples. Keep reference
   detector/blind proteins and close homologues entirely out of the stream.
5. **Validation:** a large homology-separated pseudo-labeled validation stream
   monitors optimization and drift; it is not evidence of biological accuracy.
   Only independently annotated, untouched DLD/DisProt/CAID-style sets can
   estimate detector precision, recall, MCC, AUPRC, boundary IoU, and `none`
   false-positive rate. Ranker validation additionally uses reference-injected
   MRR with production coverage reported separately.

The target is at least 1,000,000 *distinct records actually consumed* for
training and 1,000,000 for large-stream validation, subject to a measured
yield of acceptable domain-pair candidates. Do not count all UniProt entries,
all InterPro matches, or repeat epochs as labeled examples. Stop and report the
real yield if either target is not met.

An initial no-storage InterPro 110.0 probe processed 100,000 accession groups:
69,567 had domain-type matches and 14,154 had at least one 5-30-residue gap
between qualifying domain hits (63,820 candidate pairs before overlap
adjudication). These are **unlabeled windows**. The first 100,000 accessions are
not a random sample, so this fraction must not be projected to the full archive
without a broader, stratified scan.

## 2. GPU classifier architecture and baselines

The first trainable detector is a small residue-level 1-D CNN with amino-acid
embeddings, domain-position channels, dilated residual blocks, and three heads:
residue class (none/IDL/DDL), start/end boundary, and sequence-level presence.
Use class-weighted cross-entropy plus boundary and presence losses. Calibrate
the detection threshold on gold validation clusters. Explicit `none` examples
and region-level evaluation are mandatory. All model training/inference runs
on CUDA; CPU is allowed only for network decoding, format checks, and batching.
Do not silently fall back to CPU training.

Compare, on the same untouched gold split, a simple composition/length rule,
the 2014 random-forest inter-domain detector, DFLpred where runnable,
IDP-ELM and LINKER-Pred/Lite where license and throughput permit, our CNN, and
an optional frozen-ESM-2 or LoRA-ESM-2 head. Published scores from different
datasets are context, **not** a head-to-head benchmark. Modern PLMs may improve
per-residue tasks but are costly at hundreds of millions of sequences; the CNN
is the high-throughput screening model and the PLM variant is an ablation on a
smaller fixed reference set.

## 3. Data stream and resource contract

Sources are pinned releases, not mutable `latest` URLs. The measured InterPro
probe used `current_release` with ETag `31b75aa0a-65a587502fe8f`; the same
object is available under the pinned
`https://ftp.ebi.ac.uk/pub/databases/interpro/releases/110.0/` path. InterPro's
`protein2ipr.dat.gz` was verified as a six-column tab-separated stream:
UniProt accession, InterPro ID, description, member signature, start, end.
The current file is about 13.3 GB compressed; UniProt TrEMBL FASTA is about
40.6 GB compressed. These sizes make the college cloud the appropriate host.
Neither full archive belongs in Git, web hosting, CI, or this laptop's working
tree. Obtain a true homology-cluster mapping before split assignment; a CATH
architecture is not a substitute.

The loader holds batch *n* on GPU while a single bounded worker fetches and
decodes batch *n+1*. Batch memory is released after optimizer use. Network
reads have timeouts and retries. Sequential `.gz` streams cannot resume at an
arbitrary compressed byte or be globally shuffled for free; resume from a
documented source shard/record position or restart the current shard. Prefer
immutable, seekable source shards when available. Shuffling is bounded within
a window, and splits use a stable hash of the homology cluster, not row order.

Training must be a standalone CLI run under Slurm (college cloud) or Windows
Task Scheduler (local), independent of this chat. Save atomic checkpoints and
small manifests. Retry transient Windows sharing violations (32/33) with
backoff. On WinError 5, use only a preconfigured writable fallback checkpoint
directory; otherwise stop and report the permission failure. Never silently
skip a data batch or bypass access controls.

## 4. Metadata-only provenance

Persist `manifest.json` plus compressed CSV shards. Each used record has source
database/release/accession, sequence SHA-256 and length, domain IDs and
boundaries, detector output and confidence,
experimental-gold/curated-reference/pseudo/unlabeled tier, true
homology cluster, split, model-checkpoint hash, and config hash. No sequence or
coordinates are stored in this ledger. The run manifest carries immutable
source object URLs/checksums, source versions, code commit, counts and shard
checksums. This is sufficient to audit selection and reconstruct records *if
the source release remains accessible*; it is not a backup of raw data.

## 5. Gates before saying ``millions trained and validated''

- Reference labels acquired with source/license and residue mapping verified.
- Homology cluster IDs present and split leakage audit passes.
- GPU framework installed and CUDA smoke batch, checkpoint, and resume pass.
- Detector independent-reference validation reports region and no-linker metrics before
  pseudo-label expansion; confidence threshold frozen.
- Cloud stream reports actual unique consumed training/validation counts, not
  source archive sizes; provenance CSV shards and manifest validate.
- Independent blind set remains untouched until final prediction freeze.

## 6. Literature that constrains this plan

- Shatnawi, Zaki and Yoo (2014), random-forest domain-linker prediction:
  <https://doi.org/10.1186/1471-2105-15-S16-S8>.
- Meng et al. (2026), DLD domain-linker-domain dataset:
  <https://doi.org/10.1016/j.jmb.2026.169994>.
- DFLpred (2016), high-throughput flexible-linker baseline:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC4908364/>.
- IDP-ELM (2024), PLM ensemble including flexible-linker prediction:
  <https://doi.org/10.1021/acs.jcim.3c01202>.
- CAID2 linker assessment (2024):
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC10968229/>.
- CAID3 assessment (2025/2026):
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/>.
- Fine-tuning protein language models on per-residue tasks (2024):
  <https://doi.org/10.1038/s41467-024-51844-2>.
- LINKER-Pred/Lite published web documentation and source, a current direct
  comparator whose associated server paper is listed as submitted:
  <https://pcrgwd.ucd.ie/linker_pred/help/>.
